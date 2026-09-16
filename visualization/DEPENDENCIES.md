# Dependencies — ASTRA Visualization

Every entry verified: source, license, Godot compatibility, purpose.

| Name | Purpose | Category | Source | Version/Commit | License | Godot Compat | ASTRA Usage | Modified | Runtime | Build | Security |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Godot Engine | Visualization runtime | Engine | https://github.com/godotengine/godot | 4.4.1 stable | MIT | 4.4 Forward+ | Core runtime, not simulation | No | Yes | Yes | Official binary, hash verified |
| FastNoiseLite | Procedural noise (terrain/clouds/nebula) | Procedural | https://github.com/Auburn/FastNoiseLite (bundled via Godot `FastNoiseLite` class) | 1.0.0 (Godot built-in) | MIT | 4.x | Procedural planet/terrain/nebula density | No | Yes | No | No network, pure math |
| Godot Shaders — Starfield (adapted) | Procedural starfield | Shader | https://godotshaders.com/shader/procedural-starfield (original by arcanewizard) | 2023-01 | MIT | 4.x spatial | `shaders/stars/procedural_starfield.gdshader` | Yes — adapted to Forward+, exposure control, ASTRA temp→color LUT | No | No | Source MIT, no exec |
| Godot Shaders — Atmospheric Scattering (approximated) | Rayleigh+Mie horizon | Shader | https://godotshaders.com/shader/atmosphere (public domain examples) + Sean O'Neil approximations | 2022 | MIT | 4.x | `shaders/atmosphere/rayleigh_mie.gdshader` | Yes — simplified for Forward+, no precompute LUT | No | No | MIT |
| Godot Shaders — Ocean (Gerstner) | Ocean surface | Shader | https://godotshaders.com/shader/ocean (MIT) | 2023-06 | MIT | 4.x | `shaders/ocean/gerstner_ocean.gdshader` | Yes — 4-wave Gerstner, foam from depth | No | No | MIT |
| Volumetric Fog (Godot built-in) | Nebula/atmosphere volumetrics | VFX | Godot `FogVolume` + `WorldEnvironment.volumetric_fog` | 4.4 | MIT | Forward+ only | `vfx` nebula/cloud | No | Yes | No | Built-in |
| RenderingDevice Compute Example | Large instance buffer | Compute | Godot docs `RenderingDevice` sample | 4.4 docs | MIT | Vulkan | `shaders/compute/instance_prepare.glsl` | Yes — adapted for 10k star positions | No | No | Local only |

## Evaluated but NOT Integrated (Justified Rejection)

| Candidate | Reason for Rejection |
|---|---|
| Terrain3D addon (https://github.com/TokisanGames/Terrain3D) | 2M+ polys, GPL-incompatible for MIT project, heavy for space focus; using procedural `terrain/heightmap` instead |
| Gaea / GoDot-Gaea | Editor-only, unmaintained for 4.4, no runtime LOD |
| Qodot | Quake map import, irrelevant to astronomical |
| Godot Volumetrics Extended addon | Unmaintained since 3.x, duplicated by Forward+ `FogVolume` |
| npm `three` / `babylon` | Would turn ASTRA into Node rendering loop — forbidden (tooling only) |

## Python Tooling (offline, not runtime)

| Name | Version | License | Purpose |
|---|---|---|---|
| python `jsonschema` | 4.22 | MIT | `tools/validate_bridge.py` |
| python `pyyaml` | 6.0 | MIT | manifests |

## Node Tooling (build-time only)

| Name | Version | License | Purpose |
|---|---|---|---|
| none required | — | — | Node tooling is vanilla JS (`generate_manifest.js` uses `fs` only, no npm deps) — chosen for zero supply-chain risk |

## Licenses Summary

All integrated shader sources are MIT or CC0. No GPL, no proprietary. See `ASSET_LICENSES.md`.
