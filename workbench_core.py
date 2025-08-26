# workbench_core.py
from __future__ import annotations

"""
Core helpers used by the GUI and tests.

- Tool resolution: resolve_tool_path(), have()
- Subprocess helpers: _run_capture(), run_capture(), run_quiet()
- Cancellation: CANCEL_EVENT, process tracking, terminate_all_procs()
- Cookies: _convert_cookie_editor_json_to_netscape(), prepare_cookies()
- Audio: join_via_wav_then_lame(), write_id3_tags()
- Minimal task runner surface so the GUI can import: ProcessingOptions, run_processing_task()

Everything is written conservatively to satisfy ruff (E,F,I,UP) and Pylance.
"""

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable

import json
import queue
import re
import shutil
import os
import random
import signal
import sys
import subprocess
import threading
import time
import http.cookiejar as _cj

# Global registry of running child processes
_CURRENT_PROCS_LOCK = threading.RLock()
_CURRENT_PROCS: set[subprocess.Popen] = set()


def _register_proc(p: subprocess.Popen) -> None:
    with _CURRENT_PROCS_LOCK:
        _CURRENT_PROCS.add(p)


def _unregister_proc(p: subprocess.Popen) -> None:
    with _CURRENT_PROCS_LOCK:
        _CURRENT_PROCS.discard(p)


# -----------------------
# Import/install helpers
# -----------------------


def ensure_python_package(pkg: str, import_name: str | None = None, log=None) -> bool:
    # Use the provided import name or derive it from the package name
    name = import_name or pkg.replace("-", "_")
    try:
        __import__(name)
        return True
    except ImportError:
        if log:
            log(f"Python package '{pkg}' missing → attempting pip install...")
        try:
            # Use run_quiet which should be defined in your core
            rc = run_quiet([sys.executable, "-m", "pip", "install", "-U", pkg])
            if rc == 0:
                if log:
                    log(f"Installed '{pkg}' successfully.")
                __import__(name)  # Verify import after install
                return True
            else:
                if log:
                    log(f"pip install returned rc={rc} for '{pkg}'")
        except Exception as e:
            if log:
                log(f"pip install failed for '{pkg}': {e}")
    return False


def ensure_mutagen_installed(log) -> bool:
    """Convenience wrapper to check for the 'mutagen' package."""
    return ensure_python_package("mutagen", "mutagen", log=log)


# -----------------------
# Process/cancel plumbing
# -----------------------

CURRENT_PROCS: list[subprocess.Popen] = []
CURRENT_PROCS_LOCK = threading.Lock()
CANCEL_EVENT = threading.Event()


def _spawn_process(cmd: list[str], **kwargs) -> subprocess.Popen:
    """
    Start a child in its own process group to support cross-platform cancellation.
    Always pass an argv list (no shell).
    """
    # Text mode defaults
    kwargs.setdefault("stdin", subprocess.PIPE)
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.PIPE)
    kwargs.setdefault("text", True)

    if os.name == "nt":
        # New process group so we can send CTRL_BREAK_EVENT
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | CREATE_NEW_PROCESS_GROUP
    else:
        # New group; SIGTERM/SIGKILL can be sent to the whole tree
        kwargs.setdefault("preexec_fn", os.setsid)

    p = subprocess.Popen(cmd, **kwargs)  # nosec: trusted argv list
    _register_proc(p)
    return p


def spawn_streaming(cmd: list[str], **kwargs) -> subprocess.Popen:
    """
    Start a long-running command whose stdout/stderr you will read incrementally.
    Use this for yt-dlp streaming in the GUI.
    """
    p = _spawn_process(cmd, **kwargs)
    return p


def finalize_process(p: subprocess.Popen) -> None:
    """Remove a child from the registry after it exits (GUI streaming case)."""
    _unregister_proc(p)


