"""N-Body tolerances and defaults.

The gravitational constant G and the recommended minimum softening are
imported from astra.physics.constants to avoid duplication.

MIN_SOFTENING is the smallest softening length this layer will accept as
a positive value; below this, softening is treated as zero and true
singularities raise NBodySingularityError.
"""

from astra.physics.constants import (
    GRAVITATIONAL_CONSTANT as G,
    DEFAULT_SOFTENING,
)

# Softening below this is treated as zero (exact Newtonian).
MIN_SOFTENING: float = 0.0

# Acceleration magnitude below this is considered "zero" for drift tests.
ACC_TOL: float = 1.0e-30

# Relative energy/momentum drift tolerance for long-run tests.
ENERGY_TOL: float = 1.0e-9
