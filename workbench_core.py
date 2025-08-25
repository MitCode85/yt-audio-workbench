from __future__ import annotations
__all__ = ['resolve_tool_path', 'have', 'write_id3_tags', 'prepare_cookies', 'join_via_wav_then_lame', 'get_album_name', '_run_quiet', '_run_capture', 'run_capture', 'run_quiet', 'CANCEL_EVENT', 'CURRENT_PROCS', 'CURRENT_PROCS_LOCK']
"""
Core engine
"""
import os, sys, re, json, time, shutil, threading, subprocess, platform, queue
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

CURRENT_PROCS: list[subprocess.Popen] = []
CURRENT_PROCS_LOCK = threading.Lock()
CANCEL_EVENT = threading.Event()

def run_capture(cmd, cwd: Optional[Path]=None, env: Optional[dict]=None, text: bool=True) -> str:
    p = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=text)
    with CURRENT_PROCS_LOCK:
        CURRENT_PROCS.append(p)
    out, _ = p.communicate()
    rc = p.returncode or 0
    with CURRENT_PROCS_LOCK:
        try: CURRENT_PROCS.remove(p)
        except ValueError: pass
    if rc != 0:
        raise RuntimeError(f"{cmd[0]} exited with {rc}: {out.strip()}")
    return out

def run_quiet(cmd, cwd: Optional[Path]=None, env: Optional[dict]=None) -> int:
    p = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with CURRENT_PROCS_LOCK:
        CURRENT_PROCS.append(p)
    p.wait()
    rc = p.returncode or 0
    with CURRENT_PROCS_LOCK:
        try: CURRENT_PROCS.remove(p)
        except ValueError: pass
    return rc

def terminate_all_procs() -> None:
    with CURRENT_PROCS_LOCK:
        procs = list(CURRENT_PROCS)
    for p in procs:
        try: p.terminate()
        except Exception: pass

def have(exe: str) -> bool:
    return shutil.which(exe) is not None

def resolve_tool_path(exe: str) -> Optional[str]:
    p = shutil.which(exe)
    if p:
        return p
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        candidates = [
            rf"{pf}\ffmpeg\bin\{exe}.exe",
            rf"{pf86}\ffmpeg\bin\{exe}.exe",
            rf"C:\ffmpeg\bin\{exe}.exe",
        ]
        if exe.lower()=="mp3gain":
            candidates += [rf"{pf}\MP3Gain\mp3gain.exe", rf"{pf86}\MP3Gain\mp3gain.exe"]
        for c in candidates:
            if Path(c).exists():
                return c
    return None

def ensure_python_package(pkg: str, import_name: str, *, log=None) -> bool:
    try:
        __import__(import_name)
        return True
    except Exception:
        if log: log(f"Installing Python package '{pkg}'...")
        try:
            rc = run_quiet([sys.executable, "-m", "pip", "install", "-U", pkg])
            if rc == 0:
                if log: log(f"Installed '{pkg}' successfully.")
                __import__(import_name)
                return True
            else:
                if log: log(f"pip install returned rc={rc} for '{pkg}'")
        except Exception as e:
            if log: log(f"pip install failed for '{pkg}': {e}")
        return False

def ensure_mutagen_installed(log) -> bool:
    return ensure_python_package("mutagen", "mutagen", log=log)