def terminate_all_procs(timeout: float = 3.0) -> None:
    """
    Try graceful shutdown of all registered children, then escalate.
    Safe to call multiple times.
    """
    with _CURRENT_PROCS_LOCK:
        procs = list(_CURRENT_PROCS)

    # 1) Graceful
    for p in procs:
        try:
            if p.poll() is not None:
                continue
            if os.name == "nt":
                p.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                # signal whole group
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass

    # 2) Wait a bit
    deadline = time.time() + max(0.1, timeout)
    for p in procs:
        try:
            if p.poll() is None:
                remaining = deadline - time.time()
                if remaining > 0:
                    p.wait(remaining)
        except Exception:
            pass

    # 3) Hard kill leftovers
    for p in procs:
        try:
            if p.poll() is None:
                if os.name == "nt":
                    p.kill()
                else:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            pass

    # Cleanup registry
    for p in procs:
        _unregister_proc(p)


def _last_lines(s: str, n: int = 12) -> str:
    try:
        return "\n".join(s.splitlines()[-n:])
    except Exception:
        return s


def _run_capture(
    cmd: list[str], *, timeout: float | None = None, check: bool = True, cwd: str | None = None
) -> tuple[int, str, str]:
    """
    Run a command to completion, capturing stdout/stderr with optional timeout.
    Raises CalledProcessError when check=True and rc != 0 (with stderr tail).
    """
    p = _spawn_process(cmd, cwd=cwd)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # escalate on timeout
        try:
            if os.name == "nt":
                p.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            pass
        finally:
            try:
                out, err = p.communicate(timeout=1.0)
            except Exception:
                out, err = "", ""
        rc = p.poll() if p.poll() is not None else -9
    else:
        rc = p.returncode
    finally:
        _unregister_proc(p)

    if check and rc != 0:
        tail = _last_lines(err)
        raise subprocess.CalledProcessError(rc, cmd, output=out, stderr=tail)
    return rc, out, err


def run_quiet(
    cmd: list[str], *, timeout: float | None = None, cwd: str | None = None
) -> tuple[int, str]:
    """
    Run and return (rc, stderr_tail). Keeps last lines of stderr for diagnostics.
    """
    try:
        rc, _out, err = _run_capture(cmd, timeout=timeout, check=False, cwd=cwd)
    except subprocess.CalledProcessError as e:
        # shouldn't happen because check=False above, but just in case
        return e.returncode, _last_lines(e.stderr or "")
    return rc, _last_lines(err or "")


# -----------------------
# Subprocess helpers
# -----------------------


def run_capture(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    text: bool = True,
) -> str:
    """Convenience wrapper returning stdout (raises on non-zero)."""
    rc, out, err = _run_capture(cmd, cwd=cwd, env=env, text=text)
    if rc != 0:
        raise RuntimeError(f"{cmd[0]} exited with {rc}: {(err or out).strip()}")
    return out


# -----------------------
# Tool resolution
# -----------------------


def resolve_tool_path(exe: str) -> str | None:
    """Best-effort cross-platform lookup for external tools."""
    # 1) PATH
    p = shutil.which(exe)
    if p:
        return p
    # 2) Windows common locations
    if os.name == "nt":
        candidates = []
        local = os.environ.get("LOCALAPPDATA", "")
        userprofile = os.environ.get("USERPROFILE", "")
        program_files = os.environ.get("ProgramFiles", "")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "")
        # WinGet shim
        if local:
            candidates.append(os.path.join(local, "Microsoft", "WinGet", "Links", f"{exe}.exe"))
        # Chocolatey shims
        candidates.append(
            os.path.join(
                os.environ.get("ProgramData", "C:\\ProgramData"),
                "chocolatey",
                "bin",
                f"{exe}.exe",
            )
        )
        # Scoop shims
        if userprofile:
            candidates.append(os.path.join(userprofile, "scoop", "shims", f"{exe}.exe"))
        # App-specific installs
        if exe.lower() == "mp3gain":
            if program_files_x86:
                candidates.append(os.path.join(program_files_x86, "MP3Gain", "mp3gain.exe"))
            if program_files:
                candidates.append(os.path.join(program_files, "MP3Gain", "mp3gain.exe"))
        # ffmpeg/ffprobe common dir
        for base in [program_files, program_files_x86]:
            if base:
                candidates.append(os.path.join(base, "FFmpeg", "bin", f"{exe}.exe"))
        for c in candidates:
            if c and os.path.exists(c):
                return c
    # 3) macOS/Homebrew typical
    if sys.platform == "darwin":
        for pth in ["/opt/homebrew/bin", "/usr/local/bin"]:
            cand = os.path.join(pth, exe)
            if os.path.exists(cand):
                return cand
    # 4) Linux common
    for pth in ["/usr/bin", "/usr/local/bin"]:
        cand = os.path.join(pth, exe)
        if os.path.exists(cand):
            return cand
    return None


