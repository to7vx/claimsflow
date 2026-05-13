@echo off
REM ClaimsFlow live-demo runner (Windows).
REM Usage:  demo.bat [clean|mismatch|fraud|denial|all|status]
REM Submits demo_claims\*.json through the CLI pipeline; the dashboard at
REM http://localhost:5173 updates within ~5s as decisions land.

setlocal EnableDelayedExpansion

set "SCRIPT_DIR=%~dp0"
set "PY=%SCRIPT_DIR%backend\.venv\Scripts\python.exe"
set "CLI=%PY% -m claimsflow.cli.main"
set "CLAIMS=%SCRIPT_DIR%demo_claims"

if not exist "%PY%" (
  echo [ERROR] Python venv not found at %PY%
  echo Run:  cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -e .[dev]
  exit /b 1
)

set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=help"

pushd "%SCRIPT_DIR%backend"

if /I "%ACTION%"=="clean"    goto :run_clean
if /I "%ACTION%"=="mismatch" goto :run_mismatch
if /I "%ACTION%"=="fraud"    goto :run_fraud
if /I "%ACTION%"=="denial"   goto :run_denial
if /I "%ACTION%"=="deny"     goto :run_denial
if /I "%ACTION%"=="all"      goto :run_all
if /I "%ACTION%"=="status"   goto :run_status
goto :usage

:run_clean
echo.
echo ============================================================
echo  SCENARIO A - CLEAN APPROVAL  (asthma + spirometry)
echo  Expected: auto_approve with bilingual EOB
echo ============================================================
%CLI% process "%CLAIMS%\01_clean_approval.json"
goto :end

:run_mismatch
echo.
echo ============================================================
echo  SCENARIO B - MISMATCH  (asthma diagnosis + brain MRI)
echo  Expected: human_review with AI reasoning explaining mismatch
echo ============================================================
%CLI% process "%CLAIMS%\02_mismatch_human_review.json"
goto :end

:run_fraud
echo.
echo ============================================================
echo  SCENARIO C - FRAUD VELOCITY  (6 same-day same-procedure claims)
echo  Expected: first 5 auto_approve, 6th trips velocity+duplicate
echo            and lands in fraud_hold
echo ============================================================
for %%F in (03a_fraud_velocity.json 03b_fraud_velocity.json 03c_fraud_velocity.json 03d_fraud_velocity.json 03e_fraud_velocity.json 03f_fraud_velocity.json) do (
  echo.
  echo --- submitting %%F ---
  %CLI% process "%CLAIMS%\%%F"
  timeout /t 2 /nobreak >nul
)
goto :end

:run_denial
echo.
echo ============================================================
echo  SCENARIO D - AUTO DENY  (dental claim on Bronze plan, OON)
echo  Expected: auto_deny via eligibility short-circuit
echo            (plan does not cover dental)
echo ============================================================
%CLI% process "%CLAIMS%\04_out_of_network.json"
goto :end

:run_all
call :run_clean
echo.
echo  --- pausing 3s ---
timeout /t 3 /nobreak >nul
call :run_mismatch
echo.
echo  --- pausing 3s ---
timeout /t 3 /nobreak >nul
call :run_denial
echo.
echo  --- pausing 3s ---
timeout /t 3 /nobreak >nul
call :run_fraud
goto :end

:run_status
echo.
echo ============================================================
echo  STATUS - last 10 decisions in the database
echo ============================================================
%PY% -c "from claimsflow.core.db import get_session_factory; from claimsflow.models import Decision; from sqlalchemy import select; s=get_session_factory()(); rows=s.scalars(select(Decision).order_by(Decision.decided_at.desc()).limit(10)).all(); print(f'{\"claim_id\":<18} {\"decision\":<28} {\"confidence\":>10}'); [print(f'{r.claim_id:<18} {r.decision_type:<28} {r.confidence_score:>10.2f}') for r in rows]"
echo.
echo Healthz:
curl -s http://localhost:8000/healthz
echo.
goto :end

:usage
echo.
echo ClaimsFlow live-demo runner
echo.
echo Usage:  demo.bat ^<scenario^>
echo.
echo Scenarios:
echo   clean      Submit 01 - asthma + spirometry  (auto_approve, bilingual EOB)
echo   mismatch   Submit 02 - asthma dx + brain MRI (human_review with AI reasoning)
echo   fraud      Submit 03 - 6 same-procedure claims (fraud_hold on the 6th)
echo   denial     Submit 04 - dental on Bronze plan (auto_deny)
echo   all        Run all four scenarios with pauses between them
echo   status     Show last 10 decisions and backend healthz
echo.

:end
popd
endlocal