def _ffprobe_duration_seconds(path: Path) -> float:
    try:
        out = run_capture(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1", str(path)])
        return float(out.strip())
    except Exception:
        return 0.0

def _sanitize_filename_component(name: str) -> str:
    name = name.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    import re as _re
    name = _re.sub(r"[\/:*?\"<>|]", "-", name)
    name = _re.sub(r"[&;$'\"()!]", "-", name)
    name = _re.sub(r"[\[\]{}#%,]", "-", name)
    name = _re.sub(r"\s+", " ", name)
    name = _re.sub(r"[-\s]{2,}", " ", name)
    name = name.strip(" .-_")
    return name or "untitled"

def _sanitize_and_rename(files: list[Path], log) -> list[Path]:
    out: list[Path] = []
    seen = set()
    for p in files:
        stem = p.stem
        san = _sanitize_filename_component(stem)
        i = 1
        cand = san
        while cand in seen:
            i += 1
            cand = f"{san} ({i})"
        seen.add(cand)
        newp = p.with_stem(cand)
        try:
            p.rename(newp)
        except Exception:
            newp = p
        out.append(newp)
    return out

def _dedup_artist_in_filenames(files: list[Path]) -> None:
    import re as _re
    for p in files:
        t = p.stem.strip()
        m = _re.match(r"^(?P<a>[^-]+) - (?P<t>.+) - (?P=a)$", t)
        if m:
            new = f"{m.group('a').strip()} - {m.group('t').strip()}"
            try: p.rename(p.with_stem(new))
            except Exception: pass

def write_vlc_segment_playlist(files: list[Path], target: Path) -> None:
    lines = ["#EXTM3U"]
    for f in files:
        dur = int(round(_ffprobe_duration_seconds(f)))
        lines.append(f"#EXTINF:{dur},{f.stem}")
        lines.append(str(f.name))
    target.write_text("\n".join(lines), encoding="utf-8")

def convert_cookie_editor_json_to_netscape(json_path: Path, out_path: Path) -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    with out_path.open("w", encoding="utf-8", newline="") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# Generated by YT Audio Workbench\n")
        for c in data:
            domain = c.get("domain") or c.get("host") or ""
            tail = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path") or "/"
            secure = "TRUE" if c.get("secure") else "FALSE"
            expiry = int(c.get("expirationDate", 0)) or 0
            name = c.get("name") or ""
            value = c.get("value") or ""
            f.write(f"{domain}\t{tail}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")

def validate_netscape_cookiefile(path: Path) -> bool:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return txt.startswith("# Netscape HTTP Cookie File")

class YDLLogger:
    def __init__(self, log, verbose: bool=False):
        self.log = log; self.verbose = verbose
    def debug(self, msg): 
        if self.verbose: self.log(str(msg))
    def info(self, msg): 
        self.log(str(msg))
    def warning(self, msg): 
        self.log("[WARN] " + str(msg))
    def error(self, msg): 
        self.log("[ERROR] " + str(msg))

def build_outtmpl(numbering: bool, fallback_numbering: bool, include_id: bool) -> str:
    core = "%(uploader,channel)s - %(title)s"
    prefix = "%(playlist_index,autonumber)03d - " if (numbering or fallback_numbering) else ""
    idsfx = " [%(id)s]" if include_id else ""
    return prefix + core + idsfx + ".%(ext)s"

def get_album_name(url: str, log) -> str | None:
    try:
        ensure_python_package('yt-dlp','yt_dlp', log=log)
        import yt_dlp
        opts = {'quiet': True, 'skip_download': True, 'ignoreerrors': True}
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=False)
        if isinstance(info, dict) and info.get('_type') == 'playlist':
            title = (info.get('title') or '').strip()
            return title or None
        if isinstance(info, dict):
            return (info.get('channel') or info.get('uploader') or '').strip() or None
    except Exception:
        pass
    return None

@dataclass
class ProcessingOptions:
    url: str
    output_dir: Path
    run_sub_dir: Path
    sample_rate: int
    bitrate: int
    use_archive: bool
    numbering: bool
    fallback_numbering: bool
    include_id: bool
    sanitize_filenames: bool
    dedup_artist: bool
    embed_metadata: bool
    write_cue: bool
    embed_chapters: bool
    vlc_segments: bool
    random_join: bool
    keep_temp_wavs: bool
    sleep_between: int
    verbose_ydl: bool
    cookies_file: Optional[Path] = None
    cookies_browser: Optional[str] = None
    playlist_format: Optional[str] = None

