from __future__ import annotations

from pathlib import Path
from collections.abc import Callable

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from workbench_core import resolve_tool_path

_APP_NAME = "YT Audio Workbench"
_VERSION = "0.0"


def set_app_meta(app_name: str, version: str) -> None:
    global _APP_NAME, _VERSION
    _APP_NAME, _VERSION = app_name, version


def _center_on_screen(win: tk.Toplevel) -> None:
    try:
        win.update_idletasks()
        w = win.winfo_width() or 800
        h = win.winfo_height() or 600
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = int((sw - w) / 2)
        y = int((sh - h) / 2)
        win.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass


def _tool_info(cmd: str, args: list[str]) -> list[str]:
    import shutil, subprocess, sys, os

    first_line = "(not found)"
    p = shutil.which(cmd) or resolve_tool_path(cmd)
    if not p:
        # Some additional platform-specific locations
        if os.name == "nt":
            for base in [
                os.environ.get("LOCALAPPDATA", ""),
                os.environ.get("ProgramFiles", ""),
                os.environ.get("ProgramFiles(x86)", ""),
            ]:
                for sub in ["yt-dlp", "FFmpeg", "mp3gain"]:
                    cand = os.path.join(
                        base, sub, cmd + (".exe" if not cmd.endswith(".exe") else "")
                    )
                    if os.path.exists(cand):
                        p = cand
                        break
                if p:
                    break
        elif sys.platform == "darwin":
            for base in ["/opt/homebrew/bin", "/usr/local/bin"]:
                cand = os.path.join(base, cmd)
                if os.path.exists(cand):
                    p = cand
                    break
        else:
            for base in ["/usr/bin", "/usr/local/bin"]:
                cand = os.path.join(base, cmd)
                if os.path.exists(cand):
                    p = cand
                    break

    out: list[str] = [f"{cmd} path: {p or '(not found)'}"]
    try:
        if p:
            proc = subprocess.run(
                [p] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=2
            )
            first_line = proc.stdout.splitlines()[0].strip() if proc.stdout else "(no output)"
        out.append(f"{cmd} version: {first_line}")
    except Exception as e:  # pragma: no cover - purely diagnostic
        out.append(f"{cmd} version: error: {e}")
    return out


def _copy_diagnostics(parent: tk.Misc, get_text: Callable[[str, str], str]) -> None:
    import platform, sys

    lines: list[str] = [
        f"{_APP_NAME} v{_VERSION}".strip(),
        f"Python: {sys.version.splitlines()[0]}",
        f"OS: {platform.system()} {platform.release()}",
    ]
    for tool, args in [
        ("yt-dlp", ["--version"]),
        ("ffmpeg", ["-version"]),
        ("ffprobe", ["-version"]),
        ("mp3gain", ["-v"]),
    ]:
        lines.extend(_tool_info(tool, args))

    try:
        parent.clipboard_clear()
        parent.clipboard_append("\n".join(lines))
        messagebox.showinfo(
            get_text("help.diag_copied_title", "Diagnostics"),
            get_text("help.diag_copied_msg", "Diagnostic info copied to clipboard."),
            parent=parent,
        )
    except Exception:
        pass


