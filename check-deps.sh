#!/usr/bin/env bash
# Check for required external tools: ffmpeg, ffprobe, mp3gain
# Usage: bash check-deps.sh

set -e

tools=("ffmpeg" "ffprobe" "mp3gain")

for t in "${tools[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    echo "✅ $t found: $(command -v $t)"
  else
    echo "❌ $t NOT found in PATH"
  fi
done
