"""Deterministic seed management — SHA-256 hierarchical derivation.

Guarantees:
  - Same universe_seed + same hierarchy_path → same int seed (bit-identical)
  - Independent of Python's `hash()`, dict iteration order, wall time, OS, or thread
  - Hierarchy: Universe → Galaxy → Region → System → Object
  - Truncated to 64-bit (fits Python's `random.Random` and `numpy` legacy)

Example path: ["galaxy_milky_way", "region_0_0_0", "system_alpha", "star_primary"]
"""

from __future__ import annotations

import hashlib
from typing import List


class SeedManager:
    """Deterministic hierarchical seed derivation."""

    def __init__(self, universe_seed: str):
        if not isinstance(universe_seed, str) or not universe_seed:
            raise ValueError("universe_seed must be non-empty string")
        # Normalize: strip, no hidden whitespace
        self.universe_seed = universe_seed.strip()
        if not self.universe_seed:
            raise ValueError("universe_seed cannot be whitespace only")

    def derive_seed(self, hierarchy_path: List[str]) -> int:
        """Derive a 64-bit int seed for a given hierarchy path.

        The path is order-sensitive: ["a","b"] != ["b","a"].
        Each element must be a non-empty string without ':' (reserved separator).
        """
        if not isinstance(hierarchy_path, list):
            raise TypeError("hierarchy_path must be list[str]")
        for i, elem in enumerate(hierarchy_path):
            if not isinstance(elem, str) or not elem:
                raise ValueError(f"hierarchy_path[{i}] must be non-empty string, got {elem!r}")
            if ":" in elem:
                raise ValueError(f"hierarchy_path element cannot contain ':', got {elem!r}")
            if len(elem) > 256:
                raise ValueError(f"hierarchy_path element too long (>256): {elem!r}")

        # Canonical combined string: universe_seed + ":" + ":".join(path)
        # If path empty, use just universe_seed (universe-level seed)
        if hierarchy_path:
            combined = f"{self.universe_seed}:" + ":".join(hierarchy_path)
        else:
            combined = self.universe_seed

        # SHA-256 hex, take first 16 hex chars = 64 bits
        hex_digest = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        seed_hex = hex_digest[:16]
        seed_int = int(seed_hex, 16)
        # Ensure non-zero? Zero is valid but we avoid to prevent degenerate rng
        # Keep as is — random.Random(0) is valid
        return seed_int

    def derive_seed_for(self, *path_elements: str) -> int:
        """Convenience: derive_seed(["a","b"]) == derive_seed_for("a","b")."""
        return self.derive_seed(list(path_elements))

    def child_manager(self, sub_path: List[str]) -> "SeedManager":
        """Create a child manager rooted at a sub-path (deterministic)."""
        # The child's universe_seed is the derived seed hex, but we keep string form
        # to preserve hierarchy without exposing int
        derived = self.derive_seed(sub_path)
        # Use hex representation as new universe seed (deterministic, reversible)
        return SeedManager(f"{self.universe_seed}:{':'.join(sub_path)}:{derived:016x}")

    def to_dict(self) -> dict:
        return {"universe_seed": self.universe_seed}

    @classmethod
    def from_dict(cls, data: dict) -> "SeedManager":
        return cls(str(data["universe_seed"]))