def have(exe: str) -> bool:
    return resolve_tool_path(exe) is not None


# -----------------------
# Stubs used by GUI (safe no-ops if not used)
# -----------------------


def _ffprobe_duration_seconds(path: Path, log) -> float:
    try:
        out = run_capture(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ]
        )
        d = float(out.strip())
        if d != d or d == float("inf"):
            return 0.0
        return max(0.0, d)
    except Exception as e:
        log(f"ffprobe duration failed: {e}")
        return 0.0


def verify_tools(log: Callable[[str], None] | None = None) -> None:
    """Checks for required tools and logs their status."""
    if not log:
        return

    log("Verifying required tools...")
    tools_to_check = {
        "yt-dlp": True,
        "ffmpeg": True,
        "ffprobe": True,
        "mp3gain": False,  # Optional
    }

    for tool, is_required in tools_to_check.items():
        if have(tool):
            log(f"✅ {tool}: Found")
        else:
            status = "MISSING" if is_required else "Missing (Optional)"
            log(f"❌ {tool}: {status}")


def check_and_install_deps(log: Callable[[str], None] | None = None) -> None:
    """Checks for and attempts to install system dependencies like ffmpeg."""
    if not log:
        return

    app_dir = Path(__file__).resolve().parent
    scripts_dir = app_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    missing = [exe for exe in ("ffmpeg", "ffprobe") if not have(exe)]
    if not have("mp3gain"):
        missing.append("mp3gain (optional)")

    if not missing:
        log("All system dependencies already installed.")
        return
    else:
        log("Missing dependencies: " + ", ".join(missing))

    if sys.platform.startswith("win") and have("winget"):
        log("Attempting to install via WinGet...")
        cmds_to_run = []
        if not have("ffmpeg"):
            cmds_to_run.append(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "Gyan.FFmpeg",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )
        if not have("mp3gain"):
            cmds_to_run.append(
                [
                    "winget",
                    "install",
                    "-e",
                    "--id",
                    "GlenSawyer.MP3Gain",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )
        for c in cmds_to_run:
            try:
                log(f"Running: {' '.join(c)}")
                run_capture(c)
                log(f"Successfully ran install command for {c[4]}.")
            except Exception as e:
                log(f"Install step failed: {e}")
        log("If tools are still not detected, you may need to restart your shell/terminal.")

    # Write helper scripts for manual installation.
    ps1 = scripts_dir / "install_deps.ps1"
    ps1.write_text(
        "winget source update\n"
        "winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements\n"
        "winget install -e --id GlenSawyer.MP3Gain --accept-package-agreements --accept-source-agreements\n",
        encoding="utf-8",
    )
    sh = scripts_dir / "install_deps.sh"
    sh.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "if command -v brew >/dev/null 2>&1; then brew update; brew install ffmpeg mp3gain; exit 0; fi\n"
        "if command -v apt >/dev/null 2>&1; then sudo apt update; sudo apt install -y ffmpeg mp3gain; exit 0; fi\n"
        "if command -v dnf >/dev/null 2>&1; then sudo dnf install -y https://mirrors.rpmfusion.org/free/fedora/"
        "rpmfusion-free-release-$(rpm -E %fedora).noarch.rpm || true; sudo dnf install -y ffmpeg mp3gain; exit 0; fi\n"
        "echo 'No supported package manager detected (checked for brew, apt, dnf). Please install ffmpeg and mp3gain manually.'\n",
        encoding="utf-8",
    )
    try:
        os.chmod(sh, 0o700)
    except Exception:
        pass
    log(f"Wrote helper installation scripts to: {scripts_dir}")


