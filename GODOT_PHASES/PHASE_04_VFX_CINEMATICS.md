# GODOT PHASE 04 — VFX & CINEMATICS

**Version:** 1.0 — 2026-09-17  
**Target:** Godot 4.4.1 Forward+ (GPU particles `GPUParticles3D`, volumetric fog breakup, postprocess `GLOW/SSAO/DoF`, camera rigs)  
**Branch:** `arena/01a0a5a2-astra-cosmos`  
**Prerequisite:** Phases 01–03 YELLOW+ (foundation + astronomical instancing + honesty for extreme). This phase is **event-driven**: VFX triggers from `ASTRA simulation_state.json` (tick `ImpactEvent`/`WarpEnter`) not autonomous loop.  
**Status taxonomy:** STATIC VERIFIED / RUNTIME VERIFIED / NOT VERIFIED / ENVIRONMENT BLOCKED; preserves `REAL/THEO/SPEC` labeling (impacts `REAL`, warp entry `SPECULATIVE` watermark persists).

---

## 1. Phase Identity

- **Phase:** `PHASE_04_VFX_CINEMATICS`
- **Order:** 4 of 5 (`01[X]→02[X]→03[X]→04→05`)
- **Code prefix:** `phase_04_vfx_cinematics/` under `visualization/godot/`
- **Deliverable:** `GODOT_PHASES/PHASE_04_VFX_CINEMATICS.md` (this file) + `visualization/godot/phase_04_vfx_cinematics/`
- **Gate scene:** `phase04_validation.tscn` seed `0xA576` triggers mock `ImpactEvent` + `WarpEntry` + cinematic camera spline synchronously and verifies ASTRA tick sync.

---

## 2. Objective

Add **synchronized visual effects and cinematic presentation** that makes ASTRA’s authoritative physics **feel impactful and observable** without **inventing physics**.

Deliver: impact/collision VFX (GPU particles + decals), warp entry/exit distortion, environmental/nebula volumetric breakup, GPU particle systems at scale (32 LOW → 1024 CINEMATIC), postprocess stack (bloom/glow `0.35 HIGH`, `SSAO`, `DoF`, motion blur), fog `VolumetricFog`, and **cinematic camera rigs** (dolly, crane, shake, follow, replay) **driven by `ASTRA simulation_state` ticks** (not free random).

---

## 3. Scope

**In scope (sync to ASTRA state required):**

- **Impact/collision VFX:** `ImpactVFX.gd` listening `AstraBridge.render_state_updated` `events[]: {type:"Impact", position, energy, tick}` → spawn `GPUParticles3D` (`impact_spark.gdshader` with `RANDOM_SEED` — not `randf()`), `GPUParticlesAttractor`, decal `Decal` crater `size ∝√energy`, shockwave `MeshInstance3D` expanding `1.5 s` `ease_out`, `impact_flash` light `energy 3.0 decay 0.3s`
- **Warp VFX:** `WarpVFX.gd` `events type WarpEnter/WarpExit` → lensing `SubViewport` distortion (reuse Phase 03 lens pattern) + `warp_streak.gdshader` streak particles `512 HIGH`, bubble `Alcubierre` watermark persisted `SPECULATIVE`
- **Environmental VFX:** `EnvironmentalVFX.gd` nebula `FogVolume` breakup noise `fBm` scrolling `0.02 u/s`, `environmental_particles.gdshader` dust motes `128 MEDIUM`, `atmospheric_entry` trail (optional if bridge provides `entry` event)
- **GPU particles:** `ParticleSystems.gd` manager pooling `GPUParticles3D` `amount 32 LOW/128 MED/256 HIGH/512 ULTRA/1024 CINEMATIC`, fixed `process_material ShaderMaterial` with `RANDOM_SEED`, burst vs continuous modes, culling by distance.
- **Volumetrics:** `VolumetricFog` global (`environment.volumetric_fog_enabled` + `FogVolume` per nebula `density 0.02 HIGH`, `albedo 0.6,0.3,0.8`), breakup via `nebula_volumetric.gdshader` noise, density gated by `QualityPresets` `64 LOW fog off` → `192 CINEMATIC`
- **Postprocess:** `PostProcessStack.gd` `WorldEnvironment` `glow_enabled` `0/0.2/0.35/0.6/0.8` + `glow_bloom 0.05`, `SSAO enabled HIGH+`, `SDFGI` `ULTRA+`, `DoF blur CINEMATIC only` (`dof_blur_far_enabled true distance 20`), motion blur stub (shader `motion_blur.gdshader` if present, else `Environment.sdfgi_enabled` note)
- **Cinematic cameras:** `CinematicCameraRig.gd` extended `CameraSystem` (`phase01 CameraSystem` base) with `dolly(N:Path3D)`, `crane(height)`, `shake(intensity tick-synced not random)`, `follow(target)`, `replay(tick interpolation)`; timeline `CameraTimeline.gd` keyframes `tick→transform` interpolated by `SimulationClock`, all modes via `set_mode(Mode.CINEMATIC)` + `play_timeline(events)`
- **ASTRA sync:** every VFX queries `AstraBridge.render_state.tick` / `sim_time`, interpolation `lerp` between `tick_n` and `tick_n+1` with `origin_offset`; no autonomous tick generator.

