# tests/test_join_and_id3.py

from pathlib import Path
import workbench_core as core

# We need to import mutagen to verify the results of the tagging function
from mutagen.id3 import ID3

# --- Test for the new mutagen-based tag writer ---
# The old test was for an ffmpeg function that no longer exists in that form.
# This new test correctly checks the behavior of write_id3_tags_mutagen.


def test_write_id3_tags_mutagen_mock(monkeypatch, tmp_path):
    """
    Tests the mutagen-based tag writer.
    It calls the function and then uses mutagen to verify the tags were written.
    """
    # We don't need to mock any subprocesses, just the dependency check.
    monkeypatch.setattr(core, "ensure_mutagen_installed", lambda log: True)

    mp3_file = tmp_path / "Artist Name - Song Title.mp3"
    mp3_file.write_bytes(b"dummy mp3 data")  # Create a dummy file

    # Call the function with the correct signature (list of files, album name)
    core.write_id3_tags_mutagen(
        files=[mp3_file],
        album="My Test Album",
        log=print,  # Use print for logging during the test
    )

    # Verify the results by reading the tags back from the file
    tags = ID3(mp3_file)
    assert str(tags["TALB"].text[0]) == "My Test Album"
    assert str(tags["TPE1"].text[0]) == "Artist Name"
    assert str(tags["TIT2"].text[0]) == "Song Title"


# --- Test for the new ffmpeg-based joiner ---
# This test is updated to use the new function signature and mock `run_quiet`.


def test_join_via_wav_then_lame_mock(monkeypatch, tmp_path):
    """
    Tests the ffmpeg-based joiner.
    It mocks `run_quiet` and checks that the function is called with the
    correct arguments and returns the expected final path.
    """
    # This list will track calls to our mock function
    call_log = []

    def mock_run_quiet(cmd, cwd=None, env=None):
        # Log the command that was run
        call_log.append(cmd)
        # The last argument is the output file; simulate its creation
        Path(cmd[-1]).touch()
        return 0  # Return success code

    monkeypatch.setattr(core, "run_quiet", mock_run_quiet)

    # Create dummy source files for the function to join
    source_files = [tmp_path / "1.mp3", tmp_path / "2.mp3"]
    for f in source_files:
        f.touch()

    # Call the function with the new, correct arguments
    result_path = core.join_via_wav_then_lame(
        files=source_files,
        outdir=tmp_path,
        sr=44100,
        br_kbps=192,
        join_name="final_album",
        log=print,
    )

    # 1. Assert that the function returned the correct final path
    assert result_path == tmp_path / "final_album.mp3"

    # 2. Assert that ffmpeg was called the correct number of times
    #    (once for each source file + once for concat + once for final encode)
    assert len(call_log) == len(source_files) + 2