def write_playlist(outdir: Path, files: list[Path], log, name: str, fmt: str) -> None:
    """Write M3U/M3U8 playlists.
    - M3U8: UTF-8, #EXTM3U + #EXTINF:duration,title lines.
    - M3U: latin-1 fallback, simple list of filenames (broadest compatibility).
    """
    fmtU = (fmt or "M3U8").upper()
    try:
        # Collect metadata for EXTINF
        meta = []
        try:
            from mutagen.id3 import ID3

            have_tags = True
        except Exception:
            have_tags = False
        for f in files:
            dur = int(round(_ffprobe_duration_seconds(f, log)))
            title = f.stem
            artist = ""
            if have_tags:
                try:
                    tags = ID3(f)
                    if tags.get("TIT2"):
                        title = str(tags["TIT2"].text[0])
                    if tags.get("TPE1"):
                        artist = str(tags["TPE1"].text[0])
                except Exception:
                    pass
            disp = (
                f"{artist + ' - ' if artist else ''}{title}".replace("\n", " ").lstrip("#").strip()
            )
            meta.append((f.name, dur, disp))

        if fmtU in ("M3U8", "BOTH"):
            pl = outdir / f"{name}.m3u8"
            lines = ["#EXTM3U"]
            for fname, dur, disp in meta:
                lines.append(f"#EXTINF:{dur},{disp}")
                lines.append(fname)
            txt = "\n".join(lines) + "\n"
            pl.write_text(txt, encoding="utf-8")
            log(f"Wrote playlist: {pl.name}")
        if fmtU in ("M3U", "BOTH"):
            pl2 = outdir / f"{name}.m3u"
            body = "\n".join([f.name for f in files]) + "\n"
            try:
                pl2.write_text(body, encoding="latin-1")
            except Exception:
                pl2.write_text(body, encoding="utf-8")
            log(f"Wrote playlist: {pl2.name}")
    except Exception as e:
        log(f"Playlist write failed: {e}")


