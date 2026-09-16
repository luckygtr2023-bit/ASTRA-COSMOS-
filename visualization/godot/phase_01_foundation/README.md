# Phase 01 — Rendering Foundation

**Target:** Godot 4.4.1 stable, Forward+ (desktop), Compatibility (web/debug)  
**Branch:** `arena/01a0a5a2-astra-cosmos`  
**Status taxonomy:** STATIC VERIFIED / RUNTIME VERIFIED / NOT VERIFIED / ENVIRONMENT BLOCKED

## Forward+ Configuration

| Field | Value | Verified |
|---|---|---|
| `config_version` | `5` | `cat project.godot` |
| `renderer/rendering_method` desktop | `forward_plus` | `validate_godot_project.py` |
| `renderer/rendering_method.mobile` | `forward_plus` | same |
| `renderer/rendering_method.web` | `gl_compatibility` | web only |
| `default_environment` | `res://phase_01_foundation/environments/default_env.tres` | exists, `volumetric_fog_enabled true`, `glow_enabled true` |
| `physics_ticks` | `60` | `common/physics_ticks_per_second=60` |
| `autoloads` | `AstraBridge`, `QualityPresets`, `Telemetry` at `res://phase_01_foundation/scripts/*` | 3 present |
| `input` | `orbit_modifier`, `free_camera_forward` | mapped |

Single `[rendering]` section, no duplicate.

## Bridge

`AstraBridge.gd` (autoload) polls `res://../../bridge_state.json` (relative to `visualization/godot/`) with `FileAccess.open` guard, 30 Hz `POLL_INTERVAL 1/30`, `JSON.parse`, `hash != _last_state.hash()` emit `render_state_updated`. `request_interaction(action:Dictionary)->Dictionary` delegates to `astra.interaction.InteractionEngine` (offline echo, never `set_position_directly`/`teleport`). `get_origin_offset()`/`get_frame_id()` are single source for `ObjectRegistry`.

Render-state dict: `tick`, `simulation_time_s`, `frame_id`, `origin_offset`, `objects[] {id,kind,position[3],frame,classification,lod,material}`, `camera`, `quality`.

## Coordinate & Hierarchy

- `CoordinateBridge.gd` `origin_offset:Vector3`, `world_to_local`/`local_to_world`, `rebase(new_origin)` via `Tween` `0.6s TRANS_SINE EASE_IN_OUT` (no teleport).
- Five-level hierarchy validation `World(10,0,0)`→`System`→`Galactic`→`Cosmological`→`Universe`→`DeterministicTestObject(2,0,0)` = world `52,0,0` ±0.001 (checked via `global_position`).
- Floating-origin at `1e3, 1e11, 1e16, 1e21, 1e26` scientific unchanged, render stable `5,0,0` via `OriginRebaser`/`CoordinateBridge`.

## Validation Scene

`scenes/phase01_validation.tscn` UID `uid://astra_phase01_validation` `load_steps=8` deterministic seed `0xA573`:

- `Phase01Root` `Node` script `phase01_validation.gd`
  - `WorldEnvironment` `default_env.tres`
  - `TestLight` `DirectionalLight3D` `energy 1.2 shadows true` at `10,10` rot `45,30,0`
  - `TestCameraSystem` `Node3D` `camera_system.gd` `mode 0 distance 20 smooth 6` → `TestCamera` `Camera3D` `fov60 current` at `0,5,10` → `CoordinateBridge`
  - `CoordinateGrid` `MeshInstance3D` `ImmediateMesh` 10×10 lines `y=0 -50..50 step10` (built by script if missing)
  - `OriginMarker` `SphereMesh 0.5` red at `0,0,0`
  - `FloatingOriginMarker` `SphereMesh 0.35` blue at `5,0,0`
  - `HierarchyRoot` chain as above → `DeterministicTestObject` `BoxMesh 1,1,1` at `2,0,0` world `52,0,0`
  - `DiagnosticsOverlay` `CanvasLayer layer100` → `DiagnosticsLabel` `Label 10,10 800×600 font12`
  - `ObjectRegistry` `object_registry.gd` + `Telemetry` `telemetry.gd`

Headless `DisplayServer headless` → `get_tree().quit(0/1)` after `0.5s`. No `randf()` unless `seed(0xA573)`.

Plus `scenes/validation.tscn` legacy and `scenes/main.tscn` (WorldEnvironment+CameraSystem+ObjectRegistry+DirectionalLight).

## Scripts

