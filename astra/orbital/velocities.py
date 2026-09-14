"""Orbital velocity relationships (vis-viva and special cases)."""
from __future__ import annotations
import math

from astra.orbital.errors import InvalidOrbitError


def vis_viva(r: float, a: float, mu: float) -> float:
    """v = sqrt(mu * (2/r - 1/a)).  For hyperbolic, a < 0 is valid."""
    if r <= 0.0:
        raise InvalidOrbitError(f"r must be positive, got {r!r}")
    if a == 0.0:
        raise InvalidOrbitError("semi-major axis must be non-zero")
    val = mu * (2.0 / r - 1.0 / a)
    if val < 0.0:
        raise InvalidOrbitError(
            f"vis-viva has no real solution (2/r - 1/a < 0)"
        )
    return math.sqrt(val)


def circular_velocity(r: float, mu: float) -> float:
    """v_c = sqrt(mu/r)."""
    if r <= 0.0:
        raise InvalidOrbitError(f"r must be positive, got {r!r}")
    return math.sqrt(mu / r)


def escape_velocity(r: float, mu: float) -> float:
    """v_esc = sqrt(2 mu / r)."""
    if r <= 0.0:
        raise InvalidOrbitError(f"r must be positive, got {r!r}")
    return math.sqrt(2.0 * mu / r)


def periapsis_velocity(p: float, e: float, mu: float) -> float:
    """v at r_periapsis = p/(1+e)."""
    r_p = p / (1.0 + e)
    if e < 1.0:
        a = p / (1.0 - e * e)
        return vis_viva(r_p, a, mu)
    if abs(e - 1.0) < 1e-12:
        return math.sqrt(2.0 * mu / r_p)
    a = p / (1.0 - e * e)  # negative for hyperbolic
    return vis_viva(r_p, a, mu)


def apoapsis_velocity(p: float, e: float, mu: float) -> float:
    """v at r_apoapsis = p/(1-e). Only defined for e < 1."""
    if e >= 1.0:
        raise InvalidOrbitError(f"apoapsis is undefined for e >= 1, got e={e!r}")
    r_a = p / (1.0 - e)
    a = p / (1.0 - e * e)
    return vis_viva(r_a, a, mu)
