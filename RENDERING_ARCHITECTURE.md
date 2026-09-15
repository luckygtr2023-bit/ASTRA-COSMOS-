# ASTRA Rendering Architecture v0.1.0

Authoritative boundary:

```
AUTHORITATIVE SIMULATION STATE
            ↓
        RENDER STATE
            ↓
       RENDER CONTEXT
            ↓
         RENDERER
            ↓
       VISUAL OUTPUT
```

Rendering is a **consumer**. It never mutates authoritative simulation state and never becomes a physics engine.

---

## 1. Authority Boundary

- Simulation (World, SceneGraph, Motion, Celestial, Physics, Destruction, Black-Hole, Spacetime, Temporal) is **truth**.
- `RenderPipeline` produces `RenderState` as a **derived snapshot**: it copies positions into render-friendly structures (`position` in floating-origin space, `camera_relative_position`, `distance_to_camera_m`, `apparent_size_rad`, `lod`, `visibility`), never writing back.
- `FloatingOriginRenderer` is **renderer-side** floating origin: it tracks `render_origin` subtracted from world positions. It does NOT call `astra.core.coords.OriginRebaser`; simulation `OriginRebaser` is untouched.
- Rendering errors (`RenderError` hierarchy) are isolated; they do not corrupt `EntityManager`, `SceneGraph`, or `DestructionSystem` ledger.

---

## 2. Render State (`astra.rendering.render_state`)

- `RenderObject` – single visual object (mutable dataclass but cloned on insertion):
  - identity: `id`, `name`, `kind: RenderObjectKind`, `category`
  - spatial: `position: Vector3` (render space), `orientation: Quaternion`, `scale`, `bounding_radius_m`
  - camera-derived: `camera_relative_position`, `distance_to_camera_m`, `apparent_size_rad` (filled by pipeline)
  - visibility: `enabled`, `visible`, `visibility: VisibilityState`, `lod: LODLevel`
  - visual classification: `material: MaterialRef` (placeholder, no shader), `importance 0..1`
  - planetary hints: `atmosphere_params`, `terrain_params`, `ocean_params` (dicts or None)
  - lighting hints: `receives_light`, `casts_shadow`, `emissive`
  - destruction: `damage_state: DamageVisualState`, `fragment_ids`, `ejecta_ids`
  - temporal: `temporal_mode: TemporalRenderMode`, `observation_time_s`, `emission_time_s`, `provenance`, `source_ref`
  - metadata/tags: renderer-independent extensions

- `RenderState` – frame snapshot:
  - `tick`, `simulation_time_s`, `render_origin`, `temporal_mode`, `provenance`
  - deterministic insertion order (`order: List[str]`), bounded `max_objects` (default 200k)
  - `add/update/remove/get/clone/iterate/is_renderable/to_dict` – `get` returns a clone for isolation

- `MaterialRef` – placeholder `id/kind/params` tuple; resolved by future Graphics/VFX, never a shader here.

---

## 3. Render Context (`astra.rendering.render_context`)

Bundles per-frame inputs without acquiring authority:

- `camera: Camera` (clone)
- `viewport: Viewport` (`x,y,width,height`, `aspect`)
- `render_state: RenderState | None`
- `coordinate_frame: str` (`"world"`), `render_origin: Vector3`
- observation: `observation_state: TemporalRenderMode`, `observation_time_s`, `observer_id`
- quality: `quality: QualityLevel`, `lod_config: LODConfig`, `constraints: RenderingConstraints`
- `visual_seed: int` for deterministic visual randomness
- `extensions: Dict` for future Graphics/VFX bridge
- `clone/with_render_state/to_dict/from_dict` – isolated copies

---

## 4. Camera (`astra.rendering.camera`)

Single camera model scaled from spacecraft to galaxy:

- `Camera(position: Vector3 world, orientation: Quaternion, fov_y_deg, near, far, projection: Perspective|Orthographic, viewport, target, mode, follow_target_id, ortho_height_m)`
- Validation: finite vectors, unit quaternion, `1 ≤ fov < 179`, `far > near`
- Methods: `look_at(target, up)`, `get_forward/up/right/view_direction`, `move(delta)`, `orbit(yaw,pitch,distance)`, `set_perspective/set_orthographic`, `world_to_camera/distance_to/apparent_angular_size`, `track(follow)`, `clone/to_dict/from_dict`
- Scales: `far` up to `1e18`–`1e25` (cosmic), `near` down to `0.01` (spacecraft), double-precision world positions + floating-origin for precision.
- `CameraMode`: `FREE | ORBIT | TRACKING | FOLLOW | FIXED`
- `CameraController` – deterministic `update_tracking/update_follow/move_free/orbit_around_target/update(dt)` driven by explicit `dt`/`target positions`, no wall-clock.

