from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from workbench_core import resolve_tool_path

# --- Constants for better maintainability ---
_TOC_WIDTH = 30
_SEARCH_HIGHLIGHT_TAG = "search_hit"
_BOOKMARK_HIGHLIGHT_TAG = "bookmark_hit"

# --- Global variables for app metadata ---
_APP_NAME = "YT Audio Workbench"
_VERSION = "0.0"


def set_app_meta(app_name: str, version: str) -> None:
    """Sets the application name and version for the help/about dialogs."""
    global _APP_NAME, _VERSION
    _APP_NAME, _VERSION = app_name, version


def _center_on_screen(win: tk.Toplevel) -> None:
    """Centers a Toplevel window on the screen."""
    try:
        win.update_idletasks()
        w = win.winfo_width()
        h = win.winfo_height()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = int((sw - w) / 2)
        y = int((sh - h) / 2)
        win.geometry(f"+{x}+{y}")
    except tk.TclError:
        pass


def _tool_info(cmd: str, args: list[str]) -> list[str]:
    """Gathers version information for a given command-line tool."""
    path = shutil.which(cmd) or resolve_tool_path(cmd)
    out: list[str] = [f"{cmd} path: {path or '(not found)'}"]

    if not path:
        return out
    try:
        proc = subprocess.run(
            [path] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=3,
            encoding='utf-8',
        )
        first_line = proc.stdout.splitlines()[0].strip() if proc.stdout else "(no output)"
        out.append(f"{cmd} version: {first_line}")
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        out.append(f"{cmd} version: error: {e}")
    return out


def _copy_diagnostics(parent: tk.Misc, get_text: Callable[[str, str], str]) -> None:
    """Collects and copies system/tool diagnostic info to the clipboard."""
    lines: list[str] = [
        f"{_APP_NAME} v{_VERSION}".strip(),
        f"Python: {sys.version.splitlines()[0]}",
        f"OS: {platform.system()} {platform.release()}",
    ]
    tool_checks = [
        ("yt-dlp", ["--version"]),
        ("ffmpeg", ["-version"]),
        ("ffprobe", ["-version"]),
        ("mp3gain", ["-v"]),
    ]
    for tool, args in tool_checks:
        lines.extend(_tool_info(tool, args))

    try:
        parent.clipboard_clear()
        parent.clipboard_append("\n".join(lines))
        messagebox.showinfo(
            get_text("help.diag_copied_title", "Diagnostics"),
            get_text("help.diag_copied_msg", "Diagnostic info copied to clipboard."),
            parent=parent,
        )
    except tk.TclError:
        messagebox.showwarning(
            get_text("help.diag_copy_failed_title", "Clipboard Error"),
            get_text("help.diag_copy_failed_msg", "Could not copy to clipboard."),
            parent=parent,
        )


