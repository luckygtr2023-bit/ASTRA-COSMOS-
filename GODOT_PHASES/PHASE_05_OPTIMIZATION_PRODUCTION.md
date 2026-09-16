# GODOT PHASE 05 — OPTIMIZATION & PRODUCTION

**Version:** 1.0 — 2026-09-17  
**Target:** Godot 4.4.1 Forward+ production-ready (`RenderingDevice` instancing/LOD/HLOD/culling/streaming/profiling/presets)  
**Branch:** `arena/01a0a5a2-astra-cosmos`  
**Prerequisite:** Phases 01–04 YELLOW+ intact (foundation → astronomical instancing → extreme honesty → VFX/cinematics). **Phase 05 changes nothing visually without profiling proof; all 01–04 validation scenes must stay GREEN/YELLOW.**  
**Status taxonomy:** STATIC / RUNTIME / NOT VERIFIED / ENVIRONMENT BLOCKED; performance sections must distinguish **TARGET (budget, 5 specs) vs MEASURED (Telemetry, GPU)**.

---

## 1. Phase Identity

- **Phase:** `PHASE_05_OPTIMIZATION_PRODUCTION`
- **Order:** 5 of 5 (`01[X]→02[X]→03[X]→04[X]→05`)
- **Code prefix:** `phase_05_optimization_production/` under `visualization/godot/` (plus project-wide optimizer autoloads/tools that serve all prior phases)
- **Deliverable:** `GODOT_PHASES/PHASE_05_OPTIMIZATION_PRODUCTION.md` (this file) + `visualization/godot/phase_05_optimization_production/`
- **Gate scene:** `phase05_validation.tscn` seed `0xA577` benchmarking `10k stars + 50 planets lod + VFX 256` across presets `LOW/MEDIUM/HIGH/ULTRA/CINEMATIC` **without visual regression**.

---

## 2. Objective

Make ASTRA COSMOS **shippable at 60/30 fps** across hardware (`Intel UHD LOW 30 fps` → `RTX 40 ULTRA/CINEMATIC 60 fps`) by optimizing the **already built** systems (Phases 01–04) with **measured** instancing, LOD/HLOD, frustum+occlusion culling, async streaming, quality-driven feature gating, and production diagnostics, **without breaking** any prior validation scene or honesty labeling.

Output: hardware detection, presets `LOW–MEDIUM–HIGH–ULTRA–CINEMATIC` applied at runtime (13 features), `RenderingDevice` compute instancing where profiled, fallback GDScript measured, headless/deterministic still, clean build.

---

## 3. Scope

**In scope (only optimizations for already-built visuals):**

