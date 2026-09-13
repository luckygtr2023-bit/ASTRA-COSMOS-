# ASTRA CORE

Foundational runtime layer for the ASTRA simulation engine.

## Overview

ASTRA CORE provides the infrastructure required by future specialist systems:

- Mathematics
- Physics
- Motion
- Spacetime
- Astronomy
- Celestial systems
- Cosmology
- Observation
- Rendering
- Graphics
- UI
- Backend/integration

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

See `CORE_CONTRACT.md` for the detailed API contract.
See `ASTRA_CORE.txt` for the architectural specification.

## License

MIT
