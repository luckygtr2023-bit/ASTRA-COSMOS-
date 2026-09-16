# Quality Presets

Presets are runtime-tunable via `QualityPresets` autoload (`quality_presets.gd`).

## Preset Matrix

| Feature | LOW | MEDIUM | HIGH | ULTRA | CINEMATIC |
|---|---|---|---|---|---|
| Shadows | Off | 1024 | 2048 | 4096 | 8192 (PSSM) |
| Volumetrics (fog) | Off | Off | On (64) | On (128) | On (192) |
| Particles (GPUParticles amount) | 32 | 128 | 256 | 512 | 1024 |
| Bloom | Off | On (0.2) | On (0.35) | On (0.6) | On (0.8) + lens flare |
| Resolution scale | 0.75 | 1.0 | 1.0 | 1.0 | 1.25 (SS) |
| Atmosphere | 2D horizon | 2D | FogVolume | FogVolume + Mie | FogVolume + Mie + clouds |
| Cloud quality | Off | 2D | 2.5D | Volumetric | Volumetric |
| Star count (density) | 0.35 | 0.55 | 0.7 | 0.85 | 0.95 |
| Nebula density | 0.3 | 0.5 | 0.8 | 1.0 | 1.2 |
| Lensing quality | Off | Off | CanvasItem (1 tap) | CanvasItem (3 taps) | Compute |
| Postprocess | None | Tonemap | Tonemap+Bloom | +DoF | +MotionBlur |
| LOD bias | 2.0 | 1.2 | 1.0 | 0.6 | 0.4 |
| GPU instancing | On (no compute) | On | On+compute | On+compute | On+compute |

## Hardware Detection

- `RenderingServer.get_video_adapter_name()` + `OS.get_memory_info()`
- Intel / <3GB VRAM → LOW
- RTX 40 / RX 7000 / >8GB → ULTRA
- Manual override via `ProjectSettings` or `--quality cinematic` launch flag

## Modest Hardware Promise

ASTRA runs on Intel UHD at LOW (no volumetrics, 0.75x scale, 32 particles) at 30 fps for 2k stars. Tested via `phase_05_optimization/scenes/stress_low.tscn`.

## Cinematic

`CINEMATIC` is not for gameplay but for `phase_04_vfx_cinematics`: 24 fps lock, motion blur, DoF, 1.25x supersampling. Use `--quality cinematic` + `quality_presets.gd: apply(Preset.CINEMATIC)`.
