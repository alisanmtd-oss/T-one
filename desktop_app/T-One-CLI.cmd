@echo off
setlocal
set "TONE_RUNTIME=%~dp0t-one-runtime\t-one-runtime.exe"
if not exist "%TONE_RUNTIME%" (
  echo T One CLI runtime not found: %TONE_RUNTIME% 1>&2
  exit /b 2
)
set "TONE_ROOT=%APPDATA%\teelab-commerce-agent-desktop\workspace"
if not exist "%TONE_ROOT%" set "TONE_ROOT=%APPDATA%\t-one-commerce-agent-desktop\workspace"
if not exist "%TONE_ROOT%\config\workspace_projects.json" (
  if not exist "%~dp0t-one-runtime\template\config\workspace_projects.json" (
    echo T One CLI workspace template not found. 1>&2
    exit /b 2
  )
  if not exist "%TONE_ROOT%" mkdir "%TONE_ROOT%"
  xcopy "%~dp0t-one-runtime\template\*" "%TONE_ROOT%\" /E /I /Y /Q >nul
)
if "%~1"=="" (
  title T One CLI
  doskey tone="%TONE_RUNTIME%" cli --root "%TONE_ROOT%" -- $*
  echo T One CLI is ready. Type tone --help or tone status.
  echo Administrator access is available only after tone elevate and Windows UAC confirmation.
  "%TONE_RUNTIME%" cli --root "%TONE_ROOT%" -- --help
  cmd.exe /d /k
  exit /b %ERRORLEVEL%
)
"%TONE_RUNTIME%" cli --root "%TONE_ROOT%" -- %*
exit /b %ERRORLEVEL%
