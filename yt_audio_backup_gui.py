#!/usr/bin/env python3
"""
YT Audio Workbench (formerly "YT Audio Backup")
Reliability-first wrapper around yt-dlp + ffmpeg (+ optional mp3gain).

Key features
- Robust logs (GUI + file), progress bar, cancellable runs
- JSON → Netscape cookies converter with header + httpOnly handling
- Cookies validator with auto-repair of missing header (logs the repair)
- Optional join into a single MP3, with CUE + ID3 chapters (mutagen)
- MP3Gain normalization if present, detected even if not on PATH
- Verify Tools & Check/Install Deps (winget, plus helper scripts for macOS/Linux)
- Config persistence for all options
- Optional "Verbose yt-dlp logging" checkbox
"""

from __future__ import annotations

import os
import sys
import json
import time

import threading
from workbench_core import (
    # Process Helpers
    run_capture,
    CANCEL_EVENT,
    terminate_all_procs,
    verify_tools,
    check_and_install_deps,
    have,
    spawn_streaming,
    # File & Audio Logic
    _sanitize_and_rename,
    _dedup_artist_in_filenames,
    join_via_wav_then_lame,
    validate_sample_rates,
    write_id3_tags_mutagen,
    # Playlist & Chapter Logic
    write_playlist,
    write_cue_for_joined,
    embed_id3_chapters,
    write_vlc_segment_playlist,
    # Cookie Logic
    convert_cookie_editor_json_to_netscape,
    validate_netscape_cookiefile,
    # Task Runner Surface
    ProcessingOptions,
)


from tooltips import attach_tooltip, reset_tooltips
import subprocess
import queue
from pathlib import Path

import tkinter as tk
from help_window import open_help_window, show_about_dialog, set_app_meta

# Robustly import the local help_window.py to avoid clashes on sys.path
import importlib.util

_HELP_MOD_PATH = Path(__file__).with_name("help_window.py")
_hw = None
try:
    import help_window as _hw  # may be a different module on sys.path
except Exception:
    _hw = None
if (
    not _hw
    or not getattr(_hw, "__file__", "")
    or Path(_hw.__file__).resolve() != _HELP_MOD_PATH.resolve()
):
    _spec = importlib.util.spec_from_file_location("awb_help_window", str(_HELP_MOD_PATH))
    _mod = importlib.util.module_from_spec(_spec)
    assert _spec and _spec.loader, "Failed to create loader for help_window.py"
    _spec.loader.exec_module(_mod)
    open_help_window = _mod.open_help_window
    show_about_dialog = _mod.show_about_dialog
    set_app_meta = _mod.set_app_meta
else:
    open_help_window = _hw.open_help_window
    show_about_dialog = _hw.show_about_dialog
    set_app_meta = _hw.set_app_meta

from i18n import Language
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from ui_extras import add_help_right_aligned_menu

APP_NAME = "YT Audio Workbench"
VERSION = "0.1.8n-p9b"


# ---------- yt-dlp logger ----------


class YDLLogger:
    def __init__(self, logfunc, verbose: bool = False):
        # Debug: log which help_window module file is in use
        try:
            self.log(f"help_window module: {getattr(open_help_window, '__module__', '?')}")
        except Exception:
            pass
        self._log = logfunc
        self._verbose = verbose

    def debug(self, msg):
        if self._verbose:
            self._log(str(msg))

    def info(self, msg):
        self._log(str(msg))

    def warning(self, msg):
        self._log("WARNING: " + str(msg))

    def error(self, msg):
        self._log("ERROR: " + str(msg))


# ---------- media helpers ----------


