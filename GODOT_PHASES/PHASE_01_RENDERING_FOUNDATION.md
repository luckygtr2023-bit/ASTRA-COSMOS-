# GODOT PHASE 01 — RENDERING FOUNDATION

**Version:** 1.0 — 2026-09-17  
**Target:** Godot 4.4.1 stable, Forward+ (desktop), Compatibility (web/debug)  
**Branch:** `arena/01a0a5a2-astra-cosmos`  
**Prerequisite:** Repository already contains `visualization/godot/`, 19 shaders, 10 VFX, materials, validation work — AUDIT BEFORE BUILDING.  
**Status taxonomy:** STATIC VERIFIED / RUNTIME VERIFIED / NOT VERIFIED / ENVIRONMENT BLOCKED (implemented ≠ verified).

---

## 1. Phase Identity

- **Phase:** `PHASE_01_RENDERING_FOUNDATION`
- **Order:** 1 of 5 (`01 → 02 → 03 → 04 → 05`)
- **Code prefix:** `phase_01_foundation/` under `visualization/godot/`
- **Deliverable directory:** `GODOT_PHASES/PHASE_01_RENDERING_FOUNDATION.md` (this file); implementation lives in `visualization/godot/phase_01_foundation/` plus project-level `visualization/godot/project.godot`.
- **Gate file:** `visualization/VALIDATION_REPORT.md` section `PHASE 01 RUNTIME IMPLEMENTATION` distinguishes prior evidence vs current run.

---

## 2. Objective

Make Godot Phase 01 **actually runnable and deterministically verifiable** on a machine with Godot 4.4.1 and Forward+.

Provide: project foundation, Forward+ renderer init, graphics capability detection, ASTRA→Godot bridge, render-state representation, object registry (instancing), hierarchical coordinates with floating-origin, simulation/render boundary, camera foundation (6 modes with extension point), debug/diagnostics/telemetry, deterministic validation scene, clean init/shutdown, GDExtension integration (compile where justified, fallback otherwise), resource-path safety, and **runtime validation** (headless where possible). No Phase 02-05 features.

---

## 3. Scope

**In scope:**

- `project.godot` Forward+ config, `config_version=5`, autoloads `AstraBridge`, `QualityPresets`, `Telemetry`, input map `orbit_modifier`/`free_camera_forward`, physics `60 Hz`, `WorldEnvironment` default
- ASTRA Visualization API (read-only render-state), `AstraBridge.gd` polling (`bridge_state.json` 30 Hz fallback + HTTP), `request_interaction()` delegation to `astra.interaction.InteractionEngine`
- Render-state dict: `tick`, `simulation_time_s`, `frame_id`, `origin_offset`, `objects[]` (`id`, `kind`, `position[3]`, `frame`, `classification`, `lod`, `material`), `camera`, `quality`
- `ObjectRegistry.gd` bucketed `MultiMeshInstance3D` per `kind`, `instance_count`/`visible_instance_count`, `get_origin_offset()` subtraction, `custom_data` LOD
- `CoordinateBridge.gd` `origin_offset: Vector3`, `world_to_local`/`local_to_world`, `rebase(new_origin)` via `Tween` 0.6s `SINE/EASE_IN_OUT` (no teleport)
- Five-level hierarchy validation (`World(10,0,0)` → `System` → `Galactic` → `Cosmological` → `Universe` → `DeterministicTestObject(2,0,0)` = world `52,0,0`)
- Floating-origin at `1e3, 1e11, 1e16, 1e21, 1e26` (scientific unchanged, render stable at `5,0,0`)
- Camera foundation: `free`, `follow`, `orbit`, `scientific observation`, `spacecraft`, `cinematic` (foundation) via `CameraSystem.gd` `enum Mode {ORBITAL,FREE,SPACECRAFT,OBSERVATION,CINEMATIC,REPLAY}` + `set_mode`/`set_target`/`_update_orbital/free/cinematic` + 6-mode validation
- Debug: `DiagnosticsOverlay` `CanvasLayer` + `DiagnosticsLabel` (sim time, object count, camera pos, origin offset, renderer, FPS, frame time, bridge state), `CoordinateGrid` `ImmediateMesh` 10×10, `OriginMarker` red, `FloatingOriginMarker` blue
- Telemetry: `Telemetry.gd` every 60 frames `fps, avg60, objects`, `RenderingServer.get_rendering_info` draw calls when available; `phase01_validation.gd` `_process` label
- Deterministic validation scene `phase01_validation.tscn` (UID `uid://astra_phase01_validation`) with above plus `WorldEnvironment`/`TestLight`
- Clean init/shutdown: `_ready` builds deterministically (seed `0xA573`), headless `get_tree().quit(0/1)` after 0.5s, no leaked nodes
- GDExtension: `visualization/scripts/cpp/gdextension_instance.cpp` with `gdext_library_init` + `AstraInstanceHelper.prepare_buffers(origin_offset,count)`; build `scons target=template_release api_version=4.4`; fallback GDScript path documented
- Resource-path safety & runtime validation (see §24, §26)

