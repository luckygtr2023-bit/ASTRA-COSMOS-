"""Ejecta model.

Simplified, empirical model (SIMULATED_DATA): a caller-tunable mass fraction
of the target is launched from the impact site into the hemisphere opposing
the incoming direction, with cosine-weighted directions and a characteristic
speed scale. Not a first-principles cratering model — a real regolith /
cratering model belongs to the physics layer when it exists.
"""
from __future__ import annotations

import math
from typing import List, Tuple

from astra.mathematics import Vector3

from .config import DestructionConfig
from .errors import NumericalError
from .fragmentation import RNGProvider
from .provenance import DataProvenance
from .types import EjectaState, ImpactEnergy, ImpactEvent


def generate_ejecta(
    event: ImpactEvent,
    energy: ImpactEnergy,
    rng: RNGProvider,
    config: DestructionConfig,
    *,
    ejecta_mass_fraction: float = 0.05,
    characteristic_speed_m_s: float = 100.0,
) -> Tuple[EjectaState, ...]:
    """Produce a bounded, deterministic ejecta population.

    A limit of ``max_ejecta_per_impact == 0`` disables ejecta (returns ()).
    """
    if not (0.0 <= ejecta_mass_fraction <= 1.0):
        raise NumericalError("ejecta_mass_fraction must be in [0,1]")
    if characteristic_speed_m_s < 0.0:
        raise NumericalError("characteristic_speed_m_s must be >= 0")

    cap = config.limits.max_ejecta_per_impact
    if cap == 0:
        return ()

    m_ejecta_total = event.target_mass_kg * ejecta_mass_fraction
    if m_ejecta_total <= 0.0:
        return ()

    n = max(
        1,
        int(
            round(
                math.log1p(m_ejecta_total / max(config.limits.min_fragment_mass_kg, 1e-30))
            )
        ),
    )
    n = min(cap, n)

    per_mass = m_ejecta_total / n

    # Hemisphere axis: opposite the incoming relative velocity.
    if event.relative_speed() > 0.0:
        n_hat = (-event.relative_velocity()).normalized()
    else:  # pragma: no cover - validate_impact forbids this path
        n_hat = Vector3(0.0, 0.0, 1.0)
    ref = Vector3(0.0, 0.0, 1.0) if abs(n_hat.z) < 0.9 else Vector3(1.0, 0.0, 0.0)
    t1 = n_hat.cross(ref).normalized()
    t2 = n_hat.cross(t1)

    out: List[EjectaState] = []
    for i in range(n):
        u1 = rng.next_float()
        u2 = rng.next_float()
        # Cosine-weighted direction in the hemisphere around n_hat.
        theta = math.acos(math.sqrt(1.0 - u1))
        phi = 2.0 * math.pi * u2
        direction = (
            n_hat * math.cos(theta)
            + t1 * (math.sin(theta) * math.cos(phi))
            + t2 * (math.sin(theta) * math.sin(phi))
        )
        speed = characteristic_speed_m_s * (0.5 + rng.next_float())
        vel = event.target_velocity + direction * speed
        pos = event.target_position + direction * max(event.target_radius_m, 0.0)
        ke = 0.5 * per_mass * speed * speed
        out.append(
            EjectaState(
                ejecta_id=f"{event.impact_id}:ejecta:{i}",
                impact_id=event.impact_id,
                source_id=event.target_id,
                mass_kg=per_mass,
                position=pos,
                velocity=vel,
                kinetic_energy_j=ke,
                created_at_s=event.sim_time_s,
                provenance=DataProvenance.SIMULATED_DATA,
            )
        )
    return tuple(out)
