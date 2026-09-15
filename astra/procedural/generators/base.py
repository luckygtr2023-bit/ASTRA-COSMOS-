"""Base deterministic generator — seed, RNG, metadata, no global state."""

from __future__ import annotations

import random
from typing import Any, Dict

from astra.procedural.provenance import DataProvenance, GenerationVersion, ProvenanceTag


class DeterministicGenerator:
    """Base for all procedural generators.

    - Owns a `random.Random` seeded deterministically (no global `random`)
    - No wall-clock, no `os.urandom`, no `hash()` usage
    - Emits base metadata with provenance, version, seed
    """

    def __init__(self, seed: int):
        if not isinstance(seed, int):
            raise TypeError(f"seed must be int, got {type(seed).__name__}")
        # Clamp to 64-bit unsigned range for portability (random.Random accepts large ints but we keep canonical)
        if seed < 0 or seed > (1 << 64) - 1:
            # Allow larger but hash to 64-bit via modulo for determinism
            seed = seed & ((1 << 64) - 1)
        self.seed = seed
        self.rng = random.Random(seed)
        self.version = GenerationVersion.CURRENT_ALGORITHM_VERSION
        self.schema_version = GenerationVersion.CURRENT_SCHEMA_VERSION

    def get_base_metadata(self, provenance: DataProvenance = DataProvenance.GENERATED_DATA) -> Dict[str, Any]:
        tag = ProvenanceTag(
            provenance=provenance,
            source_label="astra.procedural",
            generation_version=self.version,
            schema_version=self.schema_version,
            seed_used=self.seed,
        )
        return tag.to_dict()

    def _choice(self, seq):
        return self.rng.choice(seq)

    def _uniform(self, a: float, b: float) -> float:
        return self.rng.uniform(a, b)

    def _randint(self, a: int, b: int) -> int:
        return self.rng.randint(a, b)

    def _random(self) -> float:
        return self.rng.random()

    def reset(self) -> None:
        """Reset RNG to initial seed (for replay)."""
        self.rng = random.Random(self.seed)
