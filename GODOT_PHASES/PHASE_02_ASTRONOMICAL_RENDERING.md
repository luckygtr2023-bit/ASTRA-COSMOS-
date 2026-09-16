# GODOT PHASE 02 — ASTRONOMICAL RENDERING

**Version:** 1.0 — 2026-09-17  
**Target:** Godot 4.4.1 Forward+ (RenderingDevice/Vulkan)  
**Branch:** `arena/01a0a5a2-astra-cosmos`  
**Prerequisite:** Phase 01 GREEN or YELLOW (floating-origin + hierarchy + bridge VERIFIED). This phase extends `ObjectRegistry`/`ShaderManager`; do not replace Phase 01 systems.  
**Status taxonomy:** STATIC VERIFIED / RUNTIME VERIFIED / NOT VERIFIED / ENVIRONMENT BLOCKED.

---

## 1. Phase Identity

- **Phase:** `PHASE_02_ASTRONOMICAL_RENDERING`
- **Order:** 2 of 5 (`01[X] → 02 → 03 → 04 → 05`)
- **Code prefix:** `phase_02_astronomical/` under `visualization/godot/`
- **Deliverable:** `GODOT_PHASES/PHASE_02_ASTRONOMICAL_RENDERING.md` (this file) + implementation `visualization/godot/phase_02_astronomical/`
- **Gate scene:** `phase02_validation.tscn` (analogous to `phase01_validation.tscn` deterministic seed `0xA574`)

---

## 2. Objective

Render the **astronomical population at scale** — stars (spectral/temperature), planets (spheroidal, not textured planes), nebula fields, galaxies, procedural terrain/sky/space — with **instancing, LOD, GPU-driven selection, and visual honesty** (REAL/SIMULATED/THEORETICAL/SPECULATIVE distinction carried into shaders).

Achieve **60 fps 1080p RTX 3060 HIGH** for `10k stars + 50 planets + 4 nebulae + 1 galaxy field` by leveraging `MultiMeshInstance3D`, procedural shaders, and compute-based LOD culling (prepare `RenderingDevice` path, GDScript fallback measured).

---

## 3. Scope

**In scope:**

- **Stars:** spectral `O/B/A/F/G/K/M` → `star_temperature_lut.ppm` (16×256 CC0) → `star_corona.gdshader` + `procedural_starfield.gdshader` skybox + `ShaderManager` temperature/size mapping; `StarRenderer.gd` using `ObjectRegistry` bucket `star` with `custom_data` temperature/luminosity
- **Planets:** `PlanetRenderer.gd` spheroid mesh (subdivided icosphere 2–5 LOD) + `heightmap_terrain.gdshader` (noise fBm, height_scale by `LOW/MEDIUM/HIGH` preset 100/400/800) + `atmosphere.gdshader` Rayleigh/Mie scattering (density by altitude, `4.0e-6`/`2.1e-5`); albedo from `earth_like_albedo.ppm` 512 and procedural fallback; `planet_material.tres` already correct `1_terrain`
- **Nebulae/Galaxies:** `NebulaRenderer.gd` volumetric fog (`volumetric_fog_enabled` true, density 64/128 per preset) via `nebula_volumetric.gdshader` + `galaxy_structure.gdshader` spiral density wave (2–4 arms, log spiral `b=0.22`), `GalaxyField.gd` 500-sample density texture
- **Procedural generation:** `FastNoiseLite` terrain (seeded `0xA574`), `noise/` `particles/` LUTs generation via `generate_lut.py`, deterministic per-seed reproduction, streaming tile budget 256 KB/tile
- **Instancing/LOD:** extend `ObjectRegistry` to `10k MultiMesh` target (48 measures), HLOD distance tiers `0–5/5–50/50–500/500–5k/5k+` `LOD0-4`, `instance_prepare.glsl` compute culling preparer (see §13), CPU frustum culling fallback
- **Materials:** reuse `planet_material.tres`/`star_material.tres`, add `nebula_material.tres`/`galaxy_material.tres` `ShaderMaterial` with correct `res://shaders/...` id numeric, no `GradientTexture1D` SubResource inside `.tres` (use `preload` or uniform)
- **Quality presets effect on astronomical:** `LOW` 2k stars 32 particles → `CINEMATIC` 20k stars 1.25× supersample per `QUALITY_PRESETS.md`
- **Telemetry:** extend to `draw_calls`, `instance_count`, `visible_instance_count`, `material switches`, per-renderer `update time` MEASURED
- **Validation scene:** deterministic star grid + planet hierarchy subset + `DiagnosticsOverlay` extended with `star count / planet verts / nebula density`
- **GDExtension where profiled:** `AstraInstanceHelper` already compiles — extend to `prepare_star_buffers`, `cull_lod(buffers)` ~0.08ms compute path, GDScript fallback measured

