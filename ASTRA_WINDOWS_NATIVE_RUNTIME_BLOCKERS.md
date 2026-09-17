# ASTRA Windows native runtime — blockers

Date: 2026-09-17

## Status: STOPPED at the required Windows execution gate

The user explicitly requires stopping if Windows execution is unavailable. That condition is confirmed. **No native implementation changes, Windows executable, launcher or package were produced in this turn.** Existing scientific systems, native source, tests and prior startup files were preserved.

No claim is made that ASTRA runs as a real Windows production simulator.

## 1. Exact missing Windows capability

Actual project root: `/home/user/ASTRA-COSMOS-`.

The host reports Linux x86-64 (`uname -a`: Linux e2b.local, kernel 6.1.158+). This is not a Windows build or GUI-test environment.

The following executable-discovery checks returned no path:

```sh
command -v cmd.exe
command -v powershell.exe
command -v wine
command -v wine64
command -v cl.exe
command -v MSBuild.exe
command -v dumpbin.exe
command -v cmake
```

Consequently:

- No usable Windows CMD/MSVC/MSBuild toolchain was detected.
- No usable Windows SDK build environment was established.
- No Windows execution environment was detected, including Wine.
- No interactive Windows desktop/GPU session is available through this workspace for verifying window creation and presentation.
- There is no observed Windows GPU name, Vulkan driver version, swapchain result, frame count, process lifetime or shutdown code to report.

These are limitations of the current execution environment, not instructions for final users to install developer tools. They also are not a new observed failure on the user's Windows PC.

## 2. Why the current native program exits immediately

Confirmed source: `native_renderer/src/main.cpp`.

| Location | Behavior |
|---|---|
| Line 52 | Existing native `main()` |
| Lines 53–62 | Parses flags and prints startup diagnostics; normal mode is still the same diagnostic body |
| Line 153 | Fixed `for(int i=0;i<120;i++)` loop, not a window-lifetime event/render loop |
| Lines 325–334 | Audio/resource/RHI shutdown after finite subsystem checks |
| Lines 335–337 | Computes diagnostic `all_ok`, prints shutdown result and returns |

There is no persistent application lifetime in this entry point. Removing the final return or adding a sleep would not create a real window, GPU rendering, or scientific integration.

**Prior-turn execution evidence, not rerun or Windows verification in this turn:** the existing packaged Linux binary was invoked without flags from the project root. It exited with code 0 after approximately 0.059 seconds, printed mock Vulkan device/swapchain messages, and reported a missing `/tmp/glslangValidator`. Details are in `ASTRA_WINDOWS_RELEASE_REPORT.md`. The finite source flow explains this observed lifetime; the zero diagnostic exit is not production readiness.

## 3. Exact mock-runtime locations

All line references below are to the inspected working tree and may move after edits.

### `native_renderer/src/rhi/vulkan_rhi.cpp`

| Location | Missing real implementation / mock behavior |
|---|---|
| `VulkanInstance::create()`, line 10 onward | Marks the instance valid; `vkCreateInstance` appears as a comment/intention rather than an actual call |
| `PhysicalDeviceSelector::enumerate()`, line 40 onward | Constructs mock GPU candidates instead of enumerating physical devices |
| `LogicalDevice::create()`, line 73 onward | Supplies placeholder queue handles rather than creating a Vulkan logical device and obtaining queues |
| Command pool code, around lines 100–108 | `vkCreateCommandPool` is a comment; mock success remains |
| `Swapchain::create()`, line 138 onward | Logs a mock swapchain instead of creating a real swapchain and images |
| `Swapchain::acquire_next()`, line 150 | Returns a stored image instead of acquiring a swapchain image with Vulkan synchronization |
| `Swapchain::present()`, line 151 | No-op; does not present to a window |
| Render-target code, around line 161 | Mock resource behavior |
| Shader code, lines 203–232 | Shell compiler invocation, static fallback/mock module, and commented-out `vkCreateShaderModule` |
| Pipeline code, around line 253 | Mock graphics pipeline path |
| RHI initialization, around line 379 | Hard-coded mock queue-family indices |
| RHI initialization, lines 390–391 | Passes `VK_NULL_HANDLE` as surface; swapchain failure can set headless fallback |

### `native_renderer/src/rhi/vulkan_rhi.h`

- Lines 18–46 select `ASTRA_HAS_VULKAN` based on whether Vulkan headers can be included.
- Around line 459, `has_vulkan_` derives from that header flag. This is not a driver/device initialization result.
- Line 272 defaults the shader compiler to `/tmp/glslangValidator`.

