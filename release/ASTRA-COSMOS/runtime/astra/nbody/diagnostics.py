"""Conservation diagnostics: momentum, angular momentum, energy."""
from __future__ import annotations
from typing import Sequence

from astra.mathematics import Vector3
from astra.physics.constants import GRAVITATIONAL_CONSTANT, DEFAULT_SOFTENING
from astra.nbody.bodies import NBodyBody
from astra.nbody.barycenter import center_of_mass, center_of_mass_velocity
from astra.nbody.gravity import gravitational_potential_energy


def total_linear_momentum(bodies: Sequence[NBodyBody]) -> Vector3:
    """P = sum(m_i v_i)."""
    P = Vector3(0.0, 0.0, 0.0)
    for b in bodies:
        P = P + b.velocity * b.mass
    return P


def kinetic_energy(bodies: Sequence[NBodyBody]) -> float:
    """K = sum(1/2 m_i |v_i|^2)."""
    K = 0.0
    for b in bodies:
        K += 0.5 * b.mass * b.velocity.magnitude_sq()
    return K


def total_energy(
    bodies: Sequence[NBodyBody],
    G: float = GRAVITATIONAL_CONSTANT,
    softening: float = DEFAULT_SOFTENING,
) -> float:
    """E = K + U. Pairwise potential counted once."""
    return kinetic_energy(bodies) + gravitational_potential_energy(
        bodies, G=G, softening=softening
    )


def total_angular_momentum(bodies: Sequence[NBodyBody],
                           about_origin: bool = True) -> Vector3:
    """L = sum(r_i x m_i v_i).

    about_origin=True : positions are absolute (world frame).
    about_origin=False: positions/velocities are measured relative to COM.
    """
    if about_origin:
        L = Vector3(0.0, 0.0, 0.0)
        for b in bodies:
            L = L + b.position.cross(b.velocity * b.mass)
        return L
    R = center_of_mass(bodies)
    V = center_of_mass_velocity(bodies)
    L = Vector3(0.0, 0.0, 0.0)
    for b in bodies:
        r = b.position - R
        v = b.velocity - V
        L = L + r.cross(v * b.mass)
    return L


def momentum_drift(P_initial: Vector3, P_current: Vector3) -> float:
    """Magnitude of momentum change (linear)."""
    return (P_current - P_initial).magnitude()


def energy_drift(E_initial: float, E_current: float) -> float:
    """Absolute energy change."""
    return E_current - E_initial
