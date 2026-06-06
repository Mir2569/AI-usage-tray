@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================================
echo  AI Usage Tray - Setup
echo ============================================================
echo.

echo [1/4] Checking Python...
set "PY=python"
if exist .venv312\Scripts\python.exe (
  set "PY=.venv312\Scripts\python.exe"
  echo Using .venv312 virtual environment.
) else if exist .venv\Scripts\python.exe (
  set "PY=.venv\Scripts\python.exe"
  echo Using .venv virtual environment.
)
"%PY%" --version
if errorlevel 1 goto NOPYTHON
echo.

echo [2/4] Installing Python dependencies...
"%PY%" -m pip install -r requirements.txt
echo.

echo [3/4] Checking Node.js / npm...
where npm >nul 2>nul
if errorlevel 1 goto NONODE
node --version
npm --version
echo.
echo   Installing antigravity-usage globally...
call npm install -g antigravity-usage
if errorlevel 1 goto NPMFAIL
goto VERIFY

:NONODE
echo   [!] npm not found. Install Node.js from nodejs.org.
echo       (Codex usage will still work without it.)
goto VERIFY

:NPMFAIL
echo.
echo   [!] Global install failed, but that is OK.
echo       The app falls back to npx automatically (slower first run).
goto VERIFY

:VERIFY
echo.
echo [4/4] Test run (print usage once)...
echo.
"%PY%" ai_usage_tray.py --once
echo.
echo ============================================================
echo  Done. Run run.bat to start the tray.
echo ============================================================
echo.
pause
goto END

:NOPYTHON
echo   [!] Python not found. Install from python.org and add it to PATH.
echo.
pause
goto END

:END
endlocal
