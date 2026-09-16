# GODOT PHASE 03 — EXTREME PHYSICS

**Version:** 1.0 — 2026-09-17  
**Target:** Godot 4.4.1 Forward+ (RenderingDevice compute ray-marching + lensing)  
**Branch:** `arena/01a0a5a2-astra-cosmos`  
**Prerequisite:** Phases 01–02 YELLOW+ (instancing, LOD, classification→shader mapping, floating-origin). Visual honesty principle introduced Phase 02 is **mandatory** here.  
**Status taxonomy:** STATIC VERIFIED / RUNTIME VERIFIED / NOT VERIFIED / ENVIRONMENT BLOCKED; **classification taxonomy:** `REAL_DATA` / `SIMULATED_DATA` / `THEORETICAL` / `SPECULATIVE` (see §13/21).

---

## 1. Phase Identity

- **Phase:** `PHASE_03_EXTREME_PHYSICS`
- **Order:** 3 of 5 (`01[X] → 02[X] → 03 → 04 → 05`)
- **Code prefix:** `phase_03_extreme_physics/` under `visualization/godot/`
- **Deliverable:** `GODOT_PHASES/PHASE_03_EXTREME_PHYSICS.md` (this file) + `visualization/godot/phase_03_extreme_physics/`
- **Gate scene:** `phase03_validation.tscn` seed `0xA575` **must** visualize `REAL` black hole shadow vs `SPECULATIVE` wormhole with distinct labeling/watermark.

---

## 2. Objective

