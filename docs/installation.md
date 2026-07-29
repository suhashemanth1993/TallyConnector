# Installation Guide

## Prerequisites

- TallyPrime with its HTTP/XML gateway enabled (F1 > Settings > Connectivity
  > Client/Server configuration, port 9000 by default) on the machine
  running the connector, or reachable over the network.
- A Frappe site with an API key/secret pair (User > API Access > Generate
  Keys) and the DocTypes referenced in `frappe/mapping.yaml` created (or
  edit the mapping to point at DocTypes you already have).
- Python 3.10+ (for running from source) or the prebuilt `.exe` (Windows).

## Option A — Run from source

```bash
git clone <this repo>
cd TallyConnector
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: TALLY_URL, FRAPPE_BASE_URL, FRAPPE_API_KEY, FRAPPE_API_SECRET

python app.py --health-check
```

## Option B — Windows executable

PyInstaller cannot cross-compile a Windows `.exe` from macOS/Linux, so the
`.exe` must be produced on Windows (or via CI):

**On a Windows machine:**
```powershell
.\build.ps1
```
produces `dist\tally-connector.exe`.

**Via GitHub Actions:** push a tag (`git tag v0.1.0 && git push --tags`) or
run the `Build Windows executable` workflow manually — it builds on a
`windows-latest` runner and uploads the `.exe` as a build artifact / release
asset. See `.github/workflows/build-windows.yml`.

Once you have the `.exe`, place a `.env` file (see `.env.example`) and
`frappe/mapping.yaml` next to it and run:
```
tally-connector.exe --health-check
```

## Auto-start (not yet built)

Running the `.exe` as a Windows Service / registering it for auto-start on
login, and a graphical configuration wizard, are listed in the PRD as
follow-up work — today the connector is a console application configured
via `.env`.
