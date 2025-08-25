# Check for required external tools: ffmpeg, ffprobe, mp3gain
# Usage: .\check-deps.ps1

$tools = @("ffmpeg","ffprobe","mp3gain")

foreach ($t in $tools) {
    $cmd = Get-Command $t -ErrorAction SilentlyContinue
    if ($cmd) {
        Write-Host "✅ $t found at $($cmd.Source)"
    } else {
        Write-Host "❌ $t NOT found in PATH"
    }
}