Render **extreme gravitational phenomena** — black hole photon sphere/shadow, accretion disk thermodynamics, gravitational lensing, relativistic effects (Doppler/beaming/redshift where photon-traced), wormhole throat topology, and warp metric visualization — with **clear epistemic boundary**: `REAL` (imaged/measured M87*, `THEORETICAL` (GR solutions), `SPECULATIVE` (traversable wormhole, Alcubierre) are visually and textually distinguishable and never misrepresented as observed.

Use **ray-marching + compute** where justified (profile vs GDScript), with GDScript fallback measured, under Forward+ ` RenderingDevice` where Vulkan available.

---

## 3. Scope

**In scope:**

- **Black holes:** `BlackHoleRenderer.gd` photon sphere `r_ph=3/2 r_s`, shadow radius `≈2.6 r_s`, `black_hole_raymarch.gdshader` ray-marching (`MAX_STEPS 64 LOW → 128 HIGH → 256 CINEMATIC`, `RAY_EPS 0.01`), Schwarzschild deflection `α≈2r_s/b`, thin-disk Novikov-Thorne temperature `T∝r^{-3/4}`, `accretion_disk.gdshader` Doppler beaming `g^3` factor; Hawking radiation stub uniform (not luminous)
- **Gravitational lensing:** `GravitationalLensing.gd` / `gravitational_lensing.gdshader` full-screen `subViewport` lensing pass `α=4GM/c²b` (reusable for Phase 02 galaxy weak lens later), Einstein ring `θ_E`, multiple images, time delay stub
- **Relativistic effects:** `RelativisticEffects.gd` redshift `1+z`, Doppler `g`, beaming `(p·u)²`, aberration (optional aberration quad) — computed per-disk sample, not postprocess global tint
- **Wormholes:** `WormholeRenderer.gd` / `wormhole_throat.gdshader` Morris-Thorne `b(r)=b0²/r`, embed diagram `z(r)`, 2 mouths `MouthA/B` `Node3D` + `Portal` `SubViewport` texture, **distinct `SPECULATIVE` shader + watermark** `Label "THEORETICAL — TRAVERSABLE WORMHOLE (UNOBSERVED)"`
- **Warp drive:** `WarpField.gd` / `warp_bubble.gdshader` Alcubierre `f(r_s)` with `σ, R, v` uniforms, spacetime grid `grid_curvature.gdshader`, bubble border `brighter`, interior `contract`, `SPECULATIVE` watermark `Label "SPECULATIVE — ALCUBIERRE (UNPHYSICAL ENERGY)"`
- **Spacetime visualization:** `SpacetimeGrid.gd` Re-use `grid_curvature.gdshader` 10×10 with curvature deflection by `r_s/b`
- **Classification enforcement:** Every extreme renderer checks `state.classification` from `bridge_state.json` (mapped from `astra.theoretical` vs `astra.scientific`) and selects `THEORETICAL`/`SPECULATIVE` shader variant; `SPECULATIVE` adds semi-transparent overlay + text, `ShaderManager.get_extreme_shader(kind,classification)` logs distribution.
- **Validation scene:** deterministic `1 ` Schwarzschild `10 M☉` black hole + `1` wormhole + `1` warp bubble + spacetime grid, diagnostics distinguishes `REAL/THE/SPEC` counts
- **Compute:** `black_hole_raymarch` `compute` variant `shaders/compute/lensing_prepare.glsl` optional (see §13) — GDScript loop fallback measured, `Telemetry` lensing ms separately

**Out of scope — see §4.**

---

## 4. Non-Goals

- No accurate Kerr spin raytracing beyond Schwarzschild stub (Kerr `a` uniform present but not fully traced — document as `SIMPLIFIED SCHWARZSCHILD` in shader comment, Phase 05 could extend).
- No `astra.theoretical` Python computation inside Godot (Godot only visualizes `bridge_state.json` fields `mass`, `r_s`, `classification`; true `Kerr` metric stays Python).
- No explosion/warp VFX particles (Phase 04)
- No HLOD/streaming or performance tuning beyond baseline LOD presets (Phase 05)
- No claiming `SPECULATIVE` as observed — **mandatory** watermark/label; failing this = RED (YELLOW at minimum if renderer exists without labeling).

---

## 5. Existing ASTRA Systems to Inspect

- `astra/theoretical/black_holes.py` / `astra/theoretical/wormholes.py` / `astra/theoretical/warp.py` — theoretical/speculative definitions, `classification==SPECULATIVE` for `TraversableWormhole`, `Alcubierre` — bridge must pass this.
- `astra/scientific/black_holes.py` — `REAL_DATA` imaged shadows (M87) vs simulated. `ShaderManager` must map `REAL_DATA → shadow+disk accurate`, `THEORETICAL → idealized`, `SPECULATIVE → watermarked`.
- `astra/core/coords.py` — extreme distances still rebased; black hole at `1e11` → render `5,0,0` delta as Phase 01
- `astra/interaction/engine.py` — navigating to black hole still `request_interaction`, not `teleport`
- `tests/test_theoretical*` — preserves epistemic invariants; `pytest 1660 passed` must remain

---

## 6. Existing Visualization Systems to Reuse

**AUDIT → REUSE → EXTEND → TEST**

- `phase_01_foundation` `CoordinateBridge`/`AstraBridge.get_origin_offset()`/`ObjectRegistry` — reuse, add `black_hole`/`wormhole`/`warp` buckets (singletons not MultiMesh but `Node3D`+`MeshInstance3D` with raymarch material)
- `phase_02_astronomical` `ShaderManager` → extend `get_extreme_shader(kind,classification)->ShaderMaterial` with `REAL/THEO/SPEC` branching; `Telemetry` extend lensing ms
- `visualization/godot/shaders/` 19 → `spacetime/` `black_hole_raymarch.gdshader` / `gravitational_lensing.gdshader` / `wormhole_throat.gdshader` / `warp_bubble.gdshader` / `grid_curvature.gdshader` (verify 5 exist, add stubs if missing with `shader_type spatial` + watermark param), `compute/lensing_prepare.glsl` if adding, `utility/common_lib.gdshaderinc` shared math `ray_sphere`/`deflect`
- `visualization/godot/materials/` 4 (`planet/star/nebula/galaxy`) → add `black_hole_material.tres` / `wormhole_material.tres` / `warp_material.tres` numeric `ExtResource`
- `visualization/godot/vfx/` — not used (Phase 04), keep existence check only
- `visualization/tools/validate_*` → extend expected shaders to 24+, `validate_shaders.py` must pass `shader_type` for all spacetime shaders, `generate_shader_catalog.py` → 23+ lines

---

## 7. Architecture

```
ASTRA theoretical objects[] ({kind:"black_hole"|"wormhole"|"warp", mass, r_s, spin_a, classification:"THEORETICAL"|"SPECULATIVE"})
        ↓ bridge_state.json (origin_offset, sim_time)
AstraBridge → ObjectRegistry (buckets: black_hole Node3D, wormhole 2-mouth, warp bubble) → ShaderManager (classification→material)
        ↓ origin subtract, r_s scaled render
BlackHoleRenderer / WormholeRenderer / WarpField  (raymarch lensing SubViewport, throat portal textures)
        ↓ Forward+ full-screen lens quad + volume meshes
GPU Forward+  (Vulkan RenderingDevice compute lens if available, else GDScript 64-step)
        ↓ labeled output (SPECULATIVE watermark overlay)
```

**Honesty gate:** `phase03_validation.gd` asserts `SPECULATIVE` objects have `watermark 1.0` uniform and `Label "SPECULATIVE"` child visible; otherwise `_check` FAIL → RED.

---

## 8. Data Flow

1. Python `astra.theoretical.wormholes.TraversableWormhole` produces `{"id":"WH-01","kind":"wormhole","position":[0,0,0],"r0":2.0,"classification":"SPECULATIVE","frame":"system"}` in `bridge_state.json` (bridge must serialize `classification` verbatim).
2. `AstraBridge._poll_astra` hash diff → `ObjectRegistry` spawns `WormholeRenderer` at `pos_local = world - origin_offset`, `ThroatMaterial.set_shader_parameter("throat_radius",r0)`, `set_shader_parameter("watermark",1.0)` if `SPECULATIVE`.
3. `BlackHoleRenderer._process` ray-marches per fragment (GPU) with `MAX_STEPS` by `QualityPresets` → writes shadow+disk+redshift; `GravitationalLensing` full-screen quad samples `SCREEN_TEXTURE` deflected `α=2r_s/b` (HIGH) where `b` = impact param from `r_s` uniform.
4. `WarpField` `grid_curvature.gdshader` displaces grid vertices `f(r_s)*(v)` bubble formula; border `emission` bright.
5. `Telemetry` per-frame `black_hole_ms`, `lensing_ms`, `wormhole_visible`.

Never derive `mass` inside Godot; only render uniforms from `bridge_state.json`.

---

## 9. Required Systems

- `BlackHoleRenderer.gd: Node3D` with `SphereMesh shadow 2.6*r_s`, `DiskInstance MeshInstance3D` `accretion_disk` material, `LensingQuad SubViewportContainer`, `func set_black_hole(mass:float, r_s:float, classification:String)` (honesty branch)
- `GravitationalLensing.gd: Node` with `SubViewport` `1024×1024` (HIGH) `512 LOW`, `func set_lens_mass(r_s:float)`, fullscreen lensing shader.
- `RelativisticEffects.gd: Node` helper `func doppler_factor(v:Vector3, n:Vector3)->float`
- `WormholeRenderer.gd: Node3D` `MouthA`/`MouthB` `SphereMesh r0` + `ThroatMesh Tube` + `PortalA/B SubViewport` texture, `func set_wormhole(r0:float, classification:String)`
- `WarpField.gd: Node3D` `BubbleMesh Sphere 1.0` scaled `R`, `GridMesh Plane 20×20` with `grid_curvature`, `func set_warp(v:float, R:float, sigma:float, classification:String)`
- `SpacetimeGrid.gd: MeshInstance3D` reusing `grid_curvature.gdshader`
- `phase03_validation.gd: Node` deterministic `SEED 0xA575`, 1 BH + 1 WH + 1 warp + grid, plus hierarchy `52,0,0` regression, watermark checks, `quit(0/1)` headless

---

## 10. Required Files/Directories

```
visualization/godot/phase_03_extreme_physics/
  README.md
  scenes/phase03_validation.tscn  (UID uid://astra_phase03_validation)
  scenes/extreme_physics.tscn     (reusable BH/WH/warp compositing)
  scripts/black_hole_renderer.gd
  scripts/gravitational_lensing.gd
  scripts/relativistic_effects.gd
  scripts/wormhole_renderer.gd
  scripts/warp_field.gd
  scripts/spacetime_grid.gd
  scripts/phase03_validation.gd
  environments/extreme_env.tres
  materials/black_hole_material.tres    (raymarch)
  materials/wormhole_material.tres      (throat + portal)
  materials/warp_material.tres          (bubble + grid)
visualization/godot/shaders/spacetime/black_hole_raymarch.gdshader
visualization/godot/shaders/spacetime/gravitational_lensing.gdshader
visualization/godot/shaders/spacetime/wormhole_throat.gdshader
visualization/godot/shaders/spacetime/warp_bubble.gdshader
visualization/godot/shaders/spacetime/grid_curvature.gdshader
visualization/godot/shaders/compute/lensing_prepare.glsl (optional)
visualization/godot/shaders/utility/common_lib.gdshaderinc (shared ray/deflect)
```

Preserve `phase_01_foundation/` + `phase_02_astronomical/`.

---

## 11. Godot Scene Requirements

**`phase03_validation.tscn` deterministic seed `0xA575`:**

- `Phase03Root` `Node` script `phase03_validation.gd`
  - `WorldEnvironment` environment `extreme_env.tres` `glow 0.6`, `volumetric_fog 0.02`
  - `TestCamera` `Camera3D` at `(0,15,35)` looking at origin reuses Phase 01 `CameraSystem` or direct; must show BH shadow and WH throat simultaneously (FOV 60)
  - `BlackHole` `Node3D` at `(-10,0,0)` `BlackHoleRenderer` `mass 10 M☉` `r_s 0.3` render units `classification "THEORETICAL"` shadow sphere + disk torus outer `8 r_s` + lensing quad `SubViewport 512` (LOW) to `1024` (HIGH) sampled
  - `Wormhole` `Node3D` at `(10,0,0)` `WormholeRenderer` `r0 2.0` two mouths `±2.5` + throat tube + portal viewports `256×256` with secondary camera, watermark `Label3D/CanvasLayer Label "THEORETICAL — TRAVERSABLE WORMHOLE (UNOBSERVED)"` `modulate a 0.8`
  - `WarpBubble` `Node3D` at `(0,8,0)` `WarpField` `R 4, v 1.2, sigma 8` + `Grid 20×20` plane `y=-2`, warp `SPECULATIVE` watermark `Label "SPECULATIVE — ALCUBIERRE (UNPHYSICAL)"`
  - `SpacetimeGrid` `MeshInstance3D` `PlaneMesh 20×20 subdiv 20` at `y=-1` with `grid_curvature` `r_s` from BH
  - `DiagnosticsOverlay` `Label` with `BH r_s 0.3, photon 0.45, shadow 0.78, lens alpha HIGH 2r_s/b, wormhole SPECULATIVE 1, warp SPECULATIVE 1, classification counts REAL 0 THEO 1 SPEC 2`
  - `ObjectRegistry` + `ShaderManager` nodes
  - `DummyRealStar` `MeshInstance3D` `Sphere 0.5` at `(0,0,10)` `classification REAL_DATA` to test ShaderManager `REAL` branch (not lensed strongly)

Headless `0.85s` quit, no `randf` without seed.

---

## 12. GDScript Requirements

**Typed GDScript 2.0, honest branching explicit.**

| File | Key API |
|---|---|
| `black_hole_renderer.gd` | `class_name BlackHoleRenderer: Node3D`, `func set_black_hole(mass:float, rs:float, cla:String)`, `func _physics_process(lensing alpha 2*rs/b)` sets `material.set_shader_parameter("rs",rs)`, `_check` classification branch watermark `set_shader_parameter("watermark", cla=="SPECULATIVE"?1.0:0.0)` |
| `gravitational_lensing.gd` | `class_name GravitationalLensing: Node`, `var _viewport:SubViewport`, `func set_lens_mass(rs:float)`, `func set_quality(p:QualityPresets.Preset)` `LOW 512/64 steps → CINEMATIC 2048/256` |
| `relativistic_effects.gd` | `class_name RelativisticEffects: Node`, `func doppler_factor(v:Vector3, normal:Vector3, temp:float)->float` pure math |
| `wormhole_renderer.gd` | `class_name WormholeRenderer: Node3D`, `var mouth_a,b:MeshInstance3D`, `func set_wormhole(r0:float, cla:String)` creates throat `Tube` `segments 32`, watermark `Label` `visible = cla=="SPECULATIVE"` |
| `warp_field.gd` | `class_name WarpField: Node3D`, `var bubble:MeshInstance3D, grid:MeshInstance3D`, `func set_warp(v:float,R:float,s:float,cla:String)` |
| `phase03_validation.gd` | `extends Node`, `const SEED=0xA575`, `var _ok/_fail`, `_check_watermark(spec_nodes)`, hierarchy `52,0,0` regression, `headless quit(1)` if watermark missing |

No `set_position_directly`.

---

## 13. Shader Requirements

- **Contracts (comments at top of each `.gdshader` mandatory):**
  - `black_hole_raymarch.gdshader`: `// BH RAYMARCH: MAX_STEPS 64/128/256 by quality, RAY_EPS 0.01, alpha≈2rs/b, SIMPLIFIED SCHWARZSCHILD (no Kerr). Params: rs, mass, watermark 0/1. Includes common_lib ray_sphere/deflect.`
  - `gravitational_lensing.gdshader`: `// LENSING: alpha=4GM/c²b=2rs/b, Einstein ring theta_E, SubViewport sample.`
  - `wormhole_throat.gdshader`: `// WORMHOLE b(r)=b0²/r, embed z, portal UV, watermark uniform. SPECULATIVE variant bright throat.`
  - `warp_bubble.gdshader`: `// ALCUBIERRE f(rs) tanh sigma*(rs±R), v uniform, SPECULATIVE watermark.`
  - `grid_curvature.gdshader`: `// GRID: vertex deflection rs/b, 20×20 baseline.`
- **Boilerplate:** `shader_type spatial` (raymarch lens as `canvas_item` for fullscreen also accepted but document), `uniform float rs`, `uniform float watermark:hint_range(0,1)`, `#include "res://shaders/utility/common_lib.gdshaderinc"` at least 2 shaders, `watermark` mix overlay text via `if (watermark>0.5) ALBEDO += vec3(0.2)` pattern.
- **Compute (optional):** `compute/lensing_prepare.glsl` `#version 450` `local_size 64` with `layout(binding=0) buffer` culling — document if not added (fallback GDScript 64-step `1.0ms TARGET`).
- **Validation:** `validate_shaders.py` `shader_type` no `python`, `RANDOM_SEED` check still passes; `phase03_validation.gd` `ResourceLoader.exists+load` all 5 spacetime shaders + `common_lib` include resolve, `watermark` param set without error.
- **Budget:** raymarch `1.0ms HIGH 128 steps` (TARGET), lensing fullscreen `0.5ms`, warp grid `0.3ms` — MEASURED only with GPU timer.

---

## 14. Material Requirements

- `black_hole_material.tres` `ShaderMaterial` `shader ExtResource("1_raymarch") → res://shaders/spacetime/black_hole_raymarch.gdshader` `rs 0.3`, `watermark 0.0`, numeric id, `checked ext_resources 1 ok`
- `wormhole_material.tres` `ShaderMaterial` `shader → wormhole_throat.gdshader` `throat_radius 2.0`, `watermark 1.0` (SPECULATIVE default, test asserts)
- `warp_material.tres` `ShaderMaterial` `shader → warp_bubble.gdshader` `R 4, v 1.2, sigma 8`, `watermark 1.0`
- No `GradientTexture1D_*` SubResource inside `.tres`; all numeric ids, `res://` constrained.

---

## 15. C++/GDExtension Requirements Where Justified

- **Justification exists:** `AstraInstanceHelper` BH raymarch prep 64-step 60Hz would be GDScript `1.2ms` → compute `0.08ms` per `PERFORMANCE.md` pattern. Phase 03 **may** extend `lensing_prepare` compute (same build). Not mandatory for Phase 03 functional correctness (GDScript 64-step renders headless without compute). Keep `scons target=template_release api_version=4.4`, `gdext_library_init` verified. Document fallback: if `RenderingDevice` unavailable (`headless gl_compatibility`),skip compute, run GDScript loop 64 steps `<2ms` (TARGET).
- **Do not** add Kerr numeric kernel as standalone `.so` without profiling evidence.

---

## 16. Python Tooling Requirements Where Justified

- Extend `validate_godot_project.py` expected shaders to include 5 spacetime → `24+` total, expected materials to `7`, keep `57 base` 0 FAIL.
- `validate_shaders.py` `shader_type` all 5 new must pass; add `watermark` presence check for `SPECULATIVE` shaders (optional warning, not fail).
- `validate_bridge.py` add `classification in {REAL_DATA,THEORETICAL,SPECULATIVE}` check for `kind black_hole/wormhole/warp` without breaking legacy 3-object.
- Keep `validate_coordinates.py` 27 OK and `pytest 1660 passed`.

---

## 17. Node/JavaScript Tooling Requirements Where Justified

- Update `bridge_adapter.js` allowlist to include `black_hole/wormhole/warp` + `classification` quartet; `generate_manifest.js` deterministic 9 assets unchanged (no new binary). No npm runtime deps.

---

## 18. Addon/Dependency Requirements

- **Document any new addon** `DEPENDENCIES.md` row. **Prefer none.** If adding `Godot Starfield` etc., already rejected. Raymarch is hand-written GLSL `<5KB`.
- If proposing `GDExt raymarch plugin`, document GPL risk and reject unless MIT.

---

## 19. Asset Requirements

- Reuse 9 assets CC0, `<2MB`. No HDR from `polyhaven`, no new `*.ppm` >512 without `generate_lut.py`. Lensing uses `ViewportTexture`, not asset file.

---

## 20. Coordinate-System Requirements

- Reuse `OriginRebaser`/`CoordinateBridge`. BH/wormhole at `±10` local tests same rebasing as astronomical. Keep `52,0,0` hierarchy regression test in `phase03_validation.gd` (World→Universe chain still valid).

---

## 21. ASTRA ↔ Godot Boundary

- `bridge_state.json` for extreme objects **must include** `classification`: `black_hole: THEORETICAL` (simulated) or `REAL_DATA` (M87* image-based), `wormhole/warp: SPECULATIVE` always — `phase03_validation.gd` asserts this mapping.
- `ShaderManager` **never invents** classification; `SPECULATIVE` visuals are `ShaderManager._speculative_overlay()` with distinct shader + `Label` watermark. `Telemetry` logs `classification histogram`.
- `AstraBridge.request_interaction` still only way to move toward BH (no `teleport`).

---

## 22. Performance Requirements

- **TARGET RTX 3060 `HIGH`:** BH raymarch `1.0ms` (128 steps) + lensing `0.5ms` (1024 viewport) + wormhole portal `0.4ms` (256) + warp grid `0.3ms` + nebula baseline `0.8ms` = `3.0ms`. `LOW: 64 steps 512 viewport 0.4ms BH` → `CINEMATIC 256 steps 2048 1.8ms` supersampled.
- **Fallback:** headless/LOW 64 steps GDScript `≈1.5ms`; if `>2ms` log `WARN` not FAIL (TARGET).
- **Measured only** with `Telemetry` `RenderingServer` when Vulkan.

---

## 23. Quality Presets

- `LOW 0.5 ms` (`64 steps`, `512 lens`, no portal supersample) → `CINEMATIC 2.5 ms` (`256`, `2048`, `DoF+glow`). Verify `QualityPresets.apply` toggles `MAX_STEPS`, `viewport size`, `watermark intensity`?

---

## 24. Security/Resource Boundaries

- `res://` constrained same §24 Phase 01; new materials numeric `ExtResource`, 1 ok, no `../` outside.
- No `/home`, no `*so` outside `extensions/bin`, no `http` runtime, no `eval`.
- Lensing `SubViewport` `ViewportTexture` not file path, safe.

---

## 25. Testing Requirements

- `pytest 1660 passed`
- `validate_godot_project.py` 0 FAIL spanning 24+ shaders 7 materials
- `validate_shaders.py` all spacetime have `shader_type`, include common_lib, `local_size` if compute, no python tokens
- `phase03_validation.gd` checks: `hierarchy 52,0,0`, 1 BH `r_s/photon/shadow` values sanity, lens `theta_E` finite, wormhole `SPECULATIVE watermark 1.0` visible, warp `SPECULATIVE watermark 1.0`, `ResourceLoader` 5 shaders 3 materials `!=null`, malformed bridge no crash, headless quit 1 on watermark miss.

---

## 26. Runtime Validation Requirements

- `godot --path visualization/godot --headless --scene res://phase_03_extreme_physics/scenes/phase03_validation.tscn` → `[OK]BlackHole`, `[OK]Lensing`, `[OK]Wormhole SPECULATIVE watermark`, `[OK]Warp SPECULATIVE watermark`, summary `X OK 0 FAIL`, exit 0
- Regression both prior scenes still exit 0
- `godot --version` `4.4.1`, zero fatal warnings.
- If no Vulkan: `ENVIRONMENT BLOCKED` for raymarch pixels expected, but `ResourceLoader` + watermark checks still VERIFIED.

---

## 27. Failure Handling

- Missing `black_hole_raymarch.gdshader` → fallback `StandardMaterial3D` black sphere, `FAIL` not crash
- `ViewportTexture` unavailable headless → disable lensing quad, log `WARN lens unavailable headless`
- `SPECULATIVE` branch missing → `FAIL watermark` → `quit(1)` headless (honesty enforcement)
- Malformed `rs` NaN → guard `is_finite`, fallback `rs 0.3`.

---

## 28. Documentation Requirements

- `phase_03_extreme_physics/README.md` formulas (`alpha≈2rs/b`, `r_ph 1.5 r_s`), quality step table, honesty policy with `REAL/THEO/SPEC` legend, how to run 3 scenes
- `VALIDATION_REPORT.md` append `PHASE 03` taxonomy, preserve 01–02, explicit `SPECULATIVE watermark` evidence
- `SHADER_CATALOG.md` via `generate_shader_catalog.py` include 5 spacetime shaders line per shader params
- No erasure of prior evidence

---

## 29. Completion Criteria

- 5 spacetime shaders + 3 materials load `!=null` headless, `watermark` uniform set
- `phase03_validation` deterministic `SEED 0xA575`, 1 BH +1 WH +1 warp + grid placed, `SPECULATIVE` labels visible (verified via `get_node Label visible` check headless without pixel)
- Lensing `alpha` finite, shadow `2.6 r_s`, photon `1.5 r_s` checks
- No regression `52,0,0`, prior scenes still exit 0, `validate_*` 0 FAIL, `pytest` 1660 passed

---

## 30. Evidence Required

- `git branch --show-current` + `godot --version` + `godot --headless --scene ...phase03_validation.tscn` stdout/exit
- `validate_godot_project/validate_shaders/pytest` logs
- Optional `Telemetry` `lensing_ms` when GPU
- Screenshot optional headless, but `DiagnosticsLabel` text + watermark `Label.text` logged

---

## 31. Final Status Criteria

- **GREEN:** all §29 + `godot --headless` exit 0, watermark checks pass, zero shader compile error, lensing `theta_E` finite, no P0/P1. Requires Vulkan for raymarch pixel GREEN else YELLOW still achievable via `ResourceLoader`+watermark.
- **YELLOW:** scene+shaders+materials exist and `validate_*` OK but Godot/Vulkan blocked (`ENVIRONMENT BLOCKED`) — raymarch visual not pixel-verified, GDScript fallback not timed, but watermark logic verified via `ResourceLoader`. Acceptable with NETWORK-INSTALL failed logs.
- **RED:** `RED` if wormhole/warp renders without `SPECULATIVE` watermark, `black_hole_raymarch` missing `shader_type` or fails to `load`, `validate_shaders` >0 FAIL, hierarchy regression, or `SPECULATIVE` classification invented/missing.

---

## 32. Handoff to Next Phase

- **Preserve** `phase_03_extreme_physics/` alongside 01–02; do not merge spacetime shaders into astronomical.
- **Dependencies for Phase 04:** extreme lensing `SubViewport` pattern reused for VFX distortion, `SpacetimeGrid` syncs to ASTRA state but does not animate battle. Phase 04 VFX must not overwrite `black_hole_raymarch` nor remove watermark.
- **Next agent:** `PHASE_04_VFX_CINEMATICS.md` — impact/GPU particles/volumetrics/post/cinematic cameras **sync’d to ASTRA `simulation_state.json` ticks** (contrast with Phase 03 static theoretical).

---

*Philosophy: **simulate honestly** — `REAL` observed, `THEORETICAL` mathematically solved, `SPECULATIVE` unobserved; shaders and labels maintain this at 60 fps.*