**Out of scope — see §4.**

---

## 4. Non-Goals

- Do not implement Phase 02 astronomical (stars/planets/nebulae/galaxies)
- Do not implement Phase 03 extreme physics (black holes/lensing/wormholes)
- Do not implement Phase 04 VFX/cinematics beyond loading check
- Do not implement Phase 05 HLOD/streaming/async optimization
- Do not redesign ASTRA physics, `astra.core`, `astra.temporal`, `astra.world`
- Do not add commercial assets, GPL, `three`/`babylon` render loops
- Do not add landing page, auth, player DB, lobby (product layer)

---

## 5. Existing ASTRA Systems to Inspect

Before coding, read (do not modify):

- `astra/core/coords.py` — `CoordinateFrame`, `OriginRebaseRequest`, `OriginRebaser` (floating-origin logic Python)
- `astra/core/engine.py` / `astra/core/scene.py` — authoritative `Engine.tick()` → `Scene`
- `astra/world/hierarchy.py` — `WorldHierarchy`/`WorldNode` DAG, cycle detection — your 5-level hierarchy must mirror this
- `astra/world/scene_graph.py`, `astra/world/spatial.py` — spatial queries used by ObjectRegistry culling later
- `astra/interaction/engine.py` — `InteractionEngine`, dispatch → `RenderState`, `request_interaction` contract (no `set_position_directly`)
- `astra/temporal/` — `SimulationClock`, `TimeMode` (bridge must not mutate `sim_time`)
- `astra/scientific/` + `astra/theoretical/` — `classification` enums that `ShaderManager` maps (visual honesty)
- `tests/test_interaction.py` — 48 tests define FSM, `request_interaction` success/failure shapes

**Reuse note:** All above are **read-only** from Godot. If you need a new field, add it in `bridge_state.json` generation (Python), not in GDScript.

---

## 6. Existing Visualization Systems to Reuse

**AUDIT EXISTING → REUSE WHERE CORRECT → EXTEND → TEST**

- `visualization/godot/project.godot` — already Forward+ (`renderer/rendering_method="forward_plus"` desktop/mobile, `gl_compatibility` web). Audit: ensure single `[rendering]`, `config_version=5`, autoloads at `res://phase_01_foundation/scripts/*`. If fixing, sync `visualization/scripts/gdscript/` copies.
- `visualization/godot/phase_01_foundation/scripts/` (7 files): `astra_bridge.gd`, `coordinate_bridge.gd`, `object_registry.gd`, `camera_system.gd`, `quality_presets.gd`, `telemetry.gd`, `shader_manager.gd` + `validation.gd`/`phase01_validation.gd`. Reuse all; enhance, don’t rewrite. `astra_bridge.gd` already polls `res://../../bridge_state.json` with guard.
- `visualization/godot/phase_01_foundation/scenes/` — `main.tscn`, `validation.tscn`, `phase01_validation.tscn` (new). Reuse, extend validation scene per §11.
- `visualization/godot/phase_01_foundation/environments/default_env.tres` — `volumetric_fog_enabled true`, `glow_enabled true` — keep.
- `visualization/godot/phase_01_foundation/assets/icon.svg`
- `visualization/godot/shaders/` + `visualization/shaders/` — 19 `.gdshader`/`.glsl` + `utility/common_lib.gdshaderinc` (Phase 01 needs `star_corona`, `heightmap_terrain`, `procedural_starfield`, `grid_curvature` coverage)
- `visualization/godot/vfx/` + `visualization/vfx/` — 10 categories (existence check only for Phase 01)
- `visualization/godot/materials/` — `planet_material.tres` already fixed to `res://shaders/terrain/heightmap_terrain.gdshader` id `1_terrain`, `star_material.tres` `StandardMaterial3D`
- `visualization/godot/VERSION.md` — declares Godot 4.4.1 Forward+ — update if you change renderer config
- `visualization/tools/` — `validate_godot_project.py` (57 checks), `validate_coordinates.py` (27), `validate_shaders.py` (19), `validate_assets.py` (9), `generate_shader_catalog.py`, `generate_lut.py`, `evaluate_addons.py` — extend, don’t duplicate
- `visualization/ARCHITECTURE.md`, `INTEGRATION.md`, `PERFORMANCE.md`, `QUALITY_PRESETS.md` — update deltas only

If you find earlier bugs (duplicate `[rendering]`, `gl_compatibility` fallback, placeholder `ExtResource("1_celestial_star")`, shaders outside `res://`), fix by copying/rewriting as done in `708d487`/`03628f2`, not by adding new parallel systems.

---

## 7. Architecture