**Out of scope — see §4.**

---

## 4. Non-Goals

- No black hole ray-marching/lensing (Phase 03)
- No relativistic Doppler/redshift or wormhole topology (Phase 03)
- No explosion/collision/warp VFX or cinematic cameras (Phase 04)
- No full HLOD/streaming optimizer or `ULTRA` 8K supersampling pipeline (Phase 05); Phase 02 uses baseline LOD, not async streaming
- No new physics authority (still `astra.core` Python)

---

## 5. Existing ASTRA Systems to Inspect

- `astra/scientific/stars.py` / `astra/scientific/planets.py` / `astra/scientific/galaxies.py` — `classification` enums (`REAL_DATA` Hipparcos `SIMULATED_DATA` etc.) — shader selection must follow, not invent.
- `astra/core/coords.py` `OriginRebaser` — floating-origin continues for astronomical distances (planets at `1e11` → `1e16` galactic, reuse §21)
- `astra/world/scene_graph.py` + `astra/world/spatial.py` — hierarchical culling already spatial; leverage for LOD decisions
- `astra/temporal/simulation_clock.py` — if star evolution uses `SimulationClock`, time in `sim_time_s`, not render `frame_id`
- `tests/test_*_astronomical*` if present — preserve `1660 passed` flow

---

## 6. Existing Visualization Systems to Reuse

**AUDIT → REUSE → EXTEND → TEST**

- `visualization/godot/phase_01_foundation/scripts/*` — reuse all, extend:
  - `ObjectRegistry.gd` bucketing → add `star`, `planet`, `nebula`, `galaxy` buckets + `custom_data` temperature/Lod
  - `ShaderManager.gd` → add `get_star_shader(spectral, classification)` / `get_planet_shader(...)` watermark for `SPECULATIVE`
  - `QualityPresets.gd` already 5 presets — verify `apply()` toggles `volumetric_fog` `star_density` `height_scale`
  - `AstraBridge.get_origin_offset()` remains sole origin source for all 10k instances
- `visualization/godot/shaders/` 19 categories — reuse without duplicating:
  - `celestial/star_corona.gdshader` (corona), `stars/procedural_starfield.gdshader` (sky, 4 params), `stars/star_lensing.gdshader` (stub for Phase 03, keep loadable), `celestial/magnetosphere.gdshader` (optional aurora), `terrain/heightmap_terrain.gdshader` + `terrain/atmosphere.gdshader` (planets), `vfx/nebula_volumetric.gdshader` / `galaxies/galaxy_structure.gdshader` (existence only if not present, add via `generate_shader_catalog`)
  - `shaders/utility/common_lib.gdshaderinc` 13 lines shared math — include via `#include "res://shaders/utility/common_lib.gdshaderinc"`
  - `shaders/compute/instance_prepare.glsl` with `local_size 64,1,1` already
- `visualization/godot/materials/` — `planet_material.tres`/`star_material.tres` stay, add `nebula_material.tres`/`galaxy_material.tres` same resource-id convention `1_terrain`/`1_corona` numeric, `checked ext_resources: 1 ok`
- `visualization/godot/vfx/` 10 categories — do not touch (Phase 04)
- `visualization/tools/validate_godot_project.py` already 57/19 — extend to cover new shaders/materials (increase to 62+ but keep 57 base passing)
- `visualization/tools/generate_shader_catalog.py` writes `SHADER_CATALOG.md` 23 lines — run after adding nebula/galaxy shaders
- `visualization/assets/luts/star_temperature_lut.ppm` 16×256 — reuse, document CC0, no new LUT without `generate_lut.py`

---

## 7. Architecture