- **Instancing (`MultiMeshInstance3D`):** consolidate Phase 02 stars/Phases 02–03 density/galaxy fields to `MultiMesh` buckets `10k HIGH → 20k CINEMATIC` (48 measures), `custom_data` temperature/lod, `RenderingDevice` storage buffer path `instance_prepare.glsl` where `>1ms` profiled, GDScript loop fallback measured (`0.14ms 10k` already **`TARGET`** baseline)
- **LOD/HLOD:** hierarchical `LOD0-4` `0–5/5–50/50–500/500–5k/5k+` `lod switches` by `QualityPresets` distance scale (42 measures), planet icosphere `LOD 2–5` subdiv `42→10k verts`, HLOD clusters `32 objects/cluster` `Node3D` batching distance `500`, Dither fade `0.2s`
- **Culling:** frustum `Camera3D.frustum` + `World3D` `VisibilityNotifier3D` + occlusion `RenderingServer occlusion_culling`, distance culling `>5000` `LOD4→culled`, `instance count visible/total` Telemetry, quality scales culling aggressiveness (LOW 2k visible cap 256 fog off vs CINEMATIC 8k)
- **Streaming:** async `ResourceLoader.load_threaded_request` for large assets (heightmaps, galaxy density textures `256 KB/tile`), tile grid `16×16` per `spatial.py`, streaming budget `4 MB/frame`, fallback inline `load` headless
- **Profiling:** `PerformanceMonitor.gd` autoload `RenderingServer.get_rendering_info(RENDERING_INFO_TYPE_VISIBLE_OBJECTS)` `draw calls`, `get_video_adapter_name`, `OS.get_memory_info`, `Engine.get_frames_per_second` rolling 60 avg, Telemetry now logs `fps, avg60, frame_time_ms, draw_calls, instance visible/total, cull_culled, lod_switches, stream_pending, per-phase ms (stars/planets/nebula/lensing/vfx/post)` MEASURED when GPU, else TARGET with reason
- **Quality presets complete verification:** matrix 13 features shadows/fog/particles/star_density/terrain/lensing/raymarch/volumetric/SDFGI/DoF/supersample (LOW 0/0/32/0.35/100/64 vs CINEMATIC 8192/192/1024/0.95/800/256+ss/1.25×) auto-detect via `OS.get_processor_name/get_memory_info` + `RenderingServer` + manual `--quality` override.
- **Fallbacks:** Forward+ desktop `RenderingDevice` compute when `RenderingDevice.get_type()=="Vulkan"` else GDScript path proven headless; `QualityPresets.is_forward_plus()` gate compute/SSAO; `gl_compatibility` web path `LOW` automatically
- **Headless/deterministic:** streaming mocked (`load_threaded` falls back `load` synchronously when `DisplayServer headless`), LOD deterministic `seed 0xA577`, no `randf()`.
- **Clean build:** `GODOT_PHASES/` 5 specs present, `visualization/VALIDATION_REPORT.md` all phases, `SHADER_CATALOG.md` 23+ updated, `DEPENDENCIES.md`/`THIRD_PARTY.md`/`ASSET_LICENSES.md` final, no `GODOT NOT AVAILABLE` unless truly env-blocked with logs

**Out of scope — §4.**

---

## 4. Non-Goals

- No new visuals (no new planet type, no new VFX) — only optimizations of existing `01–04`
- No new physics, no `astra.core/world` changes
- No editor tooling/export pipeline beyond `validate_*` + `generate_shader_catalog`
- No network multiplayer, no asset store upload, nobinary signing
- No claiming `60 FPS` MEASURED without `Telemetry` GPU logs

---

## 5. Existing ASTRA Systems to Inspect

- `astra/world/spatial.py` `SpatialIndex` tiling `16×16` — streaming grid must align, not reinvent
- `astra/world/hierarchy.py` / `astra/core/coords.py` `OriginRebaser` — culling/LOD distances operate on `local = world - origin`, not scientific double
- `astra/temporal/simulation_clock.py` — performance does not change `sim_time`; interpolation still tick-synced
- `astra/benchmarks/` if present — baseline benchmarks to compare
- `tests/test_performance*` if present — keep `1660 passed`

---

## 6. Existing Visualization Systems to Reuse

**AUDIT → REUSE → EXTEND → TEST (extends all prior phases, replaces none)**

- `phase_01_foundation` `project.godot` Forward+ `config_version 5` singleton `[rendering]` (keep `708d487` fix), `QualityPresets.gd` already 5 presets + `is_forward_plus`, `Telemetry.gd` extend to full metrics, `AstraBridge`/`CoordinateBridge`/`CameraSystem` unchanged
- `phase_02_astronomical` `ObjectRegistry` `10k MultiMesh` target + `star/planet/nebula/galaxy` buckets + `custom_data` — optimize to `instance_prepare.glsl compute` when Vulkan, keep GDScript path measured; `ShaderManager` honest mapping retained
- `phase_03_extreme_physics` `black_hole_raymarch` `MAX_STEPS` by quality + lens `SubViewport` — optimize via quality-scaled steps/viewport, keep watermark
- `phase_04_vfx_cinematics` `ParticleSystems` pooling `32→1024` + `PostProcessStack` glow/SSAO/DoF/fog + `CinematicCameraRig` — gate by preset, measure `vfx_ms`/`post_ms`
- `visualization/godot/shaders/compute/instance_prepare.glsl` `local_size 64` instance buffer prep (already) — reuse for stars/galaxy instancing optimization; `lensing_prepare.glsl` if added Phase 03 for BH lens
- `visualization/godot/shaders/utility/common_lib.gdshaderinc` shared math — reuse
- `visualization/godot/materials/` 9 (`planet/star/nebula/galaxy/bh/wormhole/warp/impact/warp_vfx`) — no new material; ensure numeric `ExtResource` still `1 ok`
- `visualization/tools/` — `validate_godot_project.py` (57 + phases 02–04 extensions → final `70+` with optimizer checks, but 57 base 0 FAIL), `validate_coordinates.py` 27 OK, `validate_shaders.py` 19+ with compute `local_size`, `validate_assets.py` 9, `generate_shader_catalog.py` 23+, `generate_lut.py`; **no tools duplicate**
- `visualization/PERFORMANCE.md` benchmarks `~5.2ms HIGH`, 48 instancing 42 LOD measures — extend with final `TARGET` budgets `LOW 2.0ms → CINEMATIC 8.5ms` table, keep measured section separate

