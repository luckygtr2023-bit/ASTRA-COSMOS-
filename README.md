# ASTRA COSMOS

**Author:** Lucky Kumar  
**Copyright © 2026 Lucky Kumar**  
**Version:** 0.1.1 (astra-core) / 0.1.0 (native renderer) — **License:** Original work © 2026 Lucky Kumar; third-party retains respective licenses (see `COPYRIGHT.md`)

**Short description:** ASTRA COSMOS is a scientifically-authoritative space simulation and visualization platform. The Python scientific engine (`astra/`) owns truth (orbital mechanics, N-body, relativity, black holes, universe evolution) with deterministic double-precision and floating-origin. The native C++20/Vulkan 1.3 renderer (`native_renderer/`) visualizes without mutating science (HDR, GPU-driven, VFX, cinematic, extreme-scale performance). The Supabase product layer handles accounts/saves/preferences with RLS. The primary user-facing launcher is **`ASTRA COSMOS.exe`** → `native_renderer/astra_native`.

---

## Quick Start

### How to Build

**Requirements:** CMake 3.28+, Ninja, C++20 compiler (g++ 11+ / MSVC 2022), Vulkan-Headers (or Vulkan SDK), Python 3.11+, Supabase CLI (optional for product).

```bash
# Native renderer (Release, LTO, -O3)
cmake -S native_renderer -B /tmp/astra_build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/astra_build -j2
# Produces: /tmp/astra_build/astra_native (161K) and "/tmp/astra_build/ASTRA COSMOS.exe" (46K launcher)
# Verify shaders:
bash -c 'cd /home/user/ASTRA-COSMOS- && /tmp/astra_build/astra_native --headless'  # 23/23 shaders
# Or via launcher:
bash -c 'cd /home/user/ASTRA-COSMOS- && "/tmp/astra_build/ASTRA COSMOS.exe" --headless'

# Python engine
pip install -e .  # from pyproject.toml astra-core 0.1.1
pip install pytest supabase python-dotenv httpx  # dev
```

**Release build configuration (preferred):** `Release` `-O3` `-march=native` `-flto` (LTO where safe) — see `native_renderer/CMakeLists.txt`. No unsafe optimizations.

### How to Launch