def open_help_window(
    parent: tk.Misc,
    help_path: Path,
    get_text: Callable[[str, str], str],
    section: str | None = None,
) -> None:
    """Open a help window rendering the HELP.md text; simple ToC based on headings."""
    top = tk.Toplevel(parent)
    top.title(get_text("dialog.help.title", f"Help — {_APP_NAME}").format(app=_APP_NAME))
    top.geometry("940x640")
    top.transient(parent)

    container = ttk.Frame(top, padding=6)
    container.pack(fill="both", expand=True)

    searchf = ttk.Frame(container)
    searchf.pack(fill="x")
    ttk.Label(searchf, text="Search:").pack(side="left")
    qvar = tk.StringVar()
    q = ttk.Entry(searchf, textvariable=qvar, width=50)
    q.pack(side="left", padx=6)

    body = ttk.Frame(container)
    body.pack(fill="both", expand=True)

    toc = tk.Listbox(body, width=28)
    toc.pack(side="left", fill="y", padx=(0, 8))

    txt = ScrolledText(body, wrap="word")
    txt.pack(side="right", fill="both", expand=True)

    # Load Markdown and build anchors (very simple headings-based ToC)
    try:
        content = help_path.read_text(encoding="utf-8")
    except Exception as e:
        txt.insert("1.0", f"Failed to load HELP.md: {e}")
        _center_on_screen(top)
        top.grab_set()
        top.wait_window()
        return

    anchors: list[tuple[str, int, int]] = []
    lines = content.splitlines()
    for i, line in enumerate(lines, start=1):
        if line.startswith("#"):
            depth = len(line) - len(line.lstrip("#"))
            title = line.lstrip("#").strip()
            anchors.append((title, i, depth))
    txt.insert("1.0", content)

    for title, _ln, depth in anchors:
        toc.insert("end", ("  " * (depth - 1)) + title)

    def do_search(*_):
        term = qvar.get().strip().lower()
        if not term:
            return
        text = txt.get("1.0", "end-1c").lower()
        pos = text.find(term)
        if pos >= 0:
            line = txt.get("1.0", f"{pos}c").count("\n") + 1
            txt.see(f"{line}.0")
            txt.tag_remove("sel", "1.0", "end")
            txt.tag_add("sel", f"{line}.0", f"{line}.0 lineend")

    q.bind("<Return>", do_search)

    def jump(_e=None, target: str | None = None):
        if target is None:
            sel = toc.curselection()
            if not sel:
                return
            idx = sel[0]
            _title, lineno, _depth = anchors[idx]
        else:
            lineno = None
            for title, ln, _depth in anchors:
                if title.lower().startswith(target.lower()):
                    lineno = ln
                    break
            if lineno is None:
                return
        txt.see(f"{lineno}.0")
        txt.tag_remove("sel", "1.0", "end")
        txt.tag_add("sel", f"{lineno}.0", f"{lineno}.0 lineend")

    toc.bind("<<ListboxSelect>>", jump)
    if section:
        jump(target=section)

    _center_on_screen(top)
    top.grab_set()
    top.wait_window()


def show_about_dialog(
    parent: tk.Misc, help_path: Path, get_text: Callable[[str, str], str]
) -> None:
    """Restore original About layout: app + version, two left buttons, Close on right."""
    top = tk.Toplevel(parent)
    top.title(get_text("dialog.about.title", "About"))
    top.resizable(False, False)
    top.transient(parent)

    frm = ttk.Frame(top, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=_APP_NAME, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    ttk.Label(
        frm, text=get_text("dialog.about.version", "Version: {version}").format(version=_VERSION)
    ).pack(anchor="w", pady=(0, 8))

    # Buttons row: Copy diagnostics & Open Help→Troubleshooting on the left, Close on the right
    row = ttk.Frame(frm)
    row.pack(fill="x", pady=(4, 0))

    ttk.Button(
        row,
        text=get_text("menu.copy_diagnostics", "Copy diagnostic info"),
        command=lambda: _copy_diagnostics(parent, get_text),
    ).pack(side="left")

    ttk.Button(
        row,
        text=get_text("dialog.about.open_troubleshooting", "Open Help → Troubleshooting"),
        command=lambda: open_help_window(parent, help_path, get_text, section="Troubleshooting"),
    ).pack(side="left", padx=6)

    ttk.Button(row, text=get_text("dialog.about.close", "Close"), command=top.destroy).pack(
        side="right"
    )

    _center_on_screen(top)
    # Non-modal like the original; comment next two lines back in if you prefer modal
    # top.grab_set()
    # top.wait_window()
