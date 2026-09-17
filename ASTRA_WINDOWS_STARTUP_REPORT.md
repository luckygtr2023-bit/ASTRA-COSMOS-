# ASTRA Windows startup report

Date: 2026-09-17

## Status and verification levels

- **CREATED:** START.bat, scripts/start_astra.ps1, scripts/check_python_dependencies.py, logs/.gitkeep, portable regression tests, this report.
- **STATICALLY VERIFIED:** entry-point quoting/retention, native target selection policy, declared Python dependency check, logging/redaction paths, explicit-only headless mode. Ten portable regression tests pass; existing native static validator: 221 OK, 0 FAIL.
- **BUILD VERIFIED:** NO. CMake and a Windows compiler/runtime are unavailable in this environment. The MSVC flag correction has not been compiled.
- **RUNTIME VERIFIED:** NO for Windows launcher/application. Python dependency-check behavior was tested with mocked installed metadata, not actual Windows package installations.
- **GPU VERIFIED:** NO. No Vulkan device enumeration, real renderer initialization, or presentation verified.

This is not a claim that the simulator is fixed or running.

## 1. Previous EXE launcher problem

Direct binary-header checks in this turn confirm root `ASTRA COSMOS.exe` has MZ/PE signatures, whereas `release/ASTRA-COSMOS/bin/astra_native` has Linux ELF magic. Windows cannot execute that child as a native Windows application. The earlier forensic report describes the disappearing console; its claimed Windows observations were not reproduced here. Keeping the existing EXE does not solve the incompatible child artifact.

There is a separate source-level blocker: `native_renderer/src/rhi/vulkan_rhi.cpp` mocks instance creation, device enumeration, logical devices and swapchain behavior, including with Vulkan headers present. `main.cpp` runs 120 diagnostic iterations, additional subsystem checks, then shuts down. It supplies no persistent GUI/readiness handshake. A bootstrapper cannot repair that scientific/rendering implementation without a separate engine change.

## 2. New START.bat architecture

START.bat discovers `%~dp0`, disables delayed expansion, changes to that directory, and invokes the explicit Windows PowerShell system executable. It does not invoke the legacy EXE or forward arbitrary command fragments. Standard user, no elevation. A double-click console remains available via the script ENTER prompt and batch fallback pause on host failures. `-NoExit` is removed so parse/policy failures return directly to the batch error handler.

## 3. PowerShell bootstrap flow

Banner → Windows/x64 check → logs directory → project configuration/assets → optional Python setup → native PE discovery/build → system Vulkan loader probe → working-directory validation → direct native process creation → concurrently drained stdout/stderr → exit diagnostics → prompt.

PowerShell 5.1 compatibility is intended, with UTF-8 BOM and CRLF for the script and CRLF for the batch file. Parser/runtime verification on PowerShell is still required. Emoji rendering depends on the terminal font; missing glyphs do not imply startup failure.

## 4. Dependency detection

Inspected `pyproject.toml`: Python >=3.9, setuptools/wheel backend, runtime dependencies `supabase>=2.0`, `python-dotenv>=1.0`, `httpx>=0.24`; development extras already exist. No new manager or requirements file introduced. No tracked Windows virtual environment was found. Native main does not start Python, so default startup does not install unused packages or make science dependent on Supabase.

Native tools are located through application commands on PATH, rejecting tools inside the project directory. CMake's existing target is `astra_native`. Required tracked source/configuration/shader/assets paths are checked; missing source/assets produce restore instructions rather than invented downloads.

## 5. Dependency installation

`-SetupPython` uses pip inside the project environment and installs the project with `pip --isolated install --index-url https://pypi.org/simple -e <root>` only when declaration/version metadata requires repair. Transitive dependencies and declared build requirements remain pip's responsibility. `pip check` detects inconsistent installed dependencies. A conflicting/broken environment may require manual repair; it is not deleted automatically.

A missing native artifact triggers configure/build of the existing CMake project in `native_renderer/build-windows`, Release, target `astra_native`, tests/tools/legacy launcher disabled. Existing valid artifacts are reused. Compiler flags now distinguish MSVC from GCC/Clang instead of passing GNU optimization flags to MSVC. All native targets/source remain intact.

No Python installer, compiler, SDK, GPU driver, DLL, random EXE or remote script is downloaded. Missing prerequisite tools cause actionable errors. Existing CMake Linux-specific header/tool paths and remaining compiler portability issues may still prevent a Windows build; automatic build is an attempt, not a guarantee.

## 6. Python environment handling

Python is optional for native startup. With `-SetupPython`, prefer `.venv/Scripts/python.exe`, then `venv/Scripts/python.exe`, otherwise use installed `python.exe` to create `.venv`. Check Python >=3.9 and that the selected environment is isolated. No activation or global package mutation. Interpreter acquisition is manual from the official provider. Systems exposing only `py.exe` must make their Python interpreter available on PATH first. Invalid existing environments fail visibly instead of being destroyed.

