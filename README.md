# ASTRA COSMOS

**Project:** ASTRA COSMOS  
**Author:** Lucky Kumar  
**Copyright:** Copyright © 2026 Lucky Kumar.  
**Version:** 0.1.1 (astra-core) / 0.1.0 (native renderer) — `pyproject.toml` / `native_renderer/CMakeLists.txt`  
**Approximate development period:** ~1 month — developed iteratively over ~1 month (architecture, science, rendering, optimization, integration, testing, product). Not exact hours.

## Windows distribution status — BLOCKED

**A working ASTRA Windows runtime distribution is not available yet.** The native target still contains mock/diagnostic Vulkan execution and incomplete scientific integration. Windows build, GPU rendering and clean-machine launch are **NOT VERIFIED**. Do not download the source archive expecting a ready-to-run simulator.

The self-bootstrap infrastructure is now implemented in source:

```text
Published ASTRA-COSMOS.zip (not yet available)
    → extract
    → START.bat
    → compiled ASTRA COSMOS.exe bootstrap host
    → verified prebuilt private runtime
    → real simulator
```

After a verified first installation, the intended normal action is simply to double-click **ASTRA COSMOS.exe**, without START.bat, a terminal, or a network request. **This user workflow has not yet been tested or released.**

End users will not install CMake, Visual Studio, MSVC, Ninja, Git, Python, pip or Vulkan SDK. Build tools remain on the release machine. Any necessary Python/.NET application runtime must be bundled privately; Windows and a compatible GPU-vendor driver remain system requirements.

**Current behavior:** START.bat only invokes the compiled distribution host. In this source checkout that EXE is absent, so it explains that no verified release is available and keeps the error visible. It does not compile ASTRA or install developer tools. The checked-in release catalog is deliberately `blocked`; no fabricated runtime URL or checksum is provided.

See:

- [Self-bootstrap architecture](ASTRA_SELF_BOOTSTRAP_ARCHITECTURE.md): private runtime, manifests, download security, updates/rollback, offline behavior and build-machine commands.
- [Implementation report](ASTRA_SELF_BOOTSTRAP_IMPLEMENTATION_REPORT.md): exact implementation and verification status.
- [Native runtime blockers](ASTRA_WINDOWS_NATIVE_RUNTIME_BLOCKERS.md): remaining real rendering/scientific integration work.

### Developer source workflow — not the user distribution

Existing developer commands remain available in the checkout, but are not packaged in the end-user ZIP:

```bat
rem Developer-only source checks/build attempt, requiring development tools.
scripts\terminal.bat
rem Optional Python development/product environment preparation.
scripts\terminal.bat --setup-python
rem Explicit diagnostics; not production simulation/GPU verification.
scripts\terminal.bat --headless
```

The optional scientific/product Python dependencies remain declared by `pyproject.toml`. Supabase remains optional for local scientific functionality; bootstrap code never requests an account or reads .env credentials. The complete runtime's offline/scientific behavior is still a release acceptance gate.

**Release builders only:** `distribution/build_bootstrap.cmd` uses the .NET SDK to publish the proposed Windows GUI host with a private runtime. `distribution/release_tools.py` audits runtime archives, enforces reviewed acceptance evidence, generates pinned catalogs and assembles the bootstrap ZIP. Neither tool is shipped as an end-user prerequisite. The release tool explicitly refuses the known diagnostic native main. No public release was uploaded.

> Source of Truth: This README documents the actual repository as inspected 2026-09-17. No Godot, no Blender, no fabrication.

---

## 1. What ASTRA COSMOS Is

Large scientific simulation & visualization across enormous scales: planetary (1e3 m) → stellar (1e16) → galactic (1e21) → cosmological (1e26) via `scene/floating_origin.h` `test_five_scales`.

- **Scientific simulation** owns truth (orbital, N-body, relativity, black holes, evolution) double-precision deterministic (`DeterministicRNG` seed `0xA573`, `common.glsl` hash `43758.5453`).
- **Visualization** visualizes truth without silent alteration (floating-origin, RenderState).
- **Product** (Supabase) stores identity/persistence, never physics.