---

## 5. Coordinates (`astra.rendering.coordinates`)

Boundary:

```
WORLD (absolute, double)
  ↓  world_to_render(world, render_origin) = world - origin
RENDER (floating-origin, camera-friendly)
  ↓  world_to_camera_relative(world, camera) = world - camera
CAMERA-RELATIVE (highest precision at eye)
```

- Pure functions: `world_to_render`, `render_to_world`, `world_to_camera_relative`, `render_to_camera_relative`, `batch_world_to_render`, `apply_render_origin_to_state` – all validate finiteness, return new vectors, never mutate.
- `FloatingOriginRenderer`: independent renderer-side rebaser
  - `origin: Vector3`, `config: FloatingOriginConfig(threshold, hysteresis, max_render_distance)`
  - `needs_rebase(camera_world_pos)`, `rebase_to(new_origin)`, `rebase_to_camera(camera)`, `world_to_render/render_to_world`, `apply_to_render_state`, `transform_render_state_camera_relative`, `history/reset`, `rebase_count`
  - Rebase preserves physical relative positions: `new_render = old_render + (old_origin - new_origin)`

---

## 6. LOD (`astra.rendering.lod`)

Visual-only, deterministic:

- `LODLevel`: `ULTRA(0) < HIGH < MEDIUM < LOW < IMPOSTOR < CULLED(5)`
- `LODConfig`: distance thresholds (`ultra/high/medium/low/cull`), angular thresholds (`ultra/high/medium/low/impostor`), `kind_bias` (star 100, galaxy 1000, planet 10…), `quality_bias`, `global_bias`
- `LODSelector.select(distance_m, radius, apparent_size_rad, kind, quality, importance)` – pure function, no RNG:
  - If `apparent_size_rad` present, it overrides distance (stars/galaxies always `IMPOSTOR` when tiny instead of `CULLED`).
  - Importance maps to `imp_bias = 0.5 + importance`, `effective_distance = raw / (kind_bias * quality_bias * imp_bias)`.
  - Returns deterministic LOD; `is_visible(lod) -> lod != CULLED`.

---

## 7. Visibility / Culling (`astra.rendering.culling`)

Simulation objects are never removed because culled.

- `Plane(normal, d)` and `Frustum(planes: [near,far,left,right,top,bottom])` – `Frustum.from_camera(camera)` extracts six inward planes analytically (perspective tanHalfY/X, orthographic extents), `contains_point/sphere`.
- `CullingConfig`: `enable_frustum/distance/category_filter`, `max_distance_m`, `culled_categories`, `visible_categories`, `min_importance`, `respect_enabled/visible`.
- `VisibilitySystem`:
  - `classify(obj, camera, frustum) -> VisibilityState(VISIBLE|HIDDEN|CULLED_FRUSTUM|CULLED_DISTANCE|CULLED_CATEGORY|DISABLED)`
  - Respects `enabled/visible` flags, `lod == CULLED`, `importance`, `distance_to_camera_m` vs `max_distance`, frustum sphere test (uses world positions via `world = render + origin` to stay coherent with floating origin), category filtering.
  - `filter_visible(objects, camera, frustum)` preserves order deterministically.
  - `apply_to_render_state(state, camera)` mutates clone’s `visibility` flags and returns `culled_count`.

---

## 8. Celestial Rendering (`astra.rendering.celestial`)

Consumes existing `astra.celestial` without duplicating the database:

- `celestial_kind_to_render_kind(ObjectCategory) -> RenderObjectKind`
- `CelestialRenderDescriptor(object_id, name, category, render_kind, radius_m?, mass_kg?, spectral_type, color_hint, material, provenance)` – `describe_celestial(CelestialObject) -> descriptor` extracts radius/mass where known (tries `require_*` then optional fields, never fabricates), maps `SpectralType -> RGB` hint, preserves provenance.
- `celestial_to_render_object(celestial_obj, world_position, orientation?, render_origin?, scale?) -> RenderObject` – converts to `RenderObject` with `bounding_radius_m` heuristic if unknown, `emissive` for stars/galaxies/nebulae, `source_ref` links back to celestial id.