---

## 7. Architecture

```
ASTRA scientific objects (10k+ stars/planets/nebula/WH/BH) → bridge_state.json (origin_offset)
        ↓ AstraBridge poll 30 Hz
ObjectRegistry (MultiMesh buckets, lod tag)  →  LODManager (distance→LOD0-4 + HLOD clusters 32)
        ↓ local positions + custom_data            ↓ dither 0.2s + distance culling >5k
RenderingDevice (if Vulkan: instance_prepare.glsl compute 0.08ms) ←GPPU fallback 0.14ms 10k (TARGET)
        ↓ visible instances
CullingManager (frustum + occlusion + distance) → PerformanceMonitor (draw_calls, visible/total, ms per phase)
        ↓
StreamingManager (load_threaded 4MB/frame, 256KB tile) → ShaderManager (preset-gated material features) → PostProcessStack (preset-gated glow 0.2→0.8/SSAO/SDFGI/DoF)
        ↓
Forward+ Forward tiling renderer, quality auto-detect (Intel UHD→LOW, RTX40→ULTRA) + manual --quality
        ↓ quality overlay (DiagnosticsOverlay shows preset, fps, culled, LOD)
```

**Constraint:** Optimizers are additive decorators (`ObjectRegistry` + `LODManager` + `CullingManager` signals) not replacements; prior scenes load without optimizer autoload if disabled.

---

## 8. Data Flow

1. `bridge_state.json` extended `objects[] 10k` + `stream_manifest {tile:"12_34", url:"res://assets/tiles/12_34.res"}` optional (if not present, optimization works without streaming — synthetic test tiles).
2. `AstraBridge` → `ObjectRegistry.update_render_state` now tags `lod_distance = (pos_local - camera_pos).length()` before `MultiMesh.set_instance_transform`.
3. `LODManager._process` buckets by `lod_distance` tiers `LOD0<5, LOD1<50, LOD2<500, LOD3<5k, LOD4 else`, assigns `HLOD clusters` for `>500`, counts `lod_switches` delta vs last frame.
4. `CullingManager` frustum tests `camera.frustum` `AABB` per bucket, occlusion via `RenderingServer`, caps `visible_instances` by preset `LOW 2k→CINEMATIC 20k`.
5. `RenderingDevice` path (if `RenderingServer.get_rendering_device()` != null) dispatches `compute` `instance_prepare.glsl` `dispatch ceil(visible/64)`; else GDScript loop `for i in visible: multimesh.set_instance_transform`.
6. `StreamingManager` `load_threaded_request(tile)` 4 MB/frame budget, `pending→loaded` emits, `ObjectRegistry` swaps tile mesh when `status == THREAD_LOAD_LOADED`.
7. `PerformanceMonitor` every 60 frames logs `fps avg60 draw visible/total culled lod stream_pending stars_ms planets_ms fog_ms` distinguish TARGET label if headless.

---

## 9. Required Systems

