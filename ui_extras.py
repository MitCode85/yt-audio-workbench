from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

import tkinter as tk
from tkinter import ttk, simpledialog

from help_window import open_help_window, show_about_dialog, set_app_meta, _copy_diagnostics

# Re-exported tooltip settings; if not available, provide fallbacks.
try:
    from tooltips import set_tooltip_delay, set_tooltip_wrap, get_tooltip_settings  # type: ignore
except Exception:  # pragma: no cover

    def set_tooltip_delay(_ms: int) -> None:  # noqa: D401 - trivial shim
        """No-op when tooltips module not present."""
        return

    def set_tooltip_wrap(_ch: int) -> None:  # noqa: D401 - trivial shim
        """No-op when tooltips module not present."""
        return

    def get_tooltip_settings() -> tuple[int, int]:  # noqa: D401 - trivial shim
        """Return default delay/wrap when tooltips module not present."""
        return (500, 60)


def _t(parent: tk.Misc, key: str, default: str, get_text: Callable[[str, str], str] | None) -> str:
    return get_text(key, default) if get_text else default


def add_help_right_aligned_menu(
    parent: tk.Misc,
    app_name: str,
    version: str,
    help_md_path: Path | None = None,
    get_text: Callable[[str, str], str] | None = None,
    locales: dict[str, Path] | None = None,
    on_switch_language: Callable[[str], None] | None = None,
) -> tk.Frame:
    """Create a thin, right-aligned Help menu strip with original layout/behavior."""
    set_app_meta(app_name, version)

    # Restore pre-GitHub behavior: create and PACK the bar here
    bar = ttk.Frame(parent)
    bar.pack(side="top", fill="x", padx=0, pady=(0, 6))

    btn = ttk.Menubutton(bar, text=_t(parent, "menu.help", "Help", get_text))
    menu = tk.Menu(btn, tearoff=False)

    # 1) Open Help
    if help_md_path is not None:
        menu.add_command(
            label=_t(parent, "menu.open_help", "Open Help", get_text),
            command=lambda: open_help_window(parent, help_md_path, get_text or (lambda _k, d: d)),
        )

    # 2) Copy diagnostics (restored to the menu)
    menu.add_command(
        label=_t(parent, "menu.copy_diagnostics", "Copy diagnostic info", get_text),
        command=lambda: _copy_diagnostics(parent, get_text or (lambda _k, d: d)),
    )

    # 3) Tooltips submenu (manual number inputs like before)
    tips_menu = tk.Menu(menu, tearoff=False)

    def _set_delay() -> None:
        cur_delay, _cur_wrap = get_tooltip_settings()
        val = simpledialog.askinteger(
            title=_t(parent, "menu.tooltips.delay", "Tooltip delay", get_text),
            prompt=_t(parent, "menu.tooltips.delay", "Tooltip delay (ms):", get_text),
            initialvalue=int(cur_delay),
            minvalue=0,
            parent=parent,
        )
        if val is not None:
            set_tooltip_delay(int(val))
            # Persist if the app exposes a config saver
            try:
                parent._save_config()
            except Exception:
                pass

    def _set_wrap() -> None:
        _cur_delay, cur_wrap = get_tooltip_settings()
        val = simpledialog.askinteger(
            title=_t(parent, "menu.tooltips.wrap", "Tooltip wrap", get_text),
            prompt=_t(parent, "menu.tooltips.wrap", "Wrap length (px):", get_text),
            initialvalue=int(cur_wrap),
            minvalue=0,
            parent=parent,
        )
        if val is not None:
            set_tooltip_wrap(int(val))
            try:
                parent._save_config()
            except Exception:
                pass

    tips_menu.add_command(
        label=_t(parent, "menu.tooltips.delay", "Tooltip delay…", get_text), command=_set_delay
    )
    tips_menu.add_command(
        label=_t(parent, "menu.tooltips.wrap", "Tooltip wrap…", get_text), command=_set_wrap
    )
    menu.add_cascade(label=_t(parent, "menu.tooltips", "Tooltips", get_text), menu=tips_menu)

    # 4) Language submenu (unchanged)
    if locales and on_switch_language:
        lang_menu = tk.Menu(menu, tearoff=False)
        for code in sorted(locales):
            lang_menu.add_command(
                label=code,
                command=lambda c=code: on_switch_language(c),
            )
        menu.add_cascade(label=_t(parent, "menu.language", "Language", get_text), menu=lang_menu)

    # 5) About (at the bottom, match original order)
    def _about() -> None:
        try:
            set_app_meta(app_name, version)
        except Exception:
            pass
        show_about_dialog(parent, help_md_path or Path("HELP.md"), get_text or (lambda _k, d: d))

    menu.add_separator()
    menu.add_command(label=_t(parent, "menu.about", "About", get_text), command=_about)

    btn.configure(menu=menu)
    btn.pack(side="right")  # right aligned in the bar

    # F1 opens full help (restored)
    try:
        if help_md_path is not None:
            parent.bind_all(
                "<F1>",
                lambda e: open_help_window(parent, help_md_path, get_text or (lambda _k, d: d)),
            )
    except Exception:
        pass

    return bar