---

## 9. Planetary Rendering (`astra.rendering.planetary`)

Interfaces, not VFX:

- `TerrainDescriptor(height_scale_m, base_radius_m, height_map_ref?, detail_level, material, lod_bias)`
- `AtmosphereDescriptor(height_m, rayleigh_scale_height, mie_scale_height, rayleigh_scattering (3-tuple), mie_scattering/anisotropy, density_falloff, material)`
- `OceanDescriptor(sea_level_m, wave_height_m, choppiness, depth_m, normal_map_ref?, material)`
- `CloudDescriptor(coverage, thickness_m, altitude_m, material)`
- `PlanetarySurfaceDescriptor(terrain?, atmosphere?, ocean?, clouds?, axial_tilt_rad, rotation_period_s?, prime_meridian_rad)` and `PlanetaryRenderDescriptor(base: RenderObject, radius_m, surface, axial_tilt_rad, receives_shadow)` – `enrich_base()` copies terrain/atmosphere/ocean dicts into `RenderObject.metadata` and `.*_params` for Graphics/VFX, plus `from_celestial(celestial, world_pos, radius_m?, render_origin?, terrain?, atmosphere?, ocean?, clouds?)`.

---

## 10. Large-Scale (`astra.rendering.performance` + `pipeline`)

- `PerformanceBudget(max_visible_objects, max_total_objects, max_memory_mb, max_draw_calls, estimated_kb_per_object, target_frame_time_ms)` and `PerformanceManager`:
  - `prioritize(state)` sorts by `-importance, distance, kind, id` deterministically.
  - `apply_budget(state, degrade_lod=True) -> (new_state, report)` :
    1. Cap total by removing lowest importance beyond `max_total`.
    2. Degrade `max_visible`-excess renderables from least important: `HIGH->IMPOSTOR->CULLED`, recalc.
    3. Enforce memory by culling lowest importance until `estimated_memory = count*kb/1024 ≤ max_memory_mb`.
  - `build_batches(state)` groups `iterate_renderable()` by `(kind, material.id, lod)` into `BatchGroup(instanced, object_ids sorted, estimated_draw_calls=1)`.
  - `is_within_budget` and `estimated_memory_mb` for graceful degradation checks.
- Pipeline `apply_visibility -> apply_performance_budget -> build_batches` ensures bounded allocations on modest hardware (16 GB, integrated Radeon, limited VRAM).

---

## 11. Lighting / Shadow (`astra.rendering.lighting`)

Renderer-independent:

- `LightType: DIRECTIONAL | POINT | AMBIENT`
- `LightSource(id, type, position?, direction?, intensity 0.., color HDR, range_m?, casts_shadow, source_ref?)` – validates per type (directional needs direction unit-normalized, point needs position).
- `ShadowConfig(enabled, resolution 512/1024/2048/4096/8192, bias, max_distance_m, cascade_count 1..8, softness)` – data only.
- `EclipseParams(light_id, occluder_id, receiver_id, umbra/penumbra 0..1, angular radii)` – for planetary eclipses.
- `LightingState(lights, shadow, ambient_intensity/color, eclipses, exposure)` – `add/remove/get_star_lights/to_dict/from_star(star_position, star_id, intensity, color)/clone`.

---

## 12. Spacetime / Black-Hole / Wormhole / Warp (`astra.rendering.spacetime`)

Data containers consuming authoritative outputs (no physics duplication, no VFX):

- `BlackHoleRenderParams(object_id, mass_kg, spin_param -1..1, schwarzschild_radius_m, photon_sphere? , isco?, horizon_outer/inner?, ergosphere_equatorial?, lensing_strength, redshift_hint, accretion_disk_hint?)` – `black_hole_state_to_render_params(bh_state: BlackHoleState, object_id)` delegates to `astra.blackhole.api.get_*_boundaries` (single implementation), then `to_render_object(world_position, render_origin?) -> RenderObject(kind=BLACK_HOLE, radius=photonSphere or 1.5*rs)`.
- `SpacetimeCurvatureVisual` – placeholder for `kretschmann_scalar`/`tidal`.
- `WormholeRenderParams(object_id, throat_radius_m, shape_hint, classification, lensing_strength, throat_position, mouth_radius_m?, embedding_hint?)` – `wormhole_metric_to_render_params(metric: MorrisThorne|EinsteinRosen, object_id)` reads `throat_radius_m` or `2GM/c²`, maps classification via `ScientificClassification.value`, `to_render_object(render_origin?)`.
- `WarpRenderParams(object_id, bubble_radius_m, wall_steepness, velocity_m_s, shift_vector, distortion_strength, classification)` – `warp_metric_to_render_params(metric: AlcubierreMetric, object_id)` extracts `velocity, radius_m, wall_steepness`, `to_render_object(center, render_origin?)`.

