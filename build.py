"""Builds the Windows executable via PyInstaller.

Run this ON WINDOWS (PyInstaller does not cross-compile):

    python -m venv .venv
    .venv\\Scripts\\activate
    pip install -r requirements.txt pyinstaller
    python build.py

Output: dist/tally-connector.exe
"""

from __future__ import annotations

import subprocess
import sys


def main() -> int:
    if sys.platform != "win32":
        print(
            "Warning: PyInstaller cannot cross-compile a Windows .exe from this platform.\n"
            "Run this script on Windows, or use .github/workflows/build-windows.yml.",
            file=sys.stderr,
        )

    return subprocess.call([sys.executable, "-m", "PyInstaller", "pyinstaller.spec", "--clean"])


if __name__ == "__main__":
    raise SystemExit(main())
