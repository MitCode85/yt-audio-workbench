# YT Audio Workbench — Help

Welcome to the help documentation for YT Audio Workbench. This guide will walk you through the main features and options available in the application.

## Table of Contents
- [Getting Started](#getting-started)
- [Main Window Explained](#main-window-explained)
  - [Core Settings](#core-settings)
  - [Cookies](#cookies)
  - [Download & Formatting](#download--formatting)
  - [Filename & Options](#filename--options)
  - [Joining](#joining)
  - [System Dependencies](#system-dependencies)
  - [Controls & Log](#controls--log)
- [Troubleshooting](#troubleshooting)
  - [Tool Not Found Errors](#tool-not-found-errors)
  - [Downloads are Slow or Failing](#downloads-are-slow-or-failing)
  - [Private/Members-Only Videos Not Working](#privatemembers-only-videos-not-working)

## Getting Started

The primary purpose of this tool is to create high-quality, consistent MP3 backups from a YouTube URL, whether it's a single video or a playlist.

#### Basic Workflow:
1.  **Paste** a YouTube URL into the top field.
2.  **Select** an Output folder where the files will be saved.
3.  **Choose** your desired Bitrate and Sample Rate.
4.  **Click** the **Run** button.

## Main Window Explained

This section details each option available in the application's main window.

### Core Settings
- **Playlist or video URL:** The source URL from YouTube.
- **Output folder:** The main directory where all files and logs will be saved.
- **Use per-run subfolder:** (Recommended) When checked, each time you click "Run", a new subfolder with a timestamp (e.g., `run_20250826_164000`) will be created inside your output folder. This is the safest way to keep download sessions separate and ensures the "Join" feature works correctly.

### Cookies
- **Cookies file:** You can provide a `cookies.txt` (Netscape format) or a `.json` file exported from a browser extension like "Cookie-Editor". The application will automatically convert `.json` files if needed.
- **Use browser cookies:** Alternatively, select a browser (e.g., Chrome, Firefox) and the application will attempt to use its live cookie data to access private content.

### Download & Formatting
- **Sample rate:** Enforces a consistent audio sample rate for all files. `44100 Hz` is standard for CD quality, while `48000 Hz` is common for video.
- **Bitrate (kbps):** Sets the quality of the MP3 file. `192` provides good quality, while `320` is the highest quality available for the MP3 format.
- **Delay between items (s):** A pause (in seconds) between downloading each item in a playlist to avoid being rate-limited by YouTube's servers.
- **Playlist format:** Creates a playlist file (`.m3u` or `.m3u8`) of the downloaded tracks for easy playback in media players.

### Filename & Options
- **Add numbering:** Prefixes filenames with a number (e.g., `001_...`, `002_...`).
- **Include YouTube ID in filename:** Appends the unique YouTube video ID in brackets (e.g., `... [dQw4w9WgXcQ].mp3`). >**Note:** Brackets can cause issues with some older media players.
- **Sanitize filenames:** (Recommended) Removes special characters from filenames that can cause problems with file systems, playlists, or scripts.
- **Use download archive:** The app will keep a record of downloaded files in `download_archive.txt`. If you run the same playlist again, it will skip any files it has already downloaded.
- **Normalize with MP3Gain:** Uses the `mp3gain` tool to adjust the volume of all tracks to a standard level without re-encoding or losing quality.
- **De-duplicate artist in filename:** Cleans up filenames by removing repeated artist names (e.g., `Artist - Artist - Title` becomes `Artist - Title`).
- **Validate with ffprobe:** Uses `ffprobe` to validate the sample rate and format after the audio conversion is complete.
- **Verbose yt-dlp logging:** Runs the underlying `yt-dlp` tool in verbose mode, which is useful for troubleshooting download issues.
- **Fallback to progressive:** If the standard download method (DASH) yields no audio, this option will retry the download using older progressive HTTP streams.

### Joining
- **Join into one MP3:** Enables the joining feature to combine all downloaded MP3s into a single large audio file.
- **Name:** The filename for the final combined MP3.
- **Write CUE for joined file:** Creates a `.cue` sheet with accurate `INDEX 01` markers for each track, allowing players to skip between chapters.
- **Embed ID3 chapters:** Embeds chapter markers directly into the joined MP3 file (requires the `mutagen` library).
- **Randomize order when joining:** Shuffles the playlist before combining the files into one.
- **Keep temp WAVs:** Prevents the deletion of intermediate WAV files used during the joining process. This is useful for debugging.
- **Write VLC segment playlist:** Creates a special `.m3u` playlist that points to the specific start and stop times for each chapter inside the joined MP3, for use with VLC Media Player.

### System Dependencies
- **Verify Tools:** Checks if `yt-dlp`, `ffmpeg`, `ffprobe`, and `mp3gain` are installed and accessible in the system's PATH.
- **Check & Install System Deps:** Attempts to automatically install the required tools using common package managers (Windows: `winget`; macOS: `brew`; Linux: `apt/dnf/pacman`).

### Controls & Log
- **Run/Cancel:** Starts or stops the current process.
- **Progress Bar:** Shows the progress of downloads and the joining process.
- **Log Window:** Displays detailed real-time information about the ongoing process. Right-click to copy or clear the log.

## Troubleshooting

### Tool Not Found Errors
If the log reports that a tool like `ffmpeg` or `mp3gain` is "missing" even after you have installed it, your system may not be aware of its location. **Try restarting the application** or your computer to ensure the updated system PATH is recognized.

### Downloads are Slow or Failing
- **Rate Limiting:** Try increasing the **Delay between items** to 5 seconds or more.
- **Connection Issues:** Check your internet connection.
- **Content Availability:** The video may have been removed or be restricted in your region.

### Private/Members-Only Videos Not Working
This is almost always a cookie issue.
1.  Ensure you are logged into YouTube in your browser.
2.  Use a browser extension like **"Cookie-Editor"** to export your YouTube cookies to a `.json` file.
3.  In the app, select that `.json` file in the "Cookies file" field and try again.