---

## 13. Destruction Integration (`astra.rendering.destruction`)

Physics lives in `astra.destruction`; rendering only visualizes outputs:

- `FragmentVisual, EjectaVisual, DebrisVisual` – each `to_render_object(render_origin?) -> RenderObject` (FRAGMENT/EJECTA/DEBRIS, small heuristic radii).
- `DestructionVisualState(object_id, damage_state: DamageVisualState(INTACT|DAMAGED|FRACTURED|FRAGMENTED|DESTROYED), fragments, ejecta, debris, impact_id?, original_visible)` – `FRAGMENTED|DESTROYED => original_visible=False`.
- `destruction_result_to_visual(impact_result: ImpactResult) -> DestructionVisualState` – maps `target_state_after -> DamageVisualState`, extracts `fragments/ejecta/debris` lists without recomputing.
- `apply_destruction_visual_to_object(render_obj, visual_state) -> RenderObject` – clones, sets `damage_state`, `fragment_ids/ejecta_ids`, hides original if `FRAGMENTED|DESTROYED`, preserves authoritative state.

---

## 14. Temporal / Observation (`astra.rendering.temporal`)

Distinguishes:

- `CURRENT` – authoritative `simulation_time_s` positions
- `OBSERVED` / `HISTORICAL` – light-delay corrected emission positions

- `ObservedRenderRecord(object_id, observation_time_s, emission_time_s, lookback_time_s, emission_position, actual_position, observer_position, observer_id)` – `is_delayed/light_travel_distance/to_dict`.
- `compute_lookback(observer, emission, observation_time_s, emission_time_s?) -> travel = |observer-emission|/c`.
- `observed_state_to_render_record(observed_state: ObservedState, object_id, observer_position) -> record` – extracts `SpacetimeEvent x,y,z`.
- `apply_observed_state_to_render_object(render_obj, record, render_origin?) -> RenderObject` at emission position, `temporal_mode=OBSERVED`.
- `apply_temporal_mode_to_render_state(state, mode, observer_position?, observed_records?) -> RenderState` – clones, sets `temporal_mode`; for `OBSERVED|HISTORICAL` without records it approximates `emission_time = t_obs - |observer-world|/c` and marks `approx_lookback_s`; with `observed_records` (authoritative `ObservedState`s) it replaces positions with emission positions.

Honesty: if geometry requires history beyond recorded `Worldline`, `astra.temporal.observation.observe` raises `TemporalHistoryUnavailableError`; this layer never fabricates history.

---

## 15. Pipeline (`astra.rendering.pipeline`)

`RenderPipeline(config: PipelineConfig(lod_config, culling_config, performance_budget, default_quality, enable_floating_origin, render_origin, populate_camera_relative))`

- `object_from_world_entry(...)` – helper to create `RenderObject` from generic dict (validates, converts via `render_origin`).
- `build_render_state(tick, simulation_time_s, world_objects: List[Dict{id, world_position: Vector3, kind?, category?, orientation?, scale?, bounding_radius_m?, importance?, material?, visible?, enabled?, tags?, source_ref?, metadata?, damage_state?, lod?}], render_origin?) -> RenderState` – deterministic, does not mutate `world_objects`.
- `apply_camera_and_lod(state, camera, quality?) -> RenderState` – fills `camera_relative_position/distance/apparent_size` (`apparent = 2*asin(min(1,r/d))`) and selects LOD via `LODSelector`.
- `apply_visibility(state, camera, frustum?) -> (state, culled)` – world-space frustum test (`world = render+origin`), sets `visibility`.
- `apply_performance_budget(state) -> (state, report)` delegates to `PerformanceManager`.
- `build_frame(tick, simulation_time_s, world_objects, camera, quality?, lighting?, render_origin?, temporal_mode?, observed_records?) -> RenderFrame(render_state, context: RenderContext, lighting?, batches, visibility_culled, performance_report, temporal_mode)` – full path; clones inputs.
- `build_frame_from_adapters(tick, simulation_time_s, camera, adapters: [()->List[Dict]], ...)` – decoupled integration for World/SceneGraph/Celestial adapters.
- Helpers: `scene_graph_adapter(scene_graph, include_disabled?)` and `celestial_adapter(celestial_objects, world_positions)` produce adapter callables without mutating sources.

