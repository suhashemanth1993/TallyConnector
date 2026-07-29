# Builds the Windows executable via PyInstaller. Run on Windows PowerShell.
#
#   .\build.ps1

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\pip install -r requirements.txt pyinstaller
.\.venv\Scripts\python -m PyInstaller pyinstaller.spec --clean

Write-Host "Built dist\tally-connector.exe"
