# ASTRA self-bootstrap architecture

Date: 2026-09-17. **Infrastructure implemented; Windows execution NOT VERIFIED; production release BLOCKED.**

This specification describes the accompanying implementation, not a claim that a usable simulator package exists. The shipped `bootstrap/release.json` explicitly says `blocked`. There is no invented URL, checksum, binary, GPU result or published runtime.

## 1. Source versus user distribution

Development tree retains `astra`, `native_renderer`, visualization, Supabase, source tests and the developer-only `scripts/terminal.bat`. Source archives from GitHub are **not** end-user runtime downloads.

After production acceptance, the build-machine package tool will produce:

```
ASTRA-COSMOS.zip
  START.bat
  ASTRA COSMOS.exe             # compiled GUI bootstrap/normal-launch host
  bootstrap/release.json      # immutable version/URL/checksum/file inventory pin
```

The user-facing EXE is compiled from `bootstrap/src`, not the old legacy native launcher. It is a .NET 8 Windows x64 GUI application published with its own runtime/single-file settings. The target user does not install .NET or the .NET SDK. This publish configuration has **not been built or audited here**, so no self-contained certification is made. The native production payload is separate and does not yet exist.

First setup: `START.bat` invokes the GUI host with `--update` to install/check the **locally bundled pinned release**. It does not launch CMD scripts from a download, compile source, run pip or invoke any build tools. It pauses if the compiled host is absent or returns an error. The current source checkout contains no compiled host and therefore displays an honest unavailable-distribution message.

Later: double-click `ASTRA COSMOS.exe` directly. With an installed runtime and no explicit update request, it selects the local version without any network/catalog fetch. START.bat is not required for normal use. No terminal is created by the GUI host. It launches the real payload at `versions/<version>-<archive-sha256>/ASTRA COSMOS.exe` using an absolute path and `UseShellExecute=false`.

## 2. Private runtime and writable user state

Use the standard user's `%LOCALAPPDATA%\ASTRA COSMOS` folder rather than assuming the extracted folder is writable:

```
ASTRA COSMOS/
  current.json
  previous.json
  session.lock
  versions/
    <version>-<sha256>/        # inventory-checked immutable application payload
      ASTRA COSMOS.exe        # must be the real production runtime
      ...                     # actual audited DLL/shader/asset files, no invented required folders
  staging/<random-id>/        # temporary download/extraction
  userdata/
    config/
    saves/
    screenshots/
    recordings/
    scenarios/
  logs/
    astra_bootstrap.log
```

Only version payloads are replaced/selected. Existing versions and user data are never deleted by updates. The root bootstrap EXE stays in the extracted distribution folder; keep that folder for the normal double-click launch. No elevation or registry execution-policy change. Fixed application identity means all bootstrap copies for the same user share this store; an exclusive session file lock prevents concurrent install/update/game sessions.

Payloads must honor `ASTRA_USER_DATA` and never write caches, saves or mutable configuration into their immutable version tree. The host creates writable directories but does not invent scientific settings. This runtime integration is **BLOCKED**, not implemented in the current native engine.

## 3. Release artifacts and manifests

Target GitHub Release layout (not currently published):

```
v<major.minor.patch>
  ASTRA-Windows-x64-Runtime.zip
  ASTRA-COSMOS.zip
  ASTRA-COSMOS.zip.sha256
  release.json
  acceptance.json / test records
  optional publisher signatures
```

Runtime ZIP layout is the real application's own audited layout with exactly `ASTRA COSMOS.exe` as entry point. The archive must contain regular file entries only, not directory/symlink entries. If scientific Python is required, private Python files are ordinary inventory records, not global installations.

`distribution/release_tools.py catalog` generates schema 1 ready metadata **only after** the evidence gate and archive audit. Fields: `schema`, `state`, `version`, `url`, archive `size`, archive `sha256`, `entryPoint`, `python` (`none` or `embedded`) and `files` containing each exact path, size and SHA-256. The archive URL is constrained to this repository's `/releases/download/v<version>/ASTRA-Windows-x64-Runtime.zip`.

The checked-in catalog contains only schema/state/reason and **no ready runtime fields**. Both the release tool and GUI host fail closed on it. There is no remote unsigned `latest.json` trust mechanism.

`distribution/acceptance.template.json` starts BLOCKED/NOT VERIFIED. A maintainer must attach archive-specific Windows build, GPU/science, shader, DLL, offline/clean-machine, lifecycle and readiness-contract results. The tool requires all named checks to be VERIFIED and ties the record to the archive SHA-256. This is a **reviewer attestation**, not automated proof that a GPU test occurred. An additional source guard rejects the known current finite diagnostic main even if a record asserts success. That heuristic is not a general semantic production verifier; independent review remains mandatory.

## 4. Download and integrity implementation

