# Architecture — ASTRA Visualization Ecosystem

## 1. Authority Flow

```
[astra.core.Engine] → tick → [astra.world.Scene + astra.temporal.TemporalClock]
               ↓ snapshot
[astra.interaction.InteractionEngine] → validated actions → [RenderState]
               ↓ JSON (VisualBridge)
[VisualizationAPI (GDScript autoload)] → sanitizes, queues deltas
               ↓
[ObjectRegistry.gd] → instancing / LOD
[CameraSystem.gd] → orbital / cinematic / scientific / free
[ShaderManager.gd] → binds per-object uniforms (no state mutation)
```

Godot → API → ASTRA → Godot. No direct `set_position_directly()`.

## 2. Coordinate Bridge

- ASTRA: `FrameRegistry` + `OriginRebaser` + `WorldHierarchy` (hierarchical, floating-origin).
- Godot: `CoordinateBridge.gd` holds `origin_offset: Vector3` and `frame_id: String`; all `Node3D.global_transform` are `local = world - origin`. Rebase event from ASTRA triggers `rebase_offset` tween — no teleport.

## 3. Render-State Representation

```gdscript
# RenderState.gd (GDScript dict, not class)
{
  "tick": 42,
  "simulation_time_s": 1234.5,
  "objects": [{"id": "star-1", "kind": "STAR", "position": [x,y,z], "frame": "world",
               "classification": "SIMULATED_DATA", "lod": 0, "material": "star_corona"}],
  "camera": {"mode": "orbital", "target": "planet-1"},
  "quality": "HIGH"
}
```

Consumed by `ObjectRegistry`; never reconstructed in Godot.

## 4. Scene Organization

- `phase_01_foundation/scenes/main.tscn` — root with `WorldEnvironment`, `DirectionalLight3D`, `CameraSystem`, `ObjectRegistry`
- `phase_02_astronomical_rendering/scenes/` — celestial bodies (instanced)
- `phase_03_extreme_physics/scenes/` — black hole quad + accretion disk
- `phase_04_vfx_cinematics/scenes/` — GPUParticles3D pools
- `phase_05_optimization/scenes/` — LOD + streaming tests

## 5. Shader Pipeline

- `.gdshader` (Godot Shader Language) for spatial/canvas_item; `.glsl` for RenderingDevice compute
- `ShaderManager.gd` assigns shader per `classification` — speculative wormholes use distinct `wormhole_throat.gdshader` with `SPECULATIVE` tag, not hidden.
- Compute adapters in `shaders/compute/` prepare large instance buffers (GDExtension where justified).

## 6. VFX & Cinematics

- `vfx/` pools are `GPUParticles3D` with `amount` scaled by quality preset.
- Cinematic cameras are `PhantomCamera`-style (no addon dependency, built-in) with path interpolation.

## 7. Optimization

- Instancing: `MultiMeshInstance3D` for stars/asteroids/debris (one draw call per bucket)
- LOD: `HLOD` + distance-based shader LOD
- Culling: frustum + occlusion (Godot occlusion culling)
- Streaming: `ResourceLoader.load_threaded_request` for large nebula textures
- Shader: variant stripping per quality (LOW disables volumetric branches)

## 8. Security & Supply Chain

- All `third_party/` entries have `DEPENDENCIES.md` provenance, license, and checked `buildscripts/` for network/filesystem access.
- No downloaded scripts are executed without `tools/verify_third_party.py` hash check.