**Out of scope — §4.**

---

## 4. Non-Goals

- No new physics authority (impacts already computed Python; Godot only plays VFX for `events[]` entries)
- No black hole raymarch/wormhole warp physics changes (reuse Phase 03 shaders, not redesign)
- No HLOD/streaming or performance autotuning beyond quality preset mapping (Phase 05)
- No audio/score (visual only; telemetry mute)
- No non-deterministic camera shake (`shake` uses `seed tick` not `randf()`)
- No timeline editor UI — keyframes code-driven via `simulation_state`.

---

## 5. Existing ASTRA Systems to Inspect

- `astra/simulation/state.py` / `simulation_state.json` if exists — event log `ImpactEvent{ tick, position, energy, participants[] }`, `WarpEvent`. VFX must consume `events[]` shape without inventing fields.
- `astra/scientific/collisions.py` or `astra/world/spatial.py` collision detection produces events; `astra/theoretical/warp.py` `WarpEntry` → `SPECULATIVE` classification carries.
- `astra/temporal/simulation_clock.py` `sim_time` ticks camera interpolation; `astra/interaction/engine.py` may generate `Impact` via `request_interaction`.
- `tests/test_simulation*` `tests/test_interaction` event shapes.

---

## 6. Existing Visualization Systems to Reuse

**AUDIT → REUSE → EXTEND → TEST**

- `phase_01_foundation` `CameraSystem.gd` `Mode.CINEMATIC/REPLAY` + `AstraBridge.render_state_updated` + `Telemetry` extend VFX counts; `CoordinateBridge` origin for particle spawn positions `pos_local = event.position - origin_offset`.
- `phase_02_astronomical` `ShaderManager` → extend `get_vfx_shader(type, energy, classification)` (impact `REAL`, warp `SPECULATIVE` watermark)
- `phase_03_extreme_physics` `GravitationalLensing` `SubViewport` pattern + `warp_bubble.gdshader` reuse for warp VFX distortion; keep watermark.
- `visualization/godot/shaders/` 19 → ensure `vfx/impact_spark.gdshader` (`RANDOM_SEED` not `randf`), `vfx/warp_streak.gdshader`, `vfx/environmental_particles.gdshader`, `vfx/shockwave.gdshader` or `impact_flash.gdshader`, `postprocess/glow_composite.gdshader` if not built-in, plus `compute/instance_prepare.glsl` not used here (keep)
- `visualization/godot/vfx/` 10 categories (`impact_spark`, `warp_streak`, `environmental_particles`, `fog_breakup`, etc.) — reuse, fix `shader_type` if missing, do not duplicate `visualization/vfx/` → `visualization/godot/vfx/` sync via `cp -r`
- `visualization/godot/materials/` 7 (`planet/star/nebula/galaxy/bh/wormhole/warp`) → reuse, add `impact_material.tres` `ShaderMaterial` `impact_spark` if not `StandardMaterial3D` pool, numeric `ExtResource`.
- `visualization/tools/validate_*` extend expected VFX shaders, keep `57` base plus new VFX `extend` → `62+`.
- `visualization/godot/phase_02`/`phase_03` scenes preserve.

