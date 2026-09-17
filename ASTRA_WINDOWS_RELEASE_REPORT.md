# ASTRA Windows distributable release report

Date: 2026-09-17

## Release decision: BLOCKED — no distributable produced

**The requested success condition has not been met.** No `dist/ASTRA COSMOS.exe` was created. No existing diagnostic binary was renamed, substituted, wrapped or represented as the complete production simulator. No new BAT launcher, shortcut or terminal-only EXE was created.

There are two independent blockers:

1. This execution environment is Linux x86-64. CMake, MSVC, Visual Studio/MSBuild, Windows SDK tools, a Windows cross-compiler, Windows CMD and Wine were not found in the inspected environment. `cmake --version` actually failed with command-not-found, exit 127. The requested Windows/MSVC build cannot run here as currently provisioned.
2. The inspected native application is a finite diagnostic program with mocked Vulkan instance/device/swapchain behavior, not a verified persistent production simulator. Packaging it as the requested complete application would misrepresent its behavior. Obtaining a Windows compiler alone would not implement missing runtime behavior.

These findings do not diagnose a new error on the user's Windows PC. The previous user-observed policy failure and the tests below are separate evidence.

## 1. Inspection scope and project inventory

Actual root: `/home/user/ASTRA-COSMOS-`.

Enumerated repository component trees and inspected build targets, launchers, native main/RHI/shader paths, packaging layout, Python metadata/product integration, and alternative visualization configuration/bridge. This is not a claim that every scientific source line was audited.

| Component | Files enumerated, excluding Python bytecode caches | Findings |
|---|---:|---|
| `astra/` | 234 | Python scientific engine, simulation systems, product integration |
| `native_renderer/` | 197 | C++20 native target, RHI, shaders, assets, tests/tools, retained legacy launcher source |
| `visualization/` | 137 | Godot project, GDScript bridge, GDExtension source, shaders/assets/tools; not merely an empty placeholder |
| `supabase/` | 3 | Configuration and SQL migrations |
| `release/` | 360 | Previous staged tree, Linux native artifact/static library, Python source copy, assets/shaders/docs/config |
| `tests/` | 78 | Existing scientific/product tests |
| `scripts/` | 3 | Existing BAT bootstrap, Python metadata checker, portable bootstrap tests |

CMake files: `native_renderer/CMakeLists.txt`, `native_renderer/tests/CMakeLists.txt`, `native_renderer/tools/CMakeLists.txt`. No CMake presets or Windows deployment audit pipeline was found. Existing `native_renderer/toolchain-zig-windows.cmake` is a cross-build attempt, not an installed compiler or verified production build.

No `.exe`, `.dll` or `.spv` files were found in the inspected working tree. The obsolete wrapper EXEs were already removed by the previous change; they were not restored. The native Linux artifact remains intact.

## 2. Native source evidence

### Production target name

`native_renderer/CMakeLists.txt` defines `astra_native` from `src/main.cpp`, linked to the `astra_renderer` static library and threads. The optional legacy `astra_launcher` target is distinct. The launcher target is not the simulator.

### Finite entry point, not persistent windowed readiness

`native_renderer/src/main.cpp`:

- Defines the native `main()` at line 52.
- Parses `--headless`, `--benchmark`, `--validate`, but normal mode still follows the diagnostic body.
- Runs `for(int i=0;i<120;i++)` at line 153.
- Performs subsystem demonstrations/checks, shuts down audio/RHI and returns at lines 325–337.
- Computes final success using floating-origin/hierarchy/relative-position and shader checks, not proof of a window, real Vulkan rendering or complete scientific engine integration.

A search of native source and legacy launcher for `CreateWindow`, `glfwCreateWindow`, `SDL_CreateWindow`, actual `vkCreateInstance(...)`, `vkCreateDevice(...)` and `vkQueuePresentKHR(...)` call patterns found no matching implemented calls. This search supports, but does not replace, the inspected RHI implementations.

### Vulkan success is mocked

`native_renderer/src/rhi/vulkan_rhi.cpp`:

- `VulkanInstance::create()` marks itself valid without calling `vkCreateInstance`.
- Physical-device enumeration creates named mock candidate entries, including `RTX 4090 Mock`.
- Logical device/queue creation uses placeholder handles rather than a Vulkan device initialization sequence.
- Swapchain diagnostics explicitly report mock Vulkan behavior.

`ASTRA_HAS_VULKAN` in `vulkan_rhi.h` is derived from header availability. It is not proof that a Vulkan loader, real driver/device or presentation path has initialized. Compiler/header availability must not be used as the production release gate.

## 3. Actual execution performed — existing Linux diagnostic only

Executed the existing packaged artifact with **no arguments**, from the project root, using a 20-second subprocess timeout:

```
/home/user/ASTRA-COSMOS-/release/ASTRA-COSMOS/bin/astra_native
```

Observed result:

| Measurement | Result |
|---|---|
| Artifact | Existing Linux ELF; not built in this turn |
| Native exit code | 0 |
| Elapsed wall time | Approximately 0.059 seconds for this run |
| Captured stdout | 160 lines |
| Captured stderr | 0 lines; shader shell command redirects its own errors into stdout |
| Persistent simulator | Not established; process terminated |
| Windows execution | Not performed |
| Real GPU initialization | Not verified |

Selected actual output:

```
sh: 1: /tmp/glslangValidator: not found
[ASTRA Native] C++20 Vulkan 1.3 Phase01+Audio headless=0 benchmark=0
[PhysicalDevice] enumerated 3 candidates (mock)
[PhysicalDevice] picked RTX 4090 Mock VRAM 24564 score 100
[Swapchain] create 1920x1080 HDR=1 images=3 (mock Vulkan)
[Shader] compiled 23 ok 0 fail (glslangValidator /tmp/glslangValidator)
[ASTRA Native] OK Phase01+Audio shutdown ok (shaders 23/23)
```

The apparent shader/exit success is not evidence of compiled, usable SPIR-V: the inspected shader implementation accepts a static fallback after compiler failure. This run demonstrates why a wrapper must not promote code 0 to “production simulator running.” It was an investigative diagnostic test, **not the requested release launch test**.

## 4. Existing binary format/dependencies

Inspected artifact: `release/ASTRA-COSMOS/bin/astra_native`.

- Size: **164344 bytes**.
- Magic: **7f 45 4c 46**, Linux ELF, not PE.
- SHA-256: `93397878054b07278af98b5d62e345f1e0e96145e3f6e572aa19678af7635e12`.
- `readelf -d` reports `libstdc++.so.6`, `libm.so.6`, `libgcc_s.so.1`, `libc.so.6` as direct NEEDED entries.
- These are Linux dependencies, **not a Windows DLL dependency audit**.
- No Windows runtime EXE/import table was produced, so Windows missing DLLs and transitive dependencies remain unknown.

## 5. Shaders, assets and deployment paths

The native asset tree includes benchmark JSON data and a star-temperature LUT. Native GLSL shaders and the previous staged asset/shader copies exist. No precompiled `.spv` payload was found.

Current source is not deployment-independent:

- `main.cpp` requests source-layout `native_renderer/shaders/...` paths.
- `ShaderManager` defaults to `/tmp/glslangValidator`.
- Runtime shader compilation uses `std::system` and `/tmp/astra_shader.spv`.
- Failed compilation can yield a single SPIR-V magic word as a mock module rather than a usable compiled shader.
- CMake declares shader custom commands, but no shader target/dependency connects those outputs to the native executable build.
- CMake installs shaders/assets under `share/astra`, while the runtime's inspected lookups use the source layout.

A real release must compile/validate shaders at build time, make runtime loading consume the packaged binaries, and establish consistent installation-relative resource paths. Copying GLSL beside an EXE would not repair these runtime assumptions. No development-only shader compiler was bundled as a substitute.

## 6. Python and the complete scientific application

Important distinction:

- The **current native diagnostic entry point** does not embed/start Python. It does not require installed Python merely to run its C++ diagnostic path.
- The repository's authoritative scientific engine is also implemented under **`astra/` in Python**. No inspected native-main path starts or embeds that engine as a complete interactive scientific application.
- Therefore “the diagnostic runs without Python” does **not** prove that all production scientific functionality is preserved in a Python-free deployment.

`pyproject.toml` declares Python >=3.9 with setuptools/wheel and `supabase`, `python-dotenv`, `httpx` dependencies. A complete release needs a verified integration boundary and, if Python scientific modules execute in production, a bundled Python runtime/dependency strategy. Removing those modules to obtain a smaller native EXE would violate the preservation requirement and was not done.

## 7. Alternative visualization inspected, not substituted

There is a real `visualization/godot/project.godot`, with a phase-one main scene and Godot 4.4 Forward+ configuration. Earlier descriptions of `visualization/` as only a placeholder were incomplete.

However, the inspected autoload `phase_01_foundation/scripts/astra_bridge.gd` reads a file bridge and returns an explicitly labeled offline interaction echo. The GDExtension source describes a CPU fallback/compute skeleton. Its extension manifest names a Windows DLL that is absent from the tree. No Godot executable or Windows export package was found in this environment.

No verified alternative complete production package was located. Exporting a visualization scene as a substitute for the requested native simulator would be a change of application architecture and would not establish the requested scientific integration. It was not done.

## 8. Supabase

