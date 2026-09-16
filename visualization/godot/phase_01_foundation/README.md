# Phase 01 — Rendering Foundation (DONE)

- `project.godot` (Forward+)
- `scripts/astra_bridge.gd` (polls ASTRA bridge_state.json, 30Hz)
- `scripts/coordinate_bridge.gd` (floating-origin)
- `scripts/object_registry.gd` (MultiMeshInstance3D per kind)
- `scripts/camera_system.gd` (orbital/free/cinematic/replay)
- `scripts/quality_presets.gd` (5 presets, hardware detection)
- `scripts/telemetry.gd` (fps, draw calls)
- `scripts/shader_manager.gd` (classification-aware)
- `environments/default_env.tres` (volumetric fog, glow)
- `scenes/main.tscn` (WorldEnvironment + DirectionalLight + Registry)
- `docs/VALIDATION.md` — open in Godot 4.4.1, no shader errors, 60 fps empty scene