---

## 7. Architecture

```
ASTRA simulation_state (tick, sim_time, events[Impact{pos,energy,tick}, WarpEnter{pos, tick}] + origin_offset)
        ↓ bridge_state.json 30 Hz (AstraBridge polls same file extended)
AstraBridge → EventBus (signals impact_triggered(position,energy,tick), warp_enter/ warp_exit)
        ↓ origin subtract per-event pos_local
ImpactVFX / WarpVFX / EnvironmentalVFX  (pooled GPUParticles3D + Decal + Shockwave + SubViewport distort)
        ↓ GPU particles (RANDOM_SEED, amount by quality)
PostProcessStack (WorldEnvironment glow/SSAO/DoF/fog) — applies to whole viewport
        ↓
CinematicCameraRig (dolly Path3D, crane, shake seed tick, follow, replay tick-lerp)
        ↓
Forward+ render (Vulkan, Forward+ tiling handles 1k particles at 0.5ms TARGET)
```

**Sync invariant:** `CinematicCameraRig._process` queries `AstraBridge.render_state.tick` + `sim_time` → lerps `timeline[tick_n].transform → timeline[tick_next]` with `SimulationClock` delta; never `Time.get_ticks_msec()` alone.

---

## 8. Data Flow

1. Python writes `bridge_state.json` example `{"tick":100,"sim_time_s":500.0,"origin_offset":[0,0,0],"objects":[...],"events":[{"type":"Impact","position":[20,0,0],"energy":4e6,"tick":100,"classification":"REAL_DATA"},{"type":"WarpEnter","position":[10,0,0],"tick":101,"classification":"SPECULATIVE"}]}` (additive `events`, old objects remain).
2. `AstraBridge._poll_astra()` guard `JSON.parse OK` → emit `render_state_updated` → `phase04 EventBus` dispatches: `if event.type=="Impact": ImpactVFX.spawn(pos_local = event.position - origin_offset, energy, classification)` creates `GPUParticles3D` burst `amount 256 HIGH` lifetime `1.5s` + `Decal` at `pos_local` + `Shockwave` scale `0→12` tween `SINE`.
3. `WarpVFX` on `WarpEnter` enables `SubViewport distort 1024 HIGH` + `warp_streak` particles 512, keeps `warp_material watermark 1.0` visible.
4. `EnvironmentalVFX._process` scrolls `FogVolume` noise offset `+= delta*0.02` only if `QualityPresets >= MEDIUM`.
5. `CinematicCameraRig.play_timeline(events)` builds keyframes `tick→camera pos` e.g., `dolly along Path3D at 0.5 u/s sim_time`, replay interpolates between ticks with `lerp` `alpha = (sim_time - tick_time)/(next_tick_time - tick_time)`.

---

## 9. Required Systems

- `ImpactVFX.gd: Node` `func spawn_impact(pos:Vector3, energy:float, classification:String)` pooling, `var _pool:Array[GPUParticles3D]`
- `WarpVFX.gd: Node` `func enter(pos:Vector3)` / `exit()`, distortion `SubViewport`
- `EnvironmentalVFX.gd: Node` scrolling `FogVolume` + dust `GPUParticles3D`
- `ParticleSystems.gd: Node` manager `func emit_burst(count:int)` quality-scaled, `RANDOM_SEED` check
- `PostProcessStack.gd: Node` `func apply_preset(p:Preset)` toggling `WorldEnvironment` `glow/ssao/dof/sdfgi/fog` per `QUALITY_PRESETS.md`
- `CinematicCameraRig.gd: Node3D` extends `CameraSystem` `func set_mode/cinematic`, `func dolly(path:Path3D)`, `func shake(intensity, seed_tick:int)`, `func follow(target:Node3D)`, `func play_timeline(events:Array)` tick-lerp
- `CameraTimeline.gd: Resource` `Array[Dictionary] {tick:int, transform:Transform3D}`
- `EventBus.gd: Node` optional autoload or `AstraBridge` signals reused
- `phase04_validation.gd: Node` `SEED 0xA576` spawns 1 impact + 1 warp event mock, drives camera dolly 3s, checks sync `event.tick == AstraBridge.frame_id`, watermark for warp, particle `emitting`.