`astra/product/integration.py` treats account/cloud functionality as optional and leaves the engine available when the product layer is offline. No credentials were changed or exposed. Native diagnostic main does not authenticate with Supabase.

Intended release requirement: local simulation starts without `.env` or Supabase. **Clean release behavior is not tested**, because there is no release artifact. The report does not elevate the current offline source design to a clean-machine test result.

## 9. Requested build configuration versus actual build

| Item | Requested/intended | Actual result |
|---|---|---|
| Target OS | Windows | Host is Linux |
| Architecture | x64 | No Windows artifact produced |
| Configuration | Release | No Windows configure/build completed |
| Language | C++20 | Existing target declares C++20 |
| Compiler | MSVC / Visual Studio with Windows SDK | Not found here; GNU g++ exists but is not MSVC |
| CMake | >=3.28 | `cmake --version`: command not found, exit 127 |
| Launcher path | `dist/ASTRA COSMOS.exe` | Not created |
| Native runtime path | Deployment runtime directory / `astra_native.exe` | Not created |
| EXE size | Measured after build | N/A — no EXE |
| Packaged files | Audited runtime/assets/shaders/config | No new deployment produced |
| DLL imports / architecture audit | PE x64 plus transitive dependencies | Not possible without output |
| Reproducible release build scripts | Configure/build/package/audit/test | Not created as a claimed working pipeline; production payload prerequisite is blocked |

No unrelated compilers/installers were downloaded. Cross-compiling the known mock program would still fail the production-success criterion and would not satisfy the requested MSVC/Windows verification.

## 10. Runtime dependency policy — requirements, not verified claims

| Dependency | Intended final user requirement | Verification |
|---|---|---|
| CMake, Ninja | Build-time only | No final deployment to audit |
| Visual Studio/MSVC/Windows SDK headers | Build-time only | No final deployment to audit |
| Git/source/build tree | Not required | Not verified outside checkout |
| Python installation | Not required on target PC; embed runtime if production science needs it | Integration/embedding unresolved |
| VC++ runtime | Static CRT or licensed, audited app-local/redist deployment as appropriate | No MSVC binary/imports to choose or audit |
| Vulkan driver | System GPU-vendor driver with required capabilities | Not verified; an application EXE cannot replace it |
| Vulkan loader | Must be compatible/available; distribution strategy requires review | No real device initialization verified |
| Vulkan SDK development tools | Not a launch requirement | Current shader compiler dependency must be removed from runtime |
| Supabase / `.env` | Optional for local simulation | Offline source exists; clean release not tested |

No “self-contained” or “portable” certification is made. No runtime dependency list is declared complete without a produced PE and isolated test.

## 11. Tests and verification levels

Executed:

- Repository/component/build/source inspection described above.
- Existing Linux packaged artifact run with no flags: exit 0 in ~0.059 s, explicit mock output and missing shader compiler, not a persistent production app.
- Existing ELF magic/hash/size and dynamic dependency inspection.
- `cmake --version`: failed with exit 127; compiler configuration/compilation never began.
- `python -m unittest discover -s scripts/tests -v`: **13 passed**, existing BAT source/helper checks only.
- `python native_renderer/tools/validate_native_project.py`: **221 OK, 0 FAIL**, a static validator, not a build/GPU acceptance test.

Not performed / **NOT VERIFIED**:

- Windows native/launcher compilation and PE dependency audit.
- Windows EXE launch, actual window appearance or readiness.
- Clean Windows machine without developer tools, source tree and installed Python.
- Vulkan physical-device creation, swapchain presentation, genuine shader/asset load and production simulation start.
- Installer/single-file extraction, code signing, app-local runtime redistribution and distribution licensing audit.

The existing Linux run was from the source checkout and is **not clean-environment or portability verification**.

## 12. Exact remaining blockers and safe next step

1. **Build execution:** provision a Windows x64 build/test environment with MSVC, Windows SDK and CMake. These are builder requirements, not requests for end users to install build tools.
2. **Production payload:** supply the actual complete native runtime if it exists outside this checkout, or complete the existing native renderer/application integration. The inspected main/RHI is diagnostic/mock, so this is beyond a packaging-only correction.
3. **Science integration:** establish which authoritative Python functionality the native production app runs; bundle it if required rather than silently omitting it.
4. **Resource delivery:** real build-time SPIR-V compilation, runtime binary loading, installation-relative resources and dependency inventory.
5. **Acceptance:** verify one-click launch, real simulation/window/GPU readiness, then clean-machine runtime portability before distributing a package.

**No completion claim:** the EXE does not exist, no self-contained build was certified, and no production Windows launch occurred. Work this turn produced this evidence/report and a README release-status correction only; existing scientific/native/product code and prior launcher changes were preserved.