```
ASTRA SCIENTIFIC SIMULATION  (Python: astra.core.Engine, astra.world, astra.temporal)
        ↓ snapshot @ tick
ASTRA VISUALIZATION API      (Python → JSON bridge_state.json, HTTP optional)
        ↓ render-state dict (tick, sim_time, origin_offset, objects[], camera, quality)
GODOT AUTOLOADS              (AstraBridge 30Hz poll, QualityPresets, Telemetry)
        ↓
CoordinateBridge (origin_offset, frame_id)  +  ObjectRegistry (MultiMesh buckets)  +  ShaderManager (classification→material)
        ↓
phase01_validation.tscn / main.tscn (WorldEnvironment, Grid, Markers, DiagnosticsOverlay)
        ↓
GODOT RENDERER (Forward+, Vulkan) → GPU
```

**Invariants:**

- Godot never writes `sim_time`, `position`, `velocity` directly; all interaction goes `AstraBridge.request_interaction() → astra.interaction.InteractionEngine.dispatch() → new state → Godot`.
- `origin_offset` tweened 0.6s `SINE/EASE_IN_OUT`, no teleport; `AstraBridge.get_origin_offset()` is single source for render subtraction.
- `ObjectRegistry` owns no physics; `ShaderManager` owns no classification invention (speculative uses distinct shader + tag).

---

## 8. Data Flow

**ASTRA→Godot (per frame, 30Hz viz):**

1. `Engine.tick()` → `Scene` + `OriginRebaser` (if `distance > 5000` rebase)
2. `InteractionEngine` serializes `bridge_state.json` with `objects[]` positions in authoritative double (Python) → rounded to float for JSON
3. `AstraBridge._poll_astra()` `FileAccess.open("res://../../bridge_state.json")` guard → `JSON.parse` → `if hash != _last_state.hash()` → `render_state_updated.emit(state)` → `ObjectRegistry.update_render_state(state)` subtracts `origin_offset`, `CameraSystem` follows `state.camera.target`
4. `CoordinateBridge.world_to_local()` converts any debug query

**Godot→ASTRA (on input):**

1. Input (e.g., `orbit_modifier`) → `phase01_validation.gd` builds `{"type":"NAVIGATE","target_id":"..."}`
2. `AstraBridge.request_interaction(action)` prints, `astra_event.emit`, returns `{"success":bool, "note": "delegated..."}` (offline echo)
3. Future real build: HTTP POST to `http://localhost:8000/visualization` → Python validates via `astra.interaction`

**Implementation agent must keep `bridge_state.json` path `res://../../bridge_state.json` relative to `visualization/godot/` (i.e., `visualization/bridge_state.json` when repo root is `..`/`..`), with `if file:` guard, no `ExtResource` outside.

---

## 9. Required Systems

- **GodotProject:** `project.godot`, autoloads, input map, `config_version=5`
- **AstraBridge:** autoload `Node`, signals `render_state_updated`/`astra_event`, `origin_offset: Vector3`, `frame_id`, `request_interaction()`, `get_origin_offset()`, `get_frame_id()`
- **CoordinateBridge:** `Node` `origin_offset`, `world_to_local`, `local_to_world`, `rebase(new_origin)` Tween
- **ObjectRegistry:** `Node` bucketed `MultiMeshInstance3D`, `register_kind`, `update_render_state`
- **RenderState:** dict shape above, no class (keeps serialization trivial)
- **CameraFoundation:** `CameraSystem` `Node3D` with 6 modes + `TestCamera` `Camera3D`
- **DebugVis:** `CoordinateGrid` `ImmediateMesh`, `OriginMarker`/`FloatingOriginMarker` spheres, `DiagnosticsOverlay` `CanvasLayer`+`Label`
- **Telemetry:** `Telemetry.gd` 60-frame avg, `phase01_validation.gd` `_process` label
- **Validation:** `phase01_validation.gd` deterministic seed `0xA573`, 5-level hierarchy, 5-distance floating-origin, headless quit

---

## 10. Required Files/Directories

Audit then ensure existence (reuse, don’t duplicate sibling `visualization/shaders` vs `visualization/godot/shaders` — keep canonical + `res://` copy as in `708d487`):

```
visualization/godot/project.godot  (Forward+ verified)
visualization/godot/VERSION.md
visualization/godot/bridge_state.json  (3-object sample, tick 42, sim_time 1234.5)
visualization/godot/phase_01_foundation/
  README.md
  assets/icon.svg
  environments/default_env.tres
  scenes/main.tscn
  scenes/validation.tscn  (legacy)
  scenes/phase01_validation.tscn  (required, 8 load_steps, UID uid://astra_phase01_validation)
  scripts/astra_bridge.gd
  scripts/coordinate_bridge.gd
  scripts/object_registry.gd
  scripts/camera_system.gd  (enum 6 modes)
  scripts/quality_presets.gd  (5 presets)
  scripts/telemetry.gd
  scripts/shader_manager.gd
  scripts/validation.gd  (legacy)
  scripts/phase01_validation.gd  (required, 400L deterministic)
visualization/godot/shaders/  (19 mirrored from visualization/shaders/)
visualization/godot/vfx/  (10 mirrored)
visualization/godot/materials/planet_material.tres, star_material.tres
visualization/godot/extensions/astra_visualization.gdextension + bin/libastra_visualization.linux.template_release.x86_64.so (601K, gdext_library_init)
visualization/scripts/cpp/gdextension_instance.cpp + SConstruct (api_version=4.4)
visualization/tools/validate_godot_project.py, validate_coordinates.py, etc.
```

