
from __future__ import annotations
import platform, subprocess, sys
from workbench_core import resolve_tool_path
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

APP_NAME = "YT Audio Workbench"
VERSION = ""

__all__ = ["open_help_window", "show_about_dialog", "set_app_meta"]

def _center_on_screen(top: tk.Toplevel):
    try:
        top.update_idletasks()
        w = top.winfo_width() or 800
        h = top.winfo_height() or 600
        sw = top.winfo_screenwidth()
        sh = top.winfo_screenheight()
        x = int((sw - w) / 2)
        y = int((sh - h) / 2)
        top.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass


def set_app_meta(app_name: str, version: str) -> None:
    """Set application metadata used by the Help/About windows."""
    global APP_NAME, VERSION
    APP_NAME, VERSION = app_name, version

def open_help_window(parent: tk.Misc, help_path: Path, get_text, section: str | None = None):
    """Open a help window rendering the HELP.md text; simple ToC based on headings."""
    top = tk.Toplevel(parent); top.title(get_text("dialog.help.title", f"Help — {APP_NAME}").format(app=APP_NAME)); top.geometry("940x680")
    top.transient(parent)
    container = ttk.Frame(top, padding=6); container.pack(fill="both", expand=True)
    searchf = ttk.Frame(container); searchf.pack(fill="x")
    ttk.Label(searchf, text="Search:").pack(side="left")
    qvar = tk.StringVar(); q = ttk.Entry(searchf, textvariable=qvar, width=50); q.pack(side="left", padx=6)
    body = ttk.Frame(container); body.pack(fill="both", expand=True)
    toc = tk.Listbox(body, width=28); toc.pack(side="left", fill="y", padx=(0,8))
    txt = ScrolledText(body, wrap="word"); txt.pack(side="right", fill="both", expand=True)

    def do_search(*_):
        term = qvar.get().strip().lower()
        if not term: return
        content = txt.get("1.0", "end-1c").lower()
        pos = content.find(term)
        if pos >= 0:
            index = txt.index(f"1.0+{pos}c"); line = index.split(".")[0]
            txt.see(f"{line}.0"); txt.tag_remove("sel","1.0","end"); txt.tag_add("sel", f"{line}.0", f"{line}.0 lineend")
    q.bind("<Return>", do_search)

    try:
        raw = Path(help_path).read_text(encoding="utf-8")
    except Exception:
        raw = "# Help\n\n" + get_text("dialog.help.not_found", "Help file not found.")
    txt.insert("end", raw); txt.config(state="disabled")

    _center_on_screen(top)

    lines = raw.splitlines(); anchors = []
    for i, line in enumerate(lines, start=1):
        if line.startswith("#"):
            depth = len(line) - len(line.lstrip("#"))
            title = line.lstrip("#").strip()
            anchors.append((title, i, depth)); toc.insert("end", ("    "*(depth-1)) + title)

    def jump(evt=None, target=None):
        if target is None:
            sel = toc.curselection(); 
            if not sel: return
            idx = sel[0]; _, lineno, _ = anchors[idx]
        else:
            lineno = None
            for title, ln, _ in anchors:
                if title.lower().startswith(target.lower()): lineno = ln; break
            if lineno is None: return
        txt.see(f"{lineno}.0"); txt.tag_remove("sel","1.0","end"); txt.tag_add("sel", f"{lineno}.0", f"{lineno}.0 lineend")
    toc.bind("<<ListboxSelect>>", jump)
    if section: jump(target=section)