The GUI host uses `HttpClient` with automatic redirects disabled, cookies disabled, default TLS validation, no custom certificate bypass. The initial URL must be the exact pinned HTTPS GitHub release URL. Up to five redirects are accepted only over HTTPS/default port, without credentials/fragments, to `github.com` or `release-assets.githubusercontent.com`. Signed CDN queries are permitted for redirected downloads but not logged. Other hosts and HTTP downgrades fail. GitHub CDN behavior changes require a reviewed host-policy update, not arbitrary redirect acceptance.

Download to an owned random staging directory with create-new semantics and a timeout. Enforce the declared archive size while streaming and verify SHA-256 before opening it. No network credentials or GitHub API token are needed for public release assets. No unknown software URLs, compilers or drivers are downloaded.

Extraction validates:

- Manifest schema, stable three-part version and approved source URL.
- Maximum archive 4 GiB, expanded payload 12 GiB, 50,000 files and 200-character relative file paths.
- Exact inventory, no undeclared or duplicate/case-colliding files or file/directory conflicts.
- No absolute paths, backslashes, drive/ADS syntax, `..`, empty components, trailing dot/space, control/non-ASCII archive path components or Windows reserved names.
- No symlinks, Windows reparse entries or special files; destination ancestry is checked for reparse points.
- No bootstrap scripts, links or known compiler/development-tool executables in runtime payloads.
- Streaming extraction byte bounds and every file's SHA-256.
- PE signature, x64 machine and PE32+ checks for EXE/DLL/PYD files; DLL-as-EXE rejected.

ASCII-only **archive paths** do not restrict the Windows user's installation path. Full absolute paths are derived from OS/application locations, without shell interpolation. PE/header checks do not prove GPU functionality, full dependency closure, publisher identity or binary benignness.

## 5. Trust and signing

The initial downloaded bootstrap ZIP and its pinned catalog are the trust root. A checksum downloaded beside a malicious replacement from the same compromised source cannot authenticate that replacement. HTTPS and checksums protect transport/integrity, not a compromised publisher account or modified local bootstrap directory.

Authenticode signing of the GUI host and publisher verification of bootstrap/catalog releases are recommended before public distribution. No signing certificate was supplied, no artifact was signed, and there is **no implemented signature-based remote metadata rotation**. Only catalog pins delivered in a newly trusted bootstrap distribution can authorize a new runtime. Do not accept arbitrary locally substituted manifests as trusted release metadata.

Same-user malware and publisher compromise are outside the current protection boundary. The design does not claim TOCTOU resistance to a malicious process running with the same user's write permissions. Reparse/path checks and exclusive install locks are defense-in-depth, not a sandbox.

## 6. Version checks, updates and rollback

Normal direct launch: load local `current.json`, validate its manifest and full installed inventory, then run without a network request. This avoids downloads but hashing a large payload is not literally instantaneous.

Explicit update: START.bat or `ASTRA COSMOS.exe --update` reads the trusted **bundled** catalog. Same version/hash reuses files; changed content under the same version or downgrade is rejected. A new bootstrap ZIP can carry a newer reviewed catalog. No automatic background/latest-version polling, GUI update button or automatic bootstrap-host updater is implemented.

New payloads are extracted under staging, verified and moved into an immutable side-by-side version directory on the same volume. The old `current.json` remains untouched during download/extraction/initialization. Only after the child supplies the defined readiness record does `File.Replace` atomically activate the new manifest while saving `previous.json`. First installation uses an atomic move of a flushed new manifest.

Download/hash/extraction/early-process-exit/initialization-timeout failures leave the prior selection and saves unchanged. The error is shown instead of silently pretending the new version ran. Explicit `--rollback` validates the previous version, starts it, waits for its readiness, then switches the selection. A crash after activation is logged; rollback is explicit rather than an unbounded crash/relaunch loop. No save-schema migration/rollback is implemented; the production runtime must preserve compatibility or provide independently tested migrations.

The old version remains even after success. Interrupted installs can leave unreferenced version/staging files; only this attempt's random staging directory is cleaned automatically. Disk-full, interrupted pointer promotion, concurrent starts and actual Windows rollback behavior still require executable fault-injection tests.

## 7. Runtime readiness contract — not implemented by current native target

The host passes:

- `ASTRA_USER_DATA`: private writable persistent data root.
- `ASTRA_READY_FILE`: one-session readiness JSON path.
- `ASTRA_READY_NONCE`: unpredictable per-launch value.

The corrected native production runtime must write the following small record atomically **only after genuine GPU presentation and scientific integration**, using the supplied nonce:

```json
{
  "protocol": 1,
  "nonce": "<supplied per-launch nonce>",
  "stage": "ASTRA_READY",
  "renderer": "real-vulkan",
  "science": "connected",
  "presented_frames": 1
}
```

The host requires the child still alive, valid nonce/protocol/state and at least one claimed presented frame within 90 seconds. This is a health handshake from a trusted/independently tested payload, **not independent GPU certification**. No fake writer or mock implementation of this protocol was added to ASTRA. Current diagnostic binaries cannot pass the release gate and do not implement this contract. A surviving process alone is not accepted as readiness. The host records actual PID, lifetime and exit code; no fabricated GPU name/version is logged.