def open_help_window(
    parent: tk.Misc,
    help_path: Path,
    get_text: Callable[[str, str], str],
    section: str | None = None,
) -> None:
    """Opens a help window rendering the HELP.md text with a navigable ToC."""
    top = tk.Toplevel(parent)
    title = get_text("dialog.help.title", f"Help — {_APP_NAME}")
    top.title(title.format(app=_APP_NAME))
    top.geometry("940x640")
    top.transient(parent)

    container = ttk.Frame(top, padding=8)
    container.pack(fill="both", expand=True)
    container.rowconfigure(1, weight=1)
    container.columnconfigure(0, weight=1)

    search_frame = ttk.Frame(container)
    search_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    ttk.Label(search_frame, text="Search:").pack(side="left")
    query_var = tk.StringVar()
    query_entry = ttk.Entry(search_frame, textvariable=query_var)
    query_entry.pack(side="left", padx=6, fill="x", expand=True)

    body_frame = ttk.Frame(container)
    body_frame.grid(row=1, column=0, sticky="nsew")
    body_frame.rowconfigure(0, weight=1)
    body_frame.columnconfigure(1, weight=1)

    toc_listbox = tk.Listbox(body_frame, width=_TOC_WIDTH)
    toc_listbox.grid(row=0, column=0, sticky="ns", padx=(0, 8))

    text_widget = ScrolledText(body_frame, wrap="word", padx=5, pady=5)
    text_widget.grid(row=0, column=1, sticky="nsew")

    text_widget.tag_configure(_SEARCH_HIGHLIGHT_TAG, background="yellow", foreground="black")
    text_widget.tag_configure(_BOOKMARK_HIGHLIGHT_TAG, background="#e0e8f0")

    try:
        content = help_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        text_widget.insert("1.0", content)
    except OSError as e:
        text_widget.insert("1.0", f"Failed to load help file '{help_path}':\n\n{e}")
        _center_on_screen(top)
        top.grab_set()
        return

    anchors: list[tuple[str, int, int]] = []
    heading_pattern = re.compile(r"^(#+)\s+(.*)")
    for i, line in enumerate(lines, start=1):
        match = heading_pattern.match(line)
        if match:
            depth = len(match.group(1))
            title = match.group(2).strip()
            anchors.append((title, i, depth))
            indent = "  " * (depth - 1)
            toc_listbox.insert("end", f"{indent}{title}")

    def do_search(start_pos: str = "1.0"):
        text_widget.tag_remove(_SEARCH_HIGHLIGHT_TAG, "1.0", "end")
        term = query_var.get()
        if not term:
            return None
        pos = text_widget.search(term, start_pos, stopindex="end", nocase=True)
        if pos:
            end_pos = f"{pos}+{len(term)}c"
            text_widget.tag_add(_SEARCH_HIGHLIGHT_TAG, pos, end_pos)
            text_widget.see(pos)
            query_entry.focus_set()
            return pos
        if start_pos == "1.0":
            messagebox.showinfo("Search", f"Term not found: '{term}'", parent=top)
        return None

    def find_next():
        last_hit = text_widget.tag_ranges(_SEARCH_HIGHLIGHT_TAG)
        start_pos = last_hit[1] if last_hit else "1.0"
        if not do_search(start_pos):
            do_search("1.0")

    find_next_button = ttk.Button(search_frame, text="Find Next", command=find_next)
    find_next_button.pack(side="left", padx=6)
    query_entry.bind("<Return>", lambda e: find_next())

    def jump_to_selection(event=None):
        # 1. Get the currently selected item in the listbox.
        selections = toc_listbox.curselection()
        if not selections:
            return

        # 2. Clear ALL previous highlights for a clean slate.
        text_widget.tag_remove(_BOOKMARK_HIGHLIGHT_TAG, "1.0", "end")
        text_widget.tag_remove(_SEARCH_HIGHLIGHT_TAG, "1.0", "end")

        # 3. Get the line number for the selected bookmark.
        idx = selections[0]
        _title, lineno, _depth = anchors[idx]
        line_index = f"{lineno}.0"

        # 4. Apply the new highlight to the line.
        text_widget.tag_add(_BOOKMARK_HIGHLIGHT_TAG, line_index, f"{line_index} lineend")

        # --- NEW RELIABLE SCROLL-TO-TOP LOGIC ---
        # A. First, scroll to the VERY BOTTOM to ensure the target is above the viewport.
        text_widget.yview_moveto(1.0)

        # B. Now, use .see(), which will be forced to place the line at the top.
        text_widget.see(line_index)

        # C. Ensure the UI updates smoothly.
        text_widget.update_idletasks()

    # This crucial line connects listbox clicks to the jump_to_selection function.
    toc_listbox.bind("<<ListboxSelect>>", jump_to_selection)

    def jump_to_section_by_name(name: str):
        for i, (title, _ln, _depth) in enumerate(anchors):
            if title.lower().strip() == name.lower().strip():
                toc_listbox.selection_clear(0, "end")
                toc_listbox.selection_set(i)
                toc_listbox.activate(i)
                jump_to_selection()
                break

    if section:
        top.after(100, lambda: jump_to_section_by_name(section))

    _center_on_screen(top)
    top.grab_set()


def show_about_dialog(
    parent: tk.Misc,
    help_path: Path,
    get_text: Callable[[str, str], str],
) -> None:
    """Shows the About dialog with diagnostic and help buttons."""
    top = tk.Toplevel(parent)
    top.title(get_text("dialog.about.title", "About"))
    top.resizable(False, False)
    top.transient(parent)

    frm = ttk.Frame(top, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text=_APP_NAME, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    version_text = get_text("dialog.about.version", "Version: {version}")
    ttk.Label(frm, text=version_text.format(version=_VERSION)).pack(anchor="w", pady=(0, 8))

    row = ttk.Frame(frm)
    row.pack(fill="x", pady=(4, 0))

    ttk.Button(
        row,
        text=get_text("menu.copy_diagnostics", "Copy diagnostic info"),
        command=lambda: _copy_diagnostics(parent, get_text),
    ).pack(side="left")

    ttk.Button(
        row,
        text=get_text("dialog.about.open_troubleshooting", "Help → Troubleshooting"),
        command=lambda: open_help_window(parent, help_path, get_text, section="Troubleshooting"),
    ).pack(side="left", padx=6)

    ttk.Button(row, text=get_text("dialog.about.close", "Close"), command=top.destroy).pack(
        side="right"
    )

    _center_on_screen(top)