---

## 10. Required Files/Directories

```
visualization/godot/phase_04_vfx_cinematics/
  README.md
  scenes/phase04_validation.tscn  (UID uid://astra_phase04_validation)
  scenes/cinematic_rig.tscn       (Path3D + Camera + Rig)
  scripts/impact_vfx.gd
  scripts/warp_vfx.gd
  scripts/environmental_vfx.gd
  scripts/particle_systems.gd
  scripts/postprocess_stack.gd
  scripts/cinematic_camera_rig.gd
  scripts/camera_timeline.gd      (or inline in rig)
  scripts/event_bus.gd            (or reuse AstraBridge signals)
  scripts/phase04_validation.gd
  environments/cinematic_env.tres (glow 0.6 SSAO ON DoF CINEMATIC)
  materials/impact_material.tres
  materials/warp_vfx_material.tres
visualization/godot/shaders/vfx/impact_spark.gdshader (RANDOM_SEED)
visualization/godot/shaders/vfx/warp_streak.gdshader
visualization/godot/shaders/vfx/environmental_particles.gdshader
visualization/godot/shaders/vfx/shockwave.gdshader (optional)
visualization/godot/shaders/postprocess/glow_composite.gdshader (optional)
visualization/godot/vfx/ (10 mirrored, validate shader_type)
```

Preserve all prior `phase_01–03` dirs.

---

## 11. Godot Scene Requirements

**`phase04_validation.tscn` deterministic seed `0xA576` headless 1.0s:**

- `Phase04Root` `Node` script `phase04_validation.gd`
  - `WorldEnvironment` `environment cinematic_env.tres` `glow_enabled true glow_bloom 0.05 glow_strength 0.6` `ssao_enabled true` `sdfgi_enabled ULTRA+` `volumetric_fog_enabled true` `fog_density 0.02` `dof_blur_far_enabled false LOW→true CINEMATIC distance 20` (verify `MEDIUM` fog off)
  - `DollyPath` `Path3D` curve 3 points `(0,5,20)→(10,6,5)→(0,8,-5)` width `1`, `PathFollow3D` with `CinematicCameraRig` `Camera3D` `fov 60` current at path start
  - `ImpactSite` `Node3D` at `(8,0,0)` `ImpactVFX` pool `GPUParticles3D 256` `process_material ShaderMaterial impact_spark` `amount 256 HIGH` `lifetime 1.5` `emitting false` initially, `Decal` `size 4` `albedo earth_like_albedo.ppm`, `Shockwave MeshInstance3D Sphere 0.1` scale tween
  - `WarpSite` `Node3D` at `(-8,0,0)` `WarpVFX` `SubViewport 512 LOW→1024 HIGH` with `warp_bubble` material + `GPUParticles3D warp_streak 512` + watermark `Label "SPECULATIVE — WARP ENTRY"`
  - `Environmental` `FogVolume extents 30,10,30` at `y=5` `density 0.02 HIGH` with `EnvironmentalVFX` scroll, plus dust `GPUParticles3D 128`
  - `DiagnosticsOverlay` extended `Label` `impact 1 energy 4e6 tick 100, warp 1 tick 101 SPECULATIVE, particles 256/128 active, glow 0.6 ssao ON dolly progress 0.4, tick sync OK`
  - `ObjectRegistry` reused, `AstraBridge` mock `events[]` set in `_ready` before `_poll`

Trigger mock: `phase04_validation.gd _ready` writes `AstraBridge._last_state.events = [{type:"Impact",...tick:100},{type:"WarpEnter",tick:101}]` and after `0.2s` calls `ImpactVFX.spawn` + `WarpVFX.enter`, after `0.5s` drives `CinematicCameraRig.dolly` `0.5 u/s`, after `0.8s` checks `camera tick lerp`.

Headless `get_tree().quit(0/1)` after `1.0s`.

---

## 12. GDScript Requirements

**Typed, signal-driven, tick-synced.**

