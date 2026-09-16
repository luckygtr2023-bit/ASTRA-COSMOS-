"""ASTRA Black-Hole layer.

Dependency direction:
    CORE -> MATHEMATICS -> PHYSICS -> RELATIVITY -> BLACKHOLE -> (Spacetime)

Models static (Schwarzschild) and rotating (Kerr) compact-object spacetimes
under the strict TEST-PARTICLE APPROXIMATION: the black hole provides a
fixed background metric; test particles have m << M and never back-react.

Scientific scope (this phase):
    - Horizons r_s / r_+ and r_-, ergosphere (static limit), ISCO
      (Bardeen-Press-Teukolsky), circular photon orbits, gravitational time
      dilation, gravitational redshift, equatorial frame dragging (ZAMO).
    - Strict coordinate-singularity guards at horizons
      (NUMERICAL_HORIZON_EPSILON) and explicit rejection of naked
      singularities (|a*| > 1).

Out of scope (deferred to the Spacetime phase): metric tensors g_mu_nu as
matrix objects, non-equatorial frame dragging, interior geometries, full
numerical relativity.

Authority: stateless calculation layer over an immutable BlackHoleState;
it mutates nothing and holds no authority.

Determinism: 100% deterministic - no RNG, no wall-clock, no global state.
"""
from astra.blackhole.models import (
    BlackHoleModel,
    NUMERICAL_HORIZON_EPSILON,
    EXTREMAL_SPIN_TOLERANCE,
)
from astra.blackhole.exceptions import (
    BlackHoleError,
    InvalidBlackHoleMassError,
    InvalidSpinParameterError,
    InvalidGeometryInputError,
    CoordinateSingularityError,
)
from astra.blackhole.parameters import (
    BlackHoleState,
    validate_mass_kg,
    validate_spin_param,
)
from astra.blackhole import schwarzschild, kerr
from astra.blackhole.api import (
    create_black_hole,
    get_schwarzschild_boundaries,
    get_kerr_boundaries,
    calculate_ergosphere_radius,
    gravitational_time_dilation,
    gravitational_redshift,
    equatorial_frame_dragging_velocity,
)

__all__ = [
    # models & policy
    "BlackHoleModel", "NUMERICAL_HORIZON_EPSILON", "EXTREMAL_SPIN_TOLERANCE",
    # exceptions
    "BlackHoleError", "InvalidBlackHoleMassError", "InvalidSpinParameterError",
    "InvalidGeometryInputError", "CoordinateSingularityError",
    # state
    "BlackHoleState", "validate_mass_kg", "validate_spin_param",
    # subsystems (internal math, exported for direct scientific use)
    "schwarzschild", "kerr",
    # facade
    "create_black_hole", "get_schwarzschild_boundaries", "get_kerr_boundaries",
    "calculate_ergosphere_radius", "gravitational_time_dilation",
    "gravitational_redshift", "equatorial_frame_dragging_velocity",
]