- `LODManager.gd: Node` `func assign_lod(pos:Vector3, preset:Preset)->int` tiers + `func cluster_hlod(objects:Array)->Dictionary` 32/cluster, dither
- `CullingManager.gd: Node` `func cull(camera:Camera3D, objects:Array)->Array` frustum+occlusion+distance, `var culled:int`
- `StreamingManager.gd: Node` `func request_tile(id:String)` `load_threaded`, `func budget_on_frame(budget_mb:float)` 4 MB, headless fallback `load`
- `PerformanceMonitor.gd: Node` autoload or child `Telemetry` `func _process 60 avg`, uses `RenderingServer.get_rendering_info`, `OS.get_memory_info`
- Extend `QualityPresets.gd`, `Telemetry.gd` to log optimizer metrics, `ObjectRegistry.gd` to delegate LODManager
- Extend `phase*validation.gd` do **not** modify, but Phase 05 scene must still import their hierarchy regression `52,0,0` check
- `phase05_validation.gd: Node` `SEED 0xA577` spawns `10k MultiMesh stars` (synthetic, not requiring 10k bridge), `5 planets LOD`, `256 particles`, iterates presets `LOW→CINEMATIC` measuring visible/draw/lod transitions

---

## 10. Required Files/Directories

```
visualization/godot/phase_05_optimization_production/
  README.md           (budgets TARGET vs MEASURED, how to benchmark)
  scenes/phase05_validation.tscn  (UID uid://astra_phase05_validation)
  scenes/optimization_benchmark.tscn (optional larger 20k star stress)
  scripts/lod_manager.gd
  scripts/culling_manager.gd
  scripts/streaming_manager.gd
  scripts/performance_monitor.gd  (extends telemetry or new)
  scripts/phase05_validation.gd
  environments/benchmark_env.tres (extends default_env, SDFGI toggle)
  materials/ (reuse prior, no new)
visualization/godot/shaders/compute/instance_prepare.glsl (already local_size 64) + optionally streaming_prepare.glsl
visualization/godot/shaders/utility/common_lib.gdshaderinc (already)
visualization/tools/benchmark_performance.py (optional Python benchmark wrapper, not required but recommended)
```

Must preserve/prior dirs `phase_01–04` untouched.

---

## 11. Godot Scene Requirements

**`phase05_validation.tscn` deterministic `SEED 0xA577` headless `1.5s` (longest due to 10k set):**

- `Phase05Root` `Node` script `phase05_validation.gd`
  - `WorldEnvironment` `benchmark_env.tres` `SDFGI enabled ULTRA+ only` else off.
  - `BenchmarkCamera` `Camera3D` at `(0,80,150)` looking at origin reuses `CameraSystem` or direct
  - `StarBenchmark` `MultiMeshInstance3D` `multimesh 10000` `10k` grid `100×100 x/z -200..200 y 0`, `custom_data` random-but-seeded temp `3000–30000`, optimization: `LODManager` assigns `LOD culled` for out-of-view, `CullingManager` frustum, `RenderingDevice` dispatch if Vulkan else loop; diagnostics `visible  X/10000` after culling
  - `PlanetLOD` `Node3D` 5 spheroids at `dist 3/15/80/600/6000` demonstrating `LOD0-4` by distance (LOD4 `culled` at `6000`)
  - `HLODCluster` `Node3D` 64 objects `2 clusters 32` beyond `500`
  - `VFXLoad` `GPUParticles3D 256` + `FogVolume 0.02` as in Phase 04 to show preset gating shaved vs LOW
  - `StreamingTiles` `Node3D` 4 `MeshInstance3D` placeholders `tile_0_0 .. 1_1` `256KB` synthetic, `StreamingManager` requests via `load_threaded` (falls back `load`)
  - `DiagnosticsOverlay` `Label` extended multi-line `fps avg60 draw X visible 1234/10000 culled Y lod switches Z stream pending W preset MEDIUM, stars_ms planets_ms fog_ms, TARGET vs MEASURED tags, all prior hierarchies OK`
  - `ObjectRegistry` + `LODManager` + `CullingManager` + `StreamingManager` + `PerformanceMonitor` + `QualityPresets` nodes

Headless `quit(0/1)` after `1.5s`; synthetic `10k` avoids requiring large `bridge_state.json` download.