| File | Key API |
|---|---|
| `impact_vfx.gd` | `class_name ImpactVFX: Node`, `func spawn(pos:Vector3, energy:float, cla:String)` `pos_local = pos - AstraBridge.get_origin_offset()`, `particles.emitting=true`, `decal.position=pos_local`, shock tween `create_tween().tween_property(shock,"scale",Vector3(12,12,12),1.5)` |
| `warp_vfx.gd` | `class_name WarpVFX: Node`, `func trigger(pos:Vector3, cla:String)` enables `SubViewport`, `warp_streak.emitting=true`, `watermark 1.0 if SPECULATIVE`, `exit()` disables |
| `environmental_vfx.gd` | `class_name EnvironmentalVFX: Node`, `_process(delta) fog_material.set_shader_parameter("scroll", scroll+delta*0.02)` if `QualityPresets.current >=MEDIUM` |
| `particle_systems.gd` | `class_name ParticleSystems: Node`, `func get_budget(p:Preset)->int` `32/128/256/512/1024`, `RANDOM_SEED` uniform not `randf()` |
| `postprocess_stack.gd` | `class_name PostProcessStack: Node`, `func apply(p:Preset)` sets `environment.glow_enabled`, `ssao_enabled`, `sdfgi_enabled`, `fog_density`, `dof` per `QUALITY_PRESETS.md` table |
| `cinematic_camera_rig.gd` | `class_name CinematicCameraRig: CameraSystem` (extends Phase01), `func dolly(path:Path3D)`, `func shake(intensity:float, seed_tick:int)` `Camera3D.position += Vector3(sin(seed_tick),cos(seed_tick))*intensity` deterministic, `func play_timeline(events:Array[Dictionary])` lerp by `sim_time` |
| `phase04_validation.gd` | `extends Node`, `SEED 0xA576`, mock events, after ticks `_check_particles_emitting`, `_check_camera_tick_sync`, `_check_watermark_warp`, `_check_postprocess_glow`, hierarchy regression `52,0,0`, headless quit 1 on any FAIL |

All signal connections `AstraBridge.render_state_updated.connect`.

---

## 13. Shader Requirements

- **Shaders reused/extended:**
  - `impact_spark.gdshader` `shader_type particles` uses `RANDOM_SEED` (mandatory, checked `validate_assets.py` still passes), `amount` by quality, lifetime `1.5`.
  - `warp_streak.gdshader` `shader_type particles` streak length, color.
  - `environmental_particles.gdshader` `shader_type particles`.
  - `shockwave.gdshader` or `impact_flash.gdshader` `shader_type spatial` ring expand `time` uniform `0→1.5` driven by GDScript tween.
  - `postprocess/glow_composite.gdshader` optional `shader_type canvas_item` if custom bloom else rely on `WorldEnvironment glow_*` built-in (prefer built-in, shader optional).
- **Validation:** `validate_shaders.py` all VFX have `shader_type`, no `python`, `impact_spark` `RANDOM_SEED` check, `phase04_validation.gd` `ResourceLoader.exists+load` 4 VFX + `cinematic_env.tres` glow params.
- **Budget:** particles `0.5ms HIGH 256` (TARGET), post `glow 0.2ms`, fog `0.3ms`.

---

## 14. Material Requirements

- `impact_material.tres` `ShaderMaterial` `shader ExtResource("1_impact") → res://shaders/vfx/impact_spark.gdshader` or `ParticlesMaterial` pool — numeric id, `1 ok`. If `ParticlesMaterial`, must not contain `GradientTexture1D_*` SubResource (see Phase 01 fix), use `ColorRamp` uniform or `preload`.
- `warp_vfx_material.tres` `ShaderMaterial` `shader → warp_bubble` `watermark 1.0` for `SPECULATIVE`
- `cinematic_env.tres` already env, ensure `glow_enabled true` `glow_strength 0.6` `ssao_enabled true` when `HIGH+`.
- All `res://` constrained, checked.

---

## 15. C++/GDExtension Requirements Where Justified