def write_cue_for_joined(joined_mp3: Path, parts: list[Path], log) -> None:
    try:
        from mutagen.id3 import ID3
    except Exception as e:
        log(f"mutagen not available for CUE metadata: {e}")
        return
    try:
        meta: list[tuple[str, str, float]] = []
        for p in parts:
            title, artist = p.stem, ""
            try:
                tags = ID3(p)
                if tags.get("TIT2"):
                    title = str(tags["TIT2"].text[0])
                if tags.get("TPE1"):
                    artist = str(tags["TPE1"].text[0])
            except Exception:
                pass
            meta.append((title, artist, _ffprobe_duration_seconds(p, log)))
        cue = joined_mp3.with_suffix(".cue")
        lines = []
        lines.append(f'TITLE "{joined_mp3.stem}"')
        if meta and meta[0][1]:
            lines.append(f'PERFORMER "{meta[0][1]}"')
        lines.append(f'FILE "{joined_mp3.name}" MP3')
        fps = 75
        t = 0.0
        for i, (title, artist, dur) in enumerate(meta, start=1):
            frames = int(round(t * fps))
            mm = frames // (60 * fps)
            ss = (frames // fps) % 60
            ff = frames % fps
            lines.append(f"  TRACK {i:02d} AUDIO")
            if artist:
                lines.append(f'    PERFORMER "{artist}"')
            lines.append(f'    TITLE "{title}"')
            lines.append(f"    INDEX 01 {mm:02d}:{ss:02d}:{ff:02d}")
            t += dur
        cue.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log(f"Wrote CUE: {cue.name}")
    except Exception as e:
        log(f"CUE write failed: {e}")


def embed_id3_chapters(joined_mp3: Path, parts: list[Path], log) -> None:
    try:
        from mutagen.id3 import ID3, ID3NoHeaderError, CHAP, CTOC, TIT2, TPE1
    except Exception as e:
        log(f"mutagen not available for chapters: {e}")
        return
    try:
        # audio = MP3(joined_mp3)
        try:
            tags = ID3(joined_mp3)
        except ID3NoHeaderError:
            tags = ID3()

        def _attach(frame, sub):
            if hasattr(frame, "add"):
                try:
                    frame.add(sub)
                    return
                except Exception:
                    pass
            try:
                frame.subframes[sub.HashKey] = [sub]
            except Exception:
                pass

        ids = []
        start_ms = 0
        for idx, p in enumerate(parts, start=1):
            dur = _ffprobe_duration_seconds(p, log)
            end_ms = int(round((start_ms / 1000.0 + dur) * 1000))
            chap = CHAP(
                element_id=f"chp{idx}".encode("ascii"),
                start_time=start_ms,
                end_time=end_ms,
                start_offset=0,
                end_offset=0,
            )
            t_title, t_artist = p.stem, ""
            try:
                src = ID3(p)
                if src.get("TIT2"):
                    t_title = str(src["TIT2"].text[0])
                if src.get("TPE1"):
                    t_artist = str(src["TPE1"].text[0])
            except Exception:
                pass
            _attach(chap, TIT2(encoding=3, text=t_title))
            if t_artist:
                _attach(chap, TPE1(encoding=3, text=t_artist))
            tags.add(chap)
            ids.append(chap.element_id)
            start_ms = end_ms

        toc = CTOC(element_id=b"toc", flags=0x03, child_element_ids=ids)
        _attach(toc, TIT2(encoding=3, text=joined_mp3.stem))
        tags.add(toc)
        tags.save(joined_mp3, v2_version=3)
        log("Embedded ID3 chapters.")
    except Exception as e:
        log(f"Chapter embed failed: {e}")


def write_vlc_segment_playlist(joined_mp3: Path, parts: list[Path], outdir: Path, log) -> None:
    """
    Create a VLC-specific M3U that emulates chapters by repeating the same MP3
    with #EXTVLCOPT:start-time / stop-time per segment.
    """
    try:
        from mutagen.id3 import ID3

        have_tags = True
    except Exception:
        have_tags = False

    lines = ["#EXTM3U"]
    start = 0.0
    for p in parts:
        dur = _ffprobe_duration_seconds(p, log)
        end = start + max(dur, 0.1)
        title = p.stem
        artist = ""
        if have_tags:
            try:
                tags = ID3(p)
                if tags.get("TIT2"):
                    title = str(tags["TIT2"].text[0])
                if tags.get("TPE1"):
                    artist = str(tags["TPE1"].text[0])
            except Exception:
                pass
        disp = f"{artist + ' - ' if artist else ''}{title}".replace("\n", " ").lstrip("#").strip()
        secs = max(1, int(round(end - start)))
        lines.append(f"#EXTINF:{secs},{disp}")
        lines.append(f"#EXTVLCOPT:start-time={int(round(start))}")
        lines.append(f"#EXTVLCOPT:stop-time={int(round(end))}")
        lines.append(joined_mp3.name)
        start = end

    out = outdir / f"{joined_mp3.stem}.vlc-segments.m3u"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"Wrote VLC segment playlist: {out.name}")


def get_album_name(files: list[Path]) -> str:
    # Heuristic: common parent folder name or fallback
    if files:
        return files[0].parent.name or "Album"
    return "Album"


# -----------------------
# Cookies
# -----------------------


def prepare_cookies(
    cookies_file: Path | None,
    cookies_browser: str | None,
    working_dir: Path,
    log: Callable[[str], None] | None = None,
) -> Path | None:
    """
    If a JSON from Cookie-Editor is provided, convert to Netscape text and return that path.
    If a browser name is provided, return None (yt-dlp will use --cookies-from-browser).
    Otherwise, return the original cookies_file.
    """
    if cookies_file and cookies_file.suffix.lower() == ".json":
        out = working_dir / "cookies.txt"
        converted_path = convert_cookie_editor_json_to_netscape(cookies_file, out, log=log)
        return converted_path

    if cookies_browser and cookies_browser.lower() != "none":
        if log:
            log(f"[cookies] using cookies from browser: {cookies_browser}")
        return None

    return cookies_file


