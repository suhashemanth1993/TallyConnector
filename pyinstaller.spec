# PyInstaller spec for the Tally Connector Windows executable.
#
# Must be built ON Windows (PyInstaller does not cross-compile). Either run
# build.py / build.ps1 on a Windows machine, or let the
# .github/workflows/build-windows.yml CI job produce the .exe as a release
# artifact.
#
#   pyinstaller pyinstaller.spec

import sys

block_cipher = None

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("frappe/mapping.yaml", "frappe"),
        (".env.example", "."),
    ],
    hiddenimports=[
        "pydantic",
        "pydantic_settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name="tally-connector",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon=None,
)
