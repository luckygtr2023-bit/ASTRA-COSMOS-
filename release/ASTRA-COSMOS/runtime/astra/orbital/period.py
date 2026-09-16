"""Orbital period for closed (elliptic) orbits."""
from __future__ import annotations
import math

from astra.orbital.errors import InvalidOrbitError


def orbital_period(semi_major_axis: float, mu: float) -> float:
    """T = 2 pi sqrt(a^3 / mu). Requires a > 0 (bound elliptic orbit)."""
    if semi_major_axis <= 0.0:
        raise InvalidOrbitError(
            f"period requires a > 0, got a={semi_major_axis!r}"
        )
    if mu <= 0.0:
        raise InvalidOrbitError(f"mu must be positive, got {mu!r}")
    return 2.0 * math.pi * math.sqrt(semi_major_axis ** 3 / mu)