The small metadata checker reads `pyproject.toml` using stdlib tomllib or pip's vendored tomli for Python 3.9/3.10, and pip's vendored requirement/version parser. Missing/outdated project metadata or direct declared distributions trigger installation. Subsequent checks avoid reinstalling. No timestamp-only success cache.

## 7. Native renderer detection

Only explicit known `astra_native.exe` paths are searched: native_renderer build-windows Release/single-config, build Release/Debug/single-config, root build Release/single-config, native_renderer root, and release/ASTRA-COSMOS/bin. No recursive arbitrary EXE discovery. Validate MZ, PE signature, x64 machine, executable flag and not DLL. PE validation is not Authenticode verification or proof of correct linked dependencies. The Windows loader remains authoritative.

Packaged extensionless Linux binaries and the legacy launcher are never substituted. PowerShell's direct ProcessStartInfo launch handles the executable path without shell interpretation. Child working directory is the repository root, matching native shader lookups.

## 8. Vulkan checks

Probe the absolute Windows System32 `vulkan-1.dll` with LoadLibraryEx, restricting dependency lookup to System32; free the handle afterward. Missing file/load failure is a warning with driver guidance and actual Win32 error if exposed. Loader availability does not verify a driver, physical device, Vulkan 1.3 features, surfaces or rendering.

Still attempt the normal native entry point when Vulkan is missing; do not inject a fallback flag. Existing native mock behavior is disclosed. Only explicit `-Headless` sends `--headless`. No RUNNING, RENDERER_INITIALIZED, VULKAN_INITIALIZED or ASTRA_READY success is inferred from current mock messages.

## 9. Configuration handling

Check required tracked files and directories. Inspect `.env` assignment syntax without execution, interpolation, output of values or changes. Malformed line numbers are reported without line contents. Missing `.env` is nonblocking because native runtime does not consume it. This is a basic syntax check, not full dotenv semantic validation or remote credential validation.

The optional product layer needs ASTRA_SUPABASE_URL and ASTRA_SUPABASE_PUBLISHABLE_KEY (existing fallback names remain in its implementation). START does not start that layer, test remote credentials or copy example placeholder credentials. `.env.example` currently ends with a stray Markdown fence; remove it when copying. No Supabase connectivity is needed for native local diagnostics. Existing product/offline behavior is unchanged.

## 10. Error handling

Catch bootstrap exceptions with stage, actual available message, exit code and next diagnostic. Native failures report signed decimal and unsigned hexadecimal exit codes. Each native stream is asynchronously read to avoid a full stderr pipe blocking stdout. Preserve relevant stderr/error lines and distinguish stream labels.

PROCESS_CREATED records PID only. Startup output may update the observed stage but cannot establish health. The current normal-mode program's zero exit is reported accurately as native code 0, then bootstrap returns 1 because persistent readiness was never established. Explicit headless diagnostic code 0 is allowed but never described as GPU success. A future persistent app needs an actual trustworthy readiness contract before adding a RUNNING banner; mere survival is insufficient. No initialization timeout or automatic child kill is implemented; a hung process remains visible for manual interruption.

## 11. Logging

Create logs and append timestamped logs/astra_startup.log. Record Windows version, root, optional Python version/environment, checks, renderer path, command, PID, stage, child output, errors and exits. Logs are ignored by Git; .gitkeep is tracked. No raw stdout/stderr files or transcript containing secret values. Failure before log creation (e.g. read-only directory) is console-only. Logs append without rotation; users may archive/delete old logs when ASTRA is stopped. Concurrent launches are not serialized.

## 12. Security considerations

- Process-scoped `-ExecutionPolicy Bypass` only; no persistent execution-policy changes, RunAs, profile loading, arbitrary download execution or PATH mutation.
- Batch uses quoted self-relative paths and disabled delayed expansion. PowerShell uses literal paths, argument arrays and direct native process launch.
- .env is never sourced as PowerShell. Environment secret/key/token/password values and .env assignment values are collected for redaction; common JWT/key/password and URL-userinfo patterns are filtered too.
- Redaction is defense-in-depth, not a guarantee against every possible future child output/encoded secret. Review logs before sharing. No credentials added.
- Trust this checkout before running its build, declared Python build backend, known environment interpreter, or native artifact. PE headers do not prove provenance. Existing globally configured tools/package sources and normal Windows DLL search behavior remain trust boundaries.
- The existing engine uses a shell shader compilation command and Linux `/tmp` paths; that code was not rewritten here. This limits Windows shader portability independently of bootstrap path handling.

## 13. Tests performed

Executed on Linux:

```
python -m unittest discover -s scripts/tests -v
# 10 tests, all passed
python native_renderer/tools/validate_native_project.py
# Validated: 221 OK, 0 FAIL
git diff --check
# clean
```

Portable tests inspect root quoting, retention, explicit headless flag, no legacy launcher/download execution, PE and Vulkan checks, BOM/CRLF, absence of fake readiness, and actual packaged binary headers. Dependency helper tests simulate satisfied, missing and changed metadata. These tests do not execute PowerShell or Windows APIs. Native validator is static, not a native build or GPU test.

## 14. Tests not possible / Windows acceptance matrix

