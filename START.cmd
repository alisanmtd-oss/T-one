@echo off
setlocal

set "DEMO=%~dp0demo\chat-first-workspace.html"
if not exist "%DEMO%" (
  echo PUBLIC_DEMO_ERROR: missing demo\chat-first-workspace.html
  exit /b 2
)

echo PUBLIC_DEMO_READY: %DEMO%
echo Mode: public offline demo; no live store connections or external actions.
if /i "%~1"=="--verify-only" exit /b 0

start "" "%DEMO%"
if errorlevel 1 (
  echo PUBLIC_DEMO_ERROR: Windows could not open the default browser.
  exit /b 3
)
exit /b 0