**Core principle: THE SCIENTIFIC ENGINE IS AUTHORITATIVE.**
```
ASTRA Scientific Engine (Python, double, tick 42)
  ↓ Scientific State (WorldPos double)
  ↓ RenderState / Visualization API (float relative via OriginRebaser)
Native C++ Renderer (C++20) → Vulkan 1.3 → GPU → Display
```

---

## 2. Scientific Reality Classification

Distinguish always:
- **REAL** — observed, established (`planet REAL`, `earth REAL_ACOUSTIC`)
- **THEORETICAL** — mathematically sound, not observed in ASTRA (`black_hole THEORETICAL`, `wormhole THEORETICAL` Morris-Thorne)
- **SPECULATIVE** — Alcubierre warp, white holes (`warp SPECULATIVE`, `white_hole.frag` watermark 0.2)
- **SIMULATED** — physically modeled, simulation-derived (`atmosphere SIMULATED`)
- **DATA-DERIVED** — from datasets (`galaxy SCIENTIFICALLY_INTERPRETED`, `star_temperature_lut.ppm`)
- **CINEMATIC** — visual enhancement (`SciVisMode::CINEMATIC`, `CinematicCamera` shake)

**Explicit:** Wormholes, white holes, warp/Alcubierre are NOT experimentally established physics. Labeled `THEORETICAL` (Morris-Thorne) or `SPECULATIVE` (Alcubierre) in `extreme/wormhole_whitehole.h` and `main.cpp` prints `wormhole THEORETICAL warp SPECULATIVE` — never REAL.

---

## 3. Core Architecture

```
ASTRA Scientific Engine → Scientific State → RenderState / Visualization API → Native C++ Renderer → Vulkan → GPU → Display
```
- **Engine owns state:** `astra/core/engine.py` `Engine` + `astra/core/coords.py` `OriginRebaser` + `events.py` `EventBus` + `time.py` `SimulationClock` tick 42.
- **Renderer consumes visualization state:** `scene/coordinate_bridge.h`, `object_registry.h`, `scene.h`.
- **Must not mutate truth:** `destruction/destruction.h` `scientific_state_preserved`, `threading/render_threading.h` only `SIMULATION` can mutate, `camera/cinematic_camera.h` `does_not_alter_scientific_state`, `dynamic_quality.h` `only_render_fidelity`.
- **High precision:** Double for science, `world_to_relative(world, origin)` → float[3] for GPU.
- **Floating-origin:** `OriginRebaser::test_five_scales` scales `[1e3,1e11,1e16,1e21,1e26]`, hierarchy `universe→...→DeterministicTestObject` 52,0,0, no teleport.
- **Separation:** `astra/product/integration.py` `is_available()` guard, offline simulator.

---

## 4. Project Phases

### PHASE 1 — Core Architecture
Engine foundation (`engine.py`), deterministic (`rng.py` `0xA573` + `common.glsl` `43758.5453`), lifecycle (`SimulationClock`), events, commands, persistence, recovery, authority, testing `tests/test_*.py` ~84, `native_renderer/tests` 21, validation `validate_native_project.py` 221 OK. **IMPLEMENTED** — `pytest` 91, `headless` OK.

### PHASE 2 — Astronomical Rendering
Planets `planetary_lod.h` MAX_LOD12 SSE1.5 horizon_cull crack_free, terrain `heightmap_terrain.frag` 992w, atmosphere `atmosphere_params.h` Rayleigh/Mie earth/mars/venus + `rayleigh_mie.frag` 1324w, clouds `volumetrics` FogVolume, oceans `gerstner_ocean.vert` 1019w, stars `starfield.h` POINT>1e12 BILLBOARD>1e10 etc. indirect, solar systems `WorldHierarchy` 5 nodes, rings `ring_renderer` Cassini 0.46, nebulae, galaxies, clusters `generate_cluster` seed 0xA573, large-scale `cosmic_structure` Filament 1e-27, LOD/HLOD, GPU-driven `dispatch_culling`. **IMPLEMENTED**.

