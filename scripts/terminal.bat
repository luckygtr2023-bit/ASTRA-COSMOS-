@echo off
rem DEVELOPER-ONLY source bootstrap. Not shipped or invoked by the user distribution.
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "ASTRA_STAGE=PROJECT_ROOT"
set "ASTRA_LOG="
set "ASTRA_CODE=1"
set "ASTRA_ERROR=Unable to enter the project root."
cd /d "%~dp0.."
set "ASTRA_CODE=%ERRORLEVEL%"
if not "%ASTRA_CODE%"=="0" goto failed
set "ASTRA_ROOT=%CD%"
set "ASTRA_SETUP=0"
set "ASTRA_HEADLESS=0"
:options
if "%~1"=="" goto options_done
if /i "%~1"=="--setup-python" goto option_python
if /i "%~1"=="--headless" goto option_headless
set "ASTRA_CODE=2"
set "ASTRA_ERROR=Unknown option. Supported options: --setup-python and --headless."
goto failed
:option_python
set "ASTRA_SETUP=1"
shift
goto options
:option_headless
set "ASTRA_HEADLESS=1"
shift
goto options
:options_done
echo ============================================================
echo                          ASTRA📡🌌
echo                      ASTRA COSMOS
echo               Scientific Universe Simulator
echo ============================================================
set "ASTRA_STAGE=LOGGING"
if exist "logs\" goto logs_exist
mkdir "logs"
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=Unable to create logs directory; check folder write permissions."
if not "%ASTRA_CODE%"=="0" goto failed
:logs_exist
rem Store only curated metadata, never environment dumps or raw child output.
set "ASTRA_LOG=logs\astra_startup.log"
>>"%ASTRA_LOG%" echo [%DATE% %TIME%] Starting batch bootstrap
set "ASTRA_CODE=%ERRORLEVEL%"
if not "%ASTRA_CODE%"=="0" goto log_failed
set "ASTRA_MESSAGE=Initializing ASTRA COSMOS..."
call :record
set ASTRA_MESSAGE=Project root: "%ASTRA_ROOT%"
call :record
set "ASTRA_STAGE=SYSTEM"
set "ASTRA_MESSAGE=Checking system..."
call :record
ver
ver >>"%ASTRA_LOG%"
if /i not "%OS%"=="Windows_NT" goto wrong_os
set "ASTRA_STAGE=DEPENDENCIES"
set "ASTRA_MESSAGE=Checking dependencies..."
call :record
set "ASTRA_ERROR=Required native source, assets, shaders or pyproject.toml missing. Restore tracked files from this repository."
set "ASTRA_CODE=2"
if not exist "pyproject.toml" goto failed
if not exist "native_renderer\CMakeLists.txt" goto failed
if not exist "native_renderer\src\main.cpp" goto failed
if not exist "native_renderer\shaders\common\common.glsl" goto failed
if not exist "native_renderer\assets\" goto failed
set "ASTRA_STAGE=CONFIGURATION"
set "ASTRA_MESSAGE=Checking environment... Native runtime does not require Supabase."
call :record
if exist ".env" goto env_present
set "ASTRA_MESSAGE=.env absent; local native simulation is not blocked. Optional accounts need ASTRA_SUPABASE_URL and ASTRA_SUPABASE_PUBLISHABLE_KEY; see .env.example."
call :record
goto python_check
:env_present
set "ASTRA_MESSAGE=.env present. Values are not parsed, executed or logged by CMD; optional product configuration is validated by the product layer."
call :record

