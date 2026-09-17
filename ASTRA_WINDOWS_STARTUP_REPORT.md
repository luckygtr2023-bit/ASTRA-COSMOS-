# ASTRA Windows startup — BAT-only migration

Date: 2026-09-17

## 1. Current architecture

```
START.bat
  -> scripts\terminal.bat
       -> system / declared dependency / environment checks
       -> optional Python project environment setup
       -> native astra_native.exe discovery or existing CMake build
       -> Vulkan loader-file presence warning
       -> direct synchronous native invocation
       -> exit diagnostics and pause
```

The normal startup chain is **BAT/CMD only**, without PowerShell, a .ps1 prerequisite, execution-policy changes, administrator requests, or a second engine. Optional Python package validation uses the existing Python metadata helper only when the user requests Python setup; Python is not needed by the normal native startup chain.

`START.bat` sets `ASTRA_ROOT=%~dp0`, changes directory with quoted `cd /d`, checks terminal.bat presence and calls the **constant relative** `scripts\terminal.bat`. This deliberately avoids CALL's second expansion of percent signs embedded in an installation path. Both scripts disable delayed expansion to preserve exclamation marks. terminal.bat also discovers its own root, so it can be invoked independently from another working directory. No hard-coded drive. Paths containing quotes are invalid Windows paths; spaces, parentheses, Unicode and shell metacharacters are intended to work using quoted paths, but require Windows testing. UNC share working directories are not supported by `cd /d`; use a local/mapped drive, otherwise the launcher reports root failure and pauses.

## 2. Previous confirmed failure and PowerShell removal

The user-observed first failure was at **PowerShell bootstrap**: unsigned `scripts\start_astra.ps1` was blocked with `UnauthorizedAccess` before dependencies or the engine ran. Status: **IDENTIFIED**. The previous revision added a process-only policy option; this migration supersedes that design entirely.

Before deletion, a tracked repository search for `start_astra.ps1` found references only in START.bat, README, this report, .gitattributes and launcher-specific regression tests. There was no scientific engine, CMake, product, Supabase or native runtime dependency. All operational references/tests/attributes were migrated to terminal.bat before deleting the script. This report and the removal regression test intentionally retain its name as historical evidence, not a required executable component. No permanent user/machine policy was modified.

No policy-block execution path remains in the new BAT source. **That static fact is not a Windows double-click test.** No next-stage Windows error has been observed during this change.

## 3. EXE inspection and cleanup

Every existing `.exe` was enumerated before deletion; exactly two were present:

| File | Size | SHA-256 | Inspection / action |
|---|---:|---|---|
| `ASTRA COSMOS.exe` | 945152 bytes | `20720aa4a9ddaae88f1fa0cbc94606bc747f1967433e145d5a4f126836d79756` | MZ and PE signatures; contains `ASTRA COSMOS Launcher`, `astra_native`, `--headless`; obsolete wrapper, DELETED |
| `release/ASTRA-COSMOS/ASTRA COSMOS.exe` | 945152 bytes | same hash | Identical obsolete wrapper, DELETED |

Their identity matches the existing `native_renderer/launcher/launcher.cpp` wrapper, which locates/launches a separate native target. The native CMake target does not link to or depend on these wrapper binaries. They were not scientific runtimes. The earlier packaged-child mismatch remains documented: `release/ASTRA-COSMOS/bin/astra_native` starts with ELF magic, not a Windows native executable. **That native artifact was preserved**, along with native source, libraries, shader/assets, scientific systems and Supabase.

Legacy launcher C++ source and the opt-in `ASTRA_BUILD_LAUNCHER` CMake target remain for developers. Its default is now OFF so ordinary clean builds do not recreate the obsolete user-facing EXE. The BAT build also explicitly passes OFF. Older CMake caches can retain their old setting. Historical forensic/release documents remain historical, not current startup instructions.

## 4. Terminal and environment checks

Both BAT files use UTF-8 without BOM, CRLF, and `chcp 65001` for the ASTRA📡🌌 banner. Glyph appearance depends on Windows terminal/font support. terminal.bat prints initialization, system, dependencies, Python, native renderer, runtime preparation and launch messages as the respective stages are reached.

Checks include Windows OS, writeable logs directory, pyproject.toml, native CMake source/main, common shader and assets directory. Missing required project files produce restoration instructions; no fabricated assets or unknown downloads. The working directory is the repository root, matching native `native_renderer/shaders/...` lookups.

