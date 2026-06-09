@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo  AI Usage Tray - Build EXE (PyInstaller)
echo ============================================================
echo.

echo [1/4] Selecting Python 3.12 (3.14 is incompatible with PyInstaller here)...
set "PY=py -3.12"
%PY% --version
if errorlevel 1 (
  echo   [!] Python 3.12 not found. Falling back to default python.
  echo   [!] If the built exe fails to launch, install 3.12:  winget install -e --id Python.Python.3.12
  set "PY=python"
)
%PY% --version
if errorlevel 1 goto NOPYTHON
%PY% -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)"
if errorlevel 1 goto OLDPYTHON
echo.

echo [2/4] Creating isolated build venv (.venv312)...
%PY% -m venv .venv312
if errorlevel 1 goto PIPFAIL
set "VPY=.venv312\Scripts\python.exe"
echo.

echo [3/4] Installing build dependencies (pinned for reproducible builds)...
"%VPY%" -m pip install -r requirements-build.txt
if errorlevel 1 goto PIPFAIL
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto PIPFAIL
echo.

echo [4/4] Building AIUsageTray (onedir, no console window)...
"%VPY%" -m PyInstaller --onedir --noconsole --clean --noconfirm --name AIUsageTray --icon app.ico --hidden-import pystray._win32 --collect-submodules ai_usage_tray ai_usage_tray.py
if errorlevel 1 goto BUILDFAIL
echo.

echo   Copying config.json next to the exe (if present)...
if exist config.json copy /Y config.json dist\AIUsageTray\config.json >nul

echo   Copying app.ico next to the exe (settings window icon)...
if exist app.ico copy /Y app.ico dist\AIUsageTray\app.ico >nul

echo.
echo ============================================================
echo  Done!  -^>  dist\AIUsageTray\AIUsageTray.exe
echo  Double-click that exe to run with NO terminal window.
echo  (Keep the whole AIUsageTray folder together; config.json
echo   lives next to the exe inside it.)
echo ============================================================
echo.
pause
goto END

:NOPYTHON
echo   [!] Python not found. Install from python.org and add to PATH.
pause
goto END

:OLDPYTHON
echo   [!] Python 3.10+ is required (pinned build deps in requirements-build.txt).
echo   [!] Install Python 3.12:  winget install -e --id Python.Python.3.12
pause
goto END

:PIPFAIL
echo   [!] Dependency install failed. See the messages above.
pause
goto END

:BUILDFAIL
echo   [!] Build failed. See the PyInstaller output above.
pause
goto END

:END
endlocal