:python_check
set "ASTRA_STAGE=PYTHON"
set "ASTRA_MESSAGE=Checking Python... Not required by native astra_native; optional setup uses pyproject.toml."
call :record
set "ASTRA_PYTHON="
if exist ".venv\Scripts\python.exe" set "ASTRA_PYTHON=%ASTRA_ROOT%\.venv\Scripts\python.exe"
if defined ASTRA_PYTHON goto python_found
if exist "venv\Scripts\python.exe" set "ASTRA_PYTHON=%ASTRA_ROOT%\venv\Scripts\python.exe"
if defined ASTRA_PYTHON goto python_found
if "%ASTRA_SETUP%"=="0" goto python_optional
rem Search installed tools from System32, not implicitly from the project directory.
pushd "%SystemRoot%\System32"
for /f "delims=" %%P in ('where.exe python.exe') do if not defined ASTRA_PYTHON set "ASTRA_PYTHON=%%P"
popd
if not defined ASTRA_PYTHON goto python_missing
"%ASTRA_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)"
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=Python 3.9 or newer is required for optional setup. See interpreter error above; install from python.org."
if not "%ASTRA_CODE%"=="0" goto failed
rem Do not overwrite a broken environment, including a non-Windows environment.
if exist ".venv\" goto invalid_venv
if exist "venv\" goto invalid_venv
"%ASTRA_PYTHON%" -m venv ".venv"
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=Unable to create .venv. The actual Python error is displayed above."
if not "%ASTRA_CODE%"=="0" goto failed
set "ASTRA_PYTHON=%ASTRA_ROOT%\.venv\Scripts\python.exe"
:python_found
set ASTRA_MESSAGE=Python environment: "%ASTRA_PYTHON%"
call :record
"%ASTRA_PYTHON%" --version
set "ASTRA_CODE=%ERRORLEVEL%"
if not "%ASTRA_CODE%"=="0" goto python_broken
rem Interpreter version only is safe to record; stderr stays in the console.
"%ASTRA_PYTHON%" --version >>"%ASTRA_LOG%"
if "%ASTRA_SETUP%"=="0" goto python_optional
"%ASTRA_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3,9) and sys.prefix != sys.base_prefix else 1)"
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=Optional Python setup requires a working isolated Python 3.9+ environment."
if not "%ASTRA_CODE%"=="0" goto failed
if not exist "scripts\check_python_dependencies.py" goto checker_missing
"%ASTRA_PYTHON%" "scripts\check_python_dependencies.py"
if not errorlevel 1 goto python_dependencies_ok
set "ASTRA_MESSAGE=Declared Python dependencies missing or changed. Installing the existing project into its environment..."
call :record
"%ASTRA_PYTHON%" -m pip --isolated install --index-url https://pypi.org/simple -e .
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=Declared dependency installation failed. See actual pip output above; no package output is copied into startup logs."
if not "%ASTRA_CODE%"=="0" goto failed
"%ASTRA_PYTHON%" "scripts\check_python_dependencies.py"
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=Installed Python metadata does not satisfy pyproject.toml. Check the environment and pip output."
if not "%ASTRA_CODE%"=="0" goto failed
:python_dependencies_ok
"%ASTRA_PYTHON%" -m pip check
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=Python dependency conflicts detected. See pip check output above."
if not "%ASTRA_CODE%"=="0" goto failed
set "ASTRA_MESSAGE=Declared Python dependencies OK; existing installations reused."
call :record
goto native_check
:python_broken
set "ASTRA_ERROR=Existing environment interpreter failed. Actual Python/system error is above; repair the environment manually."
if "%ASTRA_SETUP%"=="1" goto failed
set "ASTRA_MESSAGE=WARNING: Existing Python environment did not execute; native startup does not require Python."
call :record
:python_optional
set "ASTRA_MESSAGE=Optional Python packages not installed by default. Use scripts\terminal.bat --setup-python to prepare the existing project environment."
call :record

:native_check
set "ASTRA_STAGE=NATIVE_RENDERER"
set "ASTRA_MESSAGE=Checking native renderer..."
call :record
call :find_native
if defined ASTRA_NATIVE goto native_found
set "ASTRA_MESSAGE=Windows astra_native.exe missing. Extensionless packaged Linux binaries are not Windows runtimes. Checking CMake..."
call :record
set "ASTRA_CMAKE="
pushd "%SystemRoot%\System32"
for /f "delims=" %%P in ('where.exe cmake.exe') do if not defined ASTRA_CMAKE set "ASTRA_CMAKE=%%P"
popd
if not defined ASTRA_CMAKE goto cmake_missing
"%ASTRA_CMAKE%" --version
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=CMake could not execute. See actual system error above."
if not "%ASTRA_CODE%"=="0" goto failed
set ASTRA_MESSAGE=CMake detected: "%ASTRA_CMAKE%"
call :record
set "ASTRA_STAGE=NATIVE_CONFIGURE"
"%ASTRA_CMAKE%" -S "native_renderer" -B "native_renderer\build-windows" -DCMAKE_BUILD_TYPE=Release -DASTRA_BUILD_LAUNCHER=OFF -DASTRA_BUILD_TESTS=OFF -DASTRA_BUILD_TOOLS=OFF
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=CMake configuration failed. See actual error above. Requires CMake 3.28+ and a Windows C++20 toolchain; use a Visual Studio developer CMD prompt."
if not "%ASTRA_CODE%"=="0" goto failed
set "ASTRA_STAGE=NATIVE_BUILD"
"%ASTRA_CMAKE%" --build "native_renderer\build-windows" --config Release --target astra_native --parallel 2
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_ERROR=Native CMake build failed. See actual compiler/linker diagnostics above."
if not "%ASTRA_CODE%"=="0" goto failed
call :find_native
if not defined ASTRA_NATIVE goto native_missing
:native_found
set ASTRA_MESSAGE=Native renderer candidate: "%ASTRA_NATIVE%"
call :record
set "ASTRA_MESSAGE=Windows loader will validate executable format and DLLs at launch; filename discovery is not binary verification."
call :record
set "ASTRA_STAGE=VULKAN_CHECK"
if exist "%SystemRoot%\System32\vulkan-1.dll" goto vulkan_file
set "ASTRA_MESSAGE=WARNING: Vulkan runtime loader file not detected. Install/update the official GPU driver. Normal native startup will still be attempted without an implicit headless flag."
call :record
goto prepare
:vulkan_file
set "ASTRA_MESSAGE=System Vulkan loader file detected. Loading, driver/device support and GPU rendering NOT VERIFIED by CMD."
call :record
:prepare
set "ASTRA_STAGE=PREPARING_RUNTIME"
set "ASTRA_MESSAGE=Preparing runtime... Current native source has mock Vulkan diagnostics and no trustworthy persistent readiness signal."
call :record
set "ASTRA_ARGUMENTS="
if "%ASTRA_HEADLESS%"=="1" set "ASTRA_ARGUMENTS=--headless"
set "ASTRA_STAGE=NATIVE_LAUNCH"
set "ASTRA_MESSAGE=Launching ASTRA..."
call :record
set ASTRA_MESSAGE=Launch command: "%ASTRA_NATIVE%" %ASTRA_ARGUMENTS%
call :record
rem Synchronous direct invocation: stdout/stderr stay visible, actual exit code is captured.
rem No START command, shell-generated command string, legacy launcher or detached child.
"%ASTRA_NATIVE%" %ASTRA_ARGUMENTS%
set "ASTRA_CODE=%ERRORLEVEL%"
set "ASTRA_MESSAGE=Native process result / exit code: %ASTRA_CODE%. No readiness has been inferred."
call :record
set "ASTRA_ERROR=Native invocation exited with a nonzero code. Actual loader/runtime diagnostics are above; no explanation is inferred from the code alone."
if not "%ASTRA_CODE%"=="0" goto failed
if "%ASTRA_HEADLESS%"=="1" goto diagnostic_complete
set "ASTRA_STAGE=NATIVE_EXIT_WITHOUT_READY"
set "ASTRA_CODE=1"
set "ASTRA_ERROR=Native exit code was 0 but persistent application readiness was not established. Bootstrap returns 1; this is not a RUNNING simulator."
goto failed
:diagnostic_complete
set "ASTRA_MESSAGE=Explicit headless diagnostics exited with code 0. GPU and application readiness NOT VERIFIED."
call :record
pause
exit /b 0

