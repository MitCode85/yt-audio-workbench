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
import shutil
import subprocess
import threading


# -----------------------
# Process/cancel plumbing
# -----------------------

CURRENT_PROCS: list[subprocess.Popen] = []
CURRENT_PROCS_LOCK = threading.Lock()
CANCEL_EVENT = threading.Event()


def _register_proc(p: subprocess.Popen) -> None:
    with CURRENT_PROCS_LOCK:
        CURRENT_PROCS.append(p)


def _unregister_proc(p: subprocess.Popen) -> None:
    with CURRENT_PROCS_LOCK:
        try:
            CURRENT_PROCS.remove(p)
        except ValueError:
            pass


def terminate_all_procs() -> None:
    with CURRENT_PROCS_LOCK:
        to_kill = list(CURRENT_PROCS)
    for p in to_kill:
        try:
            p.terminate()
        except Exception:
            pass


# -----------------------
# Subprocess helpers
# -----------------------


def _run_capture(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    text: bool = True,
) -> tuple[int, str, str]:
    """Run a command; return (rc, stdout, stderr). Tests monkeypatch this."""
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    _register_proc(p)
    try:
        out, err = p.communicate()
        rc = p.returncode or 0
        return rc, out or "", err or ""
    finally:
        _unregister_proc(p)


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


def run_quiet(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> int:
    """Run without capturing output; return rc."""
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _register_proc(p)
    try:
        p.wait()
        return p.returncode or 0
    finally:
        _unregister_proc(p)


# -----------------------
# Tool resolution
# -----------------------


def resolve_tool_path(exe: str) -> str | None:
    """Best-effort cross-platform lookup for external tools."""
    p = shutil.which(exe)
    if p:
        return p

    # A few common fallbacks (do not import platform to avoid F401 if unused)
    candidates: list[Path] = []

    # Windows common installs
    program_files = Path("C:/Program Files")
    program_files_x86 = Path("C:/Program Files (x86)")
    candidates += [
        program_files / "FFmpeg" / "bin" / f"{exe}.exe",
        program_files_x86 / "FFmpeg" / "bin" / f"{exe}.exe",
    ]

    # Homebrew on macOS / Linux user installs
    candidates += [
        Path("/opt/homebrew/bin") / exe,
        Path("/usr/local/bin") / exe,
        Path("/usr/bin") / exe,
        Path("/snap/bin") / exe,
    ]

    for c in candidates:
        try:
            if c.exists():
                return str(c)
        except Exception:
            pass
    return None


def have(exe: str) -> bool:
    return resolve_tool_path(exe) is not None


# -----------------------
# Stubs used by GUI (safe no-ops if not used)
# -----------------------


def verify_tools() -> None:
    # Lightweight check; GUI mainly calls this to prompt/log.
    _ = [have(n) for n in ("yt-dlp", "ffmpeg", "ffprobe", "mp3gain")]


def check_and_install_deps(log: Callable[[str], None] | None = None) -> None:
    if log:
        log("Automatic dependency installation is not implemented in this build.")


def validate_sample_rates(
    _files: list[Path], _sr: int, _log: Callable[[str], None] | None = None
) -> None:
    return


def write_cue_for_joined(
    _joined_mp3: Path,
    _parts: list[Path],
    _log: Callable[[str], None] | None = None,
) -> None:
    return


def embed_id3_chapters(
    _joined_mp3: Path,
    _parts: list[Path],
    _log: Callable[[str], None] | None = None,
) -> None:
    return


def write_vlc_segment_playlist(
    _joined_mp3: Path,
    _parts: list[Path],
    _out_dir: Path,
    _log: Callable[[str], None] | None = None,
) -> None:
    return


def write_playlist(
    _out_dir: Path,
    _files: list[Path],
    _log: Callable[[str], None] | None = None,
    name: str = "playlist",
    fmt: str | None = None,
) -> None:
    # Minimal m3u writer if asked
    if fmt is None:
        return
    fmt_up = fmt.upper()
    if fmt_up not in {"M3U", "M3U8", "BOTH"}:
        return
    targets: list[str] = []
    if fmt_up in {"M3U", "BOTH"}:
        targets.append(f"{name}.m3u")
    if fmt_up in {"M3U8", "BOTH"}:
        targets.append(f"{name}.m3u8")
    for t in targets:
        try:
            p = _out_dir / t
            lines = [str(f.name) for f in _files]
            p.write_text("\n".join(lines), encoding="utf-8", errors="ignore")
            if _log:
                _log(f"[playlist] wrote {p.name}")
        except Exception as e:
            if _log:
                _log(f"[playlist] write failed: {e}")


def get_album_name(files: list[Path]) -> str:
    # Heuristic: common parent folder name or fallback
    if files:
        return files[0].parent.name or "Album"
    return "Album"


# -----------------------
# Cookies
# -----------------------


def _convert_cookie_editor_json_to_netscape(
    src_json: Path,
    dst_txt: Path,
    log: Callable[[str], None] | None = None,
) -> bool:
    """
    Convert Cookie-Editor JSON (array of cookie dicts) to Netscape format.
    """
    try:
        data = json.loads(src_json.read_text(encoding="utf-8", errors="ignore"))
    except Exception as e:
        if log:
            log(f"[cookies] JSON parse failed: {e}")
        return False

    cookies = data.get("cookies") if isinstance(data, dict) else data
    if not isinstance(cookies, list):
        if log:
            log("[cookies] Unexpected JSON structure.")
        return False

    lines = ["# Netscape HTTP Cookie File"]
    for c in cookies:
        try:
            domain = str(c.get("domain", ""))
            if not domain:
                continue
            # hostOnly determines initial dot and include_sub
            host_only = c.get("hostOnly")
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

            path = str(c.get("path", "/") or "/")
            secure = "TRUE" if c.get("secure") else "FALSE"
            # expiry: use "0" if missing
            expiry = str(c.get("expirationDate") or c.get("expires") or "0")
            name = str(c.get("name", ""))
            value = str(c.get("value", ""))
            lines.append("\t".join([domain, include_sub, path, secure, expiry, name, value]))
        except Exception:
            # skip malformed entry
            continue

    try:
        dst_txt.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="ignore")
        if log:
            log(f"[cookies] wrote Netscape cookie file: {dst_txt}")
        return True
    except Exception as e:
        if log:
            log(f"[cookies] write failed: {e}")
        return False


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
        ok = _convert_cookie_editor_json_to_netscape(cookies_file, out, log=log)
        if ok:
            return out
        return cookies_file

    if cookies_browser and cookies_browser.lower() != "none":
        if log:
            log(f"[cookies] using cookies from browser: {cookies_browser}")
        return None

    return cookies_file


