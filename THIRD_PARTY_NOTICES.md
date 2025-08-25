# Third-Party Notices

This project (**YT Audio Backup GUI**) is licensed under the MIT License (see LICENSE).
It makes use of, or interoperates with, third-party software under their own licenses.

You must comply with the license terms of these third-party components if you install or use them.

---

## Python Dependencies

- **yt-dlp**
  License: [Unlicense](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE)
  Summary: Public-domain dedication. Permissive use.

- **Tkinter** (stdlib)
  License: Python Software Foundation License.
  Ships with Python.

- **pyperclip** (optional, for clipboard)
  License: MIT.

- **uv** (recommended for env management, not required at runtime)
  License: Apache-2.0.

- **Ruff**, **mypy**, **bandit** (dev tools)
  Licenses: MIT / Apache-2.0 (all permissive).

---

## External Tools

These are **not bundled** with this project. Users must install them separately and comply with their licenses:

- **ffmpeg**
  License: [LGPL 2.1+](https://ffmpeg.org/legal.html) (default builds) or GPL 2+ (if compiled with GPL options).
  This project calls ffmpeg as an external process. No ffmpeg binaries are distributed with this project.

- **mp3gain**
  License: GPL-2.0.
  This project calls mp3gain as an external process. No mp3gain binaries are distributed with this project.

---

## Notes

- Because ffmpeg and mp3gain are invoked as **external programs**, their licenses do **not** apply to the source code of this project.
- If you redistribute this project **with those binaries embedded**, you must comply with their licenses (e.g., GPL copyleft).
- Keeping them as system dependencies avoids license conflicts.

---

_Last updated: February 2025_
