"""Mathematical constants and default tolerance policy for ASTRA.

Conventions
-----------
- Angles are in RADIANS everywhere unless a function name says otherwise.
- Coordinate system is RIGHT-HANDED Cartesian.
- Quaternion convention is (w, x, y, z) with w the scalar part.
- Matrices are stored row-major, indexed (row, col), and act on column
  vectors: v' = M @ v.

Tolerance policy
----------------
Comparison of floats uses a combined absolute + relative test:

    |a - b| <= atol + rtol * |b|

Defaults:
    atol = 1e-12, rtol = 1e-9
These are documented values; callers may override per-call.
"""

import math

PI = math.pi
TAU = 2.0 * math.pi
HALF_PI = 0.5 * math.pi
E = math.e
SQRT2 = math.sqrt(2.0)
SQRT1_2 = 1.0 / SQRT2

DEFAULT_ATOL: float = 1e-12
DEFAULT_RTOL: float = 1e-9
DEFAULT_EPSILON: float = 1e-12

MACHINE_EPSILON: float = 2.220446049250313e-16
