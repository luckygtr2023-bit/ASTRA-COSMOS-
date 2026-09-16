# ASTRA COSMOS — Release Notes

**Release:** 0.1.1 (astra-core 0.1.1, native renderer 0.1.0) — **Date:** 2026-09-17 — **Branch:** `arena/01a0a5a2-astra-cosmos`  
**Author:** Lucky Kumar — **Copyright © 2026 Lucky Kumar** — **Build:** CMake 3.28 / Ninja / C++20 / Vulkan 1.3 Release -O3 LTO  
**Launcher:** `ASTRA COSMOS.exe` (46K) → `native_renderer/astra_native` (161K)

---

## Major Capabilities

### Scientific Engine (Authoritative, Python `astra/`)
- Deterministic Engine tick 42, SimulationClock, EventBus, DeterministicRNG seed 0xA573, floating-origin 5 scales 1e3..1e26
- Domain: celestial hierarchy, physics/motion, orbital/Kepler/N-body, relativity/GR, black holes (Schwarzschild/Kerr), spacetime, world/scene, destruction/impact, universe evolution, ingestion (archive queries), temporal/causal, interaction/exploration
- Provenance `Provenance {object_id,dataset,transformation,license}` + `validate_label()` REAL/THEORETICAL/SPECULATIVE/CINEMATIC

### Native Renderer (Product, C++20 Vulkan 1.3 `native_renderer/`)
- RHI thin wrapper instance→physical→logical→queues→command pools→sync→swapchain 1920x1080 HDR→descriptors→pipelines→SPIR-V 23/23 shaders (36 total, 6 new comp) via glslangValidator 11:16.6.0
- Foundational: planetary LOD MAX_LOD 12 SSE 1.5 crack-free, atmosphere Rayleigh/Mie earth/mars/venus, stars 1e12/1e10/1e9 indirect, rings Cassini 0.46, nebulae, galaxies, clusters deterministic 0xA573, deep-space filaments
- Extreme Physics: black hole photon 44310 shadow 76804 isco 88620 deflection 0.5908 theoretical, lensing, accretion disk, relativistic Doppler, spacetime grid, wormhole SPECULATIVE warp, plasma magnetosphere jets
- **GPU VFX (Phase4):** 1M particles SSBO triple/ring deterministic drag 0.02, solar flare 1e25J/1e7K, CME, aurora 557.7nm, jet Doppler g, destruction 10-stage smoke only with atmosphere, volumetrics 64 slices 0.32ms temporal empty_skip
- **Cinematic (Phase4):** 7 camera modes FREE..CINEMATIC bookmarks spline FOV 60 exposure 1.1, timeline deterministic 4 keys, time separation scientific 1234.5 vs cinematic 100
- **Audio:** Cosmic Audio mock-headless 4 sources (earth REAL_ACOUSTIC, pulsar REAL_SIGNAL_SONIFICATION, black hole PHYSICALLY_MODELED, wormhole SPECULATIVE), 7 Truth classifications, vacuum honesty, SOHO/GONG, 299792458 doppler
- **Performance (Phase5):** HLOD LOD0-4 cluster 32 dither 0.2s, GPU memory Budget 8 types pressure 0.73, 8-level streaming Universe→Local priority 18.18 mip 1 fallback 1x1 magenta, async 4MB fences/timeline, FrameBudget TARGET 16.6 ESTIMATE 5.2, DynamicQuality render_only, Importance 3150, HiZ 5 levels cost_vs_save 0.30, HardenedFrameGraph, PipelineCache hash, ShaderManager no silent fallback, threading SIM owns science, determinism 0xA573 hash 43758.5453

### Supabase Product Integration
- Auth email + Google OAuth (publishable `sb_publishable_WHOOXEK74ZpxJ0cmR2vysA_cBu7EphG` @ `https://bzfpipxjqdrinvagojor.supabase.co`, no service_role in repo), RLS `auth.uid()=id/user_id`, 11 tables (profiles, player_statistics, player_progression, player_preferences, player_achievements, player_unlocks, player_sessions, saved_simulations/scenarios/observers/configurations), 7 buckets `<user_uuid>/...`, Storage 50MiB, Realtime, offline simulator, local `supabase/config.toml` ports 54321/54322/54323

### Launcher
- `ASTRA COSMOS.exe` primary user-facing, resolves exe dir (`GetModuleFileNameA` / `/proc/self/exe`), relative paths, spaces in path, no hard-coded developer paths, checks `shaders/common/common.glsl` + `assets/benchmark.json` + `astra/core/engine.py` + `bin/astra_native`, useful errors, exit codes 0/1/2, preserves stdout/stderr, no admin, normal user