- **Phase 04 does not require new GDExtension.** `ParticleSystems` pooling `GPUParticles3D` is GPU-native; `InstanceHelper` from Phase 01–02 not needed for VFX (would be unjustified `>1ms` without compute). If profiling shows `ParticleSystems 1024` CPU emit loop `>1.0ms` at 60 Hz, then (and only then) justify `gdextension_particles.cpp` with `emit_burst` compute — require `Telemetry` measurement proof.
- Existing `astra_visualization.gdextension` 601K compiled remains optional fallback verified.

---

## 16. Python Tooling Requirements Where Justified

- Extend `validate_godot_project.py` expected VFX shaders (4) + materials (2) → `66+`; keep prior `57` 0 FAIL.
- `validate_shaders.py` still 19+ with VFX `shader_type`, `RANDOM_SEED` for `impact_spark`.
- `validate_bridge.py` add optional `events[]` validation (`type in {Impact,WarpEnter,ImpactEvent}` no crash) while 3-object still passes.
- No new Python deps.

---

## 17. Node/JavaScript Tooling Requirements Where Justified

- `bridge_adapter.js` allowlist add `Impact`/`WarpEnter` to `event.type`; `generate_manifest.js` still deterministic `9 assets`. No runtime npm.

---

## 18. Addon/Dependency Requirements

- Document any VFX addon (e.g., `Godot VFX Particles Pack`) in `DEPENDENCIES.md` row — **prefer none**, hand-written `<5KB` `.gdshader` keeps MIT small. `FastNoiseLite` etc. already allowed. No GPL.

---

## 19. Asset Requirements

- Reuse `star_temperature_lut.ppm`/`earth_like_albedo.ppm` for decal. Generate any new noise LUT via `generate_lut.py` deterministic `P3` `<200KB`.

---

## 20. Coordinate-System Requirements

- `ImpactSite` at `8,0,0` local = world after subtract `origin_offset` — same `CoordinateBridge` rebasing; `CinematicCameraRig` `global_position` follows `pos_world - origin`; keep `52,0,0` regression.

---

## 21. ASTRA ↔ Godot Boundary

- VFX **only** when `events[]` present in `render_state`; no Godot autonomous impact generation (no `if randf()<0.01: spawn`). `phase04_validation.gd` mock writes `events` mimicking Python, not via Godot `random`.
- `classification` on events drives watermark (`Warp SPECULATIVE`), `Impact REAL` no watermark but tagged `REAL_DATA`.
- Camera `tick-lerp` interpolates between `SimulationClock` ticks via `sim_time_s`, not wall clock — ASTRA authoritative.

---

## 22. Performance Requirements

- **TARGET RTX 3060 HIGH:** particles `0.5ms` (256 spark `RANDOM_SEED`) + fog breakup `0.3ms` + glow `0.4ms` + SSAO `0.2ms` + shockwave `0.1ms` = `1.5ms`; `LOW 0.3ms` (32 particles fog off), `CINEMATIC 2.2ms` (1024 + DoF).
- **Measured** via `Telemetry` `particles_active`, `vfx_ms`, `post_ms` every 60 frames when Vulkan; headless mark `NOT VERIFIED` headless.
- Pooling prevents per-frame alloc; `GPUParticles3D.emitting` toggle not instance add/remove.

---

## 23. Quality Presets

- Verify full 13-feature row for VFX: `LOW 32 particles fog_off glow OFF`, `MEDIUM 128 fog 0` `glow 0.2`, `HIGH 256 fog 64 glow 0.35 SSAO ON`, `ULTRA 512 fog 128 glow 0.6 SDFGI ON`, `CINEMATIC 1024 fog 192 glow 0.8 DoF ON`. `apply()` called in `phase04_validation.gd` for `HIGH` before checks.

---

## 24. Security/Resource Boundaries

- `res://` constrained same; `ViewPortTexture` not file path safe; no `/home` absolute; no `*.so` outside `extensions/bin`; no `http` runtime; no `eval`.

---

## 25. Testing Requirements

