@echo off
REM ClaimsFlow LIVE batch demo (Windows).
REM Submits 10 mixed claims via a single Python process with ~2s gaps,
REM so the dashboard's Live Activity panel updates at a watchable pace.
REM Wall-clock target: ~30 seconds (LLM-bound: ~10s slack for mismatch + fraud).

setlocal
set "SCRIPT_DIR=%~dp0"
set "PY=%SCRIPT_DIR%backend\.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo [ERROR] Python venv not found at %PY%
  exit /b 1
)

"%PY%" "%SCRIPT_DIR%tools\demo_live_runner.py"
endlocal