`.env` presence is reported but its contents are never executed, parsed, echoed or logged by CMD. Full dotenv/remote credential validation is not implemented in batch. Native main does not consume Supabase configuration, so missing/invalid product configuration does not block local native work. Optional accounts remain governed by the existing product layer and documented keys/offline behavior. No credentials are hard-coded or generated.

## 5. Dependency handling and Python environment

Actual declared Python workflow remains `pyproject.toml`, setuptools/wheel, Python >=3.9, dependencies `supabase>=2.0`, `python-dotenv>=1.0`, `httpx>=0.24`. No new manager or arbitrary package list.

Default startup checks for an existing `.venv\Scripts\python.exe`, then `venv\Scripts\python.exe`; if present it prints/logs the version. Python absence or a broken interpreter is nonblocking in normal native mode. It does not search/install an unnecessary global Python interpreter by default.

Explicit optional setup:

```bat
scripts\terminal.bat --setup-python
```

Reuses the same environments without activation or global package changes. If neither is usable, finds installed `python.exe` through `where.exe` with System32 as working directory, checks >=3.9 and creates `.venv` **only if no .venv/venv directory exists**. Broken/non-Windows environments are not overwritten. Only `py.exe`-available installations must expose the interpreter on PATH manually. No Python interpreter installer is downloaded.

The existing Python helper reads project declarations/installed metadata. Missing/changed direct dependencies trigger:

```bat
"<selected environment>\Scripts\python.exe" -m pip --isolated install --index-url https://pypi.org/simple -e .
```

Then validate metadata and run `pip check`. Existing declared dependencies are reused without reinstallation; detected conflicts fail visibly rather than deleting environments. Python helper tests simulate satisfied, missing and changed metadata; they are not Windows pip-install tests.

## 6. Native renderer discovery/build

CMake declares `astra_native`, built from the existing native main and linked renderer library. Search only known `astra_native.exe` locations: native_renderer build-windows Release/single-config, native_renderer build Release/Debug/single-config, root build Release/Debug/single-config, native_renderer root and release/ASTRA-COSMOS/bin. Existing candidates are reused. No recursive “run any EXE” search, no old EXE wrapper or extensionless ELF substitution.

**Pure CMD discovery checks filename presence, not PE headers/signature/architecture.** The Windows loader is authoritative at invocation, and its actual console diagnostics/result are retained. This is weaker than the removed script's PE check and is disclosed, not presented as binary verification.

If absent, resolve installed CMake via `where.exe` from System32, print version and configure the existing project:

```bat
"<cmake.exe>" -S native_renderer -B native_renderer\build-windows -DCMAKE_BUILD_TYPE=Release -DASTRA_BUILD_LAUNCHER=OFF -DASTRA_BUILD_TESTS=OFF -DASTRA_BUILD_TOOLS=OFF
"<cmake.exe>" --build native_renderer\build-windows --config Release --target astra_native --parallel 2
```

Requires CMake 3.28+ (enforced by CMakeLists) and an installed Windows C++20 toolchain. CMake chooses the generator; Ninja is not required unless selected by the developer. Missing tools/build errors remain visible with real exit codes. No third-party compiler/SDK/DLL download. The previous MSVC flag separation is preserved. Windows build portability remains **NOT VERIFIED**; Linux-specific native shader/tool paths still exist.

## 7. Vulkan and readiness honesty

CMD tests only `%SystemRoot%\System32\vulkan-1.dll` file presence. This is **not** a load test, driver/device enumeration, feature test or renderer initialization. Missing file produces official GPU-driver guidance and the normal entry point is still attempted. No Vulkan binaries are downloaded and no headless argument is injected silently.

Explicit diagnostics:

```bat
scripts\terminal.bat --headless
```

Current source inspection shows mocked instance/device/swapchain functions and a finite 120-iteration diagnostic main. This is not proof of any failure on the user's machine after the old policy block. It does mean there is no honest readiness handshake the BAT can use. The script never prints a RUNNING banner on creation, mock output, or zero exit. A zero-code exit is recorded as native code 0; in normal mode the bootstrap returns 1 for readiness not established. Explicit headless diagnostics may return 0 without claiming GPU success. A future genuine persistent runtime needs an actual trustworthy readiness signal before adding RUNNING reporting.