### PHASE 3 — Extreme Physics (classified)
Black holes **THEORETICAL** `black_hole_physics.h` photon 44310 shadow 76804, accretion disks **THEORETICAL**, lensing **THEORETICAL** `lensing.frag` 658w, Doppler/redshift **THEORETICAL**, spacetime curvature **THEORETICAL**, tidal fields **THEORETICAL**, wormholes/white holes **THEORETICAL** Morris-Thorne, warp **SPECULATIVE** Alcubierre, plasma **SIMULATED**, magnetospheres, jets, destruction, ray-tracing hybrid fallback. **IMPLEMENTED** labeled.

### PHASE 4 — GPU VFX / Cinematic
Astronomical VFX `astrophysical_vfx.h` SolarFlare 1e25J/1e7K, destruction `destruction_vfx.h` 10 stages `smoke only when hasAtmosphere`, volumetrics `volumetrics_hardened.h` 64/128/192 cost 0.005* slices 0.32ms, particles `gpu_particles.h` 1M SSBO triple/ring, plasma, cinematic camera 7 modes `does_not_alter_scientific_state`, timeline deterministic 0xA573 4 keys, HDR AgX bloom 0.35, bloom, exposure, temporal TAA `handles_origin_shift`, upscaling FSR2 scaffolding honest, SciVis modes, VFX tiers, Cosmic Audio. **IMPLEMENTED**.

### PHASE 5 — Performance / Streaming
Hierarchical LOD `lod/hierarchical_lod.h` HLOD cluster 32 screen_error 1.5, GPU culling `culling/occlusion.h` HiZ 5, meshlets `virtual_geo.h`, Nanite-like virtual geometry, virtual texturing `virtual_texture.h` 256MB-1GB, material streaming `material_priority` fallback magenta, astronomical streaming 8-level Universe→Local, extreme coordinate streaming + `async_transfer` 4MB host_visible, floating origin, async transfers fences/timeline, GPU memory budgets 8 types pressure 0.73, frame budgets TARGET 16.6 ESTIMATE 5.2, dynamic quality `only_render_fidelity`, object importance, occlusion, frame graph `HardenedFrameGraph` 10 passes, pipeline cache, shader management `validate_path`, render threading `SIMULATION` owns science, deterministic `0xA573`, headless, GPU validation `glslangValidator`, stress 100K/1M, visual regression NOT VERIFIED. **IMPLEMENTED**.

**Additional:** Supabase Product (11 tables, 7 buckets, RLS, offline) — see §14.

---

## 5. Scientific Systems (Verified)

- Mathematics `astra/mathematics/*` + `test_mathematics_*`
- Coordinates `astra/core/coords.py` + `floating_origin.h`
- Hierarchical coordinates `celestial/hierarchy.py` 5 scales
- Motion `astra/motion/*` + `test_motion_*`
- Classical physics `astra/physics/*` + `test_physics_*`
- Orbital `astra/orbital/*` Kepler/conics + `test_orbital_*`
- N-body `astra/nbody/*` + `test_nbody_*`
- Spacecraft `astra/spacecraft/` + `interaction/navigation.py`
- Relativity `astra/relativity/*` + `extreme/relativistic.h` **THEORETICAL**
- Black-hole `astra/blackhole/*` + `black_hole_physics.h` **THEORETICAL**
- Spacetime `astra/spacetime/` + `spacetime_grid.h` **THEORETICAL**
- Temporal `astra/temporal/` + `core/time.py` `SimulationClock`
- Astronomical data `astra/ingestion/*` + `celestial/objects.py` DATA-DERIVED
- World/scene `astra/world/` + `core/scene.py`
- Destruction `astra/destruction/*` 15 files
- Universe evolution `astra/evolution/*`
- Cosmic history `evolution/epoch.py` + `observer`
- Observation `interaction/observation.py` + `observer` 8 modes
- Extreme travel `theoretical/warp.py` **SPECULATIVE**
- Galactic structure `evolution/galaxy.py` + `cosmic_structure.h`
- Long-term evolution `evolution/timestep.py`
- Scientific/speculative framework `scientific/assumptions` + `visualization_modes.h`
- Interaction `astra/interaction/*`