**Do not create** `phase_02`–`05` directories here.

---

## 11. Godot Scene Requirements

**`phase01_validation.tscn` must contain (deterministic transforms):**

- `Phase01Root` `Node` with `phase01_validation.gd`
  - `WorldEnvironment` environment `res://phase_01_foundation/environments/default_env.tres`
  - `TestLight` `DirectionalLight3D` `light_energy 1.2`, `shadow_enabled true`, `transform` at (10,10) rotated 45,30,0
  - `TestCameraSystem` `Node3D` script `camera_system.gd` `mode 0` `distance 20` `smooth 6` → `TestCamera` `Camera3D` fov60 current at (0,5,10) → `CoordinateBridge` `Node` script `coordinate_bridge.gd`
  - `CoordinateGrid` `MeshInstance3D` `ImmediateMesh` 10×10 lines y=0 −50..50 step10 (built by script if not in scene)
  - `OriginMarker` `SphereMesh` radius0.5 at `0,0,0` red `StandardMaterial3D`
  - `FloatingOriginMarker` `SphereMesh` radius0.35 at `5,0,0` blue
  - `HierarchyRoot` `Node3D` → `World(10,0,0)` → `System(10,0,0)` → `Galactic(10,0,0)` → `Cosmological(10,0,0)` → `Universe(10,0,0)` → `DeterministicTestObject` `BoxMesh` 1,1,1 at `2,0,0` (world `52,0,0`)
  - `DiagnosticsOverlay` `CanvasLayer` layer100 → `DiagnosticsLabel` `Label` 10,10 800×600 font12
  - `ObjectRegistry` `Node` script `object_registry.gd`
  - `Telemetry` `Node` script `telemetry.gd`

All positions fixed; no `randf()` unless `seed(0xA573)` explicitly before. Headless `DisplayServer.get_name()=="headless"` → `get_tree().quit` after 0.5s.

---

## 12. GDScript Requirements

- **Language:** GDScript 2.0 (Godot 4.x), typed (`var _ok:int`), no `def`, no `import`, `class_name` where reusable.
- **Files to implement/audit:**

| File | Key API |
|---|---|
| `astra_bridge.gd` | `signal render_state_updated`, `signal astra_event`, `var _origin_offset:Vector3`, `func request_interaction(action:Dictionary)->Dictionary` (no `set_position_directly`/`teleport`), `func get_origin_offset()->Vector3`, `_poll_astra()` with `FileAccess.open` guard |
| `coordinate_bridge.gd` | `class_name CoordinateBridge`, `var origin_offset:Vector3`, `func world_to_local`, `func local_to_world`, `func rebase(new_origin:Vector3)` Tween 0.6s `SINE/EASE_IN_OUT` |
| `object_registry.gd` | `class_name ObjectRegistry`, `var _multimeshes:Dictionary`, `func register_kind`, `func update_render_state(state:Dictionary)` bucket + `pos -= AstraBridge.get_origin_offset()` |
| `camera_system.gd` | `class_name CameraSystem`, `enum Mode {ORBITAL,FREE,SPACECRAFT,OBSERVATION,CINEMATIC,REPLAY}`, `var mode:Mode`, `var target:Node3D`, `func set_mode`, `func set_target`, `_update_orbital/free/cinematic` |
| `quality_presets.gd` | `enum Preset {LOW,MEDIUM,HIGH,ULTRA,CINEMATIC}`, `func _detect_hardware()` via `RenderingServer.get_video_adapter_name()`+`OS.get_memory_info()`, `func apply(p:Preset)` toggling `volumetric_fog_enabled`/`glow_enabled`/`SSAO`, `func is_forward_plus()->bool` |
| `telemetry.gd` | `var _fps_history:Array`, `_process` every 60 frames `fps, avg60, objects` via `Engine.get_frames_per_second()` |
| `shader_manager.gd` | `class_name ShaderManager`, `func get_shader(kind,classification)->ShaderMaterial` fallback to `star_corona` |
| `phase01_validation.gd` | `extends Node`, `const DETERMINISTIC_SEED=0xA573`, `var _ok/_fail/_warn`, `_build_*`, `_run_*`, `_check`, headless quit, no `teleport` |

- **Warnings:** `gdscript/warnings/untyped_declaration=1`, `inferred_declaration=1` in `project.godot` must stay.

---

