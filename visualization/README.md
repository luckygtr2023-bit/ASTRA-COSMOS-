# ASTRA COSMOS — Visualization Ecosystem

> Scientific simulation is authority. Visualization is the lens.

```
ASTRA Scientific Engine (Python)
        ↓ JSON bridge (state deltas)
ASTRA Visualization API (Godot autoload)
        ↓
Godot 4.4 Forward+ (Vulkan)
        ↓
RenderingDevice / Compositor
        ↓
GPU
```

## Directory Map

- `godot/` — Godot project (Forward+), phase scenes and scripts
- `shaders/` — 19 curated shader categories (`.gdshader`, `.glsl`)
- `vfx/` — event-driven VFX (explosions, impacts, plasma, wormholes)
- `materials/` — `.tres` material library
- `procedural/` — CPU/GPU procedural systems (noise, terrain)
- `assets/` — CC0 procedural textures, LUTs, noise, HDRs
- `addons/` — third-party addons (curated, not bulk)
- `extensions/` — C++ GDExtension skeleton
- `scripts/` — GDScript, C++, JavaScript/Node, utilities
- `tools/` — Python validation, performance, shader catalog generators
- `third_party/` — licenses and source attestations
- `docs/` — per-phase deep dives

## Quick Start

```bash
# 1. Open Godot 4.4.1
godot --path visualization/godot --renderer forward_plus

# 2. Run Python validation (no Godot required)
python visualization/tools/validate_shaders.py
python visualization/tools/validate_assets.py

# 3. Generate catalogs
python visualization/tools/generate_shader_catalog.py
node visualization/scripts/node/generate_manifest.js

# 4. Run tests (ASTRA simulation still authoritative)
pytest tests/test_interaction.py -q
```

## Principles

- **Authority:** Godot never writes `sim_time`, `physics`, or `coordinates` directly. `AstraBridge.gd` → `VisualizationAPI` → `astra.*` Python validation.
- **No second physics:** All `thermal`/`orbital`/`nbody` stays in `astra.*`; Godot only consumes `RenderState`.
- **Phase gates:** Each `phase_0*` has `README.md` + `VALIDATION.md` — do not advance if broken.

## Quality Presets

`QUALITY_LOW | MEDIUM | HIGH | ULTRA | CINEMATIC` — controls shadows, volumetrics, particle counts, bloom, star count, lensing quality, LOD, GPU effects. Hardware detection in `quality_presets.gd` (VRAM, GPU family).

## Performance

Target: 60 fps at 1080p on RTX 3060 at QUALITY_HIGH for 10k instanced objects via `MultiMeshInstance3D` + LOD + frustum. See `PERFORMANCE.md`.
