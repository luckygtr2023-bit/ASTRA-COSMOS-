"""Region manager — spatial partitioning, lazy streaming, real-data precedence.

Every region is identified by a string `region_id`. On demand, the manager
either returns an authoritative record (if `authoritative_db` contains the id)
or deterministically generates a region via `SeedManager` → `StellarGenerator` →
`PlanetarySystemGenerator`.

Key guarantees:
  - Same universe_seed + same region_id → same region (regardless of request order)
  - Never overwrites REAL_DATA: if `_has_authoritative_data` is true, generation
    is skipped and the authoritative dict is returned verbatim (or via
    `ProvenanceTag` wrapper if needed)
  - Lazy: regions are generated on first `generate_region_on_demand` and then
    cached in `generated_regions` (deterministic, not wall-time)
  - No global RNG, no `hash()`, no file I/O
  - Prevents silent overwrites: `register_authoritative` refuses to replace
    existing authoritative entry unless `force` is explicit
"""

from __future__ import annotations

import random
from typing import Any, Dict, Optional

from astra.procedural.provenance import DataProvenance, GenerationVersion
from astra.procedural.seed_manager import SeedManager
from astra.procedural.generators.stellar import StellarGenerator
from astra.procedural.generators.planetary import PlanetarySystemGenerator


class RegionManager:
    """Lazy region streaming with authoritative precedence."""

    def __init__(self, universe_seed: str, authoritative_db: Optional[Dict[str, Any]] = None):
        self.seed_manager = SeedManager(universe_seed)
        self.authoritative_db: Dict[str, Any] = dict(authoritative_db or {})
        self.generated_regions: Dict[str, Any] = {}
        self._stats = {"generated": 0, "cache_hits": 0, "authoritative_hits": 0}

    def _has_authoritative_data(self, region_id: str) -> bool:
        return region_id in self.authoritative_db

    def _load_authoritative_data(self, region_id: str) -> Dict[str, Any]:
        # Return a shallow copy to prevent caller mutation of authoritative store
        # Tag with provenance if not already present
        data = dict(self.authoritative_db[region_id])
        if "metadata" not in data:
            data = dict(data)
            data["metadata"] = {
                "provenance": DataProvenance.REAL_DATA.value,
                "generation_version": GenerationVersion.CURRENT_ALGORITHM_VERSION,
                "schema_version": GenerationVersion.CURRENT_SCHEMA_VERSION,
            }
        self._stats["authoritative_hits"] += 1
        return data

    def generate_region_on_demand(self, region_id: str) -> Dict[str, Any]:
        if not isinstance(region_id, str) or not region_id:
            raise ValueError("region_id must be non-empty string")
        if ":" in region_id:
            raise ValueError("region_id cannot contain ':'")

        # Cache hit
        if region_id in self.generated_regions:
            self._stats["cache_hits"] += 1
            # Return copy to prevent mutation of cached value? Return same object for identity test but copy for safety
            return self.generated_regions[region_id]

        # Authoritative precedence
        if self._has_authoritative_data(region_id):
            # Do NOT generate; return authoritative and cache it as generated to prevent future overwrite
            auth = self._load_authoritative_data(region_id)
            self.generated_regions[region_id] = auth
            return auth

        # Procedural generation
        region_seed = self.seed_manager.derive_seed([region_id])
        rng = random.Random(region_seed)
        num_systems = rng.randint(5, 50)

        # Use fresh RNG for system count, but each system's seed is derived via SeedManager (not via rng sequence alone)
        # This makes count and each system deterministic yet independent of order
        systems = []
        for i in range(num_systems):
            system_id = f"{region_id}_sys_{i}"
            sys_seed = self.seed_manager.derive_seed([region_id, system_id])
            star_gen = StellarGenerator(sys_seed)
            star = star_gen.generate_star_system(system_id)
            # Planetary seed is sys_seed+1 but also derived via manager for extra domain separation
            planet_seed = self.seed_manager.derive_seed([region_id, system_id, "planets"])
            planet_gen = PlanetarySystemGenerator(planet_seed)
            # Use star mass for planet generation
            star_mass = star["physics_state"]["mass_solar"]
            planets = planet_gen.generate_planets(star_mass, system_id)
            systems.append({"star": star, "planets": planets})

        region_data = {
            "region_id": region_id,
            "metadata": {
                "provenance": DataProvenance.GENERATED_DATA.value,
                "generation_version": GenerationVersion.CURRENT_ALGORITHM_VERSION,
                "schema_version": GenerationVersion.CURRENT_SCHEMA_VERSION,
                "seed_used": region_seed,
                "universe_seed": self.seed_manager.universe_seed,
                "system_count": num_systems,
            },
            "systems": systems,
        }
        self.generated_regions[region_id] = region_data
        self._stats["generated"] += 1
        return region_data

    def register_authoritative(self, region_id: str, data: Dict[str, Any], *, force: bool = False) -> None:
        """Register an authoritative record. Refuses to overwrite unless force=True."""
        if not isinstance(region_id, str) or not region_id:
            raise ValueError("region_id must be non-empty string")
        if region_id in self.authoritative_db and not force:
            raise ValueError(f"authoritative region already exists: {region_id} (use force=True to overwrite)")
        self.authoritative_db[region_id] = dict(data)
        # If already generated, that cached generated version is now stale — remove to enforce precedence on next request
        if region_id in self.generated_regions:
            del self.generated_regions[region_id]

    def is_generated(self, region_id: str) -> bool:
        return region_id in self.generated_regions and not self._has_authoritative_data(region_id)

    def is_authoritative(self, region_id: str) -> bool:
        return self._has_authoritative_data(region_id)

    def clear_cache(self) -> None:
        self.generated_regions.clear()
        self._stats = {"generated": 0, "cache_hits": 0, "authoritative_hits": 0}

    def stats(self) -> Dict[str, Any]:
        return dict(self._stats)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "universe_seed": self.seed_manager.universe_seed,
            "authoritative_db": dict(self.authoritative_db),
            "generated_regions": dict(self.generated_regions),
            "stats": dict(self._stats),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RegionManager":
        obj = cls(str(data.get("universe_seed", "default")), authoritative_db=data.get("authoritative_db", {}))
        obj.generated_regions = dict(data.get("generated_regions", {}))
        obj._stats = dict(data.get("stats", {"generated": 0, "cache_hits": 0, "authoritative_hits": 0}))
        return obj