---

## Native Renderer Details
- **Shaders 36:** 6 new `vfx/gpu_particles.comp` (1094w), `solar_flare.comp` (404w), `destruction.comp` (472w), `volumetric_raymarch.comp` (371w image3D), `taa.comp` (494w), `fsr2.comp` (258w scaffolding) + existing 30; all `#version 450` + `local_size`, `common.glsl` astra_hash 43758.5453; 23 compiled headless when cwd=repo-root
- **Build:** Release -O3 -march=native -flto, LTO 2 jobs, `libastra_renderer.a` 3.0M
- **Headless:** `astra_native --headless` 23/23 OK, `launcher --headless` forwards to native, `shutdown complete — no leaks`

## VFX / Performance Systems
- GPU VFX pipeline 1M triple/ring, astrophysical param-driven, destruction visual-only, volumetrics adaptive, cinematic camera/timeline/time separation, HDR AgX bloom 0.35 TAA FSR2 scaffolding SciVis, quality tiers LOW→CINEMATIC ULTRA, culling Hi-Z, LOD meshlet streaming, origin async budgets telemetry dynamic importance occlusion cache shader threading determinism — all verified headless (see summary §§F–K)

---

## Requirements
- **OS:** Windows 10/11 (exe) or Linux (validation)
- **Build:** CMake 3.28, Ninja, C++20, Vulkan-Headers or SDK
- **Python:** 3.11+, Supabase CLI optional
- **GPU (for real):** Vulkan 1.3, RTX 40 recommended, 8–24GB VRAM, HDR display; **NOT VERIFIED** in CI (mock RTX 4090 Mock 24564) — headless mock only

---

## Launcher Usage
```bash
./"ASTRA COSMOS.exe"              # normal runtime
./"ASTRA COSMOS.exe" --headless   # CI mock
./"ASTRA COSMOS.exe" --benchmark  # 60 frames mock 5.2ms
./"ASTRA COSMOS.exe" --help       # usage
```
Launcher checks files, initializes ASTRA, launches `native_renderer/astra_native`, preserves logs, returns native exit code. Handles spaces, no admin.

---

## Known Limitations (Honest)

- **NOT VERIFIED — Windows PE build:** `x86_64-w64-mingw32-g++` not available in Linux CI, so Windows PE not cross-compiled; launcher built as ELF named `.exe` on Linux (46K) with same logic, PE requires Windows build env — **NOT VERIFIED**
- **Real GPU:** Vulkan loader `libvulkan.so`/`vulkaninfo` not in CI, physical device/queues/swapchain mock only, `VkQueryPool` timings mock `5.2ms`, `Telemetry fps=60` mock, HDR/Tracy/RenderDoc not installed — **REAL GPU PERFORMANCE NOT VERIFIED**, `HEADLESS / MOCK MEASUREMENT` only
- **Visual:** No HDR display capture, crack seams / horizon cull / bloom 0.35 / TAA ghosting / FSR2 real upscaling not GPU-verified (FSR2 is scaffolding 258w fallback copy, honestly labeled)
- **Hardware:** FPS 60/30 across Intel UHD LOW vs RTX 40 ULTRA requires real hardware; mesh shader `VK_EXT_mesh_shader` not tested; Tracy not running; Supabase local not running (offline mock)
- **Product:** Supabase local `supabase start` not in CI, realtime not live; Google OAuth secrets in dashboard not code (correct)
- No Godot/Blender, no service_role, no `sb_secret_`, no fake benchmarks

---

## Version

Based on actual repo: `pyproject.toml` `name = "astra-core" version = "0.1.1"` and `native_renderer/CMakeLists.txt` `project(ASTRA_NativeRenderer VERSION 0.1.0)` — release reported as **0.1.1** (core) / **0.1.0** (renderer). No invented semantic version beyond these.

---

## Documentation

- `README.md` — build/launch/test/exe docs
- `ASTRA_COSMOS_COMPLETE_PROJECT_SUMMARY.md` — 20 sections A–T whole project
- `ASTRA_PHASE_4_5_IMPLEMENTATION_REPORT.md` — 28 sections Phase4+5
- `COPYRIGHT.md` — © 2026 Lucky Kumar + third-party
- `ASTRA_FINAL_RELEASE_AUDIT.md` — final audit 15 items

---

*Release built via `cmake --build /tmp/astra_build -j2` Release, tested `pytest 91 passed`, `validate 221 OK`, `headless 23/23`.*