Only IMPLEMENTED when file exists.

---

## 6. Extreme Coordinates

- Hierarchical `FrameRegistry` `OriginRebaser` 5 nodes `universe→...→local_environment`
- Large-distance: `WorldPos` double (1e26), `world_to_relative()` → float[3]
- Double precision: At 1e16+5 double loses 5 (<5000 stable, floating-origin principle)
- Renderer-relative: `world_to_relative(1e11+50, 1e11)` → `50,0,0`
- Floating-origin: `OriginRebaser.current_origin`, `request_and_execute`, `test_five_scales` `[1e3,1e11,1e16,1e21,1e26]` checks `abs(render)<5000` at 1e16+
- Scales exact: 1e3 local 5,0,0; 1e11 planetary 50,0,0 (star-1); 1e16 stellar stable; 1e21 galactic; 1e26 universe; hierarchy 52,0,0
- Precision: No teleport, only rebase (`validate` No teleport)
- Deterministic: seed 0xA573 hash 43758.5453

---

## 7. Native Renderer

C++20 `CMAKE_CXX_STANDARD 20` `-O3 -flto` at `native_renderer/`

| Technology | Classification | Evidence |
|------------|----------------|----------|
| C++20 | USED | `CMakeLists.txt` |
| Vulkan 1.3 | USED | `rhi/vulkan_rhi.h` 1.3, `/home/user/Vulkan-Headers`, `ASTRA_HAS_VULKAN` |
| GLFW | NOT PRESENT (OPTIONAL) | `pkg_check_modules` not found |
| SDL3 | NOT PRESENT (OPTIONAL) | not found |
| EnTT | USED | `/home/user/entt/src` |
| Dear ImGui | INTEGRATED (NOT VERIFIED) | `/home/user/imgui` present, not rendered headless |
| GLSL | USED | `#version 450` all shaders, `common.glsl` |
| SPIR-V | USED | `glslangValidator` 11:16.6.0 23/23 258-1324w |
| CMake | USED | 3.28 |
| Ninja | USED | Ninja build |
| GoogleTest | PLANNED | Comment `Python pytest, not C++ gtest` |
| Tracy | INTEGRATED (VALIDATION-ONLY) | `src/profiling/tracy.cpp` present, not running |
| RenderDoc | NOT PRESENT | `renderdoccmd` not found |
| meshoptimizer | NOT PRESENT | not found |
| FastNoiseLite | NOT PRESENT | via `astra_hash` |
| KTX2/basisu | NOT PRESENT | not found |
| Jolt | NOT PRESENT | not found |

Renderer systems: foundational RHI/scene, planetary, terrain, atmosphere, clouds, oceans, stars, rings, nebulae, galaxies, clusters, cosmic, extreme physics, VFX, cinematic, performance — all USED per `validate 221 OK`.

---

## 8. Vulkan Validation

1. **SOURCE/STATIC** — USED: `validate_native_project.py` 221 OK, `glslangValidator -V` 23/23, `ASTRA_HAS_VULKAN` guard.
2. **HEADLESS/MOCK** — USED: `astra_native --headless` mock `RTX 4090 Mock VRAM 24564` validates 5 scales, 52,0,0, 23/23, 10 passes, no leaks; launcher forwards.
3. **REAL GPU** — NOT VERIFIED: `Vulkan SDK not found — using /home/user/Vulkan-Headers` (CMake), `vulkaninfo`/`libvulkan.so` not found, `renderdoccmd`/`tracy-server` not found. **Actual RTX/GPU not verified** (mock only). Performance target is NOT measured: **5.2 ms HIGH `estimate_ms` is target, not verified real-GPU measurement.** Headless `Benchmark 60 frames simulated 5.2ms (mock, would use VkQueryPool + Tracy)` is mock-labeled.