def _relayout_checks(container, widgets, min_col_width=220, max_cols=4):
    try:
        width = max(container.winfo_width(), 1)
    except Exception:
        width = 800
    cols = max(1, min(max_cols, width // min_col_width))
    for w in widgets:
        try:
            w.grid_forget()
        except Exception:
            pass
    for c in range(cols):
        try:
            container.grid_columnconfigure(c, weight=1, uniform="checks")
        except Exception:
            pass
    for i, w in enumerate(widgets):
        r, c = divmod(i, cols)
        w.grid(row=r, column=c, sticky="w", padx=6, pady=2)


def _bind_responsive(container, widgets, min_col_width=220, max_cols=4):
    container.bind(
        "<Configure>", lambda e: _relayout_checks(container, widgets, min_col_width, max_cols)
    )


# ---------- GUI ----------


class App(tk.Tk):
    def _t(self, key: str, fallback: str) -> str:
        try:
            return self.lang.get(key, fallback) or fallback
        except Exception:
            return fallback

    def _clear_main_ui(self) -> None:
        try:
            for child in list(self.winfo_children()):
                # Keep the help bar (right-aligned Help menu) if present
                if hasattr(self, "help_bar") and child is self.help_bar:
                    continue
                try:
                    child.destroy()
                except Exception:
                    pass
        except Exception:
            pass

    def _rebuild_main_ui(self) -> None:
        # Rebuild everything below the help bar using the current language
        self._clear_main_ui()
        try:
            self._build_ui()
        except Exception as e:
            try:
                # Fall back to at least keeping the window usable
                from tkinter import messagebox

                messagebox.showerror("Rebuild UI", f"Failed to rebuild UI: {e}")
            except Exception:
                pass

    def _rebuild_help_bar(self):
        try:
            if hasattr(self, "help_bar") and self.help_bar and self.help_bar.winfo_exists():
                self.help_bar.destroy()
        except Exception:
            pass
        try:
            from ui_extras import add_help_right_aligned_menu

            self.help_bar = add_help_right_aligned_menu(
                self,
                app_name=APP_NAME,
                version=VERSION,
                help_md_path=Path(__file__).parent / "docs" / "HELP.md",
                get_text=lambda k, f: self.lang.get(k, f),
                locales=self.lang.available_locales(),
                on_switch_language=self.change_language,
            )
        except Exception:
            pass

    def change_language(self, code: str, persist: bool = True) -> None:
        try:
            self.lang.load(code)
            self.current_language = code
        except Exception:
            return

        # Update window title
        try:
            self.title(f"{self.lang.get('app_title', 'YT Audio Workbench')} v{VERSION}")
        except Exception:
            pass

        # Rebuild help bar to update menu labels and selection
        self._rebuild_help_bar()

        # Reset tooltips before UI rebuild to prevent after() against destroyed widgets
        try:
            reset_tooltips()
        except Exception:
            pass

        # Only write config when this is a real user-initiated language change
        if persist:
            try:
                self._save_config()
            except Exception:
                pass

        # Rebuild the rest of the UI with the current language
        self._rebuild_main_ui()

    def _center_main_on_screen(self):
        try:
            if getattr(self, '_did_initial_center', False):
                return
            self._did_initial_center = True
            self.update_idletasks()
            w = self.winfo_width() or self.winfo_reqwidth() or 820
            h = self.winfo_height() or self.winfo_reqheight() or 780
            self.geometry(f"{w}x{h}")
            self.state('zoomed')
        except Exception:
            pass

    def _worker_task(self, options: ProcessingOptions) -> None:
        """The main processing pipeline that runs in a background thread."""

        # Define local helpers for thread-safe communication with the GUI
        def _log(msg: str):
            self._log_q.put(msg)

        def _progress(pct: int | None, status: str | None):
            self._progress_q.put({"pct": pct, "status": status})

        try:
            _log("Starting run...")
            _progress(0, "Preparing...")
            outdir = options.run_sub_dir
            outdir.mkdir(exist_ok=True, parents=True)

            # 1. Prepare Cookies from core
            cookies_arg = None
            if options.cookies_file and options.cookies_file.exists():
                if options.cookies_file.suffix.lower() == ".json":
                    txt_path = outdir / "cookies.txt"
                    options.cookies_file = convert_cookie_editor_json_to_netscape(
                        options.cookies_file, txt_path, _log
                    )
                ok, msg = validate_netscape_cookiefile(options.cookies_file, _log)
                if ok:
                    cookies_arg = str(options.cookies_file)
                else:
                    _log(f"Cookie file issue: {msg}")

            # 2. Build yt-dlp command
            outtmpl = self._build_outtmpl(
                options.numbering, options.fallback_numbering, options.include_id
            )
            cmd = [
                "yt-dlp",
                "-x",
                "--audio-format",
                "mp3",
                "--audio-quality",
                "0",
                "-o",
                str(outdir / outtmpl),
                "--no-simulate",
                "--no-playlist-reverse",
                "--ignore-errors",
                "--progress",
            ]
            if options.use_archive:
                cmd.extend(["--download-archive", str(outdir / "archive.txt")])
            if options.sleep_between > 0:
                cmd.extend(["--sleep-interval", str(options.sleep_between)])
            if options.verbose_ydl:
                cmd.append("--verbose")
            if options.hi_integrity:
                _log("High integrity mode enabled: wip - to be implemented.")
                cmd.extend([""])
            if cookies_arg:
                cmd.extend(["--cookies", cookies_arg])
            elif options.cookies_browser and options.cookies_browser.lower() != "none":
                cmd.extend(["--cookies-from-browser", options.cookies_browser.lower()])
            cmd.append(options.url)

            # 3. Run yt-dlp and stream output for progress
            _log(f"Running command: {' '.join(cmd)}")
            _progress(5, "Downloading...")
            p = spawn_streaming(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            downloaded_files = []
            if p.stdout:
                for line in p.stdout:
                    if CANCEL_EVENT.is_set():
                        p.terminate()
                        break
                    line = line.strip()
                    if line:
                        _log(line)
                    if "[download] Destination:" in line:
                        fpath = Path(line.split("Destination:", 1)[1].strip())
                        if fpath.exists():
                            downloaded_files.append(fpath)
                    elif "[download]" in line and "% of" in line:
                        pct = int(float(line.split("%")[0].split()[-1]))
                        _progress(5 + int(pct * 0.75), f"Downloading: {pct}%")
            p.wait()

            if CANCEL_EVENT.is_set():
                raise InterruptedError("Run cancelled by user.")

            # 4. Post-processing using core functions
            _progress(80, "Post-processing...")
            if not downloaded_files:
                _log("No new files were downloaded.")
            else:
                _log(f"Downloaded {len(downloaded_files)} files. Post-processing...")
                if options.sanitize_filenames:
                    downloaded_files = _sanitize_and_rename(downloaded_files, _log)
                if options.embed_metadata:
                    album_name = outdir.name.replace(f"run_{outdir.name.split('_')[-1]}", "").strip(
                        " _-"
                    )
                    write_id3_tags_mutagen(downloaded_files, album_name, _log)
                if options.dedup_artist:
                    downloaded_files = _dedup_artist_in_filenames(downloaded_files, _log)
                if options.validate_sr:
                    validate_sample_rates(downloaded_files, options.sample_rate, _log)
                if options.join:
                    _progress(85, "Joining files...")
                    joined_file = join_via_wav_then_lame(
                        files=downloaded_files,
                        outdir=outdir,
                        sr=options.sample_rate,
                        br_kbps=options.bitrate,
                        join_name=options.join_name,
                        log=_log,
                        shuffle=options.random_join,
                        keep_temp=options.keep_temp_wavs,
                        progress=_progress,
                    )
                    if options.write_cue:
                        write_cue_for_joined(joined_file, downloaded_files, _log)
                    if options.embed_chapters:
                        embed_id3_chapters(joined_file, downloaded_files, _log)
                    if options.vlc_segments:
                        write_vlc_segment_playlist(joined_file, downloaded_files, outdir, _log)
                if options.playlist_format:
                    write_playlist(
                        outdir, downloaded_files, _log, "playlist", options.playlist_format
                    )

                if options.mp3gain:
                    _progress(95, "Normalizing volume...")
                    _log("Applying MP3Gain normalization...")
                    # Note: We need to import 'have' from the core for this to work
                    if have("mp3gain"):
                        files_to_normalize = (
                            [joined_file]
                            if options.join and 'joined_file' in locals()
                            else downloaded_files
                        )
                        for f in files_to_normalize:
                            try:
                                run_capture(["mp3gain", "-r", "-k", "-p", str(f)])
                            except Exception as e:
                                _log(f"mp3gain failed for {f.name}: {e}")
                    else:
                        _log("mp3gain not found, skipping normalization.")

            _progress(100, "Done")
            _log("Run finished successfully.")

        except InterruptedError as e:
            _log(str(e))
            _progress(None, "Cancelled")
        except Exception as e:
            _log(f"FATAL ERROR in worker thread: {e}")
            _progress(None, f"Error: {e}")
        finally:
            # Schedule the UI update back on the main thread
            self.after(0, self._finish_run)

    def __init__(self) -> None:
        # Initialize language manager and current language
        try:
            lang_dir = Path(__file__).with_name("lang")
        except Exception:
            from pathlib import Path as _P

            lang_dir = _P("lang")
        self.lang = Language(lang_dir, code="en")
        self.current_language = self.lang.code
        super().__init__()
        self.title(f"{self.lang.get('app_title', 'YT Audio Workbench')} v{VERSION}")
        try:
            set_app_meta(self.title(), VERSION)
        except Exception:
            pass

        # Set Help/About metadata
        try:
            set_app_meta(self.title(), "0.1.8n-p9b")
        except Exception:
            pass

        w, h = 820, 780
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(w, h)

        # Help menu (right-aligned bar) + F1
        try:
            self.help_bar = add_help_right_aligned_menu(
                self,
                app_name=APP_NAME,
                version=VERSION,
                help_md_path=Path(__file__).parent / "docs" / "HELP.md",
                get_text=lambda k, f: self.lang.get(k, f),
                locales=self.lang.available_locales(),
                on_switch_language=self.change_language,
            )
        except Exception:
            pass

        # Vars
        self.url_var = tk.StringVar()
        self.out_var = tk.StringVar()
        self.sample_rate_var = tk.IntVar(value=44100)
        self.bitrate_var = tk.IntVar(value=192)
        self.embed_meta_var = tk.BooleanVar(value=True)
        self.archive_var = tk.BooleanVar(value=False)
        self.include_id_var = tk.BooleanVar(value=False)
        self.numbering_var = tk.BooleanVar(value=True)
        self.fallback_numbering_var = tk.BooleanVar(value=True)
        self.join_var = tk.BooleanVar(value=False)
        self.join_name_var = tk.StringVar(value="joined")
        self.write_cue_var = tk.BooleanVar(value=True)
        self.embed_chapters_var = tk.BooleanVar(value=True)
        self.vlc_segments_var = tk.BooleanVar(value=False)
        self.random_join_var = tk.BooleanVar(value=False)
        self.sleep_between_var = tk.IntVar(value=3)
        self.detailed_log_var = tk.BooleanVar(value=True)
        self.rolling_log_var = tk.BooleanVar(value=False)
        self.verbose_ydl_var = tk.BooleanVar(value=False)
        self.mp3gain_var = tk.BooleanVar(value=True)
        self.hi_integrity_var = tk.BooleanVar(value=False)
        self.keep_temp_var = tk.BooleanVar(value=False)
        self.dedup_artist_var = tk.BooleanVar(value=False)
        self.sanitize_names_var = tk.BooleanVar(value=True)
        self.validate_sr_var = tk.BooleanVar(value=True)
        self.playlist_format_var = tk.StringVar(value="M3U8")
        self.use_run_subdir_var = tk.BooleanVar(value=True)
        self.cookies_file_var = tk.StringVar()
        self.cookies_browser_var = tk.StringVar(value="None")

        self.status_var = tk.StringVar(value="Idle")
        self.progress_var = tk.IntVar(value=0)
        self._progress_q: queue.Queue[dict] = queue.Queue()
        self._progress_total = 0
        self._progress_done = 0

        self._log_q: queue.Queue[str] = queue.Queue()
        self.file_log_fp = None
        self.log_file_path: Path | None = None

        # Hide during initial layout to avoid off-center flash

        try:
            self.withdraw()

        except Exception:
            pass

        try:
            self._load_config()
        except Exception:
            pass

        self._build_ui()

        # Enforce minimum window size (height)
        try:
            self.update_idletasks()
            w = 820
            h = 780
            self.minsize(w, h)
        except Exception:
            pass
        self._cookies_loaded_once = False
        # Start pollers early so logs show for all actions
        self.after(100, self._poll_log)
        self.after(100, self._poll_progress)

        # Apply saved locale after config load (reuse existing change_language path)
        try:
            saved_locale = None
            if hasattr(self, "config") and isinstance(self.config, dict):
                for _k in ("locale", "language", "lang"):
                    _v = self.config.get(_k)
                    if isinstance(_v, str) and _v.strip():
                        saved_locale = _v.strip()
                        break
            if saved_locale and saved_locale != getattr(self, "current_language", None):
                self.change_language(saved_locale)
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Center main window once UI is realized
        try:
            self.after(0, self._center_main_on_screen)
        except Exception:
            pass

        # Layout → compute size → center → show

        try:
            self.update_idletasks()

            self._center_main_on_screen()

            self.deiconify()

        except Exception:
            try:
                self.deiconify()

            except Exception:
                pass

    def _build_ui(self) -> None:
        pad = dict(padx=8, pady=6)

        # URL
        urlf = ttk.LabelFrame(self, text=self._t("frames.url", "URL"))
        urlf.pack(fill="x", **pad)
        ttk.Label(urlf, text=self._t("labels.url", "Playlist or video URL:")).pack(side="left")
        url_entry = ttk.Entry(urlf, textvariable=self.url_var)
        url_entry.pack(side="left", fill="x", expand=True, padx=6)
        attach_tooltip(
            url_entry,
            lambda: self._t("tooltips.url_entry", "Paste a YouTube video or playlist URL."),
        )
        ttk.Button(urlf, text="Paste", command=lambda: self._paste_into(url_entry)).pack(
            side="left"
        )
        self._attach_context_menu(url_entry, "entry")

        # Output
        outf = ttk.LabelFrame(self, text=self._t("frames.output", "Output"))
        outf.pack(fill="x", **pad)
        ttk.Label(outf, text="Output folder:").pack(side="left")
        out_entry = ttk.Entry(outf, textvariable=self.out_var)
        out_entry.pack(side="left", fill="x", expand=True, padx=6)
        attach_tooltip(
            out_entry,
            lambda: self._t(
                "tooltips.output_folder_entry", "Choose where to save downloads and logs."
            ),
        )
        browse_out_btn = ttk.Button(
            outf, text=self._t("buttons.browse", "Browse…"), command=self._browse_out
        )
        browse_out_btn.pack(side="left")
        attach_tooltip(
            browse_out_btn,
            lambda: self._t("tooltips.browse_output_button", "Choose the output folder."),
        )
        self._attach_context_menu(out_entry, "path")
        use_run_cb = ttk.Checkbutton(
            outf,
            text=self._t("checkboxes.use_run_subdir", "Use per-run subfolder (recommended)"),
            variable=self.use_run_subdir_var,
        )
        use_run_cb.pack(side="left", padx=8)
        attach_tooltip(
            use_run_cb, lambda: self._t("tooltips.use_run_subdir", "Create per-run subfolder.")
        )

        # Cookies
        cookies = ttk.LabelFrame(self, text=self._t("frames.cookies", "Cookies"))
        cookies.pack(fill="x", **pad)
        c1 = ttk.Frame(cookies)
        c1.pack(fill="x")
        ttk.Label(c1, text=self._t("labels.cookies_file", "Cookies file (.txt or JSON)")).pack(
            side="left"
        )
        ttk.Label(c1, text=" or ").pack(side="left")
        ttk.Label(c1, text=self._t("labels.cookies_browser", "Use browser cookies:")).pack(
            side="left"
        )
        self.cookies_browser_cb = ttk.Combobox(
            c1,
            textvariable=self.cookies_browser_var,
            values=["None", "Chrome", "Edge", "Firefox"],
            width=8,
            state="readonly",
        )
        attach_tooltip(
            self.cookies_browser_cb,
            lambda: self._t(
                "tooltips.cookies_browser",
                "Use cookies from a supported browser (Chrome/Edge/Firefox).",
            ),
        )
        self.cookies_browser_cb.pack(side="left", padx=6)
        c2 = ttk.Frame(cookies)
        c2.pack(fill="x")
        self.cookies_file_entry = ttk.Entry(c2, textvariable=self.cookies_file_var)
        self.cookies_file_entry.pack(side="left", fill="x", expand=True, padx=6)
        attach_tooltip(
            self.cookies_file_entry,
            lambda: self._t(
                "tooltips.cookies_file_entry",
                "A cookies.txt (Netscape format) or Cookie-Editor JSON file.",
            ),
        )
        browse_cookies_btn = ttk.Button(
            c2, text=self._t("buttons.browse", "Browse…"), command=self._browse_cookies
        )
        browse_cookies_btn.pack(side="left")
        attach_tooltip(
            browse_cookies_btn,
            lambda: self._t("tooltips.browse_cookies_button", "Select a cookies file."),
        )
        self._attach_context_menu(self.cookies_file_entry, "path")

        # Options
        opts = ttk.LabelFrame(
            self, text=self._t("frames.download_formatting", "Download & Formatting")
        )
        opts.pack(fill="x", **pad)
        rate_frame = ttk.Frame(opts)
        rate_frame.pack(fill="x", pady=6)
        ttk.Label(rate_frame, text=self._t("labels.sample_rate", "Sample rate:")).pack(side="left")
        sr_combo = ttk.Combobox(
            rate_frame,
            textvariable=self.sample_rate_var,
            values=[44100, 48000],
            width=8,
            state="readonly",
        )
        sr_combo.pack(side="left", padx=6)
        attach_tooltip(
            sr_combo,
            lambda: self._t(
                "tooltips.sample_rate_combo", "Enforces a consistent audio sample rate."
            ),
        )
        ttk.Label(rate_frame, text=self._t("labels.bitrate", "Bitrate (kbps):")).pack(side="left")
        br_combo = ttk.Combobox(
            rate_frame,
            textvariable=self.bitrate_var,
            values=[192, 256, 320],
            width=6,
            state="readonly",
        )
        br_combo.pack(side="left", padx=6)
        attach_tooltip(br_combo, lambda: self._t("tooltips.bitrate_combo", "Sets the MP3 bitrate."))
        ttk.Label(
            rate_frame, text=self._t("labels.delay_between_items", "Delay between items (s):")
        ).pack(side="left")
        delay_spin = ttk.Spinbox(
            rate_frame, textvariable=self.sleep_between_var, from_=0, to=30, width=4
        )
        delay_spin.pack(side="left", padx=6)
        attach_tooltip(
            delay_spin, lambda: self._t("tooltips.delay_spinbox", "Delay between playlist items.")
        )

        pf = ttk.Frame(opts)
        pf.pack(fill="x", pady=4)
        ttk.Label(pf, text=self._t("labels.playlist_format", "Playlist format:")).pack(side="left")
        plf_combo = ttk.Combobox(
            pf,
            textvariable=self.playlist_format_var,
            values=["M3U8", "M3U", "Both"],
            width=8,
            state="readonly",
        )
        plf_combo.pack(side="left", padx=6)
        attach_tooltip(
            plf_combo,
            lambda: self._t("tooltips.playlist_format_combo", "Choose output playlist format."),
        )

        chk_frame = ttk.LabelFrame(
            self, text=self._t("frames.filename_options", "Filename & Options")
        )
        chk_frame.pack(fill="x", **pad)
        chk_grid = ttk.Frame(chk_frame)
        chk_grid.pack(fill="x")
        checks = [
            (
                self._t("checkboxes.add_numbering", "Add numbering"),
                self.numbering_var,
                "tooltips.checkboxes.add_numbering",
            ),
            (
                self._t("checkboxes.fallback_numbering", "Fallback numbering when not a playlist"),
                self.fallback_numbering_var,
                "tooltips.checkboxes.fallback_numbering",
            ),
            (
                self._t("checkboxes.include_id", "Include YouTube ID in filename"),
                self.include_id_var,
                "tooltips.checkboxes.include_id",
            ),
            (
                self._t("checkboxes.dedup_artist", "De-duplicate artist in filename"),
                self.dedup_artist_var,
                "tooltips.checkboxes.dedup_artist",
            ),
            (
                self._t("checkboxes.sanitize_filenames", "Sanitize filenames (max compatibility)"),
                self.sanitize_names_var,
                "tooltips.checkboxes.sanitize_filenames",
            ),
            (
                self._t("checkboxes.embed_metadata", "Embed metadata"),
                self.embed_meta_var,
                "tooltips.checkboxes.embed_metadata",
            ),
            (
                self._t("checkboxes.use_archive", "Use download archive"),
                self.archive_var,
                "tooltips.checkboxes.use_archive",
            ),
            (
                self._t("checkboxes.mp3gain_normalize", "Normalize with MP3Gain"),
                self.mp3gain_var,
                "tooltips.checkboxes.mp3gain_normalize",
            ),
            (
                self._t("checkboxes.validate_sr", "Validate with ffprobe"),
                self.validate_sr_var,
                "tooltips.checkboxes.validate_sr",
            ),
            (
                self._t("checkboxes.verbose_ydl", "Verbose yt-dlp logging"),
                self.verbose_ydl_var,
                "tooltips.checkboxes.verbose_ydl",
            ),
        ]
        check_widgets = []
        for label, var, tip_key in checks:
            w = ttk.Checkbutton(chk_grid, text=label, variable=var)
            attach_tooltip(w, lambda k=tip_key: self._t(k, "Tooltip not found."))
            check_widgets.append(w)
        _relayout_checks(chk_grid, check_widgets, min_col_width=200, max_cols=4)
        _bind_responsive(chk_grid, check_widgets, min_col_width=200, max_cols=4)

        joinf = ttk.LabelFrame(self, text=self._t("frames.joining", "Joining"))
        joinf.pack(fill="x", **pad)
        name_frame = ttk.Frame(joinf)
        name_frame.pack(fill="x")
        join_cb = ttk.Checkbutton(
            name_frame,
            text=self._t("checkboxes.join_into_one", "Join into one MP3"),
            variable=self.join_var,
        )
        join_cb.pack(side="left")
        attach_tooltip(
            join_cb,
            lambda: self._t(
                "tooltips.checkboxes.join_into_one", "Join multiple items into a single MP3 album."
            ),
        )
        ttk.Label(name_frame, text="Name:").pack(side="left", padx=(12, 0))
        self.join_name_entry = ttk.Entry(name_frame, textvariable=self.join_name_var, width=32)
        self.join_name_entry.pack(side="left", padx=6)
        attach_tooltip(
            self.join_name_entry,
            lambda: self._t("tooltips.join_name_entry", "Name for the final joined MP3 / album."),
        )
        self._attach_context_menu(self.join_name_entry, "entry")
        chk_frame2 = ttk.Frame(joinf)
        chk_frame2.pack(fill="x")
        join_checks = [
            (
                self._t("checkboxes.write_cue", "Write CUE for joined file"),
                self.write_cue_var,
                "tooltips.checkboxes.write_cue",
            ),
            (
                self._t("checkboxes.embed_chapters", "Embed ID3 chapters in joined file"),
                self.embed_chapters_var,
                "tooltips.checkboxes.embed_chapters",
            ),
            (
                self._t(
                    "checkboxes.vlc_segments",
                    "Write VLC segments playlist for joined file (M3U with EXTVLCOPT)",
                ),
                self.vlc_segments_var,
                "tooltips.checkboxes.vlc_segments",
            ),
            (
                self._t("checkboxes.random_join", "Randomize order when joining"),
                self.random_join_var,
                "tooltips.checkboxes.randomize_order",
            ),
            (
                self._t("checkboxes.keep_temp_wavs", "Keep temp WAVs"),
                self.keep_temp_var,
                "tooltips.checkboxes.keep_temp_wavs",
            ),
        ]
        join_widgets = []
        for label, var, tip_key in join_checks:
            wj = ttk.Checkbutton(chk_frame2, text=label, variable=var)
            attach_tooltip(wj, lambda k=tip_key: self._t(k, "Tooltip not found."))
            join_widgets.append(wj)
        _relayout_checks(chk_frame2, join_widgets, min_col_width=200, max_cols=4)
        _bind_responsive(chk_frame2, join_widgets, min_col_width=200, max_cols=4)
        deps = ttk.LabelFrame(self, text=self._t("frames.system_deps", "System Dependencies"))
        deps.pack(fill="x", **pad)
        ttk.Label(deps, text="Ensure ffmpeg/ffprobe and optional mp3gain are installed.").pack(
            side="left"
        )
        self.verify_btn = ttk.Button(
            deps,
            text=self._t("buttons.verify_tools", "Verify Tools"),
            command=self._verify_tools_async,
        )
        self.verify_btn.pack(side="right", padx=6)
        attach_tooltip(
            self.verify_btn,
            lambda: self._t(
                "tooltips.verify_tools_button", "Check whether required tools are installed."
            ),
        )
        self.check_deps_btn = ttk.Button(
            deps,
            text=self._t("buttons.check_install_deps", "Check & Install System Deps"),
            command=self._check_and_install_deps_async,
        )
        self.check_deps_btn.pack(side="right")
        attach_tooltip(
            self.check_deps_btn,
            lambda: self._t(
                "tooltips.check_deps_button", "Attempt to install missing dependencies."
            ),
        )

        ctrls = ttk.Frame(self)
        ctrls.pack(fill="x", **pad)
        self.run_btn = ttk.Button(ctrls, text=self._t("buttons.run", "Run"), command=self._run)
        self.run_btn.pack(side="left")
        attach_tooltip(
            self.run_btn, lambda: self._t("tooltips.run_button", "Start the processing pipeline.")
        )
        self.cancel_btn = ttk.Button(
            ctrls, text=self._t("buttons.cancel", "Cancel"), command=self._cancel, state="disabled"
        )
        self.cancel_btn.pack(side="left", padx=6)
        attach_tooltip(
            self.cancel_btn, lambda: self._t("tooltips.cancel_button", "Cancel the current run.")
        )
        ttk.Label(ctrls, textvariable=self.status_var).pack(side="right")
        pb = ttk.Progressbar(
            ctrls, orient="horizontal", mode="determinate", variable=self.progress_var, length=260
        )
        pb.pack(side="right", padx=12)

        logf = ttk.LabelFrame(self, text=self._t("frames.log", "Log"))
        logf.pack(fill="both", expand=True, **pad)
        self.log_txt = ScrolledText(logf, height=6, wrap="word")
        self.log_txt.pack(fill="both", expand=True)
        self.log_txt.configure(state="disabled")
        self._attach_context_menu(self.log_txt, "text")

        log_tools = ttk.Frame(logf)
        log_tools.pack(fill="x")
        open_log_btn = ttk.Button(
            log_tools,
            text=self._t("buttons.open_log", "View Log File"),
            command=self._view_log_file,
        )
        open_log_btn.pack(side="left")
        attach_tooltip(
            open_log_btn,
            lambda: self._t("tooltips.open_log_button", "Open the current run’s log file."),
        )
        copy_log_btn = ttk.Button(
            log_tools, text="Copy Log to Clipboard", command=self._copy_log_to_clipboard
        )
        copy_log_btn.pack(side="left", padx=6)
        attach_tooltip(
            copy_log_btn,
            lambda: self._t("tooltips.copy_log_button", "Copy log contents to clipboard."),
        )

        # ---------- small UI helpers ---------- ----------

    def refresh_i18n_ui(self) -> None:
        """
        Re-apply the current language to all UI elements WITHOUT persisting config.
        Useful right after the window is realized to get rid of any fallback labels.
        """
        try:
            # Reuse the same path as language switching, but don't write config
            self.change_language(self.current_language, persist=False)
        except Exception:
            # As a fallback, at least rebuild the visible parts with current lang
            try:
                self._rebuild_help_bar()
                self._rebuild_main_ui()
            except Exception:
                pass

    def _attach_context_menu(self, widget, kind: str = "entry") -> None:
        menu = tk.Menu(widget, tearoff=0)

        def popup(e):
            try:
                menu.delete(0, "end")
                if kind in ("entry", "path"):
                    menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"))
                    menu.add_command(
                        label="Copy", command=lambda: widget.event_generate("<<Copy>>")
                    )
                    menu.add_command(
                        label="Paste", command=lambda: widget.event_generate("<<Paste>>")
                    )
                    menu.add_separator()
                    menu.add_command(
                        label="Select All",
                        command=lambda: (widget.select_range(0, "end"), widget.icursor("end")),
                    )
                    if kind == "path":
                        menu.add_separator()
                        menu.add_command(
                            label="Open Folder / Path",
                            command=lambda: self._open_path_in_os(widget.get()),
                        )
                elif kind == "text":
                    menu.add_command(
                        label="Copy", command=lambda: self._copy_text_selection(widget)
                    )
                    menu.add_command(label="Copy All", command=lambda: self._copy_text_all(widget))
                    menu.add_separator()
                    menu.add_command(
                        label="Select All", command=lambda: widget.tag_add("sel", "1.0", "end-1c")
                    )
                    menu.add_command(
                        label="Clear Log", command=lambda: self._clear_text_widget(widget)
                    )
                menu.tk.call("tk_popup", menu, e.x_root, e.y_root)
            finally:
                try:
                    menu.grab_release()
                except Exception:
                    pass

        for seq in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            try:
                widget.bind(seq, popup, add="+")
            except Exception:
                pass

    def _open_path_in_os(self, path_str: str) -> None:
        p = (path_str or "").strip().strip('"').strip("'")
        if not p:
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(p)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", p], check=False)
            else:
                subprocess.run(["xdg-open", p], check=False)
        except Exception as e:
            self.log(f"Open path failed: {e}")

    def _copy_text_selection(self, w) -> None:
        try:
            state = None
            try:
                state = w["state"]
                w.configure(state="normal")
            except Exception:
                pass
            try:
                text = w.get("sel.first", "sel.last")
            except Exception:
                text = ""
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
            if state is not None:
                w.configure(state=state)
        except Exception:
            pass

    def _copy_text_all(self, w) -> None:
        try:
            state = None
            try:
                state = w["state"]
                w.configure(state="normal")
            except Exception:
                pass
            try:
                text = w.get("1.0", "end-1c")
            except Exception:
                text = ""
            if text:
                self.clipboard_clear()
                self.clipboard_append(text)
            if state is not None:
                w.configure(state=state)
        except Exception:
            pass

    def _clear_text_widget(self, w) -> None:
        try:
            state = None
            try:
                state = w["state"]
                w.configure(state="normal")
            except Exception:
                pass
            w.delete("1.0", "end")
            if state is not None:
                w.configure(state=state)
        except Exception:
            pass

    def _paste_into(self, entry_widget) -> None:
        try:
            entry_widget.event_generate("<<Paste>>")
        except Exception:
            pass

    def _browse_out(self) -> None:
        d = filedialog.askdirectory(title="Select output folder")
        if d:
            self.out_var.set(d)

    def _browse_cookies(self) -> None:
        f = filedialog.askopenfilename(
            title="Select cookies file (.txt or JSON)",
            filetypes=[("Cookies", "*.txt *.json"), ("All files", "*.*")],
        )
        if f:
            self.cookies_file_var.set(f)
            if f.lower().endswith(".json"):
                txt = Path(f).with_suffix(".cookies.txt")
                convert_cookie_editor_json_to_netscape(Path(f), txt, self.log)

        # ---------- logging ----------

    def log(self, msg: str) -> None:
        ts = time.strftime("[%H:%M:%S] ")
        line = ts + msg
        self._log_q.put(line)
        try:
            if self.file_log_fp:
                self.file_log_fp.write(line + "\n")
                self.file_log_fp.flush()
        except Exception:
            pass

    def _append_log_gui(self, msg: str) -> None:
        try:
            self.log_txt.configure(state="normal")
            self.log_txt.insert("end", msg + "\n")
            self.log_txt.see("end")
            self.log_txt.configure(state="disabled")
        except Exception:
            pass

    def _poll_log(self) -> None:
        try:
            while True:
                line = self._log_q.get_nowait()
                self._append_log_gui(line)
        except queue.Empty:
            pass
        self.after(100, self._poll_log)

        # ---------- progress ----------

    def _progress_update(self, overall_pct: int | None = None, status: str | None = None):
        try:
            self._progress_q.put({"pct": overall_pct, "status": status})
        except Exception:
            pass

    def _poll_progress(self) -> None:
        try:
            while True:
                ev = self._progress_q.get_nowait()
                pct = ev.get("pct")
                if pct is not None:
                    try:
                        self.progress_var.set(int(max(0, min(100, pct))))
                    except Exception:
                        pass
                status = ev.get("status")
                if status:
                    self.status_var.set(status)
        except queue.Empty:
            pass
        self.after(100, self._poll_progress)

    def _setup_file_logging(self, outdir: Path) -> None:
        outdir.mkdir(parents=True, exist_ok=True)
        logs = outdir / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.log_file_path = (
            (logs / "backup_run.log")
            if self.rolling_log_var.get()
            else (logs / f"backup_run_{ts}.log")
        )
        if self.detailed_log_var.get():
            try:
                self.file_log_fp = open(self.log_file_path, "a", encoding="utf-8", errors="ignore")
                self.log(f"File logging to: {self.log_file_path}")
            except Exception as e:
                self.file_log_fp = None
                self.log(f"Failed to open log file: {e}")

    def _view_log_file(self) -> None:
        if not self.log_file_path:
            self.log("No run log yet.")
            return
        self._open_path_in_os(str(self.log_file_path))

    def _copy_log_to_clipboard(self) -> None:
        try:
            if not self.log_file_path:
                self.log("No run log yet.")
                return
            txt = Path(self.log_file_path).read_text(encoding="utf-8", errors="ignore")
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.log("Copied log content to clipboard.")
        except Exception as e:
            self.log(f"Copy log failed: {e}")

        # ---------- lifecycle ----------

    def _on_close(self) -> None:
        try:
            self._save_config()
        except Exception:
            pass
        try:
            if self.file_log_fp:
                self.file_log_fp.close()
        except Exception:
            pass
        self.destroy()

    # ---------- run / cancel ----------

    def _cancel(self) -> None:
        """User pressed Cancel: signal workers and terminate any registered children."""
        # Use the shared CANCEL_EVENT (imported from workbench_core)
        if not CANCEL_EVENT.is_set():
            CANCEL_EVENT.set()
            try:
                self.log("Cancel requested — terminating active processes…")
            except Exception:
                pass

        # Stop anything spawned via core helpers (yt-dlp, ffmpeg, mp3gain, etc.)
        terminate_all_procs()

        # Optional UI feedback
        try:
            self.progress_var.set(0)  # if you have a progress var
            self.status_var.set("Cancelling…")
            self.cancel_btn.configure(state="disabled")  # avoid double-cancel clicks
        except Exception:
            pass

    def _run(self) -> None:
        CANCEL_EVENT.clear()
        url = (self.url_var.get() or "").strip()
        outdir = Path(self.out_var.get().strip() or ".").resolve()
        if not url:
            messagebox.showerror(APP_NAME, "Please enter a URL.")
            return

        self.run_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.status_var.set("Running...")
        run_ts = time.strftime("%Y%m%d_%H%M%S")
        outdir.mkdir(parents=True, exist_ok=True)
        out_run = (outdir / f"run_{run_ts}") if bool(self.use_run_subdir_var.get()) else outdir
        self._setup_file_logging(out_run)

        # Build ProcessingOptions to pass to the worker
        opts = ProcessingOptions(
            url=url,
            output_dir=outdir,
            run_sub_dir=out_run,
            sample_rate=int(self.sample_rate_var.get()),
            bitrate=int(self.bitrate_var.get()),
            use_archive=bool(self.archive_var.get()),
            numbering=bool(self.numbering_var.get()),
            fallback_numbering=bool(self.fallback_numbering_var.get()),
            include_id=bool(self.include_id_var.get()),
            sanitize_filenames=bool(self.sanitize_names_var.get()),
            dedup_artist=bool(self.dedup_artist_var.get()),
            embed_metadata=bool(self.embed_meta_var.get()),
            join=bool(self.join_var.get()),
            write_cue=bool(self.write_cue_var.get()),
            embed_chapters=bool(self.embed_chapters_var.get()),
            vlc_segments=bool(self.vlc_segments_var.get()),
            random_join=bool(self.random_join_var.get()),
            keep_temp_wavs=bool(self.keep_temp_var.get()),
            sleep_between=int(self.sleep_between_var.get()),
            verbose_ydl=bool(self.verbose_ydl_var.get()),
            hi_integrity=bool(self.hi_integrity_var.get()),
            cookies_file=Path(self.cookies_file_var.get()) if self.cookies_file_var.get() else None,
            cookies_browser=str(self.cookies_browser_var.get()),
            playlist_format=str(self.playlist_format_var.get()),
        )

        # Start the new worker task in a background thread
        threading.Thread(
            target=self._worker_task,
            args=(opts,),
            daemon=True,
        ).start()

    def _build_outtmpl(self, numbering: bool, fallback_numbering: bool, include_id: bool) -> str:
        core = "%(uploader,channel)s - %(title)s"
        prefix = "%(playlist_index,autonumber)03d - " if numbering else ""
        idsfx = " [%(id)s]" if include_id else ""
        return prefix + core + idsfx + ".%(ext)s"

    def _finish_run(self) -> None:
        self.run_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.status_var.set("Idle")

        # ---------- deps tools (async wrappers + impl) ----------

    def _verify_tools_async(self) -> None:
        if getattr(self, "_busy_verify", False):
            return
        self._busy_verify = True
        self.status_var.set("Verifying tools...")

        def worker():
            try:
                verify_tools(log=self.log)
            finally:
                self._busy_verify = False
                self.status_var.set("Idle")

        threading.Thread(target=worker, daemon=True).start()

    def _check_and_install_deps_async(self) -> None:
        if getattr(self, "_busy_install", False):
            return
        self._busy_install = True
        self.status_var.set("Checking system dependencies...")

        def worker():
            try:
                check_and_install_deps(log=self.log)
            finally:
                self._busy_install = False
                self.status_var.set("Idle")

        threading.Thread(target=worker, daemon=True).start()

    def _winget_is_installed(self, pkg_id: str) -> bool:
        try:
            out = run_capture(["winget", "list", "--id", pkg_id])
            return pkg_id.lower() in out.lower()
        except Exception:
            return False

    def _config_path(self) -> Path:
        try:
            return Path(__file__).resolve().parent / "config.json"
        except Exception:
            return Path("config.json")

    def _load_config(self) -> None:
        p = self._config_path()
        if not p.exists():
            return
        try:
            data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            self.config = data

            # Apply language and tooltip settings early
            try:
                lang_code = data.get("lang")
                if isinstance(lang_code, str) and lang_code:
                    self.lang.load(lang_code)
                    self.current_language = self.lang.code
            except Exception:
                pass
            try:
                from tooltips import set_tooltip_delay, set_tooltip_wrap

                if "tooltips_delay_ms" in data:
                    set_tooltip_delay(int(data.get("tooltips_delay_ms", 500)))
                if "tooltips_wrap_px" in data:
                    set_tooltip_wrap(int(data.get("tooltips_wrap_px", 420)))
            except Exception:
                pass
            self.url_var.set(data.get("url", ""))
            self.out_var.set(data.get("outdir", ""))
            self.sample_rate_var.set(int(data.get("sr", 44100)))
            self.bitrate_var.set(int(data.get("br", 192)))
            self.embed_meta_var.set(bool(data.get("embed", True)))
            self.archive_var.set(bool(data.get("archive", False)))
            self.include_id_var.set(bool(data.get("include_id", False)))
            self.numbering_var.set(bool(data.get("numbering", True)))
            self.fallback_numbering_var.set(bool(data.get("fallback_numbering", True)))
            self.join_var.set(bool(data.get("join", False)))
            self.join_name_var.set(data.get("join_name", "joined"))
            self.write_cue_var.set(bool(data.get("write_cue", True)))
            self.embed_chapters_var.set(bool(data.get("embed_chapters", True)))
            self.random_join_var.set(bool(data.get("random_join", False)))
            self.sleep_between_var.set(int(data.get("sleep_between", 3)))
            self.detailed_log_var.set(bool(data.get("detailed_log", True)))
            self.rolling_log_var.set(bool(data.get("rolling_log", False)))
            self.verbose_ydl_var.set(bool(data.get("verbose_ydl", False)))
            self.mp3gain_var.set(bool(data.get("mp3gain", True)))
            self.hi_integrity_var.set(bool(data.get("hi_integrity", False)))
            self.keep_temp_var.set(bool(data.get("keep_temp", False)))
            self.playlist_format_var.set(data.get("playlist_format", "M3U8"))
            self.use_run_subdir_var.set(bool(data.get("use_run_subdir", True)))
            self.cookies_file_var.set(data.get("cookies_file", ""))
            self.cookies_browser_var.set(data.get("cookies_browser", "None"))
        except Exception as e:
            self.log(f"Config load failed: {e}")

    def _save_config(self) -> None:
        data = {
            "url": self.url_var.get(),
            "outdir": self.out_var.get(),
            "sr": int(self.sample_rate_var.get()),
            "br": int(self.bitrate_var.get()),
            "embed": bool(self.embed_meta_var.get()),
            "archive": bool(self.archive_var.get()),
            "include_id": bool(self.include_id_var.get()),
            "numbering": bool(self.numbering_var.get()),
            "fallback_numbering": bool(self.fallback_numbering_var.get()),
            "join": bool(self.join_var.get()),
            "join_name": self.join_name_var.get(),
            "write_cue": bool(self.write_cue_var.get()),
            "embed_chapters": bool(self.embed_chapters_var.get()),
            "vlc_segments": bool(self.vlc_segments_var.get()),
            "random_join": bool(self.random_join_var.get()),
            "sleep_between": int(self.sleep_between_var.get()),
            "detailed_log": bool(self.detailed_log_var.get()),
            "rolling_log": bool(self.rolling_log_var.get()),
            "verbose_ydl": bool(self.verbose_ydl_var.get()),
            "mp3gain": bool(self.mp3gain_var.get()),
            "hi_integrity": bool(self.hi_integrity_var.get()),
            "keep_temp": bool(self.keep_temp_var.get()),
            "playlist_format": self.playlist_format_var.get(),
            "use_run_subdir": bool(self.use_run_subdir_var.get()),
            "cookies_file": self.cookies_file_var.get(),
            "cookies_browser": self.cookies_browser_var.get(),
        }
        # Persist language & tooltip settings
        try:
            from tooltips import get_tooltip_settings

            delay_ms, wrap_px = get_tooltip_settings()
        except Exception:
            delay_ms, wrap_px = 500, 420
        try:
            data["lang"] = getattr(
                self,
                "current_language",
                getattr(self, "lang", None).code if hasattr(self, "lang") else "en",
            )
        except Exception:
            data["lang"] = "en"
        data["tooltips_delay_ms"] = int(delay_ms)
        data["tooltips_wrap_px"] = int(wrap_px)
        try:
            self._config_path().write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            self.log(f"Config save failed: {e}")


if __name__ == "__main__":
    App().mainloop()
