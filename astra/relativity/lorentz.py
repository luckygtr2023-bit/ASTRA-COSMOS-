"""ASTRA COSMOS - Lorentz transformations.

Contract: preserve the Minkowski invariant under frame changes and enforce
|v| < c for every boost (LightSpeedViolation otherwise).

Known limitation (by design, deferred to a later phase): only axis-aligned
boosts are provided. Arbitrary 3D boosts require the astra.mathematics
matrix integration scheduled with the Spacecraft upgrade (see handoff
section 26).
"""

from __future__ import annotations

import math

from astra.relativity.core import SPEED_OF_LIGHT, lorentz_factor
from astra.relativity.four_vectors import FourVector


def boost_x(vector: FourVector, v: float) -> FourVector:
    """Apply a Lorentz boost along the X-axis.

    ``v`` is the velocity of the new (primed) frame w.r.t. the old one, in
    m/s. Components are in the same units as ``vector.t`` (ct).

    Standard passive transformation (frame S' moving at +v along x):
        t' = gamma * (t - beta * x)
        x' = gamma * (x - beta * t)

    Raises LightSpeedViolation for |v| >= c and InvalidVelocityError for
    NaN/Inf v.
    """
    gamma = lorentz_factor(math.fabs(v))
    b = v / SPEED_OF_LIGHT

    t_new = gamma * (vector.t - b * vector.x)
    x_new = gamma * (vector.x - b * vector.t)

    return FourVector(t_new, x_new, vector.y, vector.z)


def inverse_boost_x(vector: FourVector, v: float) -> FourVector:
    """Inverse Lorentz boost along the X-axis (boost by -v)."""
    return boost_x(vector, -v)
