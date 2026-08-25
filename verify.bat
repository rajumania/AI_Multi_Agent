@echo off
REM ============================================================================
REM CampusFlow AI - Increment 1 verification runner
REM Runs the two pytest suites SEPARATELY (see INCREMENT_1_REPORT.md, section 8):
REM   1) backend/tests  - new auth/RBAC/departments suite (isolated throwaway DB,
REM                        ALLOW_ANONYMOUS_ADMIN forced off so RBAC is enforced)
REM   2) tests          - existing suite (compatibility mode, shim on by default)
REM Your real campusflow.db is never touched by suite (1).
REM ============================================================================
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.
echo === [1/2] New auth / RBAC / departments suite (backend/tests) ===
"%PY%" -m pytest backend/tests -q
set "NEW_RC=%ERRORLEVEL%"

echo.
echo === [2/2] Existing suite (tests) ===
"%PY%" -m pytest tests -q
set "OLD_RC=%ERRORLEVEL%"

echo.
echo === Summary ===
if "%NEW_RC%"=="0" (echo   new RBAC suite : PASS) else (echo   new RBAC suite : FAIL  rc=%NEW_RC%)
if "%OLD_RC%"=="0" (echo   legacy suite   : PASS) else (echo   legacy suite   : FAIL  rc=%OLD_RC%)
echo.
echo Next: start the app and run the manual browser checklist in INCREMENT_1_REPORT.md (section 6).

endlocal
