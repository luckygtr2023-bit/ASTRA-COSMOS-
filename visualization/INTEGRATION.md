# Integration — ASTRA Scientific ↔ Godot

## Flow

```
AstraBridge.gd --(request)--> astra.interaction.InteractionEngine.dispatch()
                         <--(validated RenderState)--- astra.core.Engine + astra.world + astra.scientific
AstraBridge.gd <-- render_state_updated(state)
ObjectRegistry.gd, CameraSystem.gd, ShaderManager.gd consume state
```

## Bridge Formats

**Astra → Godot (`bridge_state.json` or HTTP):**
```json
{
  "tick": 42,
  "simulation_time_s": 1234.5,
  "frame_id": "world",
  "origin_offset": [0,0,0],
  "objects": [
    {"id": "star-1", "kind": "STAR", "position": [1e6,0,0], "frame": "world",
     "classification": "REAL_DATA", "temperature_k": 5778, "lod": 0},
    {"id": "bh-1", "kind": "BLACK_HOLE", "position": [2e9,0,0], "mass_kg": 1e31}
  ],
  "camera": {"mode": "orbital", "target": "planet-1"}
}
```

**Godot → Astra (`request_interaction`):**
```json
{"type": "NAVIGATE", "target_id": "galaxy-1", "to_scale": "GALAXY"}
→ astra.interaction.InteractionAction → validated → (if travel) astra.travel → updated state → Godot
```

## No Bypass Rule

Godot never writes `position`, `velocity`, or `sim_time`. If visualization needs `approach`, it sends `APPROACH` → Astra `NavigationService` → `OriginRebaser` → Godot rebases. `validate_bridge.py` rejects non-finite positions or unknown classifications.

## Coordinate Bridge

`CoordinateBridge.gd` holds `origin_offset`. All `Node3D` positions are `world - origin`. ASTRA rebase is tweened, not teleported.

## Classification Visual Honesty

`ShaderManager` maps `classification` to shader variant: `SPECULATIVE` wormholes use `wormhole/throat.gdshader` with chromatic aberration and `SPECULATIVE` watermark (subtle), not hidden. `Telemetry` logs classification distribution.

## Testing Integration

- `tests/test_interaction.py` exercises `InteractionEngine` → `AstraBridge` echo path.
- `visualization/tools/validate_bridge.py` validates `bridge_state.json`.
- `visualization/godot/phase_01_foundation/tests/` (future) will headless-load `project.godot` in Godot 4.4 CI.
