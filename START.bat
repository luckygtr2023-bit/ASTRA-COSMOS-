@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto unavailable
if not exist "ASTRA COSMOS.exe" goto unavailable
rem This is the compiled GUI bootstrap host supplied in the user release ZIP.
rem It downloads only pinned prebuilt runtimes; it never builds ASTRA.
".\ASTRA COSMOS.exe" --update
set "ASTRA_CODE=%ERRORLEVEL%"
if "%ASTRA_CODE%"=="0" exit /b 0
echo [ASTRA📡🌌] STARTUP FAILED. See the Windows error or application failure dialog for actual details.
echo Exit code: %ASTRA_CODE%
pause
exit /b %ASTRA_CODE%
:unavailable
echo [ASTRA📡🌌] ASTRA COSMOS could not start.
echo Problem: This folder does not contain the compiled ASTRA bootstrap application.
echo Details: A source-code archive is not an ASTRA Windows runtime distribution.
echo Recommended action: Obtain the published ASTRA-COSMOS.zip when a verified release is available.
echo No developer tools are required or installed by this entry point.
echo Exit code: 2
pause
exit /b 2
