"""Tolerance policy for Orbital Mechanics classification and solving.

These are POLICY tolerances, not fundamental constants. They classify
numerically-degenerate configurations (circular, equatorial, parabolic)
and control Kepler-equation convergence.
"""

# Circular-orbit classification: eccentricity below this is treated as zero.
CIRCULAR_TOL: float = 1.0e-8

# Equatorial-orbit classification: inclination below this (or above pi minus
# this) is treated as zero/pi respectively.
EQUATORIAL_TOL: float = 1.0e-10

# Parabolic classification: |e - 1| below this is treated as e = 1.
PARABOLIC_TOL: float = 1.0e-8

# Node magnitude below this is treated as zero (no ascending node).
NODE_TOL: float = 1.0e-12

# Kepler-equation solving policy.
KEPLER_TOL: float = 1.0e-12
KEPLER_MAX_ITER: int = 200
