# UI Options → ProcessingOptions → Core Behavior

This document maps each visible UI control in **YT Audio Workbench** to the corresponding
`ProcessingOptions` field and the downstream behavior triggered in the core (`workbench_core.py`).
Keep this in the repo (e.g., `docs/UI_to_Core_Map.md`) so contributors can quickly understand
how a checkbox or input impacts the pipeline.

> **Source of truth**: `ProcessingOptions(...)` construction in `yt_audio_backup_gui.py` and the
> functions invoked in `workbench_core.py` (e.g., `join_via_wav_then_lame`, `write_cue_for_joined`,
> `embed_id3_chapters`, `write_vlc_segment_playlist`, `validate_sample_rates`, `prepare_cookies`,
> `write_id3_tags_mutagen`, etc.).

| UI control (Tk var / control) | `ProcessingOptions` field | Core behavior / function(s) |
|---|---|---|
| URL (`url_var`) | `url` | Passed to yt-dlp as the source. |
| Output folder (`out_var`) | `output_dir` | Base output directory for all artifacts; `run_sub_dir` may add a time-stamped subfolder. |
| **Use run subfolder** (`use_run_subdir_var`) | `run_sub_dir` | Creates `run_YYYYMMDD_HHMMSS` and routes logs/outputs inside it. |
| Sample rate (dropdown `sample_rate_var`) | `sample_rate` | Enforced via ffmpeg; validated by `validate_sample_rates(...)`. |
| Bitrate (dropdown `bitrate_var`) | `bitrate` | LAME/ffmpeg CBR selection for final MP3s. |
| **Download archive (skip done)** (`archive_var`) | `use_archive` | Adds a yt-dlp `--download-archive` file in the run dir to avoid redownloads. |
| **Include video ID in name** (`include_id_var`) | `include_id` | Affects yt-dlp output template (filename pattern includes the ID). |
| **Number tracks** (`numbering_var`) | `numbering` | Adds/retains track numbers in filenames and playlist metadata. |
| **Fallback numbering** (`fallback_numbering_var`) | `fallback_numbering` | If missing, assigns sequential track numbers. |
| **Sanitize filenames** (`sanitize_names_var`) | `sanitize_filenames` | Post-process via `_sanitize_and_rename()` / `_sanitize_filename_component()`. |
| **De-dupe Artist – Artist – Title** (`dedup_artist_var`) | `dedup_artist` | Runs `_dedup_artist_in_filenames()` after downloads/encodes. |
| **Embed metadata (ID3)** (`embed_meta_var`) | `embed_metadata` | Writes tags via `write_id3_tags_mutagen(...)`. |
| **Join all to one MP3** (`join_var`) | `join` | Safe join pipeline `join_via_wav_then_lame(...)` (WAV intermediate → MP3). |
| **Write CUE for joined file** (`write_cue_var`) | `write_cue` | Emits CUE via `write_cue_for_joined(...)` after a join. |
| **Embed chapters (ID3)** (`embed_chapters_var`) | `embed_chapters` | Adds ID3 chapters via `embed_id3_chapters(...)` (if chapter data exists). |
| **Make VLC segment playlist** (`vlc_segments_var`) | `vlc_segments` | Writes a segment playlist via `write_vlc_segment_playlist(...)`. |
| **Randomize join order** (`random_join_var`) | `random_join` | Shuffles track list prior to the join step. |
| **Keep temp WAVs** (`keep_temp_var`) | `keep_temp_wavs` | Skips cleanup of WAV intermediates created for joining. |
| **Sleep between items (sec)** (`sleep_between_var`) | `sleep_between` | Inserts `time.sleep(...)` between per-item steps in the worker loop. |
| **Verbose yt-dlp** (`verbose_ydl_var`) | `verbose_ydl` | Adds `-v` to yt-dlp; more detailed logs via `YDLLogger`. |
| **High-integrity mode** (`hi_integrity_var`) | `hi_integrity` | Enables extra checks: `ffprobe` validation, `validate_sample_rates(...)`, stricter failure on anomalies. |
| Cookies file path (`cookies_file_var`) | `cookies_file` | If JSON → converts with `convert_cookie_editor_json_to_netscape(...)` then validates with `validate_netscape_cookiefile(...)`; wired via `prepare_cookies(...)`. |
| Browser cookies (`cookies_browser_var`) | `cookies_browser` | `prepare_cookies(...)` locates/exports a Netscape cookies file from the chosen browser profile. |
| Playlist format (dropdown `playlist_format_var`) | `playlist_format` | `write_playlist(...)` emits `m3u`/`m3u8`/`pls` for the run. |

---

## Notes for contributors
- If you add a new UI option, extend `ProcessingOptions` and update this table.
- Keep UI defaults, `ProcessingOptions` defaults, and help text in sync with `HELP.md`, `lang/en.json`, and `lang/fr.json`.
- The worker entry point is `run_processing_task(options, log_queue, progress_queue, cancel_event)`.