```
ASTRA scientific objects[] (kind=star/planet/nebula/galaxy, spectral, position, classification)
        ↓ bridge_state.json (tick, origin_offset)
AstraBridge → ObjectRegistry (buckets: star MultiMesh, planet MeshInstance LOD, nebula FogVolume, galaxy MultiMesh)
        ↓ origin subtract per-instance, custom_data (temp, LOD)
ShaderManager (spectral→LUT→corona, heightmap params, volumetric density)
        ↓
Godot Forward+  (Forward+ tiling, Vulkan, RenderingDevice compute prepare if available)
        ↓
StarRenderer / PlanetRenderer / NebulaRenderer / GalaxyField nodes  +  Procedural generators (FastNoiseLite)
```

**Constraint:** One render loop (Godot). No `three` particle loop, no Python matplotlib fallback at runtime.

---

## 8. Data Flow

1. Python `Engine` produces `objects: [{id:"star-001", kind:"star", position:[...], frame:"galactic", classification:"REAL_DATA", spectral:"G2V", temperature:5778, lod:"LOD2"}, {kind:"planet", radius:6371, ...}]` in `bridge_state.json` (add fields, do not break old `id/kind/position`).
2. `AstraBridge._poll_astra()` hash diff → `ObjectRegistry.update_render_state(state)` iterates `objects`, `pos_local = pos_world - origin_offset` (Vector3), `multimesh.set_instance_transform(i, Transform3D(Basis.IDENTITY, pos_local))`, `multimesh.set_instance_custom_data(i, Color(temp_norm, lod_norm, 0,1))`.
3. `ShaderManager` for each `multimesh.material_override = get_shader(kind,classification)`; `SPECULATIVE` path adds watermark overlay uniform `watermark 1.0` + label `CanvasItem` "SPECULATIVE VISUALIZATION".
4. `PlanetRenderer` for `lod` 0–2 creates `ArrayMesh` icosphere subdiv `lod+2`, assigns `planet_material` with `height_scale` uniform driven by `QualityPresets.current.terrain_quality`.
5. `NebulaRenderer` toggles `FogVolume` `extents`/`albedo` by `density` uniform + `volumetric_fog_enabled` global.
6. `Telemetry` counts `visible_instances` after culling, logs every 60 frames.

---

## 9. Required Systems

- `StarRenderer.gd` (`Node`), `PlanetRenderer.gd` (`Node3D`), `NebulaRenderer.gd` (`FogVolume` wrapper), `GalaxyField.gd` (`MultiMeshInstance3D` density)
- Extend `ObjectRegistry.gd`, `ShaderManager.gd`, `QualityPresets.gd`, `Telemetry.gd`
- `ProceduralSky.gd` + `ProceduralTerrain.gd` within planet/sky shaders (not new autoloads)
- `phase02_validation.gd` deterministic scene builder (seed `0xA574`, grid of 100 stars + 5 planets + 1 nebula + 1 galaxy)

---

## 10. Required Files/Directories

```
visualization/godot/phase_02_astronomical/
  README.md           (purpose, how to run phase02_validation.tscn, reuse notes)
  scenes/phase02_validation.tscn  (UID uid://astra_phase02_validation)
  scenes/astronomical.tscn        (reusable star/planet compositing)
  scripts/star_renderer.gd
  scripts/planet_renderer.gd
  scripts/nebula_renderer.gd
  scripts/galaxy_field.gd
  scripts/phase02_validation.gd
  environments/astronomical_env.tres (extends default_env, fog density 0.02, sky procedural)
  materials/nebula_material.tres
  materials/galaxy_material.tres
visualization/godot/shaders/stars/procedural_starfield.gdshader (already)
visualization/godot/shaders/celestial/star_corona.gdshader (already)
visualization/godot/shaders/terrain/heightmap_terrain.gdshader (already)
visualization/godot/shaders/terrain/atmosphere.gdshader (add or verify)
visualization/godot/shaders/vfx/nebula_volumetric.gdshader (add or verify)
visualization/godot/shaders/galaxies/galaxy_structure.gdshader (add or verify)
visualization/godot/shaders/compute/instance_prepare.glsl (already local_size)
visualization/godot/shaders/utility/common_lib.gdshaderinc (already)
visualization/assets/luts/star_temperature_lut.ppm (exists, regenerate if missing)
```

