"""ASTRA COSMOS - General Relativity foundations.

Contract: weak-field and Schwarzschild foundations only, with strict
coordinate-singularity guards. This module does NOT model black hole
interiors and raises DegenerateMetricError at r <= r_s.

Integration: the gravitational constant G is imported from
astra.physics.constants (single source of truth, as in astra.nbody);
SPEED_OF_LIGHT comes from astra.relativity.core.

Assumptions: static, spherically symmetric, uncharged, non-rotating mass
(Schwarzschild exterior solution).
"""

from __future__ import annotations

import math

from astra.physics.constants import GRAVITATIONAL_CONSTANT
from astra.relativity.core import C_SQUARED
from astra.relativity.exceptions import DegenerateMetricError

# Re-exported for callers that want the relativity layer's whole constant
# set without reaching into the physics layer themselves.
G: float = GRAVITATIONAL_CONSTANT  # m^3 kg^-1 s^-2


def schwarzschild_radius(mass: float) -> float:
    """Calculate the Schwarzschild radius r_s = 2 G M / c^2 (m).

    A zero mass has zero radius (flat spacetime). Negative or non-finite
    mass is nonphysical and raises DegenerateMetricError.
    """
    m = float(mass)
    if math.isnan(m) or math.isinf(m) or m < 0.0:
        raise DegenerateMetricError(f"Mass must be finite and >= 0, got {mass!r}")
    if m == 0.0:
        return 0.0
    return (2.0 * G * m) / C_SQUARED


def weak_field_time_dilation(mass: float, r: float) -> float:
    """Gravitational time dilation in the Schwarzschild weak-field limit.

    For a stationary clock at areal coordinate r outside a mass M:

        dtau/dt = sqrt(1 - r_s / r)      (proper time per coordinate time)
        dt/dtau = 1 / sqrt(1 - r_s / r)  (returned value; >= 1)

    i.e. distant observers see the deep-field clock run slow.

    Raises:
        DegenerateMetricError: if r <= 0, r <= r_s (coordinate singularity
            / event horizon), or the mass input is invalid.
    """
    rs = schwarzschild_radius(mass)

    if math.isnan(r) or math.isinf(r) or r <= 0.0:
        raise DegenerateMetricError(f"Radius must be finite and > 0, got {r!r}")
    if r <= rs:
        raise DegenerateMetricError(
            f"Radius {r} is inside or at Schwarzschild radius {rs}."
        )

    return 1.0 / math.sqrt(1.0 - (rs / r))