---

## 12. GDScript Requirements

**Typed, profile-aware branching.**

| File | Key API |
|---|---|
| `lod_manager.gd` | `class_name LODManager: Node`, `enum LOD {L0,L1,L2,L3,L4,CULLED}`, `func get_lod(dist:float)->LOD` tiers `5/50/500/5000`, `func apply(inst_idx:int,lod:LOD)` sets `custom_data` LOD, `func hllod_cluster(objects:Array)->Array[Array]` 32 per cluster |
| `culling_manager.gd` | `class_name CullingManager: Node`, `func cull(camera:Camera3D, bounds:Array[AABB])->BitMask`, `var culled:int`, uses `camera.is_position_in_frustum` (or `GeometryInstance3D` cull), no `queue_free` per frame |
| `streaming_manager.gd` | `class_name StreamingManager: Node`, `const BUDGET_MB=4.0`, `func request(path:String)`, `func _process pending→loaded` via `ResourceLoader.load_threaded_get_status`, headless fallback `load` |
| `performance_monitor.gd` | `class_name PerformanceMonitor: Node`, `var _history:Array[float]`, `_process 60 avg`, `get_rendering_info(RENDERING_INFO_TYPE_VISIBLE_OBJECTS, RENDERING_INFO_TYPE_DRAW_CALLS)` guard `if RenderingServer`, `func _physics_report()` stars/planets ms via `Time.get_ticks_usec` per section |
| `phase05_validation.gd` | `extends Node`, `SEED 0xA577`, builds `10k MultiMesh`, iterates `LOW–CINEMATIC` presets `QualityPresets.apply`, `_check_lod_correct` distance tiers, `_check_culling reduces visible when camera away`, `_check_streaming_pending→loaded fallback`, `_check_benchmark_fps TARGET 60 vs MEASURED 30 headless?`, hierarchy regression `52,0,0`, `quit(1)` on FAIL |

No `randf()` without seed.

---

## 13. Shader Requirements

- **Shaders unchanged** (reuse Phase 02–04). Phase 05 verifies `instance_prepare.glsl` contract: `#version 450` `layout(local_size_x=64)` `layout(binding=0) buffer InstanceData { vec4 pos_lod[]; }` `uniform float culled;` dispatch `ceil(visible/64)` `1 workgroup 64 threads` (`TARGET 0.08ms 10k` `HIGH`).
- Common lib still included where needed.
- **Validation:** `validate_shaders.py` still passes `shader_type` for `*.gdshader`, `local_size` for `*.glsl` `compute`. `phase05_validation.gd` `ResourceLoader` loads `instance_prepare.glsl` via `load` (godot 4.4.1 `compute` as `RDShaderFile` may `ResourceLoader.exists==true` check only — document if `load` for `.glsl` not supported, check existence counted `STATIC` not `RUNTIME`).

---

## 14. Material Requirements

- No new `.tres`; all prior `planet/star/nebula/galaxy/bh/wormhole/warp/impact` remain numeric `ExtResource` 1 ok, checked via `validate_godot_project.py` `checked ext_resources: N ok 0 missing`.

---

## 15. C++/GDExtension Requirements Where Justified

- **Same `AstraInstanceHelper` as Phase 01–02** — Phase 05 justification is strongest: `10k instance prepare` GDScript `1.2ms` → compute `0.08ms` `RTX 3060` **TARGET**. Keep `gdext_library_init` verified. Do **not** add new `.so` for LODManager (GDScript `get_lod` <0.05ms) — unjustified. Document that Phase 05 `RenderingDevice` compute is attempted if `RenderingDevice != null`, fallback GDScript measured.
- Re-verify `nm -D` `ldd` same binary; do not claim `load` verified without `godot --headless` `AstraInstanceHelper.new()` success.

---

## 16. Python Tooling Requirements Where Justified

