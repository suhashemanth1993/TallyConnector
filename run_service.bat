@echo off
REM Launcher for Task Scheduler: activates the venv and runs the connector's
REM continuous sync loop (python app.py, no args -> health check + incremental
REM sync + retry drain, repeating every SYNC_INTERVAL_MINUTES from .env).
REM Uses %~dp0 (this script's own folder) so it works regardless of where the
REM repo is cloned, instead of a hardcoded path.

cd /d %~dp0
call .venv\Scripts\activate.bat
python app.py
