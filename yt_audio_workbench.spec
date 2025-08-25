
# PyInstaller spec for YT Audio Workbench (GUI entrypoint)
# Build on Windows (PowerShell):
#   pyinstaller -y yt_audio_workbench.spec
# Executable will be in dist/YT-Audio-Workbench/YT-Audio-Workbench.exe

# NOTE: Adjust icon path if you add one (icon='app.ico').

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['yt_audio_backup_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('lang/en.json', 'lang'),
        ('lang/fr.json', 'lang'),
        ('HELP.md', '.'),
    ],
    hiddenimports=collect_submodules('tkinter'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YT-Audio-Workbench',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,   # GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
