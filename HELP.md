# YT Audio Workbench — Help
Welcome to the help documentation for YT Audio Workbench. This guide will walk you through the main features and options available in the application.

## Table of Contents
- [Getting Started](#getting-started)
- [Main Window Explained](#main-window-explained)
  - [URL & Output](#url--output)
  - [Cookies](#cookies)
  - [Download & Formatting](#download--formatting)
  - [Filename & Options](#filename--options)
  - [Joining](#joining)
  - [System Dependencies](#system-dependencies)
  - [Controls & Log](#controls--log)
- [Troubleshooting](#troubleshooting)
  - [Tool Not Found (ffmpeg, mp3gain)](#tool-not-found-ffmpeg-mp3gain)
  - [Downloads are Slow or Failing](#downloads-are-slow-or-failing)
  - [Private/Members-Only Videos Not Working](#privatevideos)

## Getting Started <a name="getting-started"></a>
The primary purpose of this tool is to create high-quality, consistent MP3 backups from a YouTube URL (either a single video or a playlist).

**Basic Workflow:**
1. Paste a YouTube URL into the top field.
2. Select an Output folder where the files will be saved.
3. Choose your desired Bitrate and Sample Rate.
4. Click Run.

## Main Window Explained <a name="main-window-explained"></a>

### URL & Output <a name="url--output"></a>
**Playlist or video URL:** The source URL from YouTube.  
**Output folder:** The main directory where all files and logs will be saved.  
**Use per-run subfolder:** (Recommended) When checked, each time you click "Run", a new subfolder with a timestamp (e.g., `run_20250824_193000`) will be created inside your output folder. This is the safest way to keep download sessions separate and ensures the "Join" feature works correctly.

### Cookies <a name="cookies"></a>
**Cookies file:** You can provide a `cookies.txt` (Netscape format) or a `.json` file exported from a browser extension like "Cookie-Editor". The application will automatically convert `.json` files.  
**Use browser cookies:** Alternatively, select a browser and the application will attempt to use its live cookie data.

### Download & Formatting <a name="download--formatting"></a>
**Sample rate:** Enforces a consistent audio sample rate for all files. `44100 Hz` is standard for CD quality, while `48000 Hz` is common for video.  
**Bitrate (kbps):** Sets the quality of the MP3 file. `192` is good quality, `320` is the highest quality for MP3.  
**Delay between items (s):** A pause between downloading each item in a playlist to avoid being rate-limited by the server.  
**Playlist format:** Creates a playlist file (`.m3u` or `.m3u8`) of the downloaded tracks for easy playback.

### Filename & Options <a name="filename--options"></a>
**Add numbering:** Prefixes filenames with a number (e.g., `001 - ...`, `002 - ...`).  
**Include YouTube ID in filename:** Appends the unique YouTube video ID in brackets (e.g., `... [dQw4w9WgXcQ].mp3`). *Note:* Brackets can cause issues with some older media players.  
**Sanitize filenames:** (Recommended) Removes special characters from filenames that can cause problems with playlists or scripts.  
**Use download archive:** The app will keep a record of downloaded files in `download_archive.txt`. If you run the same playlist again, it will skip any files it has already downloaded.  
**Normalize with MP3Gain:** Uses the mp3gain tool to adjust the volume of all tracks to a standard level without losing quality.  
**De-duplicate artist in filename:** Removes duplicated artist names from filenames (e.g., `Artist - Artist - Title` → `Artist - Title`).  
**Validate with ffprobe:** Validates sample rate/format using `ffprobe` after conversion.  
**Verbose yt-dlp logging:** Runs yt-dlp in verbose mode for troubleshooting.  
**Fallback to progressive:** If standard DASH download yields no audio, retry with progressive HTTP streams.

### Joining <a name="joining"></a>
**Join into one MP3:** Enables joining to combine all downloaded MP3s into a single large file.  
**Name:** Filename for the final combined MP3.  
**Write CUE for joined file:** Creates a `.cue` file with accurate `INDEX 01` markers.  
**Embed ID3 chapters:** Embeds chapter markers directly into the joined MP3 (requires `mutagen`).  
**Randomize order when joining:** Shuffles the playlist before combining.  
**Keep temp WAVs:** Keep intermediate WAVs from the join pipeline (useful for debugging).  
**Write VLC segment playlist:** Creates an `.m3u` playlist that points to chapter start/stop times inside the joined MP3 for VLC.

### System Dependencies <a name="system-dependencies"></a>
**Verify Tools:** Checks if `yt-dlp`, `ffmpeg`, `ffprobe`, and `mp3gain` are installed and accessible.  
**Check & Install System Deps:** Attempts automatic installation (Windows: `winget`; macOS: `brew`; Linux: `apt/dnf/pacman`).

### Controls & Log <a name="controls--log"></a>
**Run/Cancel:** Starts or stops the current process.  
**Progress Bar:** Shows determinate progress during downloads and joining.  
**Log Window:** Displays detailed information about the ongoing process. Right-click to copy or clear the log.

## Troubleshooting <a name="troubleshooting"></a>
### Tool Not Found (ffmpeg, mp3gain) <a name="tool-not-found-ffmpeg-mp3gain"></a>
If the log reports a tool is "missing" even after you've installed it, try restarting the application so PATH changes are picked up.

### Downloads are Slow or Failing <a name="downloads-are-slow-or-failing"></a>
Try increasing the **Delay between items** to 5 seconds or more. Check your internet connection. The video may have been removed or be region-locked.

### Private/Members-Only Videos Not Working <a name="privatevideos"></a>
This almost always means there is an issue with your cookies. Ensure you are logged into YouTube in your browser. Use a browser extension like "Cookie-Editor" to export your YouTube cookies to a `.json` file. Select that `.json` file in the "Cookies" section of the app and try again.