## 8. Python, Vulkan, application/system dependencies

Python: the native diagnostic main alone does not use Python, but the authoritative scientific engine includes Python components. Full production integration is unresolved. `python=none` must be justified by actual complete science tests; `embedded` means the builder supplies private CPython plus declared production packages/licenses and configures isolated embedding. The host removes inherited PYTHONPATH/PYTHONHOME and sets PYTHONNOUSERSITE, but this alone is not complete embedded isolation. It does not install pip or Python. No choice is falsely made in the blocked catalog.

Vulkan: the host checks for the system loader file only. Real physical-device/API/features/surface/device/presentation checks belong to the corrected production runtime. The loader file is **not proof of driver compatibility**. End users need the official GPU-vendor driver, not Vulkan SDK, vulkaninfo or glslangValidator. Build valid SPIR-V on the release machine and package it; never compile GLSL on the user's PC as a workaround.

Native DLL/CRT dependencies: inspect the actual final PE imports/transitive dependencies on Windows and bundle redistributable application libraries under their licenses. OS/GPU drivers are not copied. No Windows runtime or DLL audit has occurred here. The publisher evidence gate requires it before a ready catalog can be emitted.

Bootstrap .NET runtime: .NET SDK is a new **builder-only** dependency for this GUI host. Publish settings request the private .NET runtime in the host artifact. Windows single-file build/clean-machine launch, extraction behavior, licensing notices and dependency closure are **NOT VERIFIED**.

Supabase: no authentication or .env access in bootstrap code. Once installed, normal local launch performs no network request. Optional cloud/accounts remain inside the actual application. Local/offline scientific behavior still requires production verification.

Provisional host requirements: Windows x64, Windows 10 build 19041 or newer, user-writable LocalAppData, disk for download + extraction + retained versions, internet for first install/update. Production GPU/API/VRAM/minimum OS requirements are not yet established. Windows ARM64/x86 are rejected rather than silently assuming compatibility.

## 9. Build/release tooling — builders only

1. Repair/build/run the real native Windows production application; see the existing native blockers report.
2. Audit all runtime files and dependencies; produce the runtime ZIP with regular files only, no source-building scripts/toolchains.
3. Test readiness/userdata integration and clean-machine/offline behavior. Save a reviewed acceptance record tied to archive SHA-256.
4. On a build machine with Python 3.11+:

```text
python distribution/release_tools.py catalog --runtime <runtime.zip> --version <X.Y.Z> --python <none|embedded> --evidence <acceptance.json> --output <release.json>
python distribution/release_tools.py check <release.json> --runtime <runtime.zip>
```

5. On a Windows build machine with the .NET 8 SDK, run `distribution\build_bootstrap.cmd`. It publishes GUI host output to `dist/bootstrap`; it does not claim to build the native engine. Current SDK/build availability is BLOCKED here.
6. Review/sign the host, then assemble the tiny first-install ZIP:

```text
python distribution/release_tools.py bootstrap-zip --runtime <runtime.zip> --catalog <release.json> --host <published ASTRA COSMOS.exe> --evidence <acceptance.json> --output <ASTRA-COSMOS.zip>
```

7. Test that exact bootstrap ZIP/install/normal offline launch on Windows, then publish the immutable assets using GitHub Releases. The tools do not publish automatically; use `gh release create/upload` only for reviewed artifacts. No release/tag/asset was published in this turn.

The release tool's source guard blocks the existing diagnostic main, so these commands are not instructions to turn the existing mock into a valid release by filling out a form.

## 10. Failure experience and current gaps

Win32 message boxes show stage, actual available exception/Win32 error, safe recommended action and log location. Logs live in LocalAppData, not a protected install directory. Only curated metadata is logged; no environment dumps, credentials, signed CDN URLs or raw child output. The runtime must supply its own detailed renderer diagnostics and failure UI; a structured child failure protocol is not implemented yet. Network GUI progress/cancel UI is also not implemented; downloads are bounded by timeout but currently have no progress window.

First-click missing EXE in a source checkout produces a retained BAT message, never “CMake not found” or instructions to install Python. With a compiled host and blocked catalog it fails before download. No success message substitutes for a missing payload.

## 11. Clean-machine acceptance

**CLEAN-MACHINE TEST: NOT VERIFIED.** Windows C# compilation/execution, real download, extraction, transaction rollback and application launch have not run here. Linux Python archive-policy tests do not validate C# execution semantics.

Required Windows tests: missing/corrupt catalog; URL/redirect failures; partial download; archive hash mismatch; traversal/collision/symlink/bomb archives; wrong architecture/missing DLL; blocked runtime; concurrent launch; read-only extraction directory; LocalAppData permissions/disk exhaustion; interrupted update; initialization timeout; rollback; saves/config preservation; offline second launch; spaces/Unicode installation paths; real GPU/science/window lifetime/close. Repeat without Visual Studio/CMake/Ninja/Git/Python/Vulkan SDK/source/build environment.

Only that full acceptance run allows the simple download → extract → START → simulation claim to become a verified user instruction.