Existing `visualization/godot/phase_01_foundation/` must remain untouched except additive `ObjectRegistry`/`ShaderManager` extension via `class_name` extension or signal subscription (do not move files).

---

## 11. Godot Scene Requirements

**`phase02_validation.tscn` deterministic (seed `0xA574`, no `randf` without seed):**

- `Phase02Root` `Node` script `phase02_validation.gd`
  - `WorldEnvironment` environment `astronomical_env.tres` (`volumetric_fog_enabled` true, `sky` `ProceduralSkyMaterial` or `PanoramaSkyMaterial` with `procedural_starfield.gdshader` quad)
  - `TestCamera` `Camera3D` at `(0,80,150)` looking at origin (reuses Phase 01 `CameraSystem` if available, otherwise direct `Camera3D`)
  - `StarField` `MultiMeshInstance3D` multimesh `100` stars grid `10×10` at `y=0, x/z -50..50`, `custom_data` temperature gradient `3000→30000K` mapped via LUT
  - `Planets` `Node3D` → 5 `MeshInstance3D` spheroids radius 2–6 at `x 20/35/50`, LOD by distance, `planet_material` + `atmosphere.gdshader` child `MeshInstance3D` shell `1.05×`
  - `Nebula` `FogVolume` `extents 30,10,30` at `0,5,0` density `0.02`
  - `Galaxy` `MultiMeshInstance3D` `500` density points log spiral `b 0.22`, 2 arms
  - `DiagnosticsOverlay` extended `Label` with `stars 100/10k, planets 5, neb 1, galaxy 500, draw  X, instances visible Y`
  - `ObjectRegistry` + `ShaderManager` nodes (or autoloads)

All transforms fixed. Headless `DisplayServer.get_name()=="headless"` → `get_tree().quit(0/1)` after 0.75s (longer than Phase 01 due to more loads). Must also be loadable alongside Phase 01 scene (no singleton name collision).

---

## 12. GDScript Requirements

**Continue GDScript 2.0, typed, no Python idioms.**

| File | Key API (typed) |
|---|---|
| `star_renderer.gd` | `class_name StarRenderer: Node`, `var _multimesh:MultiMesh`, `func update_stars(stars:Array[Dictionary], origin:Vector3)` uses `AstraBridge.get_origin_offset()`, `func _temperature_to_color(temp:float)->Color` via LUT sampling, `custom_data Color(temp_norm,0,0,1)` |
| `planet_renderer.gd` | `class_name PlanetRenderer: Node3D`, `var _lods:Array[Mesh]`, `func _generate_icosphere(subdiv:int)->ArrayMesh` (no external mesh import), `func update_planet(state:Dictionary, quality:QualityPresets.Preset)` sets `height_scale`/`lod` |
| `nebula_renderer.gd` | `class_name NebulaRenderer: Node`, `var _fog:FogVolume`, `func set_density(d:float)` `0.0..0.1`, wraps `nebula_volumetric.gdshader` uniform, `quality_presets` gates `volumetric_fog_enabled` |
| `galaxy_field.gd` | `class_name GalaxyField: Node`, `var _multimesh:MultiMeshInstance3D`, `func _spiral_pos(r:float,a:float,b:float)->Vector3`, `500` deterministic (seed `0xA574`) |
| `phase02_validation.gd` | `extends Node`, `const SEED=0xA574`, `var _ok/_fail`, `_build_*`, `_check_resource(path)`, headless quit, no `teleport`/`set_position_directly`, preserves Phase 01 hierarchy check `52,0,0` regression |

**All** `request_interaction` stays in `AstraBridge` only; renderers are read-only.

---

## 13. Shader Requirements

