"""Post-impact orbital analysis built on astra.orbital.

Classifies fragments/ejecta as gravitationally bound or escaping relative
to a body they are launched from (typically the impact target or its
parent). This is pure analysis: it consumes an existing ImpactResult and
mutates nothing, so it needs no authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from astra.mathematics import Vector3
from astra.orbital.energy import specific_orbital_energy
from astra.orbital.state import OrbitalState
from astra.physics.constants import GRAVITATIONAL_CONSTANT

from .errors import NumericalError
from .provenance import DataProvenance
from .types import FragmentState


class OrbitClass(str, Enum):
    BOUND = "BOUND"            # epsilon < 0 (elliptic)
    PARABOLIC = "PARABOLIC"    # epsilon == 0 (within atol)
    HYPERBOLIC = "HYPERBOLIC"  # epsilon > 0 (unbound)


@dataclass(frozen=True)
class FragmentOrbit:
    body_id: str
    orbit_class: OrbitClass
    specific_orbital_energy_j_kg: float
    mu_m3_s2: float
    separation_m: float
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA


def classify_fragment_orbit(
    fragment: FragmentState,
    *,
    central_mass_kg: float,
    central_position: Vector3,
    central_velocity: Vector3,
    G: float = GRAVITATIONAL_CONSTANT,
    atol_j_kg: float = 1e-9,
) -> FragmentOrbit:
    """Classify one fragment's orbit about a central body (two-body, SIMULATED)."""
    if not (isinstance(central_mass_kg, (int, float)) and central_mass_kg > 0.0):
        raise NumericalError("central_mass_kg must be > 0")
    mu = G * (float(central_mass_kg) + fragment.mass_kg)
    rel_pos = fragment.position - central_position
    rel_vel = fragment.velocity - central_velocity
    r = rel_pos.magnitude()
    if r == 0.0:
        raise NumericalError("fragment coincides with central body; orbit undefined")
    state = OrbitalState(
        position=rel_pos, velocity=rel_vel, mu=mu, epoch=fragment.created_at_s
    )
    eps = specific_orbital_energy(state)
    if eps > atol_j_kg:
        klass = OrbitClass.HYPERBOLIC
    elif eps < -atol_j_kg:
        klass = OrbitClass.BOUND
    else:
        klass = OrbitClass.PARABOLIC
    return FragmentOrbit(
        body_id=fragment.fragment_id,
        orbit_class=klass,
        specific_orbital_energy_j_kg=eps,
        mu_m3_s2=mu,
        separation_m=r,
        provenance=DataProvenance.SIMULATED_DATA,
    )


def count_orbit_classes(orbits) -> dict:
    """Tally classifications, e.g. {"BOUND": 12, "HYPERBOLIC": 3}."""
    tally = {klass.value: 0 for klass in OrbitClass}
    for orbit in orbits:
        tally[orbit.orbit_class.value] += 1
    return tally
