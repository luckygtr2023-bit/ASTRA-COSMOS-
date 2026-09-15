"""ASTRA Procedural Universe Generation & Evolution.

Non-authoritative data provider that hands deterministic, versioned,
provenance-tagged initial conditions to the authoritative ASTRA systems
(motion, physics, celestial, world, simulation time).

No rendering, no AI planning, no physics integration here — only
configuration generation. The `RegionManager` is lazy/streaming and
never overwrites REAL_DATA.

Exports for external use:
  DataProvenance, GenerationVersion, ProvenanceTag
  SeedManager
  DeterministicGenerator, StellarGenerator, PlanetarySystemGenerator
  RegionManager
  StellarEvolutionEngine
"""

from __future__ import annotations

from .provenance import DataProvenance, GenerationVersion, ProvenanceTag
from .seed_manager import SeedManager
from .generators.base import DeterministicGenerator
from .generators.stellar import StellarGenerator
from .generators.planetary import PlanetarySystemGenerator
from .region_manager import RegionManager
from .evolution.stellar_evolution import StellarEvolutionEngine

__all__ = [
    "DataProvenance",
    "GenerationVersion",
    "ProvenanceTag",
    "SeedManager",
    "DeterministicGenerator",
    "StellarGenerator",
    "PlanetarySystemGenerator",
    "RegionManager",
    "StellarEvolutionEngine",
]

__version__ = "1.0.0"
