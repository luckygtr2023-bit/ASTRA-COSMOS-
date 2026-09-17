# ASTRA self-bootstrap implementation report

Date: 2026-09-17

## Outcome

**Infrastructure implemented; final acceptance BLOCKED.** The source/development workflow and user distribution now have separate entry points. No end-user source compilation or toolchain installation is in the new START/bootstrap chain. No fake binary or ready runtime manifest was created.

**Windows x64 execution: NOT VERIFIED. Clean-machine test: NOT VERIFIED. Real GPU/scientific simulator: BLOCKED / NOT VERIFIED.**

## 1. Inspection before implementation

Rechecked the existing main's fixed diagnostic loop and RHI `Swapchain::create/acquire_next/present`: the swapchain remains mock and present is a no-op. Earlier reports document placeholder Vulkan devices, shader fallback failures and scientific integration gaps. Those production blockers are not repaired by this infrastructure.

The current environment remains Linux. No detected dotnet, CMake, Windows/MSVC or Windows GUI test environment was available. Therefore the C# host has not been compiled, downloaded a real runtime or launched a Windows process here. The user's latest request explicitly permits implementing infrastructure verifiable in this environment; that is the scope completed.

## 2. Exact files created

- `bootstrap/release.json`: schema 1 **blocked** catalog. No invented release assets, hashes or version.
- `bootstrap/src/Astra.Bootstrap.csproj`: Windows x64 GUI host, .NET 8 private runtime/single-file publish configuration.
- `bootstrap/src/app.manifest`: standard-user Windows application manifest.
- `bootstrap/src/Program.cs`: first install/update, offline normal launch, user-data directories, lock, readiness handshake, process lifecycle and error dialog/logging.
- `bootstrap/src/Release.cs`: catalog/path/size/version/URL/PE validation policies.
- `bootstrap/src/Installer.cs`: bounded HTTPS download, archive hash, constrained extraction, per-file integrity, side-by-side version preparation and atomic pointer promotion.
- `distribution/release_tools.py`: build-machine-only archive audits, reviewed acceptance/source gate, ready catalog generation, bootstrap ZIP assembly/checksum.
- `distribution/acceptance.template.json`: release-review gates defaulting to BLOCKED/NOT VERIFIED.
- `distribution/build_bootstrap.cmd`: builder-only .NET publish command; not a runtime source compiler or end-user script.
- `distribution/tests/test_release_tools.py`: portable adversarial archive/catalog and source-structure tests.
- `ASTRA_SELF_BOOTSTRAP_ARCHITECTURE.md`: implementation contract, release layout, security/trust limits, operator steps and acceptance plan.
- `ASTRA_SELF_BOOTSTRAP_IMPLEMENTATION_REPORT.md`: this report.

## 3. Exact existing files modified in this turn

- `START.bat`: no longer calls the source-building terminal script. It invokes the compiled GUI distribution host with `--update` or displays a clear missing-distribution message with pause.
- `scripts/terminal.bat`: added a developer-only designation; retained its existing developer mechanics.
- `scripts/tests/test_windows_bootstrap.py`: adapted root entry-point assertions while preserving tests for the separate developer script.
- `.gitignore`: exclude .NET bin/obj output, retain new distribution tests.
- `.gitattributes`: CMD build-script CRLF whitespace handling.
- `README.md`: current blocked release status, intended simple user flow clearly marked unverified, separate developer/release-builder instructions.
- `RELEASE_NOTES.md`: unreleased infrastructure section and explicit historical status for earlier release claims.

Existing scientific engine, physics, native implementation, Supabase, tests and assets were not replaced or removed. Earlier local changes/deletions remain untouched. No GitHub release/tag/asset or commit/push was performed in this turn.

## 4. Runtime/bootstrap/release architecture

The proposed shipped bootstrap ZIP contains only START.bat, the compiled GUI host named ASTRA COSMOS.exe, and pinned release metadata. It is not the repository archive. The real native/scientific payload will be a separate immutable Windows runtime ZIP in this repository's GitHub Releases, but it **does not yet exist**.