- `validate_godot_project.py` final extension (optimizer checks) but retains 57 base 0 FAIL; new checks tagged `optimizer` (e.g., `LodManager exists`, `StreamingManager BUDGET 4MB`).
- `validate_coordinates.py` 27 OK, `validate_shaders.py` 19+, `validate_assets.py` 9, `generate_shader_catalog.py` `SHADER_CATALOG.md` final line count `23+`, `generate_lut.py` not regenerated silently.
- Optional `tools/benchmark_performance.py` may parse `Telemetry` output `fps/draw` and print markdown table — not required but document if absent.

---

## 17. Node/JavaScript Tooling Requirements Where Justified

- `bridge_adapter.js` / `generate_manifest.js` unchanged deterministic `9 assets`; no new npm.

---

## 18. Addon/Dependency Requirements

- Finalize `DEPENDENCIES.md` with every allowed row (purpose+version+source+license+risk) and rejected 5 pre-checked `false` via `evaluate_addons.py`. Phase 05 adds no new addon without `DEPENDENCIES.md` row; `evaluate_addons.py` run to prove rejected 5 still rejected.
- If no addon, state `none new in Phase 05` explicitly in `VALIDATION_REPORT.md`.

---

## 19. Asset Requirements

- Final 9 assets `<2MB` CC0 with license entries `ASSET_LICENSES.md`; `StreamingManager` synthetic tiles `256KB` `P3 PPM` generated, not committed as >2MB.

---

## 20. Coordinate-System Requirements

- All distance thresholds `5/50/500/5000` use `local = world - origin_offset`; scientific double untouched. HLOD clustering local only. Keep `52,0,0` regression pass.

---

## 21. ASTRA ↔ Godot Boundary

- Optimizers do not change `bridge_state.json` consumption or `classification` honesty. LOD/culling visible counts sent to `Telemetry` only, not back to `astra.world`. `Phase05` still `AstraBridge.request_interaction` for navigation. Visual honest watermarks still checked across presets (LOW still watermark `SPECULATIVE`).

---

## 22. Performance Requirements — **TARGET (budgets) vs MEASURED (report)**

**TARGET budgets** (`PERFORMANCE.md` extend, append table, **not MEASURED** unless GPU):

| Preset | Stars 10k | Planets 5 | Nebula fog | Lensing | VFX 256 | Post | Streaming | Total TARGET | FPS TARGET |
|---|---|---|---|---|---|---|---|---|---|
| LOW | 0.3ms | 0.6ms 100 verts | 0 off | 0.2 64 steps | 0.1 32 | 0 fog off | 0.1 | 1.3 | 60 LOW* |
| MED | 0.5 | 0.8 | 0.4 64 samples | 0.4 64 | 0.3 128 | 0.3 glow 0.2 | 0.2 | 2.9 | 60 |
| HIGH | 0.6 | 1.2 642 v | 0.8 128 | 1.0 128 | 0.5 256 | 0.7 glow 0.35 | 0.4 | 5.2 | 60 |
| ULTRA | 0.8 | 1.5 2562 v | 1.0 192 | 1.4 192 | 0.8 512 | 1.0 SDFGI | 0.5 | 7.0 | 60 |
| CINEMATIC | 1.0 20k | 1.8 10k v | 1.2 192 | 1.8 256 +ss | 1.0 1024 +DoF | 1.4 ss 1.25× | 0.6 | 8.8 | 30-60 |

*`LOW` Intel UHD 30 fps target.

**MEASURED** only when `RenderingServer.get_rendering_info` available: `PerformanceMonitor` logs `fps avg60 draw visible/total culled stream ms per phase` measured; headless CI `NOT VERIFIED (headless no Vulkan)` and TARGET table retained without pretending measured. `phase05_validation.gd` asserts `HIGH visible/total <40% when camera away` and `lod switches monotonic with distance` **not FPS**.

---

## 23. Quality Presets

- Verify full 13-feature matrix across `LOW→CINEMATIC` via `QualityPresets.apply(preset)` automated in `phase05_validation.gd` loop `5 presets` each setting `multimesh visible cap`, `lod scale`, `viewport sizes`, `particle amount`, `fog density`, `glow/ssao/sdfgi/dof`, `max_steps`, `supersample`. Manual `--quality cinematic` still overrides.
- `FORWARD_PLUS_RUNTIME_VERIFIED` only if `RenderingServer.get_current_rendering_method()=="forward_plus"` via `godot --headless -s detection` (handle `--rendering-driver opengl` fallback case).
- Document preset persistence not required; applying each pass `*_validation.gd` verifies instant switch without reload.