## 13. Shader Requirements

**Phase 01 does not redesign shaders.** Static 19 `.gdshader`/`.glsl` already exist and pass `validate_shaders.py` (19/19: `shader_type` present, no python, `impact_spark` uses `RANDOM_SEED` not `randf()`).

**Runtime coverage for Phase 01 infrastructure (not full 19 claim):**

- Load 4 representative via `ResourceLoader.exists` + `load` in `phase01_validation.gd`: `res://shaders/celestial/star_corona.gdshader`, `res://shaders/terrain/heightmap_terrain.gdshader`, `res://shaders/stars/procedural_starfield.gdshader`, `res://shaders/spacetime/grid_curvature.gdshader` + `res://shaders/utility/common_lib.gdshaderinc` via `#include "res://shaders/utility/common_lib.gdshaderinc"` in terrain (13 lines).
- `shaders/compute/instance_prepare.glsl` must have `layout(local_size` (checked by `validate_godot_project.py`).
- Full 19 runtime compile remains **STATIC vs RUNTIME separate** — do not claim `19/19 runtime` unless `godot --headless` actually loads each via `load()` and `shader != null`.

---

## 14. Material Requirements

- `visualization/godot/materials/planet_material.tres`: `ShaderMaterial`, `ExtResource("1_terrain")` → `res://shaders/terrain/heightmap_terrain.gdshader` numeric id, `shader_parameter/height_scale 400.0`, no `1_celestial_star`, no `res://../assets`, no `SubResource(GradientTexture1D_xxx)`, `checked ext_resources: 1 ok`.
- `visualization/godot/materials/star_material.tres`: `StandardMaterial3D`, `albedo_color 0.95,0.92,0.85,1`, `emission_enabled true`, `emission_energy_multiplier 2.5`, no `ExtResource` dangling.
- Phase 01 loads both via `ResourceLoader.exists` + `load` in `phase01_validation.gd` and checks `shader != null`.

---

## 15. C++/GDExtension Requirements Where Justified

- **Justification:** `visualization/scripts/cpp/gdextension_instance.cpp` exists because `ObjectRegistry` 50k+ instance `PackedVector3Array` prep at 60 Hz justifies 15× speedup (`1.2ms` GDScript → `0.08ms` compute on RTX 3060 per `PERFORMANCE.md`). Not for gameplay logic.
- **Files:** `visualization/scripts/cpp/SConstruct` (expects `godot-cpp/SConstruct`), `visualization/scripts/cpp/gdextension_instance.cpp` with `GDCLASS(AstraInstanceHelper, RefCounted)`, `prepare_buffers(origin_offset, count)->PackedVector3Array`, `get_version()`, `initialize_astra_module`/`uninitialize`, `extern "C" GDE_EXPORT gdext_library_init`.
- **Build:** `pip install --break-system-packages scons` → `scons target=template_release api_version=4.4 -j2` in `visualization/scripts/cpp` (requires `godot-cpp` cloned from `https://github.com/godotengine/godot-cpp.git` to `visualization/scripts/cpp/godot-cpp`). Output `bin/libastra_visualization.linux.template_release.x86_64.so` **601K**, `nm -D` must show `T gdext_library_init`.
- **Godot integration:** `visualization/godot/extensions/astra_visualization.gdextension` with `entry_symbol="gdext_library_init"`, `compatibility_minimum="4.4"`, `linux.release.x86_64="res://extensions/bin/libastra_visualization.linux.template_release.x86_64.so"`, library copied to `visualization/godot/extensions/bin/`. **Fallback:** if `.so` missing or Vulkan unavailable, `ObjectRegistry` GDScript path is tested (10k 0.14ms).
- **Phase 01 gate:** **COMPILED** is VERIFIED via `ldd` + `ctypes.CDLL` + `nm`; **load** remains NOT VERIFIED until `godot --headless` can `AstraInstanceHelper.new()`. Do not make GDExtension mandatory for Phase 01 correctness.

---

## 16. Python Tooling Requirements Where Justified

- Reuse existing, extend where needed:

| Tool | Purpose | Command | Gate |
|---|---|---|---|
| `validate_godot_project.py` | 57 checks: `forward_plus`, autoloads, scripts, tres, shaders, compute, env, VFX | `python visualization/tools/validate_godot_project.py` | 57 OK 0 FAIL |
| `validate_coordinates.py` | 5 scales + hierarchy + bridge sanitization | `python visualization/tools/validate_coordinates.py` | 27 OK |
| `validate_shaders.py` | 19 static | `python visualization/tools/validate_shaders.py` | 19/19 |
| `validate_assets.py` | 9 assets <2MB, license counterpart | `python visualization/tools/validate_assets.py` | PASSED |
| `validate_bridge.py` | 3 objects | `python visualization/scripts/utilities/validate_bridge.py` | 3 objects |
| `generate_shader_catalog.py` | writes `SHADER_CATALOG.md` 23 lines | `python visualization/tools/generate_shader_catalog.py` | 23 lines |
| `generate_lut.py` | bakes `star_temperature_lut.ppm` | `python visualization/tools/generate_lut.py` | generated |

