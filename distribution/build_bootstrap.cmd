@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0.."
if errorlevel 1 exit /b 1
rem BUILD MACHINE ONLY. .NET SDK is not an end-user dependency.
rem Output contains a private .NET runtime; it does not supply the missing ASTRA runtime.
dotnet publish "bootstrap\src\Astra.Bootstrap.csproj" -c Release -r win-x64 --self-contained true -o "dist\bootstrap"
exit /b %ERRORLEVEL%