def run_processing_task(options: ProcessingOptions,
                        log_queue: "queue.Queue[str]",
                        progress_queue: "queue.Queue[dict]",
                        cancel_event: threading.Event) -> None:
    class _Var:
        def __init__(self, v): self._v = v
        def get(self): return self._v
    class _Ctx:
        def __init__(self):
            self.options = options
            self._log_q = log_queue
            self._progress_q = progress_queue
            self.sample_rate_var = _Var(options.sample_rate)
            self.bitrate_var = _Var(options.bitrate)
            self.sleep_between_var = _Var(options.sleep_between)
            self.archive_var = _Var(options.use_archive)
            self.add_numbering_var = _Var(options.numbering)
            self.fallback_numbering_var = _Var(options.fallback_numbering)
            self.include_id_var = _Var(options.include_id)
            self.sanitize_var = _Var(options.sanitize_filenames)
            self.dedup_artist_var = _Var(options.dedup_artist)
            self.embed_metadata_var = _Var(options.embed_metadata)
            self.write_cue_var = _Var(options.write_cue)
            self.embed_chapters_var = _Var(options.embed_chapters)
            self.vlc_segments_var = _Var(options.vlc_segments)
            self.random_join_var = _Var(options.random_join)
            self.keep_temp_wavs_var = _Var(options.keep_temp_wavs)
            self.verbose_ydl_var = _Var(options.verbose_ydl)
            self.cookies_path_var = _Var(str(options.cookies_file) if options.cookies_file else "")
            self.cookies_browser_var = _Var(options.cookies_browser or "None")
        def log(self, msg: str) -> None:
            try: self._log_q.put(msg)
            except Exception: pass
        def _progress_update(self, overall_pct: int | None = None, status: str | None = None):
            try: self._progress_q.put({"pct": overall_pct, "status": status})
            except Exception: pass
        def _build_outtmpl(self, numbering: bool, fallback_numbering: bool, include_id: bool) -> str:
            return build_outtmpl(numbering, fallback_numbering, include_id)
        def _get_album_name(self, url: str) -> str | None:
            return get_album_name(url, log=self.log)
        def _finish_run(self): pass

    global CANCEL_EVENT
    CANCEL_EVENT = cancel_event
    ctx = _Ctx()

    def _legacy_worker(ctx, url: str, outdir: Path, out_run: Path) -> None:
        start = time.time()
        dl_start_ts = start
        using_subdir = (out_run != outdir)
        pre_existing = set()
        if not using_subdir:
            try:
                pre_existing = {p.name for p in outdir.glob('*.mp3')}
            except Exception:
                pre_existing = set()
        # Ensure yt-dlp (and mutagen) in worker thread
        ensure_python_package('yt-dlp','yt_dlp', log=ctx.log)
        import yt_dlp
        try:
            from yt_dlp.version import __version__ as _ydlv
            ctx.log(f"yt-dlp {_ydlv}")
        except Exception:
            ctx.log(f"yt-dlp {getattr(yt_dlp,'__version__','?')}")

        # tool presence
        for name in ("ffmpeg","ffprobe"):
            ctx.log(f"{name}: {'OK' if have(name) else 'missing'}")
        mp3gain_path = resolve_tool_path("mp3gain")
        ctx.log("mp3gain: " + (f"OK ({mp3gain_path})" if mp3gain_path else "missing (normalization step will be skipped)"))

        numbering = bool(ctx.numbering_var.get())
        include_id = bool(ctx.include_id_var.get())
        tmpl = ctx._build_outtmpl(numbering, bool(ctx.fallback_numbering_var.get()), include_id)
        sr = int(ctx.sample_rate_var.get())
        br = int(ctx.bitrate_var.get())
        sleep_between = int(ctx.sleep_between_var.get())
        use_archive = bool(ctx.archive_var.get())
        verbose = bool(ctx.verbose_ydl_var.get())

        ctx.log(f"Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        album_name = ctx._get_album_name(url)
        ctx.log(f"Python {sys.version.split()[0]} on {platform.system()}")
        ctx.log(f"Options: sr={sr} br={br} numbering={numbering} include_id={include_id} join={ctx.join_var.get()} cue={ctx.write_cue_var.get()} chapters={ctx.embed_chapters_var.get()} verbose={verbose}")

        ydl_opts = {
            "verbose": bool(ctx.verbose_ydl_var.get()),
            "outtmpl": str(out_run / tmpl),
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(br),
            }],
            "postprocessor_args": ["-ar", str(sr)],
            "nopart": True,
            "overwrites": False,
            "sleep_interval": sleep_between,
            "max_sleep_interval": sleep_between,
            "noprogress": True,  # keep GUI progress
            "quiet": False if verbose else True,
            "verbose": bool(verbose),
            "logger": YDLLogger(ctx.log, verbose=bool(verbose)),
            "nocheckcertificate": True,
            "ignoreerrors": True,
        }
        if use_archive:
            ydl_opts["download_archive"] = str(outdir / "download_archive.txt")

        ctx._prepare_cookies(ydl_opts, outdir)

        dl_files: list[Path] = []
        ctx._progress_total = 0
        ctx._progress_done = 0

        def hook(d):
            try:
                if CANCEL_EVENT.is_set():
                    raise yt_dlp.utils.DownloadError("Cancelled by user")
                st = d.get("status")
                info = d.get("info_dict") or {}
                total = info.get("playlist_count") or ctx._progress_total
                if total and total > ctx._progress_total:
                    ctx._progress_total = int(total)
                if st == "downloading":
                    cur = info.get("playlist_index") or ctx._progress_done + 1
                    p = d.get("_percent_str") or ""
                    try:
                        pct_item = float(p.strip().strip("%")) if p else None
                    except Exception:
                        pct_item = None
                    if ctx._progress_total:
                        frac = (ctx._progress_done + (pct_item or 0)/100.0) / ctx._progress_total
                        pct_overall = int(frac * 100)
                    else:
                        pct_overall = int((pct_item or 0) if pct_item is not None else 0)
                    ctx._progress_update(pct_overall, f"Downloading {cur} of {ctx._progress_total or '?'}...")
                elif st == "finished":
                    fn = d.get("filename")
                    if fn:
                        pth = Path(fn)
                        if pth.suffix.lower() == ".mp3":
                            dl_files.append(pth)
                            ctx.log(f"Saved: {pth.name}")
                    ctx._progress_done += 1
                    if ctx._progress_total:
                        pct_overall = int((ctx._progress_done / ctx._progress_total) * 100)
                        ctx._progress_update(pct_overall, f"Post-processing {ctx._progress_done} of {ctx._progress_total}...")
                elif st == "error":
                    ctx._progress_update(None, "Error during download")
            except Exception:
                pass

        ydl_opts["progress_hooks"] = [hook]

        # Download
        try:
            dl_t0 = time.perf_counter()
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as e:
            if str(e).lower().startswith('cancelled'):
                ctx.log('Cancelled.')
                ctx._finish_run()
                return
            else:
                ctx.log(f"yt-dlp failed: {e}")
        except Exception as e:
            ctx.log(f"yt-dlp failed: {e}")

                # Determine downloaded files robustly
        try:
            if out_run != outdir:
                dl_files = sorted([p for p in out_run.glob("*.mp3")], key=lambda x: x.stat().st_mtime)
            else:
                post = list(outdir.glob("*.mp3"))
                dl_files = [p for p in post if p.name not in pre_existing]
                dl_files.sort(key=lambda x: x.stat().st_mtime)
            if dl_files:
                ctx.log(f"Detected {len(dl_files)} MP3 file(s) for post-processing in {'run subfolder' if out_run != outdir else 'output folder'}")
                # Tag MP3s with Artist/Title and Album (playlist)
                try:
                    ctx._write_id3_tags(dl_files, album_name, ctx.log)
                except Exception as _e:
                    ctx.log(f'Tagging step failed: {_e}')
            else:
                ctx.log("No new MP3 files detected.")
        except Exception as e:
            ctx.log(f"Post-detect for MP3s failed: {e}")
        ctx.log(f"Download phase complete. Took {time.perf_counter()-dl_t0:.1f}s")

        if CANCEL_EVENT.is_set():
            ctx.log("Cancelled.")
            ctx._finish_run()
            return

        try:
            validate_sample_rates(dl_files, sr, ctx.log)
        except Exception as e:
            ctx.log(f"SR validate step error: {e}")

        
        # Normalize
        try:
            norm_t0 = time.perf_counter()
            if bool(ctx.dedup_artist_var.get()):
                dl_files = _dedup_artist_in_filenames(dl_files, ctx.log)
            if ctx.mp3gain_var.get() and mp3gain_path:
                norm_errors = 0
                for f in dl_files:
                    try:
                        run_quiet([mp3gain_path, "-r", str(f)])
                    except Exception as e:
                        norm_errors += 1
                        ctx.log(f"mp3gain failed on {f.name}: {e}")
                if norm_errors:
                    ctx.log(f"Normalization finished with {norm_errors} error(s).")
            ctx.log(f"Normalization phase complete. Took {time.perf_counter()-norm_t0:.1f}s")
        except Exception as e:
            try:
                ctx.log(f"Normalization phase failed after {time.perf_counter()-norm_t0:.1f}s: {e}")
            except Exception:
                ctx.log(f"Normalization phase failed: {e}")

        # Join
        joined_path: Path | None = None
        if ctx.join_var.get() and dl_files:
            ctx._progress_update(0, "Joining files...")
            files = dl_files[:]
            
            try:
                join_t0 = time.perf_counter()
                joined_path = join_via_wav_then_lame(
                    files, out_run, sr, br, ctx.join_name_var.get().strip() or "joined",
                    ctx.log, shuffle=bool(ctx.random_join_var.get()), keep_temp=bool(ctx.keep_temp_var.get()),
                    progress=lambda pct, status=None: ctx._progress_update(pct, status)
                )
                ctx.log(f"Joining phase complete. Took {time.perf_counter()-join_t0:.1f}s")
            except Exception as e:
                joined_path = None
                try:
                    ctx.log(f"Joining process failed after {time.perf_counter()-join_t0:.1f}s: {e}")
                except Exception:
                    ctx.log(f"Joining process failed: {e}")
            
            if joined_path:
                try:
                    if ctx.write_cue_var.get():
                        write_cue_for_joined(joined_path, files, ctx.log)
                except Exception as e:
                    ctx.log(f"Post-join artifact error (CUE): {e}")
                try:
                    if ctx.embed_chapters_var.get():
                        try:
                            ensure_mutagen_installed(ctx.log)
                        except Exception:
                            pass
                        embed_id3_chapters(joined_path, files, ctx.log)
                    if ctx.vlc_segments_var.get():
                        write_vlc_segment_playlist(joined_path, files, out_run, ctx.log)
                except Exception as e:
                    ctx.log(f"Post-join artifact error (chapters/segments): {e}")
                if ctx.mp3gain_var.get() and mp3gain_path:
                    try:
                        run_quiet([mp3gain_path,"-r", str(joined_path)])
                    except Exception as e:
                        ctx.log(f"mp3gain on joined file failed: {e}")
            else:
                ctx.log("Skipping post-join artifacts because joining failed or was disabled.")

        # Playlists
        ctx._progress_update(None, "Writing playlist...")
        try:
            if dl_files:
                write_playlist(out_run, dl_files, ctx.log, name="playlist", fmt=ctx.playlist_format_var.get())
        except Exception as e:
            ctx.log(f"Playlist step error: {e}")

        # Write manifest.json
        try:
            manifest = {
                "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(dl_start_ts)),
                "output_folder": str(out_run),
                "using_per_run_subdir": bool(out_run != outdir),
                "files": [p.name for p in dl_files],
                "joined": (str(joined_path.name) if "joined_path" in locals() and joined_path is not None else None),
                "options": {
                    "sr": sr, "br": br, "numbering": bool(ctx.numbering_var.get()),
                    "include_id": bool(ctx.include_id_var.get()),
                    "sleep_between": int(ctx.sleep_between_var.get()),
                    "verbose_ydl": bool(ctx.verbose_ydl_var.get()),
                }
            }
            (out_run / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            ctx.log("Wrote manifest.json")
        except Exception as e:
            ctx.log(f"Manifest write failed: {e}")

        took = time.time() - start
        ctx._progress_update(100, f"Done ({took:.1f}s).")
        ctx.log(f"Done. ({took:.1f}s)")
        ctx._finish_run()

    _legacy_worker(ctx, options.url, options.output_dir, options.run_sub_dir)


def build_yt_dlp_options(outtmpl: str, verbose: bool, cookiefile: str | None=None, cookiesfrombrowser: str | None=None) -> dict:
    opts = {
        "quiet": False,
        "verbose": bool(verbose),
        "outtmpl": outtmpl,
    }
    if cookiefile:
        opts["cookiefile"] = cookiefile
    if cookiesfrombrowser:
        opts["cookiesfrombrowser"] = cookiesfrombrowser
    return opts



def build_cue_sheet(tracks: list[tuple[str, int]], album: str | None, artist: str | None=None) -> str:
    lines = ["REM GENRE Unknown", f"PERFORMER \"{artist or 'Unknown'}\"", f"TITLE \"{album or 'Unknown'}\""]
    total = 0
    for i, (title, secs) in enumerate(tracks, 1):
        mm, ss = divmod(int(total), 60)
        lines.append(f"  TRACK {i:02d} AUDIO")
        lines.append(f"    TITLE \"{title}\"")
        lines.append(f"    INDEX 01 {mm:02d}:{ss:02d}:00")
        total += secs
    return "\n".join(lines)



def verify_tools(log) -> None:
    log("Verifying tools...")
    checks = [
        ("ffmpeg", ["ffmpeg","-version"]),
        ("ffprobe", ["ffprobe","-version"]),
        ("mp3gain", [(resolve_tool_path("mp3gain") or "mp3gain"), "-v"]),
    ]
    import shutil as _sh
    for name, cmd in checks:
        path = (resolve_tool_path(name) if name=="mp3gain" else _sh.which(name))
        if not path:
            log(f"{name}: missing")
            continue
        log(f"{name}: {path}")
        try:
            out = run_capture(cmd)
            first = out.splitlines()[0] if out.strip() else "(no output)"
            log(f"{name}: OK — {first}")
        except Exception as e:
            log(f"{name}: present but failed to run: {e}")
    log("Verify complete.")



def check_and_install_deps(log) -> None:
    import sys as _sys, shutil as _sh
    app_dir = Path(__file__).resolve().parent
    scripts_dir = app_dir / "scripts"; scripts_dir.mkdir(exist_ok=True)
    missing = [exe for exe in ("ffmpeg","ffprobe") if not _sh.which(exe)]
    mp3gain_missing = (resolve_tool_path("mp3gain") is None)
    if mp3gain_missing: missing.append("mp3gain")
    if not missing:
        log("All dependencies already installed.")
    else:
        log("Missing: " + ", ".join(missing))

    if _sys.platform.startswith("win") and _sh.which("winget"):
        log("Using WinGet to check/install...")
        def _winget_is_installed(pkg_id: str) -> bool:
            try:
                out = run_capture(["winget","list","--id", pkg_id])
                return pkg_id.lower() in out.lower()
            except Exception:
                return False
        need_ffmpeg = not _winget_is_installed("Gyan.FFmpeg")
        need_mp3gain = mp3gain_missing and not _winget_is_installed("GlenSawyer.MP3Gain")
        cmds = []
        if need_ffmpeg:
            cmds.append(["winget","install","-e","--id","Gyan.FFmpeg","--accept-package-agreements","--accept-source-agreements"])
        if need_mp3gain:
            cmds.append(["winget","install","-e","--id","GlenSawyer.MP3Gain","--accept-package-agreements","--accept-source-agreements"])
        if not cmds:
            log("Winget reports ffmpeg/mp3gain already installed.")
        for c in cmds:
            try:
                log("Running: " + " ".join(c))
                out = run_capture(c)
                first = out.splitlines()[0] if out.strip() else "(no output)"
                log(f"OK: {first}")
            except Exception as e:
                log(f"Install step failed: {' '.join(c)} :: {e}")
        log("If tools are still not detected, restart your shell to refresh PATH.")
    else:
        log("Automatic install only supported on Windows with winget. Please install ffmpeg and mp3gain manually.")

    # Write helper scripts (idempotent)
    ps1 = scripts_dir / "install_deps.ps1"
    ps1.write_text("winget install -e --id Gyan.FFmpeg\nwinget install -e --id GlenSawyer.MP3Gain\n", encoding="utf-8")
    sh = scripts_dir / "install_deps.sh"
    sh.write_text("#!/usr/bin/env bash\n# install ffmpeg/mp3gain via your package manager\n", encoding="utf-8")


# ---- Added by refactor ----

import os, shutil, sys, subprocess, json, tempfile, shlex
from pathlib import Path
from typing import Callable, Optional

def resolve_tool_path(cmd: str) -> str | None:
    """Cross-platform resolution of external tools; prefers PATH, then common install locations."""
    p = shutil.which(cmd)
    if p:
        return p

    if os.name == "nt":
        candidates = []
        local = os.environ.get("LOCALAPPDATA","")
        userprofile = os.environ.get("USERPROFILE","")
        program_files = os.environ.get("ProgramFiles","")
        program_files_x86 = os.environ.get("ProgramFiles(x86)","")
        program_data = os.environ.get("ProgramData","C:\\ProgramData")
        if local:
            candidates.append(os.path.join(local, "Microsoft", "WinGet", "Links", f"{cmd}.exe"))
        candidates.append(os.path.join(program_data, "chocolatey", "bin", f"{cmd}.exe"))
        if userprofile:
            candidates.append(os.path.join(userprofile, "scoop", "shims", f"{cmd}.exe"))
        if cmd.lower() == "mp3gain":
            if program_files_x86:
                candidates.append(os.path.join(program_files_x86, "MP3Gain", "mp3gain.exe"))
            if program_files:
                candidates.append(os.path.join(program_files, "MP3Gain", "mp3gain.exe"))
        for base in [program_files, program_files_x86]:
            if base:
                candidates.append(os.path.join(base, "FFmpeg", "bin", f"{cmd}.exe"))
        for c in candidates:
            if c and os.path.exists(c):
                return c

    if sys.platform == "darwin":
        for pth in ("/opt/homebrew/bin","/usr/local/bin"):
            cand = os.path.join(pth, cmd)
            if os.path.exists(cand):
                return cand

    for pth in ("/usr/bin","/usr/local/bin"):
        cand = os.path.join(pth, cmd)
        if os.path.exists(cand):
            return cand
    return None

def have(cmd: str) -> bool:
    return resolve_tool_path(cmd) is not None


def _run_quiet(args: list[str], cwd: Path | None = None) -> int:
    try:
        proc = subprocess.run(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return int(proc.returncode or 0)
    except Exception:
        return 1

def _run_capture(args: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
        return int(proc.returncode or 0), proc.stdout, proc.stderr
    except Exception as e:
        return 1, "", str(e)


def write_id3_tags(mp3: Path, tags: dict[str, str], log: Optional[Callable[[str], None]] = None) -> bool:
    """Write ID3 tags via ffmpeg stream copy; robust and dependency-light."""
    ffmpeg = resolve_tool_path("ffmpeg")
    if not ffmpeg:
        if log: log("[id3] ffmpeg not found; cannot write tags.")
        return False
    meta_args: list[str] = []
    for k, v in (tags or {}).items():
        if v is None:
            continue
        meta_args += ["-metadata", f"{k}={v}"]
    tmp = mp3.with_suffix(".tmp.mp3")
    rc, out, err = _run_capture([ffmpeg, "-y", "-i", str(mp3), *meta_args, "-codec", "copy", str(tmp)])
    if rc != 0:
        if log: log(f"[id3] ffmpeg failed: {err.strip() or out.strip()}")
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        return False
    try:
        tmp.replace(mp3)
        return True
    except Exception as e:
        if log: log(f"[id3] replace failed: {e}")
        return False


def _convert_cookie_editor_json_to_netscape(src_json: Path, dst_txt: Path, log: Optional[Callable[[str], None]] = None) -> bool:
    try:
        data = json.loads(src_json.read_text(encoding="utf-8", errors="ignore"))
    except Exception as e:
        if log: log(f"[cookies] JSON parse failed: {e}")
        return False
    cookies = data.get("cookies") if isinstance(data, dict) else data
    if not isinstance(cookies, list):
        if log: log("[cookies] Unexpected JSON structure.")
        return False
    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        try:
            domain = c.get("domain") or ""
            include_sub = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path") or "/"
            secure = "TRUE" if c.get("secure") else "FALSE"
            expires = int(c.get("expirationDate") or c.get("expires") or 0)
            name = c.get("name") or ""
            value = c.get("value") or ""
            lines.append("\t".join([domain, include_sub, path, secure, str(expires), name, value]))
        except Exception:
            continue
    try:
        dst_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception as e:
        if log: log(f"[cookies] write failed: {e}")
        return False

def prepare_cookies(cookies_file: Path | None, cookies_browser: str | None, working_dir: Path, log: Optional[Callable[[str], None]] = None) -> Path | None:
    """Return Netscape cookies path if conversion was needed; else original; None when browser mode is used."""
    if cookies_file and cookies_file.exists():
        try:
            raw = cookies_file.read_text(encoding="utf-8", errors="ignore").lstrip()
            is_json = raw.startswith("{") or raw.startswith("[")
        except Exception:
            is_json = False
        if is_json:
            out = working_dir / "cookies.txt"
            if _convert_cookie_editor_json_to_netscape(cookies_file, out, log=log):
                if log: log(f"[cookies] Converted Cookie-Editor JSON → Netscape: {out}")
                return out
        return cookies_file
    if cookies_browser and cookies_browser.lower() != "none":
        if log: log(f"[cookies] Using browser cookies: {cookies_browser}")
        return None
    return None


def join_via_wav_then_lame(wav_files: list[Path], output_mp3: Path, lame_bitrate_kbps: int, log: Optional[Callable[[str], None]] = None) -> bool:
    """Concat WAVs with ffmpeg then encode with lame (CBR)."""
    ffmpeg = resolve_tool_path("ffmpeg")
    lame = resolve_tool_path("lame")
    if not ffmpeg or not lame:
        if log: log("[join] Missing ffmpeg or lame.")
        return False
    try:
        listfile = output_mp3.with_suffix(".concat.txt")
        listfile.write_text("".join(f"file '{w.as_posix()}'\\n" for w in wav_files), encoding="utf-8")
        big_wav = output_mp3.with_suffix(".joined.wav")
        rc1, so1, se1 = _run_capture([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(big_wav)])
        if rc1 != 0:
            if log: log(f"[join] ffmpeg concat failed: {se1.strip() or so1.strip()}")
            return False
        rc2, so2, se2 = _run_capture([lame, "-b", str(int(lame_bitrate_kbps)), str(big_wav), str(output_mp3)])
        if rc2 != 0:
            if log: log(f"[join] lame encode failed: {se2.strip() or so2.strip()}")
            return False
        try:
            listfile.unlink(missing_ok=True); big_wav.unlink(missing_ok=True)
        except Exception:
            pass
        return True
    except Exception as e:
        if log: log(f"[join] exception: {e}")
        return False