- `pytest 1660 passed`
- `validate_godot_project.py` 0 FAIL (VFX shaders/materials/env glow checks)
- `validate_shaders.py` all VFX `shader_type` + `RANDOM_SEED` where particles
- `phase04_validation.gd` dynamic checks: `_check_impact_spawned` `particles.emitting true` after `0.2s`, `_check_warp_watermark 1.0`, `_check_camera_dolly_progress >0.1 after 0.5s`, `_check_tick_sync event.tick==100→101`, `_check_post_glow 0.6 HIGH`, `_check_env_fog`, hierarchy regression, `quit(1)` on any FAIL
- Malformed `events` no crash.

---

## 26. Runtime Validation Requirements

- `godot --path visualization/godot --headless --scene res://phase_04_vfx_cinematics/scenes/phase04_validation.tscn` → `[OK]Impact`, `[OK]Warp SPECULATIVE`, `[OK]Particles`, `[OK]Postprocess`, `[OK]Camera dolly tick-sync`, summary `0 FAIL` exit 0
- Regressions `phase01/02/03` still exit 0
- `godot --version` `4.4.1`, zero fatal.

---

## 27. Failure Handling

- `GPUParticles3D` unavailable headless (`GLES`) → disable VFX particles log `WARN`, still `quit 0` if other checks pass (ENVIRONMENT BLOCKED not FAIL).
- `Decal` unsupported → skip crater, `WARN`.
- `SubViewport` texture missing → disable warp distort, not crash.
- Missing `cinematic_env.tres` → `FAIL` (required).

---

## 28. Documentation Requirements

- `phase_04_vfx_cinematics/README.md` event-driven VFX, `events[]` schema, pooling, `CinematicCameraRig` modes, how to run 4 scenes, quality particle scaling table, `SPECULATIVE` persistence.
- `VALIDATION_REPORT.md` append `PHASE 04` taxonomy preserve 01–03, explicit `tick-sync` evidence
- `SHADER_CATALOG.md` after VFX shaders generation.

---

## 29. Completion Criteria

- 4 VFX shaders + 2 materials + `cinematic_env.tres` load `!=null` via `ResourceLoader`, `RANDOM_SEED` presence for `impact_spark`.
- `phase04_validation` deterministic seed `0xA576`, mock Impact (energy 4e6) spawns particles+decal+shock, WarpEnter shows warp particles+watermark SPECULATIVE, dolly camera progresses tick-interpolated, post glow/SSAO/fog values as `HIGH`.
- Telemetry extended `particles_active`, prior hierarchies `52,0,0` still pass, `validate_*` 0 FAIL, `pytest` 1660.

---

## 30. Evidence Required

- `git branch --show-current`, `godot --version`, `godot --headless ...phase04_validation.tscn` stdout/tick-sync lines, exit code
- `validate_godot_project/validate_shaders/pytest` logs
- `Telemetry vfx_ms` if GPU.

---

## 31. Final Status Criteria

- **GREEN:** §29 all + `godot --headless` exit 0, particles `emitting`, dolly progress, `SPECULATIVE` watermark on warp, no P0/P1
- **YELLOW:** scenes+shaders+materials + `validate_*` OK but headless GPU `GPUParticles3D/ViewportTexture` not pixel-verified `ENVIRONMENT BLOCKED` (particles logic verified via `emitting` bool + config).
- **RED:** `RED` if impact warp spawns without `tick` sync (autonomous random), `speculative` warp without watermark, `impact_spark` uses `randf()` not `RANDOM_SEED`, dolly camera ignores `sim_time`, or `validate_*` FAIL.

---

## 32. Handoff to Next Phase

- **Preserve** all `phase_04_vfx_cinematics/` + `phase_01–03`; do not change earlier validation scenes’ expectations (they should not suddenly require VFX).
- **Dependencies for Phase 05:** Phase 04 particle counts (+volumetrics) are the performance pain Phase 05 optimizes (HLOD/instancing/culling/streaming). Keep `ParticleSystems` pooling — Phase 05 will profile and batch.
- **Next agent:** `PHASE_05_OPTIMIZATION_PRODUCTION.md` — instancing/LOD/culling/streaming/profiling/presets `LOW–ULTRA–CINEMATIC` **on top of VFX/compute already built** — measure `TARGET vs MEASURED`, keep 01–04 functional.

---

*Events drive visuals; cameras tell the story; ASTRA’s tick remains the clock.*
