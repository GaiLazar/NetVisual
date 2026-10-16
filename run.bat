@echo off
REM ============================================================
REM  NetVisual A+ v4 — desktop launcher (system-tray mode).
REM  Double-click: a small icon appears in the taskbar's
REM  notification area (bottom-right).
REM    • click the icon   → open the dashboard
REM    • right-click → Stop NetVisual → clean shutdown (port freed)
REM  A one-time balloon tells you it's running.
REM ============================================================
setlocal EnableExtensions
cd /d "%~dp0"

if "%NETVISUAL_PORT%"=="" set "NETVISUAL_PORT=8730"

REM --- find a Python (.venv -> uv -> launcher -> pythonw / python) --------------
set "PYW="
set "PY="

if exist "%~dp0.venv\Scripts\pythonw.exe" (
  set "PYW="%~dp0.venv\Scripts\pythonw.exe""
  goto have_pythonw
)
if exist "%~dp0.venv\Scripts\python.exe" (
  set "PY="%~dp0.venv\Scripts\python.exe""
  goto have_python
)

where pyw >nul 2>&1 && set "PYW=pyw -3"
where pythonw >nul 2>&1 && if not defined PYW set "PYW=pythonw"
if defined PYW goto have_pythonw

where python >nul 2>&1 && set "PY=python"
if not defined PY (
  where py >nul 2>&1 && set "PY=py -3"
)
if defined PY goto have_python

echo No Python found. Install Python 3.10+ and re-run.
pause
exit /b 1

:have_python
:have_pythonw
REM Open the browser ~2s after the server is up.
start "" /b powershell -NoProfile -Command "Start-Sleep 2; Start-Process http://127.0.0.1:%NETVISUAL_PORT%"

if defined PYW (
  REM pythonw => no console window, pure tray
  start "" %PYW% netvisual_app.py --tray
) else (
  REM console python => tray still works; console shows logs
  start "" %PY% netvisual_app.py --tray
)

endlocal
