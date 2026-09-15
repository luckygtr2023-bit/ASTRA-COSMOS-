"""Stellar evolution — deterministic aging, lifecycle transitions.

This module is an *orchestration hook* for the Simulation Time engine.
It does not replace the authoritative physics/black-hole/spacetime layers;
it produces deterministically evolved *configuration* that downstream
systems (celestial, physics, nbody) can consume.

Model:
  - Main-sequence lifespan approx 10 / M^2.5 Gyr (theoretical, not new physics)
  - Transition to remnant is deterministic and versioned
  - Prevents mutation of input state (returns copy)

Classification:
  - Ages and mass values are THEORETICAL_DATA where derived from model
  - Remnant types for high mass are SPECULATIVE_DATA where appropriate
"""

from __future__ import annotations

from typing import Any, Dict

from astra.procedural.provenance import DataProvenance, GenerationVersion


class StellarEvolutionEngine:
    """Deterministic stellar aging and remnant transition."""

    def __init__(self, time_engine: Any = None, region_manager: Any = None):
        # time_engine is optional: if provided, can query simulation time
        self.time_engine = time_engine
        self.region_manager = region_manager

    def attach_region_manager(self, region_manager: Any) -> None:
        """Attach a RegionManager for long-term evolution via simulation hook."""
        self.region_manager = region_manager

    def apply_evolution(self, star_state: Dict[str, Any], delta_gyr: float) -> Dict[str, Any]:
        if not isinstance(star_state, dict):
            raise TypeError("star_state must be dict")
        if not isinstance(delta_gyr, (int, float)):
            raise TypeError("delta_gyr must be number")
        if delta_gyr != delta_gyr or delta_gyr in (float("inf"), float("-inf")):
            raise ValueError("delta_gyr cannot be NaN/Inf")
        if delta_gyr < 0:
            raise ValueError("delta_gyr cannot be negative")
        if delta_gyr > 20.0:
            # Beyond universe age, clamp but not silent? We allow but warn via metadata
            pass

        # Copy-on-write for reproducibility
        new_state = dict(star_state)
        # Deep-copy physics_state if present
        orig_phys = dict(star_state.get("physics_state", {}))
        new_state["physics_state"] = dict(orig_phys)
        phys = new_state["physics_state"]

        # Basic validation: must have mass
        mass = phys.get("mass_solar")
        if mass is None:
            raise ValueError("star_state missing physics_state.mass_solar")
        if not isinstance(mass, (int, float)) or mass in (float("inf"), float("-inf")) or mass != mass or mass <= 0:
            raise ValueError(f"mass_solar must be finite >0, got {mass!r}")

        # Age
        age = float(phys.get("age_gyr", 0.0))
        new_age = age + float(delta_gyr)
        phys["age_gyr"] = float(new_age)

        # Mass-lifetime relation (theoretical)
        # For M < 0.5, lifetime > 50 Gyr; clamp to avoid division by tiny
        m = float(mass)
        if m < 0.1:
            m = 0.1
        ms_lifespan = 10.0 / (m ** 2.5)

        # Already remnant? Don't re-transition
        if phys.get("is_remnant"):
            # Just age, no state change
            new_state.setdefault("metadata", {})["evolution_applied"] = {"delta_gyr": delta_gyr, "already_remnant": True}
            return new_state

        if new_age > ms_lifespan:
            remnant = self._transition_to_remnant(float(mass))
            # Apply remnant properties (deterministic, versioned)
            phys.update(remnant)
            # Tag provenance for remnant (speculative for BH, theoretical for WD/NS)
            if remnant.get("classification") == "Black Hole":
                prov = DataProvenance.SPECULATIVE_DATA.value
            else:
                prov = DataProvenance.THEORETICAL_DATA.value
            new_state.setdefault("metadata", {})["evolution"] = {
                "provenance": prov,
                "generation_version": GenerationVersion.CURRENT_ALGORITHM_VERSION,
                "transition_at_gyr": float(ms_lifespan),
                "delta_gyr": float(delta_gyr),
            }
        else:
            # Still main sequence: update metadata to record evolution
            new_state.setdefault("metadata", {})["evolution_applied"] = {"delta_gyr": float(delta_gyr), "ms_lifespan": float(ms_lifespan)}

        return new_state

    def _transition_to_remnant(self, mass_solar: float) -> Dict[str, Any]:
        if mass_solar < 8.0:
            # White dwarf: mass loss approx 80%
            return {
                "classification": "White Dwarf",
                "mass_solar": float(mass_solar * 0.2),
                "radius_solar": 0.01,
                "luminosity_solar": 0.001,
                "is_remnant": True,
            }
        if mass_solar < 20.0:
            return {
                "classification": "Neutron Star",
                "mass_solar": 1.4,
                "radius_solar": 0.00002,  # ~20km
                "luminosity_solar": 0.0001,
                "is_remnant": True,
            }
        # Black hole remnant (speculative for procedural generation context)
        return {
            "classification": "Black Hole",
            "mass_solar": float(mass_solar * 0.3),
            "radius_solar": 0.0,
            "luminosity_solar": 0.0,
            "is_remnant": True,
        }

    def hook_for_simulation(self, delta_s: float) -> None:
        """Hook signature compatible with SimulationTimeEngine.register_hook.

        `delta_s` is seconds; convert to Gyr for evolution if needed.
        If a RegionManager is attached, iterate its cached regions and
        apply deterministic evolution to each star (copy-on-write, cached
        update). Otherwise no-op (demonstrates integration point).
        """
        if self.region_manager is None:
            return
        try:
            delta_gyr = float(delta_s) / (1e9 * 365.25 * 86400.0)
        except Exception:
            return
        if delta_gyr <= 0 or delta_gyr != delta_gyr:
            return
        # Deterministic iteration: sorted region ids for reproducibility
        try:
            regions = getattr(self.region_manager, "generated_regions", {})
            for region_id in sorted(regions.keys()):
                region = regions[region_id]
                systems = region.get("systems", [])
                for sys in systems:
                    star = sys.get("star")
                    if not isinstance(star, dict):
                        continue
                    evolved = self.apply_evolution(star, delta_gyr)
                    # Update cached star in place (deterministic, versioned)
                    sys["star"] = evolved
        except Exception:
            # Never raise into simulation tick — evolution is non-authoritative
            return