State lives in `%LOCALAPPDATA%\ASTRA COSMOS`: version directories keyed by version+full archive hash, current/previous manifests, per-user saves/config/screenshots/recordings/scenarios, logs and private staging. The downloaded runtime must have its own real `ASTRA COSMOS.exe` entry point; no renamed Linux file or legacy launcher substitution is allowed.

First setup uses the locally pinned catalog. Later direct GUI-host launch uses current.json and makes no network request. The bootstrap host remains the thin normal launcher; the simulator does not depend on a BAT file or developer tool.

## 5. Security/dependency strategy

Implemented in source:

- HTTPS only, exact repository/version asset URL, constrained manual redirect handling to GitHub and its release-assets host.
- Expected archive size, total extraction/file count limits, archive SHA-256 before parsing and per-file SHA-256 during extraction/launch validation.
- Relative safe Windows paths, reserved-name/ADS/traversal/case-collision/file-directory-collision rejection.
- Symlink/reparse/special-file rejection, create-new extraction and own random temporary directory.
- Known build tools and executable BAT/CMD/PS1/link payloads prohibited.
- PE32+ x64 image checks; only the fixed inventoried application entry point is launched, without shell interpretation.
- No environment dumps, credential requests, Supabase .env parsing or raw child-output logs.
- No administrator request, global dependency setup, system PATH mutation, downloaded-script execution or SDK installation.

The trust root is the initially trusted bootstrap/catalog download. No Authenticode signature, publisher key or signed automatic remote metadata-update channel exists yet. A same-channel checksum does not authenticate a compromised publisher. PE/header checks are not full Windows DLL audits. Same-user malicious write races are not solved by these checks. See the architecture document for limits.

The private .NET bootstrap runtime is requested in publish settings, **not audited in an actual binary**. Python remains an unresolved production integration decision: catalog must explicitly state none or embedded, supported by evidence. No private Python is invented/downloaded now. Vulkan loader-file presence is only a prerequisite check; actual GPU/API capability comes from the verified production runtime. The Vulkan SDK stays build-time-only.

## 6. Update, rollback and offline strategy

Immutable side-by-side extraction precedes any current-pointer change. Old selected runtime and user data remain intact if download, validation or startup fails. An exclusive session lock serializes game/update operations. After real runtime readiness, write/flush/replace the current manifest and retain previous.json. Explicit rollback validates and launches the previous payload before promotion. No save deletion, speculative migrations or automatic infinite relaunch loop.

Normal direct launch validates the installed inventory offline. Same pinned version/hash avoids reinstallation; same-version content change and automatic downgrade are rejected. START.bat provides the explicit bundled-catalog update path when the user extracts a newer trusted distribution. There is no unsigned remote latest feed or background auto-updater.

**Windows transactional/update/rollback behavior: NOT VERIFIED.** Portable tests inspect relevant C# source structure only; they do not execute filesystem promotion or simulate process crashes. A compiled Windows fault-injection suite is still required. Full inventory hashing can affect startup time; no performance claim is made.

## 7. Readiness, runtime status and actual remaining blockers

The host requires the future production runtime to honor `ASTRA_USER_DATA`, `ASTRA_READY_FILE`, `ASTRA_READY_NONCE` and emit protocol 1 readiness only after real presentation and authoritative science integration. It waits up to 90 seconds and distinguishes process creation from runtime attestation. No fake readiness writer was added to the existing engine.

This handshake is not independent verification of actual GPU rendering. The production release must first pass real Windows build/run/observe testing and artifact-specific review. Missing readiness leaves the prior selected version untouched and produces an error.

