"""Stellar generator — astrophysically motivated, deterministic, no physics execution.

Generates *configuration* dictionaries for `astra.celestial` / `astra.physics`
to consume. Does not call physics integrators; downstream systems remain
authoritative for dynamics.

IMF approximation: Salpeter-like piecewise (simplified but deterministic and
tested against expected ratios: ~70% M, ~20% K/G, ~9% A/F, ~1% O/B). This is
`THEORETICAL_DATA` for the distribution, `GENERATED_DATA` for each instance.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from astra.procedural.generators.base import DeterministicGenerator
from astra.procedural.provenance import DataProvenance


class StellarGenerator(DeterministicGenerator):
    """Deterministic star system generator."""

    def generate_star_system(self, system_id: str) -> Dict[str, Any]:
        if not isinstance(system_id, str) or not system_id:
            raise ValueError("system_id must be non-empty string")
        if ":" in system_id:
            raise ValueError("system_id cannot contain ':'")

        mass_solar = self._generate_mass()
        # Main-sequence mass-luminosity: L ∝ M^3.5 (0.5 < M < 20; simplified)
        # For very low mass, keep continuous
        luminosity = float(mass_solar ** 3.5)
        # Mass-radius: R ∝ M^0.8 (M < 1), M^0.57 otherwise (approx)
        if mass_solar < 1.0:
            radius = float(mass_solar ** 0.8)
        else:
            radius = float(mass_solar ** 0.57)
        # Effective temperature via L = 4πR²σT⁴ → T ∝ (L/R²)^0.25 ; anchor at 5800K for 1M
        # Avoid extreme: clamp 2000K .. 50000K
        try:
            teff = 5800.0 * ((luminosity / (radius ** 2)) ** 0.25)
        except Exception:
            teff = 5800.0
        teff = max(2000.0, min(50000.0, float(teff)))
        age_gyr = float(self.rng.uniform(0.1, 10.0))

        # Spectral classification (theoretical, based on Teff)
        spectral = self._classify_spectral(teff)

        return {
            "identity": system_id,
            "metadata": self.get_base_metadata(DataProvenance.GENERATED_DATA),
            "physics_state": {
                "mass_solar": float(mass_solar),
                "radius_solar": float(radius),
                "luminosity_solar": float(luminosity),
                "surface_temperature_k": float(teff),
                "spectral_type": spectral,
                "age_gyr": float(age_gyr),
                "is_remnant": False,
                "classification": "main_sequence",
            },
            "theoretical_basis": {
                "provenance": DataProvenance.THEORETICAL_DATA.value,
                "imf": "Salpeter_simplified_v1",
                "mass_luminosity": "L∝M^3.5",
                "mass_radius": "R∝M^0.8/0.57",
            },
        }

    def generate_multiple(self, system_id_prefix: str, count: int) -> list[Dict[str, Any]]:
        if count < 0:
            raise ValueError("count must be >=0")
        return [self.generate_star_system(f"{system_id_prefix}_{i}") for i in range(count)]

    def _generate_mass(self) -> float:
        # Deterministic via self.rng (never global)
        val = self.rng.random()
        if val < 0.70:
            return self.rng.uniform(0.08, 0.5)  # M dwarfs
        elif val < 0.90:
            return self.rng.uniform(0.5, 1.2)   # K, G
        elif val < 0.99:
            return self.rng.uniform(1.2, 3.0)   # F, A
        else:
            return self.rng.uniform(3.0, 50.0)  # O, B (rare)

    def _classify_spectral(self, teff: float) -> str:
        if teff >= 30000:
            return "O"
        if teff >= 10000:
            return "B"
        if teff >= 7500:
            return "A"
        if teff >= 6000:
            return "F"
        if teff >= 5200:
            return "G"
        if teff >= 3700:
            return "K"
        return "M"

    def generate_remnant_for_mass(self, mass_solar: float) -> Dict[str, Any]:
        """Helper for evolution: deterministic remnant mapping (not random)."""
        if mass_solar < 8.0:
            return {"classification": "White Dwarf", "mass_solar": mass_solar * 0.2, "is_remnant": True}
        if mass_solar < 20.0:
            return {"classification": "Neutron Star", "mass_solar": 1.4, "is_remnant": True}
        return {"classification": "Black Hole", "mass_solar": mass_solar * 0.3, "is_remnant": True, "provenance": DataProvenance.SPECULATIVE_DATA.value}
