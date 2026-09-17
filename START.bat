@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "ASTRA_ROOT=%~dp0"
cd /d "%ASTRA_ROOT%"
set "ASTRA_CODE=%ERRORLEVEL%"
if not "%ASTRA_CODE%"=="0" goto root_failed
if not exist "scripts\terminal.bat" goto missing_terminal
rem CALL uses a constant relative path to avoid re-expanding percent signs in the root.
call scripts\terminal.bat
exit /b %ERRORLEVEL%

:root_failed
echo [ASTRA📡🌌] STARTUP FAILED
echo Stage: PROJECT_ROOT
echo Error: Unable to enter project root "%ASTRA_ROOT%".
echo Exit code: %ASTRA_CODE%
pause
exit /b %ASTRA_CODE%

:missing_terminal
echo [ASTRA📡🌌] STARTUP FAILED
echo Stage: BOOTSTRAP
echo Error: Required scripts\terminal.bat is missing. Restore it from this repository.
echo Exit code: 2
pause
exit /b 2
