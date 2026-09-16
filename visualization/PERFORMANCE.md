# Performance — ASTRA Visualization

Target: 60 fps @ 1080p on RTX 3060 (HIGH), 30 fps on Intel UHD (LOW).

## Budgets

| System | Budget (ms) | Technique |
|---|---|---|
| Stars (10k instanced) | 0.6 | MultiMeshInstance3D + compute buffer (GDExtension) or FastNoise CPU fallback |
| Planets/terrain (4) | 1.2 | LOD0 64k tris, LOD1 16k, triplanar shader |
| Atmosphere | 0.4 | 2D horizon shader (LOW) vs FogVolume (HIGH) — toggled by QualityPresets |
| Nebula/galaxy | 0.8 | Billboard + FogVolume, 512 noise |
| Black hole + lensing | 1.0 | Fullscreen canvas_item lensing (HIGH only), accretion disk mesh |
| VFX (100 particles) | 0.5 | GPUParticles3D GPU, amount scaled by preset |
| Postprocess | 0.7 | Tonemap + bloom (bloom mip count scaled) |
| **Total** | **~5.2ms** | Leaves 11ms for simulation bridge |

## Optimizations Implemented

- **Instancing:** `ObjectRegistry` uses `MultiMeshInstance3D` per kind (one draw call per bucket). 10k asteroids = 1 draw call, not 10k.
- **LOD:** `HLOD` for galaxy clusters + distance-based `instance_custom_data` lod in shader; `terrain` uses 3 LOD meshes.
- **Culling:** Godot frustum + occlusion culling; `SpatialIndex` from `astra.world` drives `visible_instance_count`.
- **Streaming:** `ResourceLoader.load_threaded_request` for nebula textures (512x512, not 4k) + `assets/manifest.json`.
- **Shader variants:** `#ifdef QUALITY_LOW` strips volumetric branches (preprocessor via `generate_shader_variants.py`).
- **Compute:** `instance_prepare.glsl` on Vulkan (256 threads); CPU fallback for Compatibility.
- **Memory:** Instance buffers are `PackedVector3Array` (12 bytes/obj); 10k → 120KB.

## Telemetry

`Telemetry.gd` logs every 60 frames: fps, avg60, object count, draw calls (`RenderingServer.get_rendering_info`).

Run:
```bash
python visualization/tools/validate_shaders.py # shader parse, <0.1s
python visualization/tools/validate_assets.py  # 2MB cap
```

Measured on CI (no GPU): shader validation 0.08s, asset validation 0.02s, 10k `TargetRegistry.nearby` 0.04s, 10k history 0.14s.
