@echo off
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

set "PY=python"
if exist .venv312\Scripts\python.exe (
  set "PY=.venv312\Scripts\python.exe"
) else if exist .venv\Scripts\python.exe (
  set "PY=.venv\Scripts\python.exe"
)

"%PY%" ai_usage_tray.py
pause