:find_native
set "ASTRA_NATIVE="
for %%R in ("native_renderer\build-windows\Release\astra_native.exe" "native_renderer\build-windows\astra_native.exe" "native_renderer\build\Release\astra_native.exe" "native_renderer\build\Debug\astra_native.exe" "native_renderer\build\astra_native.exe" "build\Release\astra_native.exe" "build\Debug\astra_native.exe" "build\astra_native.exe" "native_renderer\astra_native.exe" "release\ASTRA-COSMOS\bin\astra_native.exe") do if not defined ASTRA_NATIVE if exist "%%~R" set "ASTRA_NATIVE=%ASTRA_ROOT%\%%~R"
exit /b 0

:record
rem Call this label without arguments: no CALL second expansion of paths or messages.
echo [ASTRA📡🌌] %ASTRA_MESSAGE%
if defined ASTRA_LOG >>"%ASTRA_LOG%" echo [%DATE% %TIME%] [%ASTRA_STAGE%] %ASTRA_MESSAGE%
exit /b 0

:log_failed
set "ASTRA_LOG="
set "ASTRA_ERROR=Unable to append startup log. Check folder permissions; actual CMD error is above."
goto failed
:wrong_os
set "ASTRA_CODE=1"
set "ASTRA_ERROR=Windows CMD is required."
goto failed
:python_missing
set "ASTRA_CODE=9009"
set "ASTRA_ERROR=Python not found on PATH for optional setup. Install Python 3.9+ from python.org. Native startup without --setup-python does not need Python."
goto failed
:invalid_venv
set "ASTRA_CODE=1"
set "ASTRA_ERROR=Existing Python environment is unusable for Windows setup; repair it manually. It has not been overwritten or deleted."
goto failed
:checker_missing
set "ASTRA_CODE=2"
set "ASTRA_ERROR=Optional setup requires tracked scripts\check_python_dependencies.py. Restore that file."
goto failed
:cmake_missing
set "ASTRA_CODE=9009"
set "ASTRA_ERROR=No Windows native renderer found and CMake is not on PATH. Install official CMake 3.28+ and a C++20 Windows toolchain, or provide a trusted astra_native.exe build."
goto failed
:native_missing
set "ASTRA_CODE=2"
set "ASTRA_ERROR=CMake returned success but no expected astra_native.exe artifact was found. Inspect native_renderer\build-windows."
:failed
echo ============================================================
echo [ASTRA📡🌌] STARTUP FAILED
echo ============================================================
echo Stage: %ASTRA_STAGE%
echo Error: %ASTRA_ERROR%
echo Exit code: %ASTRA_CODE%
echo Check the actual command output above. Startup metadata is in logs\astra_startup.log when writable.
set "ASTRA_MESSAGE=STARTUP FAILED. Error: %ASTRA_ERROR% Exit code: %ASTRA_CODE%"
call :record
pause
exit /b %ASTRA_CODE%