- `astra_bridge.gd` signals `render_state_updated`/`astra_event`, `_origin_offset`, `request_interaction`, `get_origin_offset`, `_poll_astra` guard
- `coordinate_bridge.gd` `class_name CoordinateBridge` 0.6s tween
- `object_registry.gd` `class_name ObjectRegistry` `MultiMeshInstance3D` per kind, `pos -= AstraBridge.get_origin_offset()`
- `camera_system.gd` `class_name CameraSystem` `enum Mode {ORBITAL,FREE,SPACECRAFT,OBSERVATION,CINEMATIC,REPLAY}` 6 modes, `set_mode`/`set_target`/`_update_orbital/free/cinematic`
- `quality_presets.gd` `enum Preset {LOW,MEDIUM,HIGH,ULTRA,CINEMATIC}` `_detect_hardware()` via `RenderingServer.get_video_adapter_name()`+`OS.get_memory_info()`, `apply` toggles `volumetric_fog/glow/SSAO`, `is_forward_plus()`
- `telemetry.gd` `_fps_history` every 60 frames `fps/avg60/objects`
- `shader_manager.gd` `class_name ShaderManager` `get_shader(kind,classification)` fallback `star_corona`
- `phase01_validation.gd` `DETERMINISTIC_SEED 0xA573` 400L, headless quit

`gdscript/warnings/untyped_declaration=1`, `inferred_declaration=1` in `project.godot`.

## Shaders & Materials

- 19 `.gdshader`/`.glsl` at `visualization/godot/shaders/` mirrored from `visualization/shaders/` (canonical retained), `utility/common_lib.gdshaderinc` 13 lines via `#include "res://shaders/utility/common_lib.gdshaderinc"` in terrain, `compute/instance_prepare.glsl` `layout(local_size_x =256)` `#[compute]` `version 450`.
- Phase 01 runtime via `ResourceLoader.exists+load` 4 shaders: `celestial/star_corona`, `terrain/heightmap_terrain`, `stars/procedural_starfield`, `spacetime/grid_curvature` + `common_lib` + `planet_material.tres`/`star_material.tres`.

- `materials/planet_material.tres` `ShaderMaterial` `ExtResource("1_terrain") → res://shaders/terrain/heightmap_terrain.gdshader` numeric id `height_scale 400.0`, no `1_celestial_star`, no `res://../assets`, `checked ext_resources: 1 ok`
- `materials/star_material.tres` `StandardMaterial3D` `albedo 0.95,0.92,0.85,1` `emission 2.5`

## GDExtension

`visualization/scripts/cpp/gdextension_instance.cpp` `GDCLASS(AstraInstanceHelper, RefCounted)` `prepare_buffers(origin_offset,count)->PackedVector3Array` `get_version()` `initialize_astra_module` `uninitialize` `extern "C" GDE_EXPORT gdext_library_init`. Build `pip install scons` → `scons target=template_release api_version=4.4 -j2` in `visualization/scripts/cpp` (requires `godot-cpp` at `visualization/scripts/cpp/godot-cpp` cloned `https://github.com/godotengine/godot-cpp.git` branch `4.4`). Output `visualization/godot/extensions/bin/libastra_visualization.linux.template_release.x86_64.so` **601K**, `nm -D` shows `T gdext_library_init`, `ldd` OK, `ctypes.CDLL` OK. `extensions/astra_visualization.gdextension` `entry_symbol="gdext_library_init"` `compatibility_minimum="4.4"` `linux.release.x86_64="res://extensions/bin/libastra_visualization.linux.template_release.x86_64.so"` + copy to `godot/extensions/bin/`. GDScript 10k `0.14ms` fallback covers Vulkan unavailable.

## How to Validate

```bash
# Static (no Godot)
python visualization/tools/validate_godot_project.py # 57 OK 0 FAIL
python visualization/tools/validate_coordinates.py   # 27 OK
python visualization/tools/validate_shaders.py       # 19/19
python visualization/tools/validate_assets.py        # PASSED
python visualization/scripts/utilities/validate_bridge.py # 3 objects
PYTHONPATH=. pytest -q                               # 1660 passed
node visualization/scripts/node/generate_manifest.js # 9 assets
python visualization/tools/generate_shader_catalog.py # 23 lines
python visualization/tools/generate_lut.py

# GDExtension compile
scons target=template_release api_version=4.4 -j2 # in visualization/scripts/cpp
nm -D visualization/godot/extensions/bin/libastra_visualization.linux.template_release.x86_64.so | grep gdext_library_init
ldd   visualization/godot/extensions/bin/libastra_visualization.linux.template_release.x86_64.so

# Runtime (requires Godot 4.4.1)
godot --version # 4.4.1.stable.official
godot --path visualization/godot --headless --scene res://phase_01_foundation/scenes/phase01_validation.tscn
# → [OK] Hierarchy world-space 52,0,0 err 0.000000, 5-origin stable, 6 camera modes, 4 shaders, 2 materials, Summary X OK 0 FAIL, exit 0
godot --path visualization/godot --headless --scene res://phase_01_foundation/scenes/main.tscn
# → Telemetry every 60 frames, 0 fatal
```

If `godot` not installed, mark `ENVIRONMENT BLOCKED` — do not fabricate. See `visualization/VALIDATION_REPORT.md` taxonomy.
