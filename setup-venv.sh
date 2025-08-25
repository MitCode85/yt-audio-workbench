#!/usr/bin/env bash
# Setup Python virtual environment for YT Audio Backup GUI (macOS/Linux)
# Usage:  bash setup-venv.sh
# Then:   source .venv/bin/activate
#         make run   (or)   python yt_audio_backup_gui.py

set -euo pipefail

if command -v uv >/dev/null 2>&1; then
  echo "Using uv to create venv and sync dependencies..."
  uv venv
  uv sync
else
  echo "uv not found; falling back to python -m venv + pip"
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade pip
  if [ -f requirements.txt ]; then
    pip install -r requirements.txt
  else
    pip install yt-dlp
  fi
  # Optional dev tools
  pip install ruff mypy bandit
fi

echo ""
echo "✅ Environment ready."
echo "Activate with: source .venv/bin/activate"
echo "Run the app:   python yt_audio_backup_gui.py"