| Area | Status |
|---|---|
| Source/runtime distribution separation | VERIFIED by source inspection and portable assertions |
| Python archive/catalog policy tests | VERIFIED: 19 tests passed |
| Existing developer/bootstrap helper tests | VERIFIED: 13 tests passed |
| Native project static validator | VERIFIED: 221 OK, 0 FAIL |
| Checked-in catalog refusal | VERIFIED: checker returns 1 / BLOCKED |
| C# host compilation | NOT VERIFIED; .NET SDK not available |
| Windows bootstrap downloads/extraction/GUI/process lifecycle | NOT VERIFIED |
| Production Windows x64 runtime | BLOCKED; no verified binary |
| Real Vulkan, GPU, window and persistent native rendering | BLOCKED / NOT VERIFIED |
| Complete authoritative scientific integration | BLOCKED |
| Private Python packaging/embedding | BLOCKED pending integration decision |
| Complete Windows DLL/private-runtime dependency audit | NOT VERIFIED |
| GitHub binary release publication | BLOCKED; no asset uploaded |
| Offline installed application | NOT VERIFIED; only source control-flow checked |
| CLEAN-MACHINE TEST | NOT VERIFIED |
| Final download → extract → setup → simulation flow | BLOCKED |

## 8. Tests performed

```
python -m unittest discover -s distribution/tests -v
# 19 passed
python -m unittest discover -s scripts/tests -v
# 13 passed
python distribution/release_tools.py check bootstrap/release.json
# BLOCKED: no verified production runtime published; exit 1 (expected)
python native_renderer/tools/validate_native_project.py
# 221 OK, 0 FAIL
```

Archive/catalog tests include unsafe paths, ADS/reserved names, links/reparse records, directory entries, case collisions, file/directory conflicts, missing entry point, wrong PE architecture, DLL-as-EXE, ELF rejection, prohibited build tools/scripts, archive/per-file corruption, untrusted/version-mismatched URLs and acceptance-gate refusal. Test PE headers are synthetic byte fixtures in temporary archives only, never delivered or treated as a runtime. Test success is not C# runtime or Windows/GPU evidence.

The known diagnostic source gate is tested even with synthetic claimed acceptance, and refuses publication. This guard is deliberately specific to the known blocker, not a semantic proof of future production correctness.

## 9. Tests not performed / implementation gaps

No Windows build, real payload download, native GPU launch, clean Windows install, second offline launch, installed-root independence, executable checksum/signature/DLL audit, update interruption/rollback or Windows GUI failure test was possible here.

The host lacks a download-progress/cancel UI and GUI update/rollback controls beyond the first-click START path/explicit flags. It reports actual available exceptions and process codes, but the runtime-specific renderer failure-report protocol is not implemented. The production readiness/writable-state contract is not connected to current native code. Stale unreferenced versions are retained without automated garbage collection, and late application failures require explicit rollback. Cross-version save migration and signature key management are not implemented.

No usable end-user EXE/ZIP is created simply by checking in this infrastructure. Calling it working, production-ready, self-contained or portable would be unsupported.

## 10. Exact next actions

1. On an accessible Windows/MSVC/real-GPU environment, repair the existing native production path as documented in `ASTRA_WINDOWS_NATIVE_RUNTIME_BLOCKERS.md`; preserve scientific authority and explicitly isolate mocks to tests.
2. Integrate real scientific state, valid build-time SPIR-V/assets, private writable state and the readiness contract. Decide and implement any private Python embedding from actual production requirements.
3. Build the native x64 Release runtime and audit actual imports/dependencies/resources/licenses; test without globally installed developer software or Python.
4. Compile this host on Windows using the builder script; review compiler diagnostics, run archive and update fault-injection tests against the actual C# executable, and fix actual failures.
5. Record real acceptance evidence tied to the final runtime ZIP. Generate the pinned catalog using the release tools; do not manually claim missing checks succeeded.
6. Assemble/sign the bootstrap distribution, test first install and direct offline launch on a clean GPU-capable Windows machine, then publish versioned immutable GitHub assets.

Until then, the shipped catalog remains BLOCKED and the current mock/diagnostic native binary must not be packaged as production.
