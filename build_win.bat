
@echo off
setlocal
where pyinstaller >NUL 2>&1
if errorlevel 1 (
  echo pyinstaller not found. Please:  pip install pyinstaller
  exit /b 1
)
pyinstaller -y yt_audio_workbench.spec
echo.
echo Build complete. See dist\YT-Audio-Workbench\
