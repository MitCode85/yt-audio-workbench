from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from workbench_core import resolve_tool_path

APP_NAME = "YT Audio Workbench"
VERSION = ""

__all__ = ["open_help_window", "show_about_dialog", "set_app_meta"]


def set_app_meta(app_name: str, version: str) -> None:
    global APP_NAME, VERSION
    APP_NAME = app_name or APP_NAME
    VERSION = version or VERSION


def _center_on_screen(win: tk.Toplevel) -> None:
    win.update_idletasks()
    w = win.winfo_width()
    h = win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")


def open_help_window(
    parent: tk.Misc,
    help_path: Path,
    get_text: Callable[[str, str], str],
    section: Optional[str] = None,
) -> None:
    """Open a help window rendering the HELP.md text; simple ToC based on headings."""
    top = tk.Toplevel(parent)
    top.title(get_text("dialog.help.title", f"Help — {APP_NAME}").format(app=APP_NAME))
    top.geometry("940x700")
    top.transient(parent)

    container = ttk.Frame(top, padding=6)
    container.pack(fill="both", expand=True)

    # -- search bar
    searchf = ttk.Frame(container)
    searchf.pack(fill="x")
    ttk.Label(searchf, text=get_text("dialog.help.search", "Search:")).pack(side="left")
    qvar = tk.StringVar()
    q = ttk.Entry(searchf, textvariable=qvar, width=50)
    q.pack(side="left", padx=6)

    # -- main body (toc + text)
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

    # -- load help
    try:
        raw = Path(help_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        raw = "# Help\n\n" + get_text("dialog.help.not_found", "Help file not found.")
    txt.insert("end", raw)
    txt.config(state="disabled")

    _center_on_screen(top)

    # -- build toc
    anchors: list[tuple[str, int, int]] = []
    for i, line in enumerate(raw.splitlines(), start=1):
        if line.startswith("#"):
            depth = len(line) - len(line.lstrip("#"))
            title = line.lstrip("#").strip()
            anchors.append((title, i, depth))
            toc.insert("end", ("    " * (depth - 1)) + title)

    def jump(_evt: Optional[tk.Event] = None, target: Optional[str] = None) -> None:
        lineno: Optional[int]
        if target is None:
            sel = toc.curselection()
            if not sel:
                return
            idx = sel[0]
            _, lineno, _ = anchors[idx]
        else:
            lineno = None
            t_lower = target.lower()
            for title, ln, _depth in anchors:
                if title.lower().startswith(t_lower):
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


def show_about_dialog(parent: tk.Misc, _help_path: Path, get_text: Callable[[str, str], str]) -> None:
    top = tk.Toplevel(parent)
    top.title(get_text("dialog.about.title", "About"))
    top.resizable(False, False)

    frm = ttk.Frame(top, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=APP_NAME, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    ttk.Label(frm, text=get_text("dialog.about.version", "Version: {version}").format(version=VERSION)).pack(
        anchor="w", pady=(0, 8)
    )

    info = ttk.Label(
        frm,
        text=get_text(
            "dialog.about.blurb",
            "A reliability-first Python GUI for yt-dlp and ffmpeg, designed for "
            "creating high-quality, tagged, and normalized MP3 archives from YouTube.",
        ),
        wraplength=420,
        justify="left",
    )
    info.pack(anchor="w", pady=(0, 8))

    def _tool_info(cmd: str, version_args: list[str]) -> list[str]:
        out: list[str] = []
        path = resolve_tool_path(cmd)
        if not path:
            out.append(f"{cmd}: not found")
            return out
        out.append(f"{cmd}: {path}")
        try:
            p = subprocess.run([path, *version_args], capture_output=True, text=True, check=False)
            first = (
                p.stdout.splitlines()[0]
                if p.stdout.strip()
                else (p.stderr.splitlines()[0] if p.stderr.strip() else "(no output)")
            )
            out.append(f"{cmd} version: {first}")
        except Exception as e:
            out.append(f"{cmd} version: error: {e}")
        return out

    def _copy_diagnostics() -> None:
        lines: list[str] = []
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
        )

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))
    ttk.Button(btns, text=get_text("dialog.about.copy_diagnostics", "Copy diagnostics"), command=_copy_diagnostics).pack(
        side="left"
    )
    ttk.Button(btns, text=get_text("dialog.about.close", "Close"), command=top.destroy).pack(side="right")

    _center_on_screen(top)
