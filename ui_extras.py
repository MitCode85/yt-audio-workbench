from __future__ import annotations
from pathlib import Path
from typing import Optional, Callable, Dict
import platform, subprocess, sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText

# Always use the project's full Help/About implementation
from help_window import open_help_window, show_about_dialog, set_app_meta
from tooltips import set_tooltip_delay, set_tooltip_wrap, get_tooltip_settings

def _t(parent: tk.Misc, key: str, default: str, get_text: Optional[Callable[[str, str], str]]) -> str:
    try:
        if get_text:
            return get_text(key, default)
        if hasattr(parent, "lang") and hasattr(parent.lang, "get"):
            v = parent.lang.get(key)
            if isinstance(v, str) and v:
                return v
    except Exception:
        pass
    return default

def _copy_diagnostics(parent: tk.Misc) -> None:
    lines = []
    # Try to pull app name/version if the caller set it in About
    app = getattr(parent, "title", lambda: "Application")()
    try:
        # Pull VERSION attr from parent/App if present
        ver = getattr(parent, "VERSION", "")
        if not ver and hasattr(parent, "title"):
            ver = ""
    except Exception:
        ver = ""
    if ver:
        lines.append(f"{app} {ver}")
    else:
        lines.append(app)

    lines.append(f"Python: {sys.version.splitlines()[0]}")
    lines.append(f"OS: {platform.system()} {platform.release()}")

    for tool, args in [("yt-dlp", ["--version"]), ("ffmpeg", ["-version"]), ("ffprobe", ["-version"]), ("mp3gain", ["-v"])]:
        try:
            p = subprocess.run([tool, *args], capture_output=True, text=True, timeout=3)
            first = p.stdout.splitlines()[0] if p.stdout.strip() else (p.stderr.splitlines()[0] if p.stderr.strip() else "(no output)")
            lines.append(f"{tool}: {first}")
        except Exception as e:
            lines.append(f"{tool}: error: {e}")

    try:
        parent.clipboard_clear(); parent.clipboard_append("\n".join(lines))
        messagebox.showinfo("Diagnostics copied", "Diagnostic info copied to clipboard.")
    except Exception:
        pass

def add_help_right_aligned_menu(
    parent: tk.Misc,
    app_name: str,
    version: str,
    help_md_path: Optional[Path] = None,
    get_text: Optional[Callable[[str, str], str]] = None,
    locales: Optional[Dict[str, Path]] = None,
    on_switch_language: Optional[Callable[[str], None]] = None
) -> tk.Frame:
    """
    Create a simple right-aligned strip with a Help menubutton.
    Always opens the project's full Help/About windows.
    """
    # Make a thin bar at the top
    bar = ttk.Frame(parent)
    bar.pack(side="top", fill="x", padx=0, pady=(0, 6))

    # Right-aligned Help menu
    btn = ttk.Menubutton(bar, text=_t(parent, "menu.help", "Help", get_text))
    btn.pack(side="right", padx=(0, 6), pady=(6, 0))
    menu = tk.Menu(btn, tearoff=0)

    # Open Help
    menu.add_command(
        label=_t(parent, "menu.open_help", "Open Help", get_text),
        command=lambda: open_help_window(parent, help_md_path, get_text=get_text),
    )

    # Copy diagnostics
    menu.add_command(
        label=_t(parent, "menu.copy_diagnostics", "Copy diagnostic info", get_text),
        command=lambda: _copy_diagnostics(parent),
    )
    # Tooltips submenu
    tips_menu = tk.Menu(menu, tearoff=0)
    def _set_delay():
        cur_delay, _cur_wrap = get_tooltip_settings()
        val = simpledialog.askinteger(
            title=_t(parent, "menu.tooltips.delay", "Tooltip delay", get_text),
            prompt=_t(parent, "menu.tooltips.delay", "Tooltip delay (ms):", get_text),
            initialvalue=int(cur_delay),
            minvalue=0
        )
        if val is not None:
            set_tooltip_delay(val)
            try:
                getattr(parent, '_save_config')()
            except Exception:
                pass

    def _set_wrap():
        _cur_delay, cur_wrap = get_tooltip_settings()
        val = simpledialog.askinteger(
            title=_t(parent, "menu.tooltips.wrap", "Tooltip wrap", get_text),
            prompt=_t(parent, "menu.tooltips.wrap", "Wrap length (px):", get_text),
            initialvalue=int(cur_wrap),
            minvalue=0
        )
        if val is not None:
            set_tooltip_wrap(val)
            try:
                getattr(parent, '_save_config')()
            except Exception:
                pass

    tips_menu.add_command(label=_t(parent, "menu.tooltips.delay", "Tooltip delay…", get_text), command=_set_delay)
    tips_menu.add_command(label=_t(parent, "menu.tooltips.wrap", "Tooltip wrap…", get_text), command=_set_wrap)
    menu.add_cascade(label=_t(parent, "menu.tooltips", "Tooltips", get_text), menu=tips_menu)


    # Language submenu (optional)
    if locales and on_switch_language:
        lang_menu = tk.Menu(menu, tearoff=0)
        current = tk.StringVar(value=getattr(parent, "current_language", "en"))
        for code in sorted(locales.keys()):
            lang_menu.add_radiobutton(
                label=code,
                variable=current,
                value=code,
                command=lambda c=code: on_switch_language(c),
            )
        menu.add_cascade(label=_t(parent, "menu.language", "Language", get_text), menu=lang_menu)

    # About: set metadata then show
    def _about():
        try:
            set_app_meta(app_name, version)
        except Exception:
            pass
        show_about_dialog(parent, help_md_path, get_text=get_text)

    menu.add_separator()
    menu.add_command(label=_t(parent, "menu.about", "About", get_text), command=_about)

    btn.configure(menu=menu)

    # F1 opens full help
    try:
        parent.bind_all("<F1>", lambda e: open_help_window(parent, help_md_path, get_text=get_text))
    except Exception:
        pass

    return bar
