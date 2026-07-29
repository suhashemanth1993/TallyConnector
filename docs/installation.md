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

## Auto-start via Task Scheduler

`app.py` with no arguments runs forever (health check + incremental sync +
retry drain, repeating every `SYNC_INTERVAL_MINUTES`), so auto-start means
"launch this at logon and keep it running," not a one-shot scheduled job.

`run_service.bat` in the repo root does this: it `cd`s to its own folder
(works regardless of where you cloned the repo), activates `.venv`, and
runs `python app.py`.

Register it (adjust the path to match where you cloned the repo):
```cmd
schtasks /create /tn "TallyConnectorSync" /tr "C:\path\to\TallyConnector\run_service.bat" /sc onlogon /rl highest /f
```
This starts the sync loop automatically whenever you log in. Check it's
running via Task Manager (look for `python.exe`) or by watching
`logs\app.log` update.

**Manage it:**
```cmd
schtasks /query /tn "TallyConnectorSync"     REM check status
schtasks /end /tn "TallyConnectorSync"       REM stop it
schtasks /delete /tn "TallyConnectorSync" /f REM remove the task entirely
```

**Two things the plain command above does *not* give you** (need the Task
Scheduler GUI, since they involve settings `schtasks create` can't set and,
for the first one, a password I can't handle for you in a chat):
- **Running without anyone logged in** — open Task Scheduler → find the
  task → Properties → General tab → "Run whether user is logged on or
  not" (enter your Windows password when prompted).
- **Auto-restart if the process crashes** — Properties → Settings tab →
  "If the task fails, restart every: 1 minute" (pick an attempt limit).

A graphical configuration wizard and an installer are still not built —
today this is `.env` + Task Scheduler.