Production must not interpret header availability, placeholder handles, static shader checks, or mock device names as a real initialized backend. Mocks can remain behind explicit test/headless selection, but cannot be production fallback.

## 4. Production-entry-point findings

### Native CMake application

`native_renderer/CMakeLists.txt`, around line 119, declares `astra_native` using `src/main.cpp`, linked with `astra_renderer` and threads. This is the actual existing application target; its current body is the finite diagnostic flow described above.

The separate `astra_launcher` target compiles `native_renderer/launcher/launcher.cpp`. That file is a process wrapper, not an alternative renderer. Connecting or recompiling it cannot supply missing Vulkan/window/science behavior.

### Window-system support

CMake currently discovers GLFW through `pkg-config` and conditionally links the reported GLFW libraries. It also probes SDL3, but this does not establish an implemented window loop. Prior repository search and source inspection did not locate a complete native window creation/real Vulkan presentation implementation to connect instead of the mock RHI.

GLFW is therefore an existing architectural dependency candidate, not a currently verified Windows window implementation. Its Windows package discovery/linkage must be made explicit and tested rather than assuming Linux pkg-config discovery works under MSVC.

### Other visualization implementation

The repository contains a Godot project at `visualization/godot/project.godot`, not merely empty visualization documentation. It has phase scenes, shader resources and a GDExtension source skeleton.

The previously inspected `visualization/godot/phase_01_foundation/scripts/astra_bridge.gd` reads a file bridge and returns an explicitly labeled offline interaction echo. The extension manifest references a Windows DLL absent from the inspected tree. No verified complete alternative production deployment was found. This project must not be silently substituted for the requested existing native application.

### Scientific authority

Authoritative scientific systems exist under `astra/`, including the Python engine. The inspected native main demonstrates local C++ scene/subsystem checks; it does not establish a complete connection to the Python scientific engine.

A native diagnostic executable running without Python does not prove complete production science can run without a Python runtime. Production needs a verified RenderState/Visualization API integration contract, including lifecycle and transport/embedding where appropriate. Renderer-generated demonstration values or a static bridge file cannot be promoted to scientific authority.

## 5. Exact shader/resource blockers

- `vulkan_rhi.h:272` hard-codes `/tmp/glslangValidator`.
- `vulkan_rhi.cpp:203–204` invokes that tool through a shell at runtime and writes `/tmp/astra_shader.spv`.
- Compiler failure can enter a static text check and produce a mock module containing only the SPIR-V magic word.
- `vkCreateShaderModule` is not actually invoked in the inspected shader path.
- The native main uses source-layout `native_renderer/shaders/...` filenames.
- CMake's shader commands around lines 138–157 have no consuming shader build target/dependency that ensures the executable build produces those outputs.
- CMake installs shaders/assets under `share/astra`, which does not match the current native lookup paths.
- Existing graphics/compute pipelines and descriptors are not a validated real Vulkan implementation.

Therefore the work is not just finding the shader compiler. Build-time valid SPIR-V, actual module/pipeline creation, descriptor compatibility, resource uploads and consistent runtime resource lookup must all be implemented and tested. Known-invalid/mock shader fallback must be fatal in production.

## 6. Exact commands for the Windows build environment

These are **builder commands**, not target-user runtime requirements. They describe how to build the existing target and later validate the corrected implementation. **Running them against the current source does not turn its mock runtime into production.** They were not executed here.

Prerequisites on a Windows development/test machine:

- Visual Studio 2022 with Desktop development with C++, MSVC x64 tools and Windows SDK.
- CMake 3.28 or newer.
- A Vulkan SDK for development/build-time shader tools and headers.
- A Vulkan-capable GPU with the official vendor driver for real runtime tests.
- A Windows-compatible GLFW dependency, integrated into CMake before the real-window implementation can build.

Open an **x64 Native Tools Command Prompt for VS 2022**, then:

```bat
rem Set this to the actual checkout location; no particular drive is required.
set "ASTRA_SOURCE=C:\path\to\ASTRA-COSMOS-"
cd /d "%ASTRA_SOURCE%"

where cl.exe
where link.exe
where dumpbin.exe
where cmake.exe
cmake --version
where glslangValidator.exe
where vulkaninfo.exe

rem This is a driver diagnostic, not proof the ASTRA renderer works.
vulkaninfo.exe --summary

cmake -S native_renderer -B native_renderer\build-windows-production -G "Visual Studio 17 2022" -A x64 -DCMAKE_CONFIGURATION_TYPES=Release -DASTRA_BUILD_LAUNCHER=OFF -DASTRA_BUILD_TESTS=OFF -DASTRA_BUILD_TOOLS=OFF -DASTRA_ENABLE_VULKAN=ON
cmake --build native_renderer\build-windows-production --config Release --target astra_native --parallel 2

dumpbin /headers "native_renderer\build-windows-production\Release\astra_native.exe"
dumpbin /dependents "native_renderer\build-windows-production\Release\astra_native.exe"

rem Only an acceptance test after replacing the production mock path.
"native_renderer\build-windows-production\Release\astra_native.exe"
echo Native process exit code: %ERRORLEVEL%
```