---

## 24. Security/Resource Boundaries

- `res://` constrained same (`checked ext_resources N ok 0 missing`, numeric ids, no `../` outside except documented `../../bridge_state.json` `if file:`).
- No `http` runtime (comments + `127.0.0.1` only), no `eval/OS.execute`, no `/home` absolute, no `*.so` outside `extensions/bin`, no `*.zip`/`node_modules`, 9 assets license-documented.

---

## 25. Testing Requirements

- `PYTHONPATH=. pytest -q` `1660 passed`
- `validate_godot_project.py` 0 FAIL final (≥70 checks with optimizer), `validate_coordinates.py` 27 OK, `validate_shaders.py` 19+ `local_size`, `validate_assets.py` 9, `generate_shader_catalog.py` 23+ lines, `validate_bridge.py` 3 objects + extended kinds not crash
- `phase05_validation.gd` automated checks `SEED 0xA577`: `_check_lod_tiers` 5 distances correct LOD, `_check_culling_visible_reduces` frustum delta, `_check_hlod_clusters 32 per`, `_check_streaming_pending→loaded` fallback, `_check_visible_cap_by_preset HIGH 10k→256 fog etc`, `_check_hierarchy 52,0,0 regression`, all prior `phase01–04` validation still exit 0 (re-run in `VALIDATION_REPORT`), `quit(1)` any FAIL
- No new `randf()` without seed.

---

## 26. Runtime Validation Requirements

- **Primary:** `godot --path visualization/godot --headless --scene res://phase_05_optimization_production/scenes/phase05_validation.tscn` → `[OK]10k->visible X`, `[OK]LOD0-4`, `[OK]HLOD 32`, `[OK]Culling vis reduced`, `[OK]Streaming pending→loaded`, `LOW→CINEMATIC preset loop X OK`, hierarchy regression, `0 FAIL` exit 0
- **Regressions:** re-run `phase01_validation.tscn`, `phase02_validation.tscn`, `phase03_validation.tscn`, `phase04_validation.tscn` all still `0 FAIL` exit 0
- **Smoke:** `godot --path visualization/godot --headless --scene res://phase_01_foundation/scenes/main.tscn` `Telemetry` logs `fps/draw` 60 frames, 0 fatal
- `godot --version` `4.4.1.stable.official`, capture all warnings 0 fatal; if headless no GPU, `NOT VERIFIED (headless no Vulkan)` but `ResourceLoader`+LOD logic still VERIFIED.

---

## 27. Failure Handling

- `load_threaded` not supported headless → fallback `load` synchronous 256KB tile, `WARN` not `FAIL`
- `RenderingDevice==null` → skip compute dispatch, run GDScript loop, `Telemetry` `compute unavailable headless` WARN
- `frustum cull` thrash lod switches >100/frame → debounce dither, not FAIL
- Malformed preset `--quality unknown` → default `MEDIUM`, `WARN`.

---

## 28. Documentation Requirements

- `phase_05_optimization_production/README.md` how presets scale, budgets TARGET vs MEASURED, benchmark commands (`godot --headless --scene ...phase05_validation.tscn -- --quality high`), perceived quality vs performance tradeoffs, fallback notes
- `visualization/VALIDATION_REPORT.md` append `PHASE 05` with `TARGET vs MEASURED` split table, taxonomy per subsystem, preserve `PHASE 01–04`, branch/commit/Godot/GPU/test commands/exact results/warnings/limitations, final status YELLOW/GREEN per §31
- `visualization/PERFORMANCE.md` extend budgets table TARGET vs measured placeholder, not overwriting prior `5.2ms`
- `visualization/QUALITY_PRESETS.md` matrix already complete — verify 13 features and sync `benchmark_env.tres`
- No doc erases prior evidence

---

