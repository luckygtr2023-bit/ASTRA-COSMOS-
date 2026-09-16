# Phases — Implementation Order

## Phase 01 — Foundation (done)
- project.godot, Forward+, Visualization API, coordinate bridge, object registry, camera, quality presets, telemetry, shader infra

## Phase 02 — Astronomical Rendering (done, see shaders/celestial, terrain, ocean, stars, nebula, galaxy)
- GPU instancing, LOD, procedural starfield, planet heightmap, Gerstner ocean, spiral galaxy

## Phase 03 — Extreme Physics (done, see accretion, lensing, spacetime, wormhole)
- Accretion disk, lensing (screen-space), grid curvature, wormhole throat — all consume ASTRA classification

## Phase 04 — VFX + Cinematics (done, see vfx/, camera_system.gd cinematic mode)
- Explosions, impacts, debris, plasma, solar flare, radiation, spacetime VFX, bloom

## Phase 05 — Optimization (done, see PERFORMANCE.md, quality presets, MultiMesh, compute)
- HLOD, frustum, streaming, async loading, shader stripping, floating-origin sync
