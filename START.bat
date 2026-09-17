@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 goto root_failed
if not exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" goto powershell_missing
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -NoExit -File "%~dp0scripts\start_astra.ps1"
set "ASTRA_EXIT=%ERRORLEVEL%"
if not "%ASTRA_EXIT%"=="0" (
  echo ASTRA PowerShell failed. Exit code: %ASTRA_EXIT%
  echo Check scripts\start_astra.ps1 and your organization's PowerShell execution policy.
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
