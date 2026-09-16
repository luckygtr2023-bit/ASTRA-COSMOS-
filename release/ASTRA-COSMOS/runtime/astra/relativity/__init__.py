"""ASTRA Relativity layer.

Dependency direction:
    CORE -> MATHEMATICS -> MOTION -> PHYSICS -> RELATIVITY -> (future domains)

Relativity is a pure calculation layer: it never mutates simulation state
and holds no authority. It distinguishes proper time from coordinate time,
enforces the v < c limit for massive objects, and provides 4-vector
geometry on the Minkowski signature eta = diag(-1, 1, 1, 1).

Integration:
    - Relativistic kinetic energy converges to astra.physics energy at low v.
    - Relativistic momentum converges to astra.physics momentum at low v.
    - RelativityModel gates model selection for later phases (e.g. applying
      Schwarzschild corrections to Keplerian orbits).

Scientific scope (this phase): Special Relativity plus weak-field /
Schwarzschild-exterior foundations. No black hole interiors, no full GR.

Determinism: 100% deterministic - no RNG, no wall-clock, no global state.
"""
from astra.relativity.models import RelativityModel
from astra.relativity.exceptions import (
    RelativityError,
    LightSpeedViolation,
    DegenerateMetricError,
    InvalidVelocityError,
    InvalidRestMassError,
    SpacelikeIntervalError,
)
from astra.relativity.core import (
    SPEED_OF_LIGHT,
    C_SQUARED,
    LOW_BETA_TAYLOR_THRESHOLD,
    speed,
    beta,
    lorentz_factor,
    relativistic_mass,
    total_energy,
    kinetic_energy,
    relativistic_momentum,
    kinetic_energy_v,
    total_energy_v,
)
from astra.relativity.four_vectors import (
    SpacetimeIntervalType,
    FourVector,
    SpacetimeEvent,
)
from astra.relativity.lorentz import boost_x, inverse_boost_x
from astra.relativity.gr_foundations import (
    G,
    schwarzschild_radius,
    weak_field_time_dilation,
)

__all__ = [
    # models
    "RelativityModel",
    # exceptions
    "RelativityError", "LightSpeedViolation", "DegenerateMetricError",
    "InvalidVelocityError", "InvalidRestMassError", "SpacelikeIntervalError",
    # core constants
    "SPEED_OF_LIGHT", "C_SQUARED", "LOW_BETA_TAYLOR_THRESHOLD",
    # core functions
    "speed", "beta", "lorentz_factor", "relativistic_mass",
    "total_energy", "kinetic_energy", "relativistic_momentum",
    "kinetic_energy_v", "total_energy_v",
    # four vectors
    "SpacetimeIntervalType", "FourVector", "SpacetimeEvent",
    # lorentz
    "boost_x", "inverse_boost_x",
    # gr foundations
    "G", "schwarzschild_radius", "weak_field_time_dilation",
]
