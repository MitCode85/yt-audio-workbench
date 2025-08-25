
from pathlib import Path
import workbench_core as core

def test_write_id3_tags_mock(monkeypatch, tmp_path):
    # Pretend ffmpeg exists and _run_capture succeeds
    monkeypatch.setattr(core, "resolve_tool_path", lambda cmd: "/bin/ffmpeg" if cmd=="ffmpeg" else None)
    def ok_run(args, cwd=None):
        # Simulate ffmpeg writing tmp file
        out = Path(args[-1])
        out.write_bytes(b"dummy")
        return 0, "ok", ""
    monkeypatch.setattr(core, "_run_capture", ok_run)
    mp3 = tmp_path/"a.mp3"
    mp3.write_bytes(b"src")
    assert core.write_id3_tags(mp3, {"artist":"X"}, log=None) is True

def test_join_via_wav_then_lame_mock(monkeypatch, tmp_path):
    # Pretend tools exist and run capture OK twice
    monkeypatch.setattr(core, "resolve_tool_path", lambda cmd: "/bin/"+cmd)
    seq = {"calls":0}
    def ok_run(args, cwd=None):
        seq["calls"] += 1
        # On second run we expect output MP3 path at the end
        return 0, "ok", ""
    monkeypatch.setattr(core, "_run_capture", ok_run)
    wavs = [tmp_path/"1.wav", tmp_path/"2.wav"]
    for w in wavs: w.write_bytes(b"w")
    out = tmp_path/"joined.mp3"
    assert core.join_via_wav_then_lame(wavs, out, lame_bitrate_kbps=192, log=None) is True
    assert seq["calls"] >= 2