def show_about_dialog(parent: tk.Misc, help_path: Path, get_text):
    top = tk.Toplevel(parent); top.title(get_text("dialog.about.title", "About")); top.resizable(False, False)
    frm = ttk.Frame(top, padding=12); frm.pack(fill="both", expand=True)
    ttk.Label(frm, text=APP_NAME, font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
    ttk.Label(frm, text=get_text("dialog.about.version", "Version: {version}").format(version=VERSION)).pack(anchor="w", pady=(0,8))
    ttk.Button(frm, text="Copy diagnostic info", command=lambda: _copy_diag(top)).pack(side="left")
    ttk.Button(frm, text="Open Help → Troubleshooting", command=lambda: open_help_window(parent, help_path, section="Troubleshooting")).pack(side="left", padx=6)
    ttk.Button(frm, text="Close", command=top.destroy).pack(side="right")

    _center_on_screen(top)

def _copy_diag(parent: tk.Misc):
    lines = []
    lines.append(f"{APP_NAME} {VERSION}".strip())
    lines.append(f"Python: {sys.version.splitlines()[0]}")
    lines.append(f"OS: {platform.system()} {platform.release()}")
    for tool, args in [("yt-dlp", ["--version"]),("ffmpeg", ["-version"]),("ffprobe", ["-version"]),("mp3gain", ["-v"])]:
        lines.extend(_tool_info(tool, args))
    try: parent.clipboard_clear(); parent.clipboard_append("\n".join(lines))
    except Exception: pass
    messagebox.showinfo(get_text("dialog.copied.title", "Diagnostics copied"), get_text("dialog.copied.body", "Diagnostic info copied to clipboard."))

def _find_tool_path(cmd: str) -> str | None:
    import shutil, os, sys
    # 1) PATH
    p = shutil.which(cmd)
    if p:
        return p
    # 2) Windows common locations
    if os.name == "nt":
        candidates = []
        local = os.environ.get("LOCALAPPDATA","")
        userprofile = os.environ.get("USERPROFILE","")
        program_files = os.environ.get("ProgramFiles","")
        program_files_x86 = os.environ.get("ProgramFiles(x86)","")
        # WinGet shim
        if local:
            candidates.append(os.path.join(local, "Microsoft", "WinGet", "Links", f"{cmd}.exe"))
        # Chocolatey shims
        candidates.append(os.path.join(os.environ.get("ProgramData","C:\\ProgramData"), "chocolatey", "bin", f"{cmd}.exe"))
        # Scoop shims
        if userprofile:
            candidates.append(os.path.join(userprofile, "scoop", "shims", f"{cmd}.exe"))
        # App-specific installs
        if cmd.lower() == "mp3gain":
            if program_files_x86:
                candidates.append(os.path.join(program_files_x86, "MP3Gain", "mp3gain.exe"))
            if program_files:
                candidates.append(os.path.join(program_files, "MP3Gain", "mp3gain.exe"))
        # ffmpeg/ffprobe common dir
        for base in [program_files, program_files_x86]:
            if base:
                candidates.append(os.path.join(base, "FFmpeg", "bin", f"{cmd}.exe"))
        for c in candidates:
            if c and os.path.exists(c):
                return c
    # 3) macOS/Homebrew typical
    if sys.platform == "darwin":
        for pth in ["/opt/homebrew/bin","/usr/local/bin"]:
            cand = os.path.join(pth, cmd)
            if os.path.exists(cand):
                return cand
    # 4) Linux common
    for pth in ["/usr/bin","/usr/local/bin"]:
        cand = os.path.join(pth, cmd)
        if os.path.exists(cand):
            return cand
    return None

def _tool_info(cmd: str, version_args: list[str]) -> list[str]:
    import shutil
    out = []; path = resolve_tool_path(cmd)
    if not path:
        out.append(f"{cmd}: not found"); return out
    out.append(f"{cmd}: {path}")
    try:
        p = subprocess.run([path, *version_args], capture_output=True, text=True, timeout=3)
        first = p.stdout.splitlines()[0] if p.stdout.strip() else (p.stderr.splitlines()[0] if p.stderr.strip() else "(no output)")
        out.append(f"{cmd} version: {first}")
    except Exception as e: out.append(f"{cmd} version: error: {e}")
    return out
