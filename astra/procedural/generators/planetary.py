"""Planetary system generator — deterministic orbital & physical state.

Outputs are *initial conditions* for `astra.orbital`/`astra.physics`/`astra.nbody`.
No integration is performed here; the generators are pure configuration.
"""

from __future__ import annotations

from typing import Any, Dict, List

from astra.procedural.generators.base import DeterministicGenerator
from astra.procedural.provenance import DataProvenance


class PlanetarySystemGenerator(DeterministicGenerator):
    """Deterministic planetary system generator."""

    def generate_planets(self, star_mass_solar: float, parent_id: str) -> List[Dict[str, Any]]:
        if not isinstance(parent_id, str) or not parent_id:
            raise ValueError("parent_id must be non-empty string")
        if not isinstance(star_mass_solar, (int, float)) or star_mass_solar <= 0:
            raise ValueError("star_mass_solar must be positive number")
        if star_mass_solar != star_mass_solar or star_mass_solar in (float("inf"), float("-inf")):
            raise ValueError("star_mass_solar cannot be NaN/Inf")

        num_planets = self.rng.randint(0, 10)
        planets: List[Dict[str, Any]] = []

        # Starting distance scales weakly with stellar mass (more massive → slightly farther snow line)
        current_distance = self.rng.uniform(0.1, 0.4) * (1.0 + 0.1 * (star_mass_solar - 1.0))
        current_distance = max(0.05, float(current_distance))

        for i in range(num_planets):
            planet_id = f"{parent_id}_p{i+1}"
            # Titius-Bode-like spacing, deterministic
            spacing = self.rng.uniform(1.3, 2.0)
            current_distance = float(current_distance * spacing)
            # Clamp to avoid runaway beyond ~100 AU for 10 planets
            current_distance = min(current_distance, 80.0 + i * 2.0)

            is_gas_giant = self.rng.random() > 0.6 and current_distance > 2.0
            if is_gas_giant:
                mass_earth = self.rng.uniform(15.0, 300.0)
                # Gas giant radius scales sub-linearly; clamp 3..20 R_earth
                radius_earth = max(3.0, min(20.0, float(mass_earth ** 0.4)))
            else:
                mass_earth = self.rng.uniform(0.1, 10.0)
                radius_earth = max(0.3, min(2.5, float(mass_earth ** (1.0 / 3.0))))

            ecc = self.rng.uniform(0.0, 0.20)
            # Ensure periastron > 0.02 AU (avoid star collision)
            if current_distance * (1.0 - ecc) < 0.02:
                ecc = max(0.0, 1.0 - 0.02 / current_distance)

            planets.append({
                "identity": planet_id,
                "metadata": self.get_base_metadata(DataProvenance.GENERATED_DATA),
                "orbital_state": {
                    "semi_major_axis_au": float(current_distance),
                    "eccentricity": float(ecc),
                    "inclination_deg": float(self.rng.uniform(0.0, 5.0)),
                    "longitude_of_ascending_node_deg": float(self.rng.uniform(0.0, 360.0)),
                    "argument_of_periapsis_deg": float(self.rng.uniform(0.0, 360.0)),
                    "mean_anomaly_deg": float(self.rng.uniform(0.0, 360.0)),
                },
                "physics_state": {
                    "mass_earth": float(mass_earth),
                    "radius_earth": float(radius_earth),
                    "is_gas_giant": bool(is_gas_giant),
                },
            })

        return planets

    def generate_moons(self, planet_state: Dict[str, Any], parent_id: str, max_moons: int = 3) -> List[Dict[str, Any]]:
        """Optional moon generation for a given planet (deterministic, sparse)."""
        if not isinstance(planet_state, dict):
            raise TypeError("planet_state must be dict")
        if planet_state.get("physics_state", {}).get("is_gas_giant"):
            n = self.rng.randint(0, max_moons)
        else:
            # Terrestrials rarely have many moons (procedural approx)
            n = self.rng.randint(0, 1) if self.rng.random() > 0.7 else 0
        moons = []
        for i in range(n):
            moons.append({
                "identity": f"{parent_id}_m{i+1}",
                "metadata": self.get_base_metadata(DataProvenance.GENERATED_DATA),
                "orbital_state": {
                    "semi_major_axis_au": float(self.rng.uniform(0.001, 0.02)),
                    "eccentricity": float(self.rng.uniform(0.0, 0.1)),
                },
                "physics_state": {
                    "mass_earth": float(self.rng.uniform(0.001, 0.1)),
                },
            })
        return moons