Determinism: all pure functions, no wall-clock, no global RNG; visual randomness uses explicit `visual_seed = tick`.

Failure isolation: rendering exceptions do not touch ledger; `world_objects` authoritative data unchanged.

---

## 16. Performance

Designed for 16 GB RAM / integrated Radeon / limited VRAM:

- Bounded `RenderState.max_objects`, `PerformanceBudget` hard caps, graceful degrade `HIGH->IMPOSTOR->CULLED`.
- Batching/instancing via `BatchGroup`, culling (frustum/distance/category), LOD, lazy `MaterialRef` handles (not heavy textures), cached `RenderState.clone` (copy-on-write), minimal allocations, `estimated_memory_mb` tracking and memory capping.

---

## 17. Future Extension Points

- **Graphics/VFX phase (MiMo)** consumes `RenderState`/`CelestialRenderDescriptor`/`PlanetarySurfaceDescriptor`/`LightingState`/`BlackHoleRenderParams`/`WormholeRenderParams`/`WarpRenderParams` and replaces `MaterialRef.placeholder` with shader/texture/particle systems. No shader code lives here.

- **Blender bridge (last phase)** consumes:

```
ASTRA SIMULATION → RENDER STATE → RENDERING ARCHITECTURE → GRAPHICS/VFX → BLENDER BRIDGE → BLENDER → MCP-BLENDER
```

`RenderState.to_dict()`/`RenderContext.to_dict()`/`PlanetaryRenderDescriptor.to_dict()` etc. provide stable JSON for the bridge; no `bpy` import or MCP-Blender dependency is present now (`tests/test_rendering.py::test_no_blender_import` verifies).

---

## 18. Testing

`tests/test_rendering.py` (73 tests, all passing) covers per spec §26:

- RenderState construction/validation/isolation/conversion
- Camera position/orientation/tracking/projection/extreme scales (1e-9 m to 1e22 m)
- Coordinates world→render, camera-relative, floating-origin, 1e14 m precision, invalid NaN/Inf
- LOD deterministic, boundaries, apparent-size override, quality bias, invalid inputs
- Visibility frustum/distance/category/enable-disable and simulation-not-removed
- Celestial star/planet/black-hole/galaxy/nebula mapping and no-database-duplication
- Planetary terrain/atmosphere/ocean/cloud aggregation and enrichment
- Destruction damage states, fragments/ejecta/debris exposure and original hide
- Temporal CURRENT vs OBSERVED, `ObservedState` conversion, `compute_lookback = dist/c`, isolation
- Relativity/black-hole (Schwarzschild/Kerr) and spacetime wormhole/warp conversion
- Lighting directional star, point, shadows
- Performance budget total/visible/memory caps, batching, graceful degradation
- Pipeline authority isolation (authoritative `world_objects` never mutated), determinism, large-scale 200 asteroids → bounded 100, temporal pipeline
- Robustness missing optional, extreme coordinates, invalid values, modest-hardware degradation
- No Blender import, `RenderContext` clone isolation, viewport aspect, future bridge dict round-trip

All rendering tests pass without Blender (`python -m pytest tests/test_rendering.py`).

Regression samples: authority/entities/celestial_properties/motion_state (67 tests) and destruction/schwarzschild/spacetime-metrics/wormhole (101 tests) still pass.

---

## 19. Limitations

- Provides parameter containers and culling/LOD/batching data, not final pixel output, shaders, textures, particles, post-processing, or cinematic VFX (by spec §3).
- No backend services, persistence, or orchestration (by spec §3, GLM phase).
- No `bpy`/MCP-Blender runtime dependency; bridge must map `MaterialRef` placeholders and `to_dict` streams later.
- Geodesic / metric curved null propagation not used for observation; `temporal` uses flat-spacetime `dist/c` approximation explicitly.