## 29. Completion Criteria

- `phase05_validation.tscn` deterministic `10k` synthetic, `LOD0-4` + `CULLED` correct by distance, `HLOD` 32/cluster, `Culling` reduces `visible/total` when camera off-axis, `StreamingManager` 4 pending→loaded via fallback, `LOW→CINEMATIC` 5 preset loop each `QualityPresets.apply` toggles correct `visible cap/particles/fog/glow/dof/supersample`, hierarchy `52,0,0` regression, watermark checks still passing headless `_fail==0` `quit 0`
- All prior scenes re-run `0 FAIL` (`phase01 52,0,0`, `phase02 star/planet`, `phase03 watermark`, `phase04 tick-sync`) not broken by optimizer decorators
- `70+ validate_godot_project` 0 FAIL, `pytest 1660 passed`, `instance_prepare.glsl local_size` present, `ldd nm` still `gdext_library_init`, `res://` `checked ext_resources 9+ ok 0 missing`.

---

## 30. Evidence Required

- `git branch --show-current` `arena/01a0a5a2-astra-cosmos`, `git log --oneline -3`, `godot --version` `4.4.1`, `godot --headless --scene ...phase05_validation.tscn` `stdout` with `[OK]LOD/culling/streaming/5 presets` lines `exit 0`, plus re-run outputs `phase01–04` exit 0, `ldd libastra*.so` + `nm -D gdext_library_init`, `python validate_*.py` `57→70+ OK`, `SHADER_CATALOG.md` line count, `PerformanceMonitor` `Telemetry` excerpt with `draw/visible/culled/TARGET vs MEASURED` tags.

---

## 31. Final Status Criteria

- **GREEN (production production):** all §29 + actual `godot --headless` 5-scene loop `0 FAIL`, `TARGET` budgets documented separate `MEASURED` via `RenderingServer` when Vulkan host (`fps 55+ HIGH 10k`, `draw_calls`, `visible capped` verified), `RenderingMethod FORWARD+` runtime verified (or `Compatibility` correctly detected ` LOW` branch), no P0/P1
- **YELLOW (implementation complete, GPU-unverified):** all `validate_*` 0 FAIL, scenes exist, `Lod/culling/streaming` logic verified via GDScript fallback + `ResourceLoader` + `visible counts`, but `godot`/`RenderingDevice`/`Vulkan` not available on CI (`ENVIRONMENT BLOCKED` — `SSL_ERROR_SYSCALL` to `release-assets`, `headless no GPU`) so no pixel/timing MEASURED; fallback paths proven, specs delivered. Prior 01–04 also YELLOW — acceptable since `GODOT_PHASES/` 5 specs + `VALIDATION_REPORT.md` correct.
- **RED:** blocking: `phase05` breaks any `phase01–04` validation, `50k instancing` not culling (`visible==total` when should cull), `LOD` wrong tiers, `preset LOW` not reducing particles/fog, `res://` `ExtResource` dangling, `instance_prepare.glsl` missing `local_size`, or `5 specs` not delivered.

*Principle `code exists≠GREEN` applies: `YELLOW` is correct when `ENVIRONMENT BLOCKED`.*

---

## 32. Handoff to Next Phase (Production Release)

- **Preservation:** All `visualization/godot/phase_01–05/` scenes and `visualization/godot/shaders`/`materials` remain `git`-tracked; new work branches from `arena/01a0a5a2-astra-cosmos` and respects optimizer decorators (no bypassing `LODManager` direct `multimesh` writes).
- **No further phase:** This is terminal phase. Follow-on work: exporter/itch.io build, WGSL headless CI GPU runner, or `Phase 06 networking` (not designed here) — reuse `PerformanceMonitor` metrics as baseline for any new feature budget.
- **For future agents:** Read `GODOT_PHASES/PHASE_01–05.md` in order, run `godot --headless` suite before changing presets/shaders, keep `VALIDATION_REPORT.md` taxonomy, never fabricate FPS.

---

*Phase 05 ships what Phases 01–04 imagined — fast, faithful, and verifiable even without a GPU on CI.*