- No new Python dependencies without justification; keep `jsonschema`/`pyyaml` offline only.

---

## 17. Node/JavaScript Tooling Requirements Where Justified

- **Only offline:** `visualization/scripts/node/generate_manifest.js` (`fs` only, no `package.json` deps) → deterministic `manifest 9 assets`; `visualization/scripts/javascript/bridge_adapter.js` sanitizes `classification` allowlist, no render-loop dependency. `node v22.22.3` verified.
- **Do not introduce** `three`/`babylon` or npm runtime deps (would create second render loop — forbidden, see `DEPENDENCIES.md` rejection table).

---

## 18. Addon/Dependency Requirements

**Every external dependency must have:** purpose, version, source, license, integration reason, maintenance risk — documented in `visualization/DEPENDENCIES.md`.

- **Allowed (already):** Godot 4.4.1 MIT, `FastNoiseLite` Godot built-in MIT, `godotshaders.com` starfield/atmosphere/ocean MIT (adapted, exposure/Mie params), `FogVolume` built-in, `RenderingDevice` compute sample. All <5KB `.gdshader`, no network.
- **Rejected (documented):** `Terrain3D` GPL, `Gaea` commercial, `qodot` irrelevant, `Godot Volumetrics Extended` 3.x, `three`/`babylon` — see `DEPENDENCIES.md` 5 rejected.
- **Phase 01 adds no new addon.** If you propose one, run `tools/evaluate_addons.py` and document `DEPENDENCIES.md` before integrating.

---

## 19. Asset Requirements

- Reuse `visualization/assets/` 9 files: `README.md`, `luts/README.md`, `manifest.json`, `noise/README.md`, `particles/README.md`, `planets/README.md`+`earth_like_albedo.ppm` 512 CC0, `skyboxes/README.md`, `stars/star_temperature_lut.ppm` 16×256 (generated, CC0). All <2MB.
- `visualization/godot/phase_01_foundation/assets/icon.svg` — single.
- No `polyhaven` HDR, no binary blobs >2MB, no proprietary. `ASSET_LICENSES.md` documents CC0/MIT.

---

## 20. Coordinate-System Requirements

- **Authority:** `astra.core.coords.OriginRebaser` + `astra.world.hierarchy.WorldHierarchy` (Python double, DAG, cycle detection).
- **Godot:** `CoordinateBridge` `origin_offset:Vector3` (float), `frame_id:String`. All `Node3D.global_position` are `local = world - origin` per `object_registry.gd` `pos -= AstraBridge.get_origin_offset()`.
- **Five-level validation:** `HierarchyRoot` chain must produce world `52,0,0` ±0.001. Test A: local `0,0,0`, B: parent-relative `2,0,0`, C: nested sum, D: `world_to_local(100,0,0)`, E: `request_interaction` round-trip, F: floating-origin rebasing (see §21). Do not merely test `world - origin` subtraction; test full `Node3D` transform propagation via `global_position`.
- **Large distances:** must use `OriginRebaser`/`CoordinateBridge` indirection, not direct `Vector3(d)` where `d=1e26` would lose precision if not rebased.

---

## 21. ASTRA ↔ Godot Boundary

- **Direction ASTRA→Godot:** `bridge_state.json` JSON, validated by `validate_bridge.py` (finite positions, known `classification`). `AstraBridge._poll_astra()` 30 Hz, `hash != _last_state` emit. `ObjectRegistry` consumes, never reconstructs physics.
- **Direction Godot→ASTRA:** `AstraBridge.request_interaction(action:Dictionary)->Dictionary` — never `set_position_directly`/`teleport`. Example `{"type":"NAVIGATE","target_id":"galaxy-1"}` → Python `InteractionEngine.dispatch()` → new `tick`/`origin_offset` → Godot rebases via `CoordinateBridge.rebase()`.
- **Visual honesty:** `ShaderManager` maps `classification` `REAL_DATA`/`SIMULATED_DATA`/`THEORETICAL`/`SPECULATIVE` to distinct shaders; `SPECULATIVE` wormholes show watermark, not hidden. `Telemetry` logs distribution.
- **Malformed handling:** `JSON.parse` guard, `has_method` checks, `is_finite` checks — bridge must not crash on `{"id":"", "position":[0,0,"bad"]}`.

---

## 22. Performance Requirements

**TARGET (not MEASURED):** 60 fps @1080p on RTX 3060 `HIGH` (10k instanced), 30 fps on Intel UHD `LOW` (2k stars). Budgets per `PERFORMANCE.md`: `Stars 0.6ms` + `Planets 1.2ms` + `Atmosphere 0.4ms` + `Nebula 0.8ms` + `Lensing 1.0ms` + `VFX 0.5ms` + `Postprocess 0.7ms` = `~5.2ms` leaving 11ms for bridge.

