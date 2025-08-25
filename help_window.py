from __future__ import annotations

from pathlib import Path
from typing import Callable

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from workbench_core import resolve_tool_path

_APP_NAME = "YT Audio Workbench"
_VERSION = "0.0"


def set_app_meta(app_name: str, version: str) -> None:
    """Called by the main app to set metadata used in dialogs."""
    global _APP_NAME, _VERSION
    _APP_NAME = app_name or _APP_NAME
    _VERSION = version or _VERSION


def _center_on_screen(win: tk.Toplevel) -> None:
    win.update_idletasks()
    w = win.winfo_width()
    h = win.winfo_height()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    x = (sw // 2) - (w // 2)
    y = (sh // 3) - (h // 2)
    win.geometry(f"+{x}+{y}")


def _tool_info(cmd: str, version_args: list[str]) -> list[str]:
    out: list[str] = []
    path = resolve_tool_path(cmd)
    if not path:
        out.append(f"{cmd}: not found")
        return out
    out.append(f"{cmd}: {path}")
    try:
        import subprocess

        p = subprocess.run(
            [path, *version_args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        first = (
            p.stdout.splitlines()[0]
            if p.stdout.strip()
            else (p.stderr.splitlines()[0] if p.stderr.strip() else "(no output)")
        )
        out.append(f"{cmd} version: {first}")
    except Exception as e:  # pragma: no cover - purely diagnostic
        out.append(f"{cmd} version: error: {e}")
    return out


def _copy_diagnostics(parent: tk.Misc, get_text: Callable[[str, str], str]) -> None:
    lines: list[str] = [
        f"{_APP_NAME} v{_VERSION}",
        f"Tk version: {tk.TkVersion}",
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
    except Exception:
        pass
    messagebox.showinfo(
        get_text("dialog.copied.title", "Diagnostics copied"),
        get_text("dialog.copied.body", "Diagnostic info copied to clipboard."),
        parent=parent,
    )


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
    ttk.Label(searchf, text=get_text("dialog.help.search", "Search:")).pack(side="left")
    qvar = tk.StringVar()
    q = ttk.Entry(searchf, textvariable=qvar, width=50)
    q.pack(side="left", padx=6)

    body = ttk.Frame(container)
    body.pack(fill="both", expand=True)
    toc = tk.Listbox(body, width=28)
    toc.pack(side="left", fill="y", padx=(0, 8))
    txt = ScrolledText(body, wrap="word")
    txt.pack(side="right", fill="both", expand=True)

    def do_search(*_args: object) -> None:
        term = qvar.get().strip().lower()
        if not term:
            return
        content = txt.get("1.0", "end-1c").lower()
        pos = content.find(term)
        if pos >= 0:
            index = txt.index(f"1.0+{pos}c")
            line = index.split(".")[0]
            txt.see(f"{line}.0")
            txt.tag_remove("sel", "1.0", "end")
            txt.tag_add("sel", f"{line}.0", f"{line}.0 lineend")

    q.bind("<Return>", do_search)

    try:
        raw = help_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        raw = "# Help\n\n" + get_text("dialog.help.not_found", "Help file not found.")
    txt.insert("end", raw)
    txt.config(state="disabled")

    _center_on_screen(top)

    lines = raw.splitlines()
    anchors: list[tuple[str, int, int]] = []
    for i, line in enumerate(lines, start=1):
        if line.startswith("#"):
            depth = len(line) - len(line.lstrip("#"))
            title = line.lstrip("#").strip()
            anchors.append((title, i, depth))
            toc.insert("end", ("    " * (depth - 1)) + title)

    def jump(_evt: tk.Event | None = None, target: str | None = None) -> None:
        lineno: int | None
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

    # Diagnostics button in the search row (right side)
    ttk.Button(
        searchf,
        text=get_text("dialog.help.copy_diagnostics", "Copy diagnostics"),
        command=lambda: _copy_diagnostics(parent, get_text),
    ).pack(side="right")

    top.grab_set()
    top.wait_window()


def show_about_dialog(parent: tk.Misc, help_path: Path, get_text: Callable[[str, str], str]) -> None:
    top = tk.Toplevel(parent)
    top.title(get_text("dialog.about.title", "About"))
    top.resizable(False, False)

    frm = ttk.Frame(top, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=_APP_NAME, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    ttk.Label(
        frm,
        text=get_text("dialog.about.version", "Version: {version}").format(version=_VERSION),
    ).pack(anchor="w", pady=(0, 8))

    ttk.Button(
        frm,
        text=get_text("dialog.about.view_help", "View Help"),
        command=lambda: open_help_window(parent, help_path, get_text),
    ).pack(anchor="w")

    ttk.Button(
        frm,
        text=get_text("dialog.about.copy_diagnostics", "Copy diagnostics"),
        command=lambda: _copy_diagnostics(parent, get_text),
    ).pack(anchor="w", pady=(8, 0))

    ttk.Button(frm, text=get_text("dialog.about.close", "Close"), command=top.destroy).pack(
        anchor="e", pady=(8, 0)
    )

    _center_on_screen(top)
    top.grab_set()
    top.wait_window()
