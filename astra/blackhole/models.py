"""ASTRA Black-Hole - model selection and numerical policy constants.

Contract: distinguishes the modelled spacetime explicitly (mirroring the
``astra.relativity.models`` pattern) and centralizes the numerical-safety
policy used by both the Schwarzschild and Kerr subsystems.
"""

from enum import Enum


class BlackHoleModel(Enum):
    """Spacetime solution modelling the central compact object.

    - SCHWARZSCHILD: static, spherically symmetric, non-rotating (a* = 0).
    - KERR: stationary, axisymmetric, rotating (0 < |a*| <= 1).
    """

    SCHWARZSCHILD = "SCHWARZSCHILD"
    KERR = "KERR"


# Radial evaluations at or within this distance (metres) of an event horizon
# are refused with CoordinateSingularityError: Boyer-Lindquist-type
# coordinates are singular there and float results would be NaN/Inf poisons.
# Policy: absolute epsilon, per handoff section 14.
NUMERICAL_HORIZON_EPSILON: float = 1.0e-9  # m

# For |a*| extremely close to 1 (extremal Kerr), r_g^2 - a^2 suffers
# floating-point cancellation and can drift microscopically negative, which
# would make sqrt() raise / produce complex numbers. Discriminants within
# this tolerance below zero are clamped to exactly 0.0.
EXTREMAL_SPIN_TOLERANCE: float = 1.0e-14