---

## 9. Cosmic Audio

Engine `src/audio/` `cosmic_audio_engine.h` mock `miniaudio` dedicated thread queue 64, `HearUniverse 4`.

**Vacuum honesty:** Ordinary acoustic sound does NOT propagate through vacuum.

- LITERAL PHYSICAL SOUND — earth `REAL_ACOUSTIC` wind 0.1Hz (medium)
- PLASMA/MEDIUM-BORNE — solar SOHO/GONG `REAL_SIGNAL_SONIFICATION` plasma
- ELECTROMAGNETIC — pulsar/stellar sonified
- GRAVITATIONAL-WAVE — black hole `GW_SONIFICATION`
- SCIENTIFIC SONIFICATION — `log/linear` mapping
- DATA-DERIVED — galaxy `SCIENTIFICALLY_INTERPRETED`
- PHYSICALLY MODELED — black hole T~r^-3/4
- CINEMATIC — `CINEMATIC` mode
- SPECULATIVE — wormhole Morris-Thorne

**Classifications:** REAL_ACOUSTIC, REAL_SIGNAL_SONIFICATION, DATA_DERIVED, PHYSICALLY_MODELED, SCIENTIFICALLY_INTERPRETED, CINEMATIC, SPECULATIVE — all in `audio_types.h` + `test_cosmic_audio` 18.

**Sources:** GW data `black_hole_audio.h`, pulsar timing, solar SOHO/GONG, EM/plasma, planetary, stellar `star_temperature_lut.ppm`, spacecraft `interaction/travel`, sonification.

**Features:** 3D spatial `doppler_shift` `299792458`, observer 8 modes, relativistic `doppler_g`, provenance `Provenance`, deterministic `0xA573`, quality modes SCIENTIFIC/CINEMATIC, "Hear the Universe" 4 sources.

---

## 10. Observation / Cosmic History

**LOOKBACK TIME ≠ LITERAL TIME TRAVEL.**

- Light-travel `interaction/observation.py` — see as when light left
- Observer-relative `ObserverState` FREE..COSMOLOGICAL tick 42
- Redshift `relativistic.h` `gravitational_redshift`, `doppler.frag`
- Cosmic history `evolution/epoch.py` Filament 1e-27
- Ancient-universe `cosmic_structure` Filament/Void, clusters seed 0xA573
- Future `evolution/scenarios.py` + `timeline` cinematic 100 vs scientific 1234.5 separated
- Different locations `Observation` from `WorldPos`

Reconstruction ≠ time travel (`SimulationClock` `TimeMode` no causal violation).

---

## 11. Extreme Spacetime

- Curvature `spacetime_grid.h` `distort_grid` **THEORETICAL**
- Time dilation `relativity/core.py` **THEORETICAL**
- Wormholes Morris-Thorne `wormhole_whitehole.h` **THEORETICAL**
- White holes same **THEORETICAL**
- Warp Alcubierre `SPECULATIVE` watermark 0.2
- Relativistic travel `interaction/travel.py` **THEORETICAL/SPECULATIVE**
- Tidal `tidal_field` 1.83e-11 **THEORETICAL**

Real physics well-tested but **THEORETICAL** in visualization; wormholes **THEORETICAL**; warp **SPECULATIVE** not established.

---

## 12. Destruction System

```
Impact (1e9J, 5000, 1000, hasAtmosphere) → Energy → Collision → Fragmentation → Debris (256, dust 0.02) → Atmospheric (smoke only when hasAtmosphere) → VFX (rbd 4096, dust glow)
```
- **SCIENTIFIC:** `astra/destruction/system.py` computes mass/velocity, preserves `astra.core`
- **VISUAL:** `vfx/destruction_vfx.h` `handle_impact` visual only, `dust 0.02 glow 100 smoke 1`, `scientific_state_check` preserved

---

## 13. AI Development Workflow