## 8. Errors, process results and logging

Direct quoted synchronous native invocation keeps stdout/stderr visible and waits for completion. `%ERRORLEVEL%` is saved on the immediately following line, before logging/pause can change it. Stage, actual available exit code, contextual error and next check are displayed on failure, followed by `pause`. CMD/loader/compiler/pip errors are not redirected away. No PID or initialization event is invented. A hang is not automatically killed; use the terminal to interrupt.

`logs\astra_startup.log` is append-only curated metadata: timestamps, Windows version, quoted root/environment/tool/runtime paths, Python version when detected, checks, launch command, process result, exits and startup error summaries. `logs/.gitkeep` is preserved, log files ignored. Error before log creation is console-only.

**Security trade-off for BAT-only:** raw native/pip/CMake stdout/stderr are not duplicated to logs, because pure CMD cannot reliably redact arbitrary secrets. Full actual diagnostic text is visible in the retained console, while the log records code/stage and a curated error summary. No environment dumps, credential values, .env contents or arbitrary user arguments are logged. Review terminal output before sharing. Log rotation and concurrent-start locking are not implemented. Mid-run disk/log failures are displayed by CMD but do not reliably abort an already-running child.

Only fixed optional flags reach the native child. START.bat does not forward arbitrary arguments. All CALL statements use constant labels/paths, avoiding second expansion of root paths. No elevation, permanent policy mutation, remote script execution or PATH mutation. Existing PATH tools, known environment interpreters, native candidates and project build backends still require a trusted installation/checkout; no Authenticode provenance checks. Existing engine shader shell commands are outside this launcher change.

## 9. Tests and actual runtime result

### Executed here on Linux

- Portable source/helper suite: `python -m unittest discover -s scripts/tests -v` — **13 passed**.
- Existing native project validator: `python native_renderer/tools/validate_native_project.py` — **221 OK, 0 FAIL**.
- `git diff --check` — passed.
- Examined both EXEs' signatures, string identity, size/hash before removal.
- Checked script dependency references before removal and verified no executable startup references remain.
- Confirmed preserved native packaged ELF signature and native/legacy C++ source existence.

Tests cover root discovery/constant CALL, no PowerShell/policy chain, label references, error retention/result capture, declared optional dependencies, explicit headless, no fake readiness/GPU claims, curated logging, deletion boundaries, CRLF and metadata helper behavior. They **inspect BAT source, not execute CMD**.

### Windows acceptance tests — all NOT VERIFIED

| Requested test | Result |
|---|---|
| Double-click START.bat / visible terminal | NOT VERIFIED |
| Banner and project-root detection | NOT VERIFIED |
| From another directory / special-character paths | NOT VERIFIED |
| No PowerShell invocation / no policy error | Static source confirms no invocation; Windows run NOT VERIFIED |
| Dependency and Python checks execute | NOT VERIFIED |
| Missing Python/packages, malformed config | NOT VERIFIED |
| Native renderer discovery or auto-build | NOT VERIFIED |
| Missing Vulkan, immediate child exit/missing DLL | NOT VERIFIED |
| Launch attempted / actual application success | NOT VERIFIED |
| Errors remain visible / log created | NOT VERIFIED |

No Windows CMD, PowerShell, Wine or Windows toolchain is available here; no Windows double-click or build/GPU test has occurred. **WINDOWS RUNTIME VERIFICATION: NOT VERIFIED. ASTRA: NOT LAUNCHED.** Windows native artifact: NOT FOUND in the supplied checkout. Actual next runtime error: **none observed; awaiting Windows execution**, not guessed from inspection findings.

## 10. Final validation and remaining limitations

- **CREATED / STATICALLY CHECKED:** BAT-only startup, dependency/configuration logic, logging/retention, updated README/report/tests.
- **REMOVED:** PowerShell startup script and the two inspected obsolete wrapper binaries. No engine/runtime source or scientific/Supabase systems removed.
- **BUILD VERIFIED:** NO.
- **RUNTIME VERIFIED:** NO.
- **GPU VERIFIED:** NO.

Remaining work is actual Windows acceptance testing, a Windows native build if absent, and separately implementing/verifying genuine persistent renderer readiness. These are not claimed to be the next observed error. The new chain eliminates the PowerShell dependency by design; it does not establish that the whole application is fixed.