`ASTRA_ENABLE_VULKAN=ON` currently is not a production-readiness guarantee. The implementation must enforce real backend selection independently of the existing header flag. GLFW/resource/shader dependency options must be added to the build commands when their actual supported CMake integration is implemented; no nonexistent package configuration is represented here as already working.

## 7. Remaining implementation work — before any packaging

1. **Separate diagnostic and production execution.** Preserve existing checks for explicit tests/headless use. Make production reject unavailable real Vulkan/window initialization, with no mock fallback.
2. **Window lifecycle.** Integrate the existing GLFW direction with MSVC CMake discovery. Create the ASTRA window with no OpenGL context, obtain required Vulkan instance extensions, create its Vulkan surface, and handle input, resize, minimization and close requests.
3. **Instance and physical device.** Create a real Vulkan instance; enumerate devices; validate required API version, queue families, surface support, extensions and features. Report actual VkResult/device data, not hard-coded names.
4. **Logical device/resources.** Create the device/queues, swapchain, image views, render targets and required GPU memory/resources. Use valid object handles and explicit ownership.
5. **Synchronization and presentation.** Implement command pools/buffers, image acquisition, semaphore/fence synchronization, submissions and presentation. Handle out-of-date/suboptimal swapchains and device loss; recreate resources safely on resize.
6. **Real ASTRA drawing.** Connect real pipelines/descriptors/buffers/textures to existing scene/material systems. A clear-color window or triangle alone does not meet the requested visible ASTRA simulation criterion.
7. **Scientific integration.** Feed renderer state from the existing authoritative engine/Visualization API. Define transport/embedding and ownership, apply commands through science validation, and prove state updates are scientific results rather than replacement placeholder data. Preserve optional Supabase/offline startup.
8. **Shader/assets.** Add a required build-time shader target with validated SPIR-V and dependencies; load actual binary modules/resources using consistent paths. Match descriptor layouts and pipeline interfaces; remove production runtime shell/compiler and mock fallbacks.
9. **Persistent loop.** Poll events and consume scientific render-state updates while the window is open; acquire, record, submit and present real GPU work. Do not use a fixed diagnostic iteration count as production lifetime.
10. **Shutdown/error lifecycle.** Wait for appropriate GPU work, destroy owned resources in dependency order, shut down the scientific connection, and exit cleanly on window close. Preserve stage/VkResult/system-error diagnostics on failures.
11. **Windows verification.** Build and run on Windows with the real driver, record GPU/API/window/render/science/resource results and process lifetime. Only after those gates pass should launcher/deployment work begin.

## 8. Required acceptance record — currently NOT VERIFIED

| Check / measurement | Current result |
|---|---|
| Windows x64 Release `astra_native.exe` built from corrected source | NOT VERIFIED / not built |
| Native process starts on Windows | NOT VERIFIED |
| Real ASTRA window appears | NOT VERIFIED |
| Real Vulkan instance/device/surface/swapchain | NOT VERIFIED |
| Actual GPU name and Vulkan API/driver version | NOT OBSERVED |
| Valid real shaders/assets load | NOT VERIFIED |
| Persistent acquire/submit/present loop | NOT VERIFIED |
| Authoritative ASTRA scientific simulation visible and updating | NOT VERIFIED |
| Windows process lifetime | NOT MEASURED |
| Window close and clean shutdown exit code | NOT MEASURED |
| Production mock fallback disabled | NOT IMPLEMENTED in this turn |
| Launcher/package | NOT CREATED; intentionally deferred |

A future test must keep the window open long enough to observe repeated real frames and scientific state updates, exercise resize/minimize/restore, and close it normally. Record actual evidence, not merely process creation or exit 0. Diagnostic/CI tests remain useful but cannot satisfy these production checks.

## 9. Changes and conclusion

This turn rechecked the Windows capability gate and source locations, then stopped as instructed. It created this blocker report only. No engine/renderer was rewritten without the required Windows build/test capability. No existing Linux binary was renamed or packaged.

**Required next environment:** an accessible Windows x64 MSVC build environment plus an interactive Vulkan-capable GPU test session. If a complete real runtime exists outside this checkout, supply its source so it can be connected rather than rewritten. Otherwise the implementation work above is genuinely missing and must precede packaging.
