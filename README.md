# YT-Audio-Workbench

> Reliability-first, cross-platform (Windows/macOS/Linux) Python GUI for yt-dlp + FFmpeg with optional MP3Gain. Turn YouTube videos & playlists into high-quality MP3 with proper ID3 tags, loudness normalization (ReplayGain), playlist/CUE options, robust tool checks, and multilingual support (i18n: EN/FR) support.

## Features
- **Reliability-first pipeline**: robust tool checks, clear error messages, cancellable jobs, logs.
- **Core/GUI split**: `workbench_core.py` (engine) + `yt_audio_backup_gui.py` (UI).
- **yt-dlp + FFmpeg + (optional) MP3Gain**: downloads, converts, tags, and normalizes.
- **High-quality MP3 output**: proper ID3 tags; ReplayGain/MP3Gain loudness normalization.
- **Playlists**: build playlist files / album joins; optional CUE/chapters.
- **Multilingual (i18n)**: language files in `lang/` (EN + FR); in-app language switch.
- **Tooltips everywhere**: direct, translatable tips for all key widgets; configurable delay/wrap.
- **Help & About**: localized dialogs, centered windows, diagnostics copy.

## Install
Requirements:
- Python 3.10+ (3.11 recommended)
- Tools: `yt-dlp`, `ffmpeg` (and optionally `mp3gain`)

Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt  # if present; otherwise no external deps required
```

Install tools (any of):
- **WinGet**: `winget install Gyan.FFmpeg` and `winget install yt-dlp.yt-dlp`
- **Chocolatey**: `choco install ffmpeg yt-dlp`
- **Scoop**: `scoop install ffmpeg yt-dlp`
- **MP3Gain** (optional): `choco install mp3gain` or download official installer

macOS:
```bash
brew install ffmpeg yt-dlp mp3gain
```

Linux (Debian/Ubuntu):
```bash
sudo apt install ffmpeg
pipx install yt-dlp   # or apt/ytdlp from your distro
sudo apt install mp3gain  # optional
```

## Run
```bash
python yt_audio_backup_gui.py
```

## Build (Windows)
PyInstaller spec included:
```powershell
pip install pyinstaller
pyinstaller -y yt_audio_workbench.spec
# Output -> dist\YT-Audio-Workbench\YT-Audio-Workbench.exe
```

## Internationalization
Language files live in `lang/*.json`. Add a locale file (e.g., `lang/de.json`), then restart or switch in the **Help → Language** submenu. Tooltips and dialogs resolve text from the active language file.

## Configuration
The app persists language and tooltip preferences. You can also tweak tooltip delay/wrap in settings (Help → Tooltips).

## Help
See **HELP.md** (also available in-app: Help → Open Help). About dialog provides diagnostics copy and a one-click Troubleshooting section link.

## License
MIT (see LICENSE). Note that FFmpeg, yt-dlp, and MP3Gain have their own licenses.

## Contributing
PRs welcome! Please run tests:
```bash
pip install pytest
pytest -q
```