| Model | Role |
|-------|------|
| Qwen 3.8 Max | primary code generation, core architecture, coordinates, native renderer via Agent LM |
| DeepSeek | mathematics, physics, relativity, spacetime, temporal, universe evolution, observation, extreme travel, galactic, speculation, handoff |
| Gemini 3.1 Pro | astronomy, rendering architecture, observatory |
| MiMo | graphics, VFX, shaders, performance, adversarial testing |
| GLM 5.3 | backend, services, persistence, integration |
| DeepSeek V4 Flash | support, utilities, adapters, tests |
| Kimi K2.6 | auditing, final adversarial audit |
| Replit | prototypes |
| Vercel | web infrastructure/dashboard |
| Agent Mode (Arena.ai) | Orchestration |

AI-assisted, not individual authorship of entire project.

---

## 14. Supabase

**Product / Account / Persistence, NOT authoritative engine.** Physics operates independently via `is_available()` offline simulator.

- Auth `auth.py` email/password `sign_up` + Google OAuth `sign_in_with_oauth({provider: google})` publishable only
- Google OAuth via Dashboard env
- Sessions `player_sessions`
- Profiles `profiles` `auth.users(id)`
- Statistics `player_statistics`
- Progression `player_progression` level/xp
- Preferences `player_preferences` jsonb
- Achievements `player_achievements`
- Unlocks `player_unlocks`
- Saved simulations/scenarios/observers/configurations + Storage buckets `simulation-saves/<user_uuid>/...` 7 buckets 50MiB
- Storage `storage.py` 7 buckets `avatars` etc.
- Replays via `saved_simulations`, screenshots via Storage

**Security — NEVER in README:** `service_role`, DB password, JWT secret, OAuth secret, private keys. Only `sb_publishable_*` via env (`SupabaseConfig`). `grep -r sb_secret` 0 real.

---

## 15. Repository Tree (Actual)

```
ASTRA-COSMOS/
├── START.bat → compiled distribution host (not built yet; source-building scripts are developer-only)
├── README.md (this file)
├── COPYRIGHT.md, RELEASE_NOTES.md, ASTRA_COSMOS_COMPLETE_PROJECT_SUMMARY.md (571 lines), ASTRA_FINAL_RELEASE_AUDIT.md
├── astra/ (core, celestial, mathematics, physics, motion, orbital, nbody, relativity, blackhole, spacetime, world, destruction, evolution, interaction, ingestion, product/supabase)
├── native_renderer/ (CMakeLists.txt 0.1.0, launcher/launcher.cpp 258 lines, src/ 52 subdirs, shaders/ 36, assets/, tools/validate 221 OK, tests/ 91)
├── supabase/ (config.toml, migrations 11 tables 7 buckets RLS)
├── tests/ (~84 scientific tests)
├── visualization/ (placeholder, no engine)
├── release/ASTRA-COSMOS/ (bin/astra_native 161K ELF, shaders, assets, documentation, config, runtime, data)
├── GODOT_PHASES/ (spec markdowns, NOT engine)
└── pyproject.toml (astra-core 0.1.1)
```

---

## 16. Build Instructions (Real)

```bash
pip install -e ".[dev]"
cmake -S native_renderer -B /tmp/astra_build -G Ninja -DCMAKE_BUILD_TYPE=Release -DASTRA_BUILD_LAUNCHER=OFF
cmake --build /tmp/astra_build -j2  # builds the native runtime
pytest native_renderer/tests/ -q  # 91 passed
python native_renderer/tools/validate_native_project.py  # 221 OK (from repo root)
bash -c 'cd ASTRA-COSMOS && /tmp/astra_build/astra_native --headless'  # 23/23
# Windows (MSVC/mingw)
cmake -S native_renderer -B build -DCMAKE_BUILD_TYPE=Release -DASTRA_BUILD_LAUNCHER=OFF
cmake --build build --config Release --target astra_native  # Windows build NOT VERIFIED
```

---

## 17. Historical Windows launcher diagnosis

