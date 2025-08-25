
"""
Robust, race-safe tooltip manager for Tkinter with rebuild support.

Public API:
    - attach_tooltip(widget, text_or_callable)
    - reset_tooltips()    # call before tearing down UI (e.g., on language change)
"""

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, TclError
from collections.abc import Callable
from typing import Optional, Any
from weakref import WeakKeyDictionary


class TooltipManager:
    def __init__(self, delay_ms: int = 500, wrap: int = 420) -> None:
        self.delay_ms = int(delay_ms)
        self.wrap = int(wrap)

        # Weak maps keyed by widget objects to avoid keeping dead widgets alive
        self._providers: "WeakKeyDictionary[tk.Misc, Callable[[], str]]" = WeakKeyDictionary()
        self._after_ids: "WeakKeyDictionary[tk.Misc, str]" = WeakKeyDictionary()

        self._tip_win: Optional[tk.Toplevel] = None
        self._label: Optional[ttk.Label] = None
        self._current_widget: Optional[tk.Misc] = None

    # ---------------------------
    # Public API
    # ---------------------------
    def attach_tooltip(self, widget: tk.Misc, text_or_callable: Any) -> None:
        """Attach a tooltip to 'widget' with a string or zero-arg callable."""
        if callable(text_or_callable):
            self._providers[widget] = text_or_callable
        else:
            s = str(text_or_callable)
            self._providers[widget] = (lambda s=s: s)

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<Destroy>", self._on_destroy, add="+")
        widget.bind("<Motion>", self._on_motion, add="+")

    def reset(self) -> None:
        """Cancel all pending callbacks and hide/destroy any tooltip window.
        Call this before you destroy/rebuild the UI (e.g., language switch)."""
        # Cancel all after() callbacks we know about
        try:
            for w, aid in list(self._after_ids.items()):
                try:
                    if w and w.winfo_exists():
                        w.after_cancel(aid)
                except Exception:
                    pass
        except Exception:
            pass
        self._after_ids = WeakKeyDictionary()  # fresh

        # Forget all providers
        self._providers = WeakKeyDictionary()

        # Hide any visible tooltip
        self._current_widget = None
        self._hide()

    # ---------------------------
    # Event handlers
    # ---------------------------
    def _on_enter(self, e: tk.Event) -> None:
        w = getattr(e, "widget", None) or e
        if not w:
            return
        self._schedule_show(w)

    def _on_leave(self, e: tk.Event) -> None:
        w = getattr(e, "widget", None) or e
        if not w:
            return
        self._cancel_scheduled(w)
        if self._current_widget is w:
            self._current_widget = None
        self._hide()

    def _on_destroy(self, e: tk.Event) -> None:
        w = getattr(e, "widget", None) or e
        if not w:
            return
        self._cancel_scheduled(w)
        try:
            if w in self._providers:
                del self._providers[w]
        except Exception:
            pass
        if self._current_widget is w:
            self._current_widget = None
        self._hide()

    def _on_motion(self, e: tk.Event) -> None:
        if self._tip_win and self._tip_win.winfo_exists():
            try:
                self._tip_win.geometry(f"+{e.x_root+12}+{e.y_root+12}")
            except Exception:
                pass

    # ---------------------------
    # Core logic
    # ---------------------------
    def _schedule_show(self, widget: tk.Misc) -> None:
        self._cancel_scheduled(widget)
        self._current_widget = widget
        try:
            aid = widget.after(self.delay_ms, lambda w=widget: self._show(w))
            self._after_ids[widget] = aid
        except Exception:
            pass

    def _cancel_scheduled(self, widget: tk.Misc) -> None:
        aid = self._after_ids.pop(widget, None)
        if aid:
            try:
                widget.after_cancel(aid)
            except Exception:
                pass

    def _resolve_text(self, widget: tk.Misc) -> str:
        prov = self._providers.get(widget)
        if not prov:
            return ""
        try:
            return str(prov() or "")
        except Exception:
            return ""

    def _show(self, widget: tk.Misc) -> None:
        try:
            if self._current_widget is not widget:
                return
            if not widget.winfo_exists() or not widget.winfo_viewable():
                return
        except Exception:
            return

        text = self._resolve_text(widget)
        if not text:
            return

        if not self._tip_win or not self._tip_win.winfo_exists():
            try:
                self._tip_win = tk.Toplevel(widget)
                self._tip_win.wm_overrideredirect(True)
                try:
                    self._tip_win.attributes("-topmost", True)
                except Exception:
                    pass
                frame = ttk.Frame(self._tip_win, borderwidth=1, relief="solid")
                frame.pack(fill="both", expand=True)
                self._label = ttk.Label(frame, text="", justify="left", padding=(6, 4))
                self._label.pack(fill="both", expand=True)
            except Exception:
                return

        try:
            if not self._label or not self._label.winfo_exists():
                return
            self._label.configure(text=text, wraplength=self.wrap)
        except (TclError, Exception):
            return

        try:
            x = widget.winfo_pointerx() + 12
            y = widget.winfo_pointery() + 12
            self._tip_win.geometry(f"+{x}+{y}")
            self._tip_win.deiconify()
        except Exception:
            pass

    def _hide(self) -> None:
        try:
            if self._tip_win and self._tip_win.winfo_exists():
                self._tip_win.destroy()
        except Exception:
            pass
        self._tip_win = None
        self._label = None


# Global manager and convenience wrappers
_DEFAULT_MANAGER: Optional[TooltipManager] = TooltipManager()


def attach_tooltip(widget: tk.Misc, text_or_callable: Any) -> None:
    (_DEFAULT_MANAGER or TooltipManager()).attach_tooltip(widget, text_or_callable)


def reset_tooltips() -> None:
    """Reset the global tooltip manager (call before UI rebuild)."""
    global _DEFAULT_MANAGER
    if _DEFAULT_MANAGER is None:
        return
    _DEFAULT_MANAGER.reset()


def set_tooltip_delay(ms: int) -> None:
    """Set global tooltip delay in milliseconds."""
    global _DEFAULT_MANAGER
    try:
        ms = int(ms)
    except Exception:
        return
    if _DEFAULT_MANAGER:
        _DEFAULT_MANAGER.delay_ms = max(0, ms)

def set_tooltip_wrap(px: int) -> None:
    """Set global tooltip wrap length in pixels."""
    global _DEFAULT_MANAGER
    try:
        px = int(px)
    except Exception:
        return
    if _DEFAULT_MANAGER:
        _DEFAULT_MANAGER.wrap = max(0, px)
        try:
            # If visible, refresh wrapping immediately
            if _DEFAULT_MANAGER._label and _DEFAULT_MANAGER._label.winfo_exists():
                _DEFAULT_MANAGER._label.configure(wraplength=_DEFAULT_MANAGER.wrap)
        except Exception:
            pass

def get_tooltip_settings():
    """Return (delay_ms, wrap_px) for the global manager."""
    if _DEFAULT_MANAGER:
        return _DEFAULT_MANAGER.delay_ms, _DEFAULT_MANAGER.wrap
    return 500, 420
