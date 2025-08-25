# Minimal developer workflow
.PHONY: dev run lint test export clean

dev:
	uv venv || python -m venv .venv
	uv sync || pip install -r requirements.txt ruff mypy bandit

run:
	python yt_audio_backup_gui.py

lint:
	ruff check .
	mypy --install-types --non-interactive || true

test:
	python - <<'PY'
print("Smoke test: import OK")
import yt_dlp
print("yt_dlp version:", getattr(yt_dlp, "__version__", "unknown"))
PY

export:
	# lock and export a pip requirements file from uv if available
	uv export --no-dev --format requirements-txt > requirements.lock.txt || echo "uv not available"

clean:
	rm -rf .mypy_cache .ruff_cache .pytest_cache dist build *.spec


# ---- Binary builds (PyInstaller) ----
.PHONY: build build-win build-mac build-linux distclean

build:
	pyinstaller yt_audio_backup.spec

build-win:
	pyinstaller yt_audio_backup.spec

build-mac:
	pyinstaller yt_audio_backup.spec

build-linux:
	pyinstaller yt_audio_backup.spec

distclean:
	rm -rf build dist *.spec


# ---- Dependency check ----
.PHONY: check-deps

check-deps:
	@echo "Checking for ffmpeg, ffprobe, mp3gain..."
	@if command -v ffmpeg >/dev/null 2>&1; then echo "✅ ffmpeg: $$(command -v ffmpeg)"; else echo "❌ ffmpeg NOT found"; fi
	@if command -v ffprobe >/dev/null 2>&1; then echo "✅ ffprobe: $$(command -v ffprobe)"; else echo "❌ ffprobe NOT found"; fi
	@if command -v mp3gain >/dev/null 2>&1; then echo "✅ mp3gain: $$(command -v mp3gain)"; else echo "❌ mp3gain NOT found"; fi