The old root and release `ASTRA COSMOS.exe` files were obsolete user-facing wrappers, not the native scientific runtime. Both have been inspected and removed. The native `astra_native` artifacts and C++ source remain. The PowerShell bootstrap was subsequently removed after the user reported an unsigned-script policy failure. The old BAT-only source-building startup is now developer-only; the new distribution host is not yet compiled or released.

For historical evidence, see `ASTRA_EXE_FORENSIC_DIAGNOSIS.md`; for current architecture, deletion evidence, tests and limitations, see `ASTRA_WINDOWS_STARTUP_REPORT.md`. Historical reports are not current launch instructions or proof of runtime success.

---

## 20. README Status Matrix

| System | Status | Evidence |
|---|---|---|
| Core Engine | IMPLEMENTED | `astra/core/engine.py` + `validate 221 OK` |
| Mathematics | IMPLEMENTED | `astra/mathematics/*` + `test_mathematics_*` |
| Coordinates | IMPLEMENTED | `astra/core/coords.py` + `floating_origin.h` 1e3..1e26 52,0,0 |
| Physics | IMPLEMENTED | `astra/physics/*` |
| Relativity | IMPLEMENTED (THEORETICAL) | `astra/relativity/` + `extreme/relativistic.h` curvature |
| Black Holes | IMPLEMENTED (THEORETICAL) | `astra/blackhole/` + `raymarch.comp` |
| Spacetime | IMPLEMENTED (THEORETICAL) | `spacetime/` + `warp.py` SPECULATIVE |
| Astronomy | IMPLEMENTED | `celestial/` + `ingestion/` + `starfield` |
| Universe Evolution | IMPLEMENTED | `evolution/` + `cosmic_structure` |
| Observation | IMPLEMENTED | `observation.py` + `observer` 8 modes |
| Destruction | IMPLEMENTED | `astra/destruction/` 15 + `vfx/destruction_vfx` |
| Native Renderer | IMPLEMENTED | `native_renderer/` C++20 `validate 221` `headless` 23/23 161K |
| Vulkan | PARTIALLY | SOURCE/STATIC + HEADLESS/MOCK VERIFIED, REAL GPU NOT VERIFIED |
| GPU VFX | IMPLEMENTED | `vfx/gpu_particles` 1M + `volumetrics` 0.32ms |
| Cosmic Audio | IMPLEMENTED | `src/audio/` `HearUniverse 4` + `test_cosmic_audio` 18 |
| Supabase | IMPLEMENTED | `supabase/migrations` 11 tables 7 buckets RLS |
| Windows distribution | BLOCKED | Bootstrap source and policy tests exist; Windows runtime and clean-machine launch NOT VERIFIED |
| Testing | IMPLEMENTED | `native_renderer/tests` 91 + `validate` 221 + `tests/` ~84 |

---

## 21. Quick Reference

```bash
pip install -e . && pip install pytest
cmake -S native_renderer -B /tmp/astra_build -G Ninja -DCMAKE_BUILD_TYPE=Release -DASTRA_BUILD_LAUNCHER=OFF && cmake --build /tmp/astra_build -j2
pytest native_renderer/tests/ -q  # 91
python native_renderer/tools/validate_native_project.py  # 221
/tmp/astra_build/astra_native --headless
```

---

## 22. Security & Honesty

No `service_role`/`sb_secret`/`DB password` in README, no hard-coded paths in launcher, `5.2 ms` is target not measured, `REAL GPU NOT VERIFIED`.

---

## 23. Copyright

Copyright © 2026 Lucky Kumar. Original source protected. Third-party retains licenses. See `COPYRIGHT.md`.

---

## 24. Final Notes

~1 month iterative. The intended distribution uses a compiled private-runtime bootstrap host; no verified production ZIP is available. Obsolete launcher binaries remain removed. Science authoritative. Wormholes/warp NOT established — labeled.

*README describes actual repository as inspected 2026-09-17 via `ls -R`, `cat`, `readelf`, `pytest`, `validate`, `cmake --build`. No fabrication.*
