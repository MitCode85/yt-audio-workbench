from __future__ import annotations

from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import ttk, messagebox

from help_window import open_help_window, show_about_dialog, set_app_meta

# Re-exported tooltip settings; if not available, provide fallbacks.
try:
    from tooltips import set_tooltip_delay, set_tooltip_wrap, get_tooltip_settings  # type: ignore
except Exception:  # pragma: no cover
    def set_tooltip_delay(_ms: int) -> None:  # noqa: D401 - trivial shim
        """No-op when tooltips module not present."""
        return

    def set_tooltip_wrap(_chars: int) -> None:  # noqa: D401 - trivial shim
        """No-op when tooltips module not present."""
        return

    def get_tooltip_settings() -> tuple[int, int]:
        return (600, 60)


def _t(parent: tk.Misc, key: str, default: str, get_text: Callable[[str, str], str] | None) -> str:
    if get_text is None:
        return default
    try:
        return get_text(key, default)
    except Exception:
        return default


def add_help_right_aligned_menu(
    parent: tk.Misc,
    app_name: str,
    version: str,
    help_md_path: Path | None = None,
    get_text: Callable[[str, str], str] | None = None,
    locales: dict[str, Path] | None = None,
    on_switch_language: Callable[[str], None] | None = None,
) -> tk.Frame:
    """
    Adds a right-aligned toolbar-style frame with Help/About and optional Language menu.
    Returns the frame so callers can pack/grid/place it as needed.
    """
    set_app_meta(app_name, version)

    frame = ttk.Frame(parent)
    menubtn = ttk.Menubutton(frame, text=_t(parent, "menu.help", "Help", get_text))
    menu = tk.Menu(menubtn, tearoff=False)

    if help_md_path is not None:
        menu.add_command(
            label=_t(parent, "menu.help.view", "View Help", get_text),
            command=lambda: open_help_window(parent, help_md_path, get_text or (lambda _k, d: d)),
        )
    menu.add_command(
        label=_t(parent, "menu.help.about", "About", get_text),
        command=lambda: show_about_dialog(parent, help_md_path or Path("HELP.md"), get_text or (lambda _k, d: d)),
    )

    # Optional language submenu
    if locales and on_switch_language:
        lang_menu = tk.Menu(menu, tearoff=False)
        for code in sorted(locales):
            lang_menu.add_command(
                label=code,
                command=lambda c=code: on_switch_language(c),
            )
        menu.add_cascade(label=_t(parent, "menu.help.language", "Language", get_text), menu=lang_menu)

    # Optional tooltip submenu
    tip_menu = tk.Menu(menu, tearoff=False)
    delay, wrap = get_tooltip_settings()
    def _set_delay(ms: int) -> None:
        set_tooltip_delay(ms)
        messagebox.showinfo(
            _t(parent, "tooltips.title", "Tooltips", get_text),
            _t(parent, "tooltips.delay_set", f"Delay set to {ms} ms.", get_text),
            parent=parent,
        )
    for ms in (0, 300, 600, 1000):
        tip_menu.add_command(label=f"Delay: {ms} ms", command=lambda x=ms: _set_delay(x))

    def _set_wrap(ch: int) -> None:
        set_tooltip_wrap(ch)
        messagebox.showinfo(
            _t(parent, "tooltips.title", "Tooltips", get_text),
            _t(parent, "tooltips.wrap_set", f"Wrap set to {ch} chars.", get_text),
            parent=parent,
        )
    for ch in (40, 60, 80):
        tip_menu.add_command(label=f"Wrap: {ch} chars", command=lambda x=ch: _set_wrap(x))

    menu.add_cascade(label=_t(parent, "menu.help.tooltips", "Tooltips", get_text), menu=tip_menu)

    menubtn["menu"] = menu
    menubtn.pack(side="right")
    return frame
