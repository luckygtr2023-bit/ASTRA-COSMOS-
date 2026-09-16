"""Velocity Verlet integration step for N-body systems.

Why velocity Verlet
-------------------
- Symplectic: bounded energy oscillation, no secular drift.
- Second-order accurate.
- Standard for gravitational N-body simulations.
- Time-reversible: stepping forward by dt then backward by dt returns
  the initial state (to float precision).

This is a thin, domain-specific composition on top of the pairwise
acceleration primitive. It does NOT re-implement RK4/Euler/RK45, which
remain in astra.mathematics.ode.
"""
from __future__ import annotations
from typing import List, Sequence, Tuple

from astra.mathematics import Vector3
from astra.physics.constants import GRAVITATIONAL_CONSTANT, DEFAULT_SOFTENING
from astra.nbody.bodies import NBodyBody
from astra.nbody.gravity import compute_accelerations
from astra.nbody.errors import InvalidTimestepError
import math


def _validate_dt(dt: float) -> None:
    if not math.isfinite(dt) or dt <= 0.0:
        raise InvalidTimestepError(f"dt must be positive finite, got {dt!r}")


def velocity_verlet_step(
    bodies: Sequence[NBodyBody],
    dt: float,
    G: float = GRAVITATIONAL_CONSTANT,
    softening: float = DEFAULT_SOFTENING,
) -> Tuple[List[NBodyBody], List[Vector3]]:
    """One velocity Verlet step.

    Returns
    -------
    (new_bodies, new_accelerations) — new accelerations are computed at the
    end of the step and can be cached by the caller to avoid recomputation.
    """
    _validate_dt(dt)
    a0 = compute_accelerations(bodies, G=G, softening=softening)

    # Half-kick + drift
    half_vels: List[Vector3] = []
    new_positions: List[Vector3] = []
    for b, a in zip(bodies, a0):
        v_half = b.velocity + a * (0.5 * dt)
        x_new = b.position + v_half * dt
        half_vels.append(v_half)
        new_positions.append(x_new)

    # Rebuild with new positions to compute new accelerations
    mid_bodies = [
        NBodyBody(id=b.id, mass=b.mass, position=x, velocity=b.velocity)
        for b, x in zip(bodies, new_positions)
    ]
    a1 = compute_accelerations(mid_bodies, G=G, softening=softening)

    # Second half-kick
    final_bodies: List[NBodyBody] = []
    for b, vh, a in zip(mid_bodies, half_vels, a1):
        v_new = vh + a * (0.5 * dt)
        final_bodies.append(NBodyBody(id=b.id, mass=b.mass,
                                       position=b.position, velocity=v_new))
    return final_bodies, a1
