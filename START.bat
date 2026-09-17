@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto root_failed
if not exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" goto powershell_missing
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_astra.ps1"
set "ASTRA_EXIT=%ERRORLEVEL%"
if not "%ASTRA_EXIT%"=="0" (
  echo [ASTRA📡🌌] STARTUP FAILED
  echo PowerShell/bootstrap exit code: %ASTRA_EXIT%
  echo The actual PowerShell error is shown above.
  echo Check scripts\start_astra.ps1. Organization Group Policy can override the process-scoped bypass.
  pause
)
exit /b %ASTRA_EXIT%
:root_failed
echo ASTRA STARTUP FAILED: Cannot access the project directory.
pause
exit /b 1
:powershell_missing
echo ASTRA STARTUP FAILED: Windows PowerShell is unavailable.
echo Check your Windows installation. No software was downloaded.
pause
exit /b 1