**MEASURED where GPU available:**

- `Telemetry.gd` every 60 frames: `fps`, `avg60`, `object count`, `draw calls` (`RenderingServer.get_rendering_info`), `render update time`, `bridge update time`, `camera update time` — all labeled `MEASURED` vs `ESTIMATED`.
- Phase 01 smoke: `100 objects` `Node3D` add <100ms, `1k`/`10k` `WorldHierarchy` traversal `0.01ms`/`0.14ms` (Python), `10k MultiMesh` `0.6ms` **TARGET** (not claimed MEASURED without GPU). Do not claim `60 FPS` without `Telemetry` log.
- If GPU metrics unavailable (headless CI), explicitly mark `NOT VERIFIED (headless, no Vulkan)` — do not reuse old benchmark as new measurement.

---

## 23. Quality Presets

- `QualityPresets` autoload `enum Preset {LOW,MEDIUM,HIGH,ULTRA,CINEMATIC}` already implements `LOW|MEDIUM|HIGH|ULTRA|CINEMATIC` matrix (13 features: shadows 0/1024/2048/4096/8192, volumetrics 0/0/64/128/192, particles 32/128/256/512/1024, bloom off/0.2/0.35/0.6/0.8, star density 0.35-0.95, etc. per `QUALITY_PRESETS.md`).
- **Phase 01:** Verify `LOW` disables expensive (`volumetric_fog_enabled false`, `glow_enabled false`, `SSAO LOW`, 32 particles) and `CINEMATIC` enables `DoF`/`motion blur` 1.25× supersampling. Hardware detection via `RenderingServer.get_video_adapter_name()` + `OS.get_memory_info()` → `Intel/<3GB LOW`, `RTX40/RX7000 ULTRA`. Manual `--quality cinematic` override.
- **Do not**
  prematurely tune beyond Phase 01; `ULTRA`/`CINEMATIC` differences are minimal at this phase.

---

## 24. Security/Resource Boundaries

- **Resource paths constrained:** every `ExtResource` `path="res://..."` must resolve inside `visualization/godot` (`checked ext_resources: 1 ok, 0 missing` via `validate_godot_project.py`). Only allowed `res://../` is `astra_bridge.gd` `res://../../bridge_state.json` with `if file:` guard (offline fallback, not `ExtResource`); document as intentional. No `/home`/`/opt` absolute.
- **Bridge input validated:** `validate_bridge.py` rejects non-finite, unknown `classification`; `phase01_validation.gd` malformed test does not crash.
- **No unsafe file loading:** no `OS.execute` with downloaded scripts, no `eval`.
- **No external network calls:** `grep -rn "http"` only comments + `127.0.0.1` bridge. No `three`/`babylon` runtime.
- **Third-party license-documented:** `DEPENDENCIES.md`/`ASSET_LICENSES.md`/`THIRD_PARTY.md` all MIT/CC0, no `*.so` outside `extensions/bin`, no `*.zip`, no `node_modules`.

---

## 25. Testing Requirements

- **Unit:** `validate_coordinates.py` 5-level hierarchy, 5-distance floating-origin
- **Integration:** `validate_godot_project.py` 57 checks, `validate_bridge.py` 3 objects, `generate_manifest` deterministic
- **Godot runtime:** `phase01_validation.gd` `_check` per §6,7,8,13; headless `get_tree().quit(1)` on FAIL
- **Deterministic:** seed `0xA573`, no `randf()` unless seeded, world `52,0,0` exact
- **Failure:** malformed bridge `{"position":[0,0,"bad"]}` must not crash, `request_interaction` missing `target_id` → `{"success":false}`
- **Resource-loading:** `ResourceLoader.exists` + `load` for 4 shaders + 2 materials, `ext_resources` 1 ok
- **Performance:** `100 Node3D <100ms`, `1k/10k traversal` MEASURED
- **Regression:** `PYTHONPATH=. pytest -q` → `1660 passed` (baseline `c890d62`), do not assume — re-run

---

## 26. Runtime Validation Requirements

Actually launch Godot (do not rely solely on `validate_*`):

- `godot --path visualization/godot --headless --scene res://phase_01_foundation/scenes/phase01_validation.tscn` — must print `[OK] Hierarchy world-space 52,0,0`, 5-origin stable, 6 camera modes, `[Phase01] Summary: X OK, 0 FAIL`, exit 0
- `godot --path visualization/godot --headless --scene res://phase_01_foundation/scenes/main.tscn` — normal launch, `Telemetry` logs `fps avg60 objects` every 60 frames, exit 0
- `godot --version` → `4.4.1.stable.official`
- Capture: stdout, stderr, exit code, parser/resource/shader/script/missing/deprecation warnings — **zero fatal** required.