- **Reuse existing:** `star_corona` (2 params `temperature`, `intensity`), `procedural_starfield` (4 params `density`, `twinkle`), `heightmap_terrain` (5 params `height_scale 400`, `noise_freq`, `lacunarity`), `atmosphere` Rayleigh/Mie (`rayleigh 4e-6`, `mie 2.1e-5`), `instance_prepare.glsl` `local_size 64,1,1` with `// instance_prepare` comment, `common_lib.gdshaderinc` shared.
- **Extend if missing:** `nebula_volumetric.gdshader` `shader_type fog`/`spatial` with `density`, `albedo`, `emission`, noise fBm from `common_lib`; `galaxy_structure.gdshader` `shader_type spatial`, uniform `arm_count:int`, `spiral_tightness:float b=0.22`; both `<5KB`, `#include "res://shaders/utility/common_lib.gdshaderinc"` where shared.
- **No runtime compilation failure:** `validate_shaders.py` must pass `shader_type` + no `python` tokens; `phase02_validation.gd` does `ResourceLoader.exists`+`load` for all 6 astronomical shaders + `common_lib` include resolve, `shader != null` check.
- **Target vs measured:** fragment cost `0.6ms` stars `1.2ms` planets `0.8ms` nebula are **TARGET**; do not claim MEASURED without GPU `Telemetry`.

---

## 14. Material Requirements

- Existing `planet_material.tres`/`star_material.tres` unchanged (numeric `ExtResource` 1_terrain, `checked ext_resources ok`).
- New `nebula_material.tres` / `galaxy_material.tres` `ShaderMaterial` with `shader = ExtResource("1_nebula") → res://shaders/vfx/nebula_volumetric.gdshader` etc., uniform defaults `density 0.02`, `albedo Color(0.6,0.3,0.8)`. No `GradientTexture1D_*` SubResource or `res://../` outside. `validate_godot_project.py` extended check `nebula_material.tres: shader exists, 1 ok`.

---

## 15. C++/GDExtension Requirements Where Justified

- **Already justified:** `AstraInstanceHelper` (see Phase 01 §15). Phase 02 extends it with `prepare_star_buffers(origin_offset:Vector3, stars:PackedVector3Array)->PackedVector3Array` and optional `cull_lod(buffers, camera_pos, lod_thresholds:PackedFloat32Array)->PackedInt32Array`. Justification: 10k star `custom_data` packing 60 Hz: GDScript `1.2ms` → compute `0.08ms` on RTX 3060 (**TARGET**, measured via `Telemetry` `instance prepare time` when Vulkan available; otherwise fallback noted `ENVIRONMENT BLOCKED`).
- **Do not** make GDExtension required for correctness; `ObjectRegistry` GDScript loop must still pass `phase02_validation.tscn` headless (100 stars load, 10k smoke via Python `validate_coordinates.py` not Godot).
- Build same `scons target=template_release api_version=4.4` path, re-verify `nm -D` `gdext_library_init`.

---

## 16. Python Tooling Requirements Where Justified

- Reuse `visualization/tools/validate_godot_project.py` (extend `expected_shaders` to include nebula/galaxy, expected materials to 4).
- `validate_shaders.py` must still `19+` (if you add 2 new shaders → 21/21) with same `shader_type` rule, including `nebula_volumetric` `shader_type fog` or `spatial` accepted.
- `generate_shader_catalog.py` must count new shaders (23→25 lines) and still write `SHADER_CATALOG.md`.
- `generate_lut.py` if `star_temperature_lut.ppm` missing, regenerate `16×256` PPM, `P3` ASCII, CC0.
- Keep `validate_bridge.py` 3-object backward compat, add optional `kind star` validation without breaking `phase01_validation.gd`.

---

## 17. Node/JavaScript Tooling Requirements Where Justified

- Reuse `bridge_adapter.js` / `generate_manifest.js` deterministic 9 assets. No new npm deps.
- If adding `galaxy` kind to manifest, extend `generate_manifest.js` `allowed_kinds` list and keep `bridge_adapter.js` allowlist in sync — no duplicate render loop.

---

## 18. Addon/Dependency Requirements

- **Document any new addon** in `DEPENDENCIES.md` row: purpose, version, source, license, reason, risk.
- **Prefer none for Phase 02.** `FastNoiseLite` is built-in (no new dep). If proposing `Gaea` or `Terrain3D`, note rejection per Phase 01 `DEPENDENCIES.md` (Gaea commercial, Terrain3D GPL).
- `godotshaders.com` starfield adaptation already licensed MIT—no per-ASTRA attribution binary, but `THIRD_PARTY.md` should list.

---

## 19. Asset Requirements

