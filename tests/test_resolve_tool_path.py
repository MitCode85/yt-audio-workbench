import builtins
import types
import shutil
import workbench_core as core


def test_have_uses_resolver(monkeypatch):
    # Simulate finding a tool via shutil.which
    monkeypatch.setattr(
        core, "resolve_tool_path", lambda cmd: "C:/Tools/" + cmd if cmd == "ffmpeg" else None
    )
    assert core.have("ffmpeg") is True
    assert core.have("notarealtool") is False


def test_resolve_prefers_path(monkeypatch, tmp_path):
    called = {"which": 0}

    def fake_which(cmd):
        called["which"] += 1
        if cmd == "yt-dlp":
            return "/usr/local/bin/yt-dlp"
        return None

    monkeypatch.setattr(shutil, "which", fake_which)
    # We don't assert OS-specific branches; just ensure PATH hit is respected
    assert core.resolve_tool_path("yt-dlp") == "/usr/local/bin/yt-dlp"
    assert called["which"] >= 1
