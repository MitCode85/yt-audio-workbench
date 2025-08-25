# Setup Python virtual environment for YT Audio Backup GUI (Windows PowerShell)
# Usage:  .\setup-venv.ps1
# Then:   .\.venv\Scripts\Activate.ps1
#         make run    (or)   python yt_audio_backup_gui.py

$ErrorActionPreference = "Stop"

# Prefer uv if available
$hasUv = $false
try {
    uv --version > $null 2>&1
    if ($LASTEXITCODE -eq 0) { $hasUv = $true }
} catch { }

if ($hasUv) {
    Write-Host "Using uv to create venv and sync dependencies..."
    uv venv
    uv sync
} else {
    Write-Host "uv not found; falling back to python -m venv + pip"
    python -m venv .venv
    & .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    if (Test-Path requirements.txt) {
        pip install -r requirements.txt
    } else {
        pip install yt-dlp
    }
    # Optional dev tools
    pip install ruff mypy bandit
}

Write-Host ""
Write-Host "✅ Environment ready."
Write-Host "Activate with: .\.venv\Scripts\Activate.ps1"
Write-Host "Run the app:   python yt_audio_backup_gui.py"