- Reuse 9 assets `<2MB`, CC0 (`earth_like_albedo.ppm` 512, `star_temperature_lut.ppm`). Do not add `polyhaven` HDR or >2MB.
- Procedural LUTs generated via `generate_lut.py`, not binary committed.
- If generating new `noise.ppm` for nebula, keep `256×256` `P3`, `<200KB`, deterministic, `assets/noise/README.md` stub.

---

## 20. Coordinate-System Requirements

- **Reuse Phase 01 `CoordinateBridge`/`OriginRebaser`/`AstraBridge.origin_offset`.** Astronomical distances `1e11-1e26` rely on same rebasing; do not introduce second coordinate system.
- Star grid `10×10` at `y=0` tests local rendering; planet at `35` and galaxy spiral at `extents 30` test world-to-local subtraction identical to hierarchy `52,0,0` regression (keep that `_check`).
- Galaxy spiral must use local positions after subtracting `origin_offset`; scientific double stays in Python.

---

## 21. ASTRA ↔ Godot Boundary

- Same `bridge_state.json` pipe (tick, origin_offset, objects[]). Extend `objects[]` schema additively (`kind star/planet/nebula/galaxy`, `spectral`, `temperature`).
- `classification` carries through to `ShaderManager` watermark for `SPECULATIVE` nebula/galaxy visuals (add `Label "SIMULATION"` watermark `Settings`).
- Never `set_position_directly` for stars/planets — orbital propagation stays `astra.core` Python.

---

## 22. Performance Requirements

- **TARGET 60fps RTX 3060 HIGH 10k stars:** `Stars 0.6ms` (instanced MultiMesh, custom_data) + `Planets 1.2ms` (LOD icosphere icosphere verts 642 LOD1, 2562 LOD2) + `Nebula 0.8ms` (fog 64 samples) + `Galaxy 0.4ms` (500 density) + `Postprocess 0.7ms` = `3.7ms` render, rest bridge. `LOW` 2k stars `0.3ms`. **TARGET not MEASURED** unless `Telemetry` + `RenderingServer` GPU timers available.
- **Fallbacks:** `volumetric_fog_enabled false` `LOW`, `height_scale 100` `LOW` vs `400` `MEDIUM` vs `800` `ULTRA`, star density `0.35→0.95` per preset.
- **Measured smoke:** Python `validate_coordinates 10k traversal 0.14ms`, `ObjectRegistry 100/1k` Godot `MultiMesh` update `<0.5ms` **if** GPU; else mark `ENVIRONMENT BLOCKED`.

---

## 23. Quality Presets

- Verify full matrix per `QUALITY_PRESETS.md` (13 features): `LOW 0 shadows/0 fog/32 particles/0.35 density`, `MEDIUM 1024/0/128/0.5`, `HIGH 2048/64/256/0.7`, `ULTRA 4096/128/512/0.9`, `CINEMATIC 8192/192/1024/0.95 + DoF on`. Phase 02 drives `volumetric_fog`, `star_density`, `height_scale`, `galaxy detail`. `apply()` toggles via `RenderingServer` where possible.
- Manual override `--quality cinematic` still works even if hardware would pick `MEDIUM`.

---

## 24. Security/Resource Boundaries

- **Constrained `res://`:** same as Phase 01; new materials `nebula_material.tres` etc. numeric `ExtResource`, `checked ext_resources` passes, no `../assets`, only documented `../../bridge_state.json` `if file:`.
- No GPL, no new `*.so`, no `*.zip`, no `/home` absolute, no `OS.execute`.
- `http` grep only comments/`127.0.0.1`.

---

## 25. Testing Requirements

- `PYTHONPATH=. pytest -q` `1660 passed` retained
- `validate_godot_project.py` 57 base (plus new shaders/materials, keep 0 FAIL)
- `validate_shaders.py` 19+ passes including new nebula/galaxy, `local_size` for compute
- `validate_assets.py` 9 pass, `validate_bridge.py` 3 objects + extended kind not crash
- `generate_shader_catalog.py` writes without error
- `phase02_validation.gd` `_check` 6 shaders + 4 materials + 100-star MultiMesh visible + 5-planet LOD + fog enabled when `HIGH`, malformed bridge no crash, headless `quit(1)` on any FAIL
- Keep Phase 01 hierarchy regression `52,0,0` inside Phase 02 validation