# In workbench_core.py


def convert_cookie_editor_json_to_netscape(json_path: Path, out_txt: Path, log) -> Path:
    """Convert Cookie-Editor/EditThisCookie JSON into a Netscape cookies.txt with header."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
        if isinstance(data, dict) and "cookies" in data:
            data = data["cookies"]
        lines = []
        header = "# Netscape HTTP Cookie File\n# This file was generated by YT Audio Workbench from a JSON export.\n"
        for c in data:
            domain = c.get("domain") or c.get("host") or ""
            host_only = bool(c.get("hostOnly")) if "hostOnly" in c else None
            if host_only is True:
                if domain.startswith("."):
                    domain = domain.lstrip(".")
                include_sub = "FALSE"
            elif host_only is False:
                if not domain.startswith("."):
                    domain = "." + domain
                include_sub = "TRUE"
            else:
                include_sub = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path") or "/"
            https = "TRUE" if c.get("secure") else "FALSE"
            exp = c.get("expirationDate") or c.get("expires") or 0
            try:
                exp = int(float(exp))
            except Exception:
                exp = 0
            name = (
                (c.get("name") or "").replace("\t", "%09").replace("\n", "%0A").replace("\r", "%0D")
            )
            value = (
                (c.get("value") or "")
                .replace("\t", "%09")
                .replace("\n", "%0A")
                .replace("\r", "%0D")
            )
            domain_field = ("#HttpOnly_" + domain) if c.get("httpOnly") else domain
            lines.append("\t".join([domain_field, include_sub, path, https, str(exp), name, value]))
        out_txt.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")

        # vvv FIX IS HERE vvv
        if log:
            log(f"Converted JSON cookies -> {out_txt}")
        return out_txt
    except Exception as e:
        # vvv AND FIX IS HERE vvv
        if log:
            log(f"Cookie JSON convert failed: {e}")
        return out_txt


def validate_netscape_cookiefile(path: Path, log) -> tuple[bool, str]:
    """Return (ok, message). If header missing, auto-repair and log it."""
    try:
        jar = _cj.MozillaCookieJar()
        jar.load(str(path), ignore_discard=True, ignore_expires=True)
        return True, f"Loaded {len(jar)} cookies from {path.name}"
    except Exception as e:
        # Try to auto-fix by adding the Netscape header if missing
        try:
            txt = Path(path).read_text(encoding="utf-8", errors="ignore")
            first_nonempty = ""
            for line in txt.splitlines():
                if not line.strip():
                    continue
                first_nonempty = line
                break
            if not first_nonempty.startswith("# Netscape HTTP Cookie File"):
                fixed = Path(path).with_suffix(path.suffix + ".withheader")
                header = "# Netscape HTTP Cookie File\n# Added header by YT Audio Workbench to satisfy validators.\n"
                fixed.write_text(
                    header + (txt if txt.endswith("\n") else txt + "\n"),
                    encoding="utf-8",
                )
                jar2 = _cj.MozillaCookieJar()
                jar2.load(str(fixed), ignore_discard=True, ignore_expires=True)
                log(f"Cookie file missing header → repaired: {fixed.name}")
                return True, f"Loaded {len(jar2)} cookies from {fixed.name}"
        except Exception:
            pass
        return False, f"Cookie file validation failed: {e}"


# -----------------------
# Audio helpers
# -----------------------


def _dedup_artist_in_filenames(files, log):
    """Rename files where filename pattern repeats the artist, e.g.:
    'Artist - Artist - Title.mp3' or '001 - Artist - Artist - Title.mp3' -> single artist once.
    """
    out = []
    pat = re.compile(
        r"^(?:(?P<num>\d+)\s*-\s*)?(?P<a>[^-]+?)\s-\s(?P=a)\s-\s(?P<rest>.+)$",
        re.IGNORECASE,
    )
    for p in files:
        try:
            m = pat.match(p.stem)
            if m:
                prefix = (m.group("num") + " - ") if m.group("num") else ""
                new_stem = f"{prefix}{m.group('a').strip()} - {m.group('rest').strip()}"
                new_path = p.with_name(new_stem + p.suffix)
                if not new_path.exists():
                    os.replace(p, new_path)
                    log(f"Renamed (dedup artist): {p.name} -> {new_path.name}")
                    out.append(new_path)
                    continue
        except Exception:
            pass
        out.append(p)
    return out


def join_via_wav_then_lame(
    files: list[Path],
    outdir: Path,
    sr: int,
    br_kbps: int,
    join_name: str,
    log,
    shuffle: bool = False,
    keep_temp: bool = False,
    progress=None,
) -> Path:
    if shuffle:
        random.shuffle(files)
        log("Join order randomized.")
    tmp_wavs: list[Path] = []
    try:
        total_steps = max(1, len(files) + 2)
        step = 0
        for idx, f in enumerate(files):
            if callable(progress):
                pct = int(((step) / total_steps) * 100)
                progress(pct, f"Joining: decoding {idx + 1}/{len(files)}...")
            wav = outdir / f"._tmp_{f.stem}.wav"
            cmd = ["ffmpeg", "-y", "-i", str(f), "-ar", str(sr), str(wav)]
            rc = run_quiet(cmd)
            if rc != 0:
                raise RuntimeError(f"WAV transcode failed for {f.name}")
            tmp_wavs.append(wav)
            step += 1
        if callable(progress):
            pct = int(((step) / total_steps) * 100)
            progress(pct, "Joining: preparing concat list...")
        listfile = outdir / "._concat_list.txt"
        listfile.write_text("\n".join(f"file '{w.name}'" for w in tmp_wavs), encoding="utf-8")
        if callable(progress):
            progress(int(((step) / total_steps) * 100), "Joining: concatenating...")
        concat_wav = outdir / "._concat.wav"
        rc = run_quiet(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listfile),
                str(concat_wav),
            ]
        )
        if rc != 0:
            raise RuntimeError("WAV concat failed")
        joined = outdir / f"{join_name or 'joined'}.mp3"
        rc = run_quiet(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(concat_wav),
                "-codec:a",
                "libmp3lame",
                "-b:a",
                f"{br_kbps}k",
                str(joined),
            ]
        )
        if rc != 0:
            raise RuntimeError("LAME encode failed")
        return joined
    finally:
        if not keep_temp:
            for p in tmp_wavs:
                try:
                    p.unlink()
                except Exception:
                    pass
            for p in (outdir / "._concat.wav", outdir / "._concat_list.txt"):
                try:
                    p.unlink()
                except Exception:
                    pass


def validate_sample_rates(files: list[Path], expected_sr: int, log) -> None:
    mismatches = []
    for f in files:
        try:
            out = run_capture(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=sample_rate",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(f),
                ]
            )
            sr = int(str(out).strip() or 0)
            if sr and sr != expected_sr:
                mismatches.append((f.name, sr))
        except Exception:
            pass
    if mismatches:
        log("Validation warnings (sample_rate mismatch):")
        for name, sr in mismatches:
            log(f" - {name}: {sr} Hz (expected {expected_sr})")


# -----------------------
# File Tasks
# -----------------------


def _sanitize_filename_component(name: str) -> str:
    """
    Replace characters that commonly break on Windows/shells/old players.
    Keeps readability; collapses runs of separators; trims trailing dots/spaces.
    """
    import re

    # Remove control chars
    name = "".join(ch for ch in name if ch >= " " and ch != "\x7f")
    # Replace reserved / risky chars with hyphen
    name = re.sub(r'[<>:"/\\|?*]', "-", name)  # filesystem reserved
    name = re.sub(r"[&;$'\"()!]", "-", name)  # shell specials
    name = re.sub(r"[\[\]{}#%,]", "-", name)  # playlist/software quirks
    # Collapse whitespace and hyphens
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[-\s]{2,}", " ", name)
    # Strip dangerous trailing chars
    name = name.strip(" .-_")
    # Guard empty
    return name or "untitled"


def _sanitize_and_rename(files: list[Path], log) -> list[Path]:
    out = []
    seen = set()
    for p in files:
        stem = p.stem
        san = _sanitize_filename_component(stem)
        cand = p.with_name(san + p.suffix)
        # Avoid collisions
        i = 1
        while cand.exists() and cand != p:
            cand = p.with_name(f"{san}_{i}{p.suffix}")
            i += 1
        if cand != p:
            try:
                p.rename(cand)
                log(f"Renamed (sanitized): {p.name} -> {cand.name}")
            except Exception as e:
                log(f"Sanitize/rename failed for {p.name}: {e}")
                cand = p
        # Track unique
        if cand.name in seen:
            # append numeric to avoid duplicates within run
            j = 1
            alt = cand.with_name(f"{cand.stem}_{j}{cand.suffix}")
            while alt.exists():
                j += 1
                alt = cand.with_name(f"{cand.stem}_{j}{cand.suffix}")
            try:
                cand.rename(alt)
                log(f"Adjusted duplicate: {cand.name} -> {alt.name}")
                cand = alt
            except Exception:
                pass
        seen.add(cand.name)
        out.append(cand)
    return out


# -----------------------
# Tagging with mutagen (if installed)
# -----------------------


def _parse_artist_title_trackno(path: Path) -> tuple[str | None, str | None, str | None]:
    stem = path.stem
    parts = stem.split(" - ")
    i = 0
    trackno = None
    if parts and parts[0].isdigit():
        trackno = parts[0]
        i = 1
    if len(parts) - i >= 2:
        artist = parts[i].strip()
        title = " - ".join(parts[i + 1 :]).strip()
        return artist or None, title or None, trackno
    return None, stem, trackno


def write_id3_tags_mutagen(files: list[Path], album: str | None, log) -> None:
    if not ensure_mutagen_installed(log):
        log("mutagen not installed; skipping ID3 tagging.")
        return

    from mutagen.id3 import ID3, ID3NoHeaderError, TALB, TIT2, TPE1, TRCK

    for p in files:
        try:
            artist, title, trackno = _parse_artist_title_trackno(p)
            try:
                id3 = ID3(p)
            except ID3NoHeaderError:
                id3 = ID3()
            if title:
                id3.delall("TIT2")
                id3.add(TIT2(encoding=3, text=title))
            if artist:
                id3.delall("TPE1")
                id3.add(TPE1(encoding=3, text=artist))
            if album:
                id3.delall("TALB")
                id3.add(TALB(encoding=3, text=album))
            if trackno:
                id3.delall("TRCK")
                id3.add(TRCK(encoding=3, text=str(trackno)))
            id3.save(p)
            log(f"Tagged: {p.name}  [{artist or '-'} — {title or p.stem}]  (Album: {album or '-'})")
        except Exception as e:
            try:
                log(f"Failed to tag {p.name}: {e}")
            except Exception:
                pass


# -----------------------
# Minimal task runner surface for GUI
# -----------------------


@dataclass
class _ProgressMsg:
    pct: int | None = None
    status: str | None = None


class ProcessingOptions:
    """
    Lightweight, flexible container – accepts any keyword args the GUI passes.
    """

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def run_processing_task(
    options: ProcessingOptions,
    log_queue: queue.Queue[str],
    progress_queue: queue.Queue[dict],
    cancel_event: threading.Event,
) -> None:
    """
    Minimal placeholder so the GUI can run without the full pipeline.
    Emits a couple of progress messages and returns.
    """

    def _log(msg: str) -> None:
        try:
            log_queue.put(msg)
        except Exception:
            pass

    def _progress(pct: int | None, status: str | None) -> None:
        try:
            progress_queue.put({"pct": pct, "status": status})
        except Exception:
            pass

    _log("[core] starting task")
    _progress(0, "Starting")
    if getattr(options, "sleep_between", 0):
        # Honor cancel quickly (no long sleeps)
        if cancel_event.is_set():
            _log("[core] cancelled")
            _progress(None, "Cancelled")
            return
    _progress(100, "Done")
    _log("[core] finished")
