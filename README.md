# ASTRA COSMOS

Universe-scale simulation engine.

## Overview

ASTRA provides infrastructure for:

- Mathematics
- Physics
- Motion
- Orbital Mechanics  ✓
- N-Body  ✓
- Spacecraft Physics  ✓
- Relativity  ✓
- Black-Hole Physics  ✓
- Spacetime Physics  ✓
- Temporal / Causality  ✓
- Celestial Objects  ✓
- Astronomical Data Ingestion  ✓
- World / Scene  ✓
- Destruction & Impact  ✓
- **Rendering Architecture  ✓**
- **Backend & Runtime Integration  ✓ (this phase)**
- Graphics / VFX (future)
- Blender Bridge (future)

## Installation

```bash
pip install -e .
```

## Usage

```python
from astra.core.engine import Engine
from astra.core.config import Config

config = Config()
engine = Engine(config)
engine.initialize()
engine.start()
engine.step()
engine.stop()
```

## Documentation

- `CORE_CONTRACT.md` – Core API contract
- `ASTRA_CORE.txt` – Core architectural specification
- `RENDERING_ARCHITECTURE.md` – Rendering architecture (authority boundary, RenderState/Context, Camera, Floating Origin, LOD, Culling, Celestial/Planetary, Destruction, Spacetime, Temporal, Performance, Pipeline, future Blender/Graphics extension points)
- `BACKEND_ARCHITECTURE.md` – Backend & runtime integration (config, persistence, services, cache, render/graphics delivery, data access, security, diagnostics, lifecycle, error boundaries; 76 tests; design for future Graphics→Blender→MCP bridge via `to_dict` without `bpy`)

## License

MIT