---

## 26. Runtime Validation Requirements

- `godot --path visualization/godot --headless --scene res://phase_02_astronomical/scenes/phase02_validation.tscn` → `[OK]Stars`, `[OK]Planets`, `[OK]Nebula`, `[OK]Galaxy`, `[Phase02]Summary X OK 0 FAIL`, exit 0
- `godot --path ... --scene res://phase_01_foundation/scenes/phase01_validation.tscn` still passes (regression)
- `godot --version` `4.4.1.stable.official`, capture warnings — zero fatal
- If headless no GPU, mark `ENVIRONMENT BLOCKED` for volumetric/visual pixels, but MultiMesh load still VERIFIED

---

## 27. Failure Handling

- Missing `star_temperature_lut.ppm` → procedural fallback gradient, `WARN` not `FAIL`
- `heightmap_terrain.gdshader` fail → `planet_material` fallback `StandardMaterial3D`, `WARN`
- `volumetric_fog` not supported (`gl_compatibility` web) → disable path, `Telemetry` shows `fog unavailable`, not crash
- `AstraBridge` malformed `classification` → `ShaderManager` fallback `star_corona`, `WARN`

---

## 28. Documentation Requirements

- `visualization/godot/phase_02_astronomical/README.md` purpose, LOD tiers, LUT generation, how to run both validation scenes, `SHADER_CATALOG.md` update
- `visualization/VALIDATION_REPORT.md` append `PHASE 02` section same taxonomy, preserve Phase 01
- `visualization/QUALITY_PRESETS.md` if matrix changes, update target ms for nebula/galaxy
- No doc overwrites without preserving prior evidence

---

## 29. Completion Criteria

- `phase02_validation.tscn` deterministic, loads `6 astronomical shaders` + `4 materials` via `ResourceLoader`, no fatal
- `100 stars` MultiMesh visible, `5 planets` LOD correct, nebula fog and galaxy spiral rendered (or gracefully disabled `LOW`/`headless` with logged reason)
- `AstraBridge` 10k `custom_data` packing not crash, headless smoke `100` passes, GDExtension optional but fallback measured
- All extended `validate_*` still 0 FAIL
- Phase 01 scene still GREEN/YELLOW (not RED regression)

---

## 30. Evidence Required

- `git branch --show-current`, `godot --version`, `godot --headless --scene ...phase02_validation.tscn` stdout/exit
- `ls -lh extensions/bin/*.so` + `nm -D gdext_library_init` if GDExtension extended
- `python validate_godot_project.py` / `validate_shaders.py` / `pytest -q` logs
- `SHADER_CATALOG.md` line count before/after

---

## 31. Final Status Criteria

- **GREEN:** §29 all pass with actual `godot --headless` run, `HIGH` preset fog+stars load, `Telemetry draw_calls >0`, no P0/P1
- **YELLOW:** Code+scenes exist, `validate_*` all OK, but `godot` or Vulkan not available (`ENVIRONMENT BLOCKED`) — volumetric visual not pixel-verified, GDScript fallback covers compute
- **RED:** Blocking: `phase02_validation` fails to load, hierarchy regression `52,0,0` broken, shader `shader_type` missing, `validate_shaders 9/19→15/19`, or `ObjectRegistry 10k` crashes

---

## 32. Handoff to Next Phase

- **Preserve** `phase_02_astronomical/` + `phase_01_foundation/` scenes.
- **Dependencies for Phase 03:** `ShaderManager` classification + `CoordinateBridge` + `instance_prepare.glsl` compute pattern reused for ray-marching neighboring. **Do not replace** star/planet shaders with black-hole approximations (keep separate `spacetime/` shaders).
- **Next agent:** implement Phase 03 `PHASE_03_EXTREME_PHYSICS.md` extreme grav/warp — requires `black_hole_raymarch` `gravitational_lensing` shaders, must honor `REAL/THEORETICAL/SPECULATIVE` labeling that Phase 02 established.

---

*Implementation order: `phase02_validation.gd` skeleton → extend ObjectRegistry/ShaderManager → add/verify nebula/galaxy shaders → materials → instancing/LOD → validation headless → `VALIDATION_REPORT.md`.*