No Windows, powershell.exe, pwsh, Wine or CMake available here. All following **Windows runtime tests are NOT VERIFIED**:

| Scenario | Required observation on a Windows test machine |
|---|---|
| Double-click from root | Visible PowerShell/banner/log and retained terminal |
| Invoke START.bat from another directory | Root resolved; shader lookup from repo root |
| Spaces/Unicode/parentheses/ampersands/percent/exclamation paths | Correct literal paths, no shell interpretation |
| Missing Python | Normal native flow unaffected; -SetupPython explains official installation |
| Missing declared package | Optional setup installs project once; next run reuses it |
| Missing renderer | CMake builds actual Windows target or displays actual prerequisite/build error |
| Invalid .env | Line-number warning, no secret values; native local flow remains independent |
| Missing Vulkan | Loader warning, no false GPU claim or implicit headless flag |
| Immediate exit / missing DLL | Actual code/streams/stage retained; no success banner |
| Normal application startup | Requires a real persistent renderer/readiness implementation first |
| Explicit headless | Diagnostic exit remains visible, no GPU-success claim |
| Policy block / missing script / unwritable logs | Visible host or bootstrap error, no disappearing failure |

Use a disposable copy/VM for destructive missing-dependency tests, not the user's live environment. Test secret canaries in both streams and .env before sharing logs. No fabricated Windows simulation results are recorded.

## 15. Exact launch commands

Double click `START.bat`, or from any directory:

```bat
"D:\path to\ASTRA COSMOS\START.bat"
```

Batch invokes:

```bat
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_astra.ps1"
```

The bootstrap uses ProcessStartInfo with FileName = selected absolute `astra_native.exe`, WorkingDirectory = project root, and empty Arguments by default. Only explicit script `-Headless` sets Arguments = `--headless`. Manual optional Python preparation: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_astra.ps1 -SetupPython`. Developer automation can use `-NoPause`; START never does.

## 16. Known limitations / final validation

Created/static checks pass for launcher files, root discovery code, intended visible host, banner construction, dependency checks/reuse/repair, native discovery, honest Vulkan reporting, basic configuration validation, redaction, logging code, failure retention code, exit handling, README and report. No original EXE, scientific implementation, physics, Supabase, test, renderer source or developer launcher was removed. CMake change is limited to compiler flags.

**Not runtime verified:** window visibility, emitted banner/log, network package installation, Windows path edge cases, PowerShell parsing, Windows native build, actual ASTRA launch, GPU initialization. An actual Windows renderer is absent from the supplied package. More importantly, the existing runtime source is diagnostic/mock and cannot currently satisfy a persistent production application's readiness contract. These are remaining issues, not solved by creating START.bat.


## 17. Confirmed PowerShell execution-policy failure and targeted repair

### Original failure — user-observed Windows evidence

- **Stage:** PowerShell bootstrap (before the script executes).
- **Failure:** Unsigned `scripts\start_astra.ps1` blocked by Windows execution policy.
- **Actual error:** “The file is not digitally signed. You cannot run this script on the current system.” `FullyQualifiedErrorId: UnauthorizedAccess`.
- **Status:** IDENTIFIED.

This is the first confirmed failure in the reported Windows workflow. It is not evidence of a Python, Vulkan, renderer or engine failure. Earlier source/binary limitations in this report are inspection findings, not observed next-stage failures for this workflow.

### Exact repair

START.bat now invokes:

```bat
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_astra.ps1"
```

No permanent Set-ExecutionPolicy command, registry edit or administrator request is used. Root discovery and quoted paths are preserved. This process-level option is appropriate only for a trusted repository; enforced MachinePolicy/UserPolicy may take precedence. No attempt is made to circumvent organization policy.

Removed `-NoExit` so an early policy/parser error returns immediately to START.bat, which captures `%ERRORLEVEL%`, prints `[ASTRA📡🌌] STARTUP FAILED`, references the actual unredirected error above, and pauses. The PowerShell script still retains its exception reporting and ENTER prompt. UTF-8 batch output is enabled for the failure label. The existing banner remains, followed by Initializing, PowerShell bootstrap started, and Checking dependencies messages. No errors are suppressed.

### Testing results for this repair

Portable regression suite: **11 tests passed**. Covers exact invocation, process-only policy option, absence of persistent policy/elevation commands, bootstrap messages, quoted root path and failure-retention structure. `git diff --check`: passed. Script reviewed for compatibility with `-File`; parameters and normal diagnostics remain unchanged. These are static/helper checks, not PowerShell parser or Windows tests.

**Double-click Windows test: NOT VERIFIED.** This environment has no Windows CMD/PowerShell runtime. Consequently none of the requested eight real workflow observations has been newly verified here: visible window, banner, script execution, disappearance of UnauthorizedAccess, dependency checks, Python checks, renderer detection or launch attempt. The first fix is implemented but Windows confirmation is pending.

**Next actual error:** None observed after this change; no Windows rerun is available. Run the updated START.bat on the affected machine and retain the next actual diagnostic, if any. Do not infer a next-stage failure from the source inspection notes above.