**Primary launcher (Windows, also works on Linux for validation):**
```bash
# From release directory (clean install):
./"ASTRA COSMOS.exe"              # normal ASTRA runtime (opens window when GPU/display available)
./"ASTRA COSMOS.exe" --headless   # headless mock (CI, no GPU)
./"ASTRA COSMOS.exe" --benchmark  # 60 frames mock 5.2ms vs 16.6 budget
./"ASTRA COSMOS.exe" --help       # usage
```
The launcher:
- resolves its own install dir (`GetModuleFileNameA` on Windows, `/proc/self/exe` on Linux)
- uses relative paths (no hard-coded `/home/...`)
- locates `native_renderer/astra_native` + `shaders/common/common.glsl` + `assets/benchmark.json`
- supports spaces in paths (`"/tmp/test space/ASTRA COSMOS/ASTRA COSMOS.exe"`)
- avoids admin / protected dirs (`C:\Windows\`), works from normal user account
- preserves stdout/stderr, returns meaningful exit codes (0 OK, 1 missing files, 2 launch failed)
- checks dependencies and prints useful errors, does NOT contain second implementation — invokes real `astra_native`

**Direct (developer):**
```bash
/tmp/astra_build/astra_native --headless
/tmp/astra_build/astra_native --headless --benchmark
```

**Python engine standalone:**
```python
from astra.core.engine import Engine
from astra.core.config import Config
config = Config()
engine = Engine(config)
engine.initialize()
engine.start()
engine.step()
engine.stop()
```

### How to Run Tests

```bash
# Native renderer (91 tests, no GPU required)
pytest native_renderer/tests/ -q  # 91 passed: 21 native +18 audio +23 phase02_03 +29 phase04_05
python native_renderer/tools/validate_native_project.py  # 221 OK 0 FAIL

# Scientific engine (if astra installed)
pytest tests/ -q  # ~40 celestial/physics/nbody/orbital/mathematics etc.

# Headless renderer
/tmp/astra_build/astra_native --headless          # 23/23 shaders, no leaks
"/tmp/astra_build/ASTRA COSMOS.exe" --headless    # via launcher

# Supabase product (offline simulator)
# No live DB required; 28 product tests use mock when Supabase unavailable
```

### How to Use `ASTRA COSMOS.exe`

The exe is the **primary user-facing launcher**. On Windows, double-click `ASTRA COSMOS.exe` in `ASTRA-COSMOS/` or `release/ASTRA-COSMOS/`. On Linux, run `./"ASTRA COSMOS.exe" --headless` from install dir. It:

1. checks `native_renderer/shaders/common/common.glsl`, `native_renderer/assets/benchmark.json`, `astra/core/engine.py`, `bin/astra_native` relative to exe
2. initializes ASTRA (prints `[ASTRA COSMOS Launcher] v0.1.1`)
3. launches `astra_native` with forwarded args
4. preserves logs, returns native exit code

**Example release layout:**
```
ASTRA-COSMOS/
├── ASTRA COSMOS.exe          # launcher (46K)
├── bin/astra_native          # real renderer (161K)
├── native_renderer/shaders/  # 36 shaders (6 new comp)
├── native_renderer/assets/   # benchmark.json, star_temperature_lut.ppm 16x256
├── astra/                    # Python engine
├── documentation/            # ASTRA_COSMOS_COMPLETE_PROJECT_SUMMARY.md etc.
└── shaders/assets symlinks (release/ASTRA-COSMOS/)
```

Do not write into `C:\Windows\` or `C:\Program Files\Windows*`; normal user account suffices.

---

## Requirements

- **OS:** Windows 10/11 (primary, exe) or Linux (validation, ELF named .exe)
- **CPU:** x86_64, C++20
- **Build:** CMake 3.28, Ninja, g++ 11+ or MSVC 2022, Threads
- **Python:** 3.9+ (3.11 tested), `supabase>=2.0`, `python-dotenv`, `httpx`, `pytest`
- **Vulkan:** Vulkan 1.3 headers at `/home/user/Vulkan-Headers` (fallback) or Vulkan SDK `libvulkan1` + validation layers; headless mock works without GPU
- **Supabase:** Project `https://bzfpipxjqdrinvagojor.supabase.co` publishable `sb_publishable_WHOOXEK74ZpxJ0cmR2vysA_cBu7EphG` (publishable only, no service_role in repo), local `supabase/config.toml` ports 54321/54322/54323 if running locally

## GPU Requirements

- **Minimum (LOW 30 fps mock):** Intel UHD or equivalent, headless mock works; real GPU not required for CI
- **Recommended (ULTRA/CINEMATIC 60 fps mock target):** RTX 40 series, driver 570.65+, Vulkan 1.3, 8–24GB VRAM, HDR display for bloom
- **Not verified in CI:** Real Vulkan loader `libvulkan.so`, `vulkaninfo`, physical device enumeration, `VkQueryPool` timings, RenderDoc, Tracy GPU zones — all marked **NOT VERIFIED** (headless mock `RTX 4090 Mock VRAM 24564` only). See `ASTRA_COSMOS_COMPLETE_PROJECT_SUMMARY.md` §§L,23-27.

## Hardware Limitations

- Headless CI is mock: `Benchmark 60 frames simulated 5.2ms` mock, not GPU; `FPS 60` via `Telemetry` is mock
- `ASTRA COSMOS.exe` built as ELF named `.exe` on Linux for validation; true Windows PE cross-compile `x86_64-w64-mingw32-g++` **NOT VERIFIED** (no mingw in CI) — logic verified on Linux, PE requires Windows build env
- Tracy/RenderDoc not installed in CI (only `src/profiling/tracy.cpp` source), no `.rdc` capture
- Supabase local not running in CI (offline simulator)
- No Godot/Blender dependency (intentionally), no `VK_EXT_mesh_shader` tested, FSR2 is scaffolding (258w fallback copy, not real temporal upscaling)
- See `COPYRIGHT.md` for third-party licenses, `ASTRA_FINAL_RELEASE_AUDIT.md` for full audit

---

## Documentation

- **Complete summary:** `ASTRA_COSMOS_COMPLETE_PROJECT_SUMMARY.md` (20 sections A–T, whole project)
- **Phase reports:** `ASTRA_PHASE_01_NATIVE_RENDERING_REPORT.md`, `ASTRA_PHASE_02_03_IMPLEMENTATION_REPORT.md`, `ASTRA_PHASE_4_5_IMPLEMENTATION_REPORT.md`
- **Supabase:** `ASTRA_SUPABASE_IMPLEMENTATION_REPORT.md`
- **Audit:** `ASTRA_FINAL_RELEASE_AUDIT.md`, `AUDIT_REPORT.md`
- **Core contract:** `CORE_CONTRACT.md`, `ASTRA_CORE.txt`

## Copyright

Copyright © 2026 Lucky Kumar — see `COPYRIGHT.md` (original work protected, third-party retains respective licenses).

## ASTRA CORE (Foundational)

*Original section preserved:* ASTRA CORE provides infrastructure for mathematics, physics, motion, spacetime, astronomy, celestial, cosmology, observation, rendering, graphics, UI, backend/integration.

```bash
pip install -e .
```

See `CORE_CONTRACT.md` for API contract.