# -----------------------
# Audio helpers
# -----------------------


def write_id3_tags(
    mp3: Path,
    tags: dict[str, str],
    log: Callable[[str], None] | None = None,
) -> bool:
    """
    Write ID3 tags with ffmpeg stream copy to avoid re-encode.
    Requires ffmpeg in PATH (or resolvable).
    """
    ffmpeg = resolve_tool_path("ffmpeg")
    if not ffmpeg:
        if log:
            log("[id3] ffmpeg not found; cannot write tags.")
        return False

    meta_args: list[str] = []
    for k, v in tags.items():
        # Map a few common keys to ID3-friendly keys; otherwise pass through
        key = k
        if k.lower() == "title":
            key = "title"
        elif k.lower() == "artist":
            key = "artist"
        elif k.lower() == "album":
            key = "album"
        meta_args.extend(["-metadata", f"{key}={v}"])

    tmp = mp3.with_suffix(".tmp.id3.mp3")
    rc, out, err = _run_capture(
        [ffmpeg, "-y", "-i", str(mp3), *meta_args, "-codec", "copy", str(tmp)]
    )
    if rc != 0:
        if log:
            log(f"[id3] ffmpeg failed: {(err or out).strip()}")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False

    try:
        tmp.replace(mp3)
        if log:
            log("[id3] tags written.")
        return True
    except Exception as e:
        if log:
            log(f"[id3] replace failed: {e}")
        return False


def join_via_wav_then_lame(
    wav_files: list[Path],
    output_mp3: Path,
    lame_bitrate_kbps: int,
    log: Callable[[str], None] | None = None,
) -> bool:
    """
    Concat WAVs via ffmpeg and encode with lame (CBR). Used by tests.
    """
    ffmpeg = resolve_tool_path("ffmpeg")
    lame = resolve_tool_path("lame")
    if not ffmpeg or not lame:
        if log:
            log("[join] missing ffmpeg or lame.")
        return False

    try:
        listfile = output_mp3.with_suffix(".concat_list.txt")
        big_wav = output_mp3.with_suffix(".joined.wav")
        list_lines = []
        for p in wav_files:
            # Perform the replacement outside the f-string
            safe_path = str(p).replace("'", "'\\''")
            list_lines.append(f"file '{safe_path}'")
        listfile.write_text("\n".join(list_lines) + "\n", encoding="utf-8", errors="ignore")

        rc1, so1, se1 = _run_capture(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(listfile),
                "-c",
                "copy",
                str(big_wav),
            ]
        )
        if rc1 != 0:
            if log:
                log(f"[join] ffmpeg concat failed: {(se1 or so1).strip()}")
            return False

        rc2, so2, se2 = _run_capture(
            [lame, "-b", str(int(lame_bitrate_kbps)), str(big_wav), str(output_mp3)]
        )
        if rc2 != 0:
            if log:
                log(f"[join] lame encode failed: {(se2 or so2).strip()}")
            return False

        try:
            listfile.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            big_wav.unlink(missing_ok=True)
        except Exception:
            pass

        if log:
            log(f"[join] wrote {output_mp3.name}")
        return True

    except Exception as e:
        if log:
            log(f"[join] exception: {e}")
        return False


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