If Godot not installed, report `GODOT NOT AVAILABLE` and keep YELLOW — do not fabricate. Headless CI may lack GPU → mark `Graphics API/GPU` as `ENVIRONMENT BLOCKED`.

---

## 27. Failure Handling

- **Bridge malformed:** `JSON.parse` != `OK` → ignore, keep `_last_state`, log `WARN`
- **Missing resource:** `ResourceLoader.exists` false → `_check` FAIL, `get_tree().quit(1)` headless
- **Rebase failure:** `OriginRebaser` returns `success false` → keep old `origin_offset`, log
- **Camera target missing:** `if not target: return` in `_update_orbital` (already in `camera_system.gd`)
- **Never silently swallow:** all failures `print("[FAIL]")` + `_fail` increment, final `quit(1)`

---

## 28. Documentation Requirements

- Update `visualization/godot/phase_01_foundation/README.md` with `project.godot` Forward+ table, `phase01_validation.tscn` contents, how to run `godot --headless --scene ...`
- Update `visualization/VALIDATION_REPORT.md` with new section `PHASE 01 RUNTIME IMPLEMENTATION` preserving prior evidence, taxonomy `STATIC VERIFIED` vs `RUNTIME VERIFIED` vs `NOT VERIFIED` vs `ENVIRONMENT BLOCKED`, include `branch, commit, Godot version, renderer, GPU, test commands, exact results, runtime evidence, warnings/errors, remaining limitations`
- Update `visualization/docs/PHASES.md` if needed (already has Phase 01 line)
- No overwriting history without preservation

---

## 29. Completion Criteria

- `project.godot` Forward+ single `[rendering]` verified
- `phase01_validation.tscn` exists with all §11 nodes, deterministic
- 5-level hierarchy `52,0,0` passes (±0.001)
- 5 floating-origin distances stable with scientific unchanged
- 6 camera modes set + finite
- Bridge 3-object sample loads, malformed does not crash
- 4 shader + 2 material loads via `ResourceLoader`
- Telemetry prints every 60 frames, diagnostics label updates
- Clean init/shutdown, no leaked nodes, headless quit code correct
- GDExtension compiled **or** GDP fallback documented (scons 4.11.1, `gdext_library_init` present)
- 57 godot_project checks, 27 coordinates, 19 shaders, 9 assets, 1660 pytest all pass

---

## 30. Evidence Required

- `git branch --show-current` → `arena/01a0a5a2-astra-cosmos`
- `godot --version` → `4.4.1` (or `GODOT NOT AVAILABLE` with `curl -v` logs)
- `godot --path visualization/godot --headless --scene ...` stdout `[OK]` lines, exit code
- `ls -lh visualization/godot/extensions/bin/*.so` + `nm -D` `gdext_library_init` + `ldd`
- `python visualization/tools/validate_godot_project.py` 57 OK, `validate_coordinates.py` 27 OK, `pytest -q` 1660 passed logs
- Screenshots not required headless, but `DiagnosticsLabel` text captured in Output

---

## 31. Final Status Criteria

- **GREEN:** All §29 criteria + `godot --headless` actually executed with 0 FAIL, `FORWARD+` runtime verified via `RenderingServer`, GPU info queried (or correctly `NOT VERIFIED` headless with justification), no P0/P1. Requires Godot 4.4.1 + Vulkan host.
- **YELLOW:** Implementation exists (scene, scripts, GDExtension compiled) but Godot headless or GPU verification blocked (e.g., `SSL_ERROR_SYSCALL` to `release-assets`, `pkg-config` missing, headless CI). Not a code defect; GDScript fallback covers GDExtension.
- **RED:** Blocking defect: hierarchy `52,0,0` fails, floating-origin teleport, `project.godot` still `gl_compatibility`, `ExtResource` dangling, bridge crashes on malformed, or `validate_godot_project` >0 FAIL.

Never `code exists = GREEN`.

---

## 32. Handoff to Next Phase

- **Preserve:** Phase 01 scene remains loadable `godot --headless --scene phase01_validation.tscn` must keep passing after Phase 02 changes.
- **Dependencies for Phase 02:** `CoordinateBridge`, `ObjectRegistry` MultiMesh, `QualityPresets`, `ShaderManager` classification, `Floating-origin` must be reused (Phase 02 astronomical rendering adds instancing/LOD but not new coordinate system).
- **Do not break:** Do not duplicate `visualization/shaders` vs `visualization/godot/shaders` sync (keep `cp -r` as in `708d487`), do not reintroduce `res://../assets` outside.
- **Next agent:** Read this file + `visualization/godot/phase_01_foundation/` + `VALIDATION_REPORT.md` new section, then implement Phase 02 per `PHASE_02_ASTRONOMICAL_RENDERING.md`.

---

*Implementation model:* **inspect → plan → implement incrementally → test → fix → re-test → document → commit** on `arena/01a0a5a2-astra-cosmos`. Never fabricate FPS/GPU.
