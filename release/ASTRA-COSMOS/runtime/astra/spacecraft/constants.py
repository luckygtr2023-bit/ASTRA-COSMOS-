"""Spacecraft Physics constants and tolerance policy.

Units (SI-coherent, matching the rest of ASTRA):
    thrust         : N
    specific impulse : s
    mass           : kg
    mass flow      : kg/s
    delta-v        : m/s
    g0             : m/s^2  (standard gravity, exact by convention)

Only the standard gravity g0 is defined here. GRAVITATIONAL_CONSTANT and
DEFAULT_SOFTENING come from astra.physics.constants.
"""

# Standard gravitational acceleration, used in the rocket equation.
# Exact by convention (CGPM / ISO 80000).
G0: float = 9.80665  # m/s^2

# Isp validation policy.
MIN_ISP: float = 1.0        # s, below this is not a physical engine
MAX_ISP: float = 1.0e7      # s, above this is not a physical engine

# Thrust validation.
MIN_THRUST: float = 0.0     # N, thrust magnitude may be zero (idle engine)

# Tolerance for "propellant is empty" classification (kg).
PROP_TOL: float = 1.0e-15

# Tolerance for Isp equality checks in tests.
DEFAULT_ISP_TOL: float = 1.0e-12
