"""Kepler-equation solvers.

Elliptic (M = E - e sin E,  0 <= e < 1): Newton-Raphson.
Hyperbolic (M = e sinh H - H, e > 1):     Newton-Raphson.
Parabolic (M = D + D^3/3):                Barker's cubic, closed form.

All solvers are deterministic, tolerance-bounded, and raise
KeplerConvergenceError when the iteration limit is exhausted without
convergence. Callers may tune tolerance and iteration limit.
"""
from __future__ import annotations
import math

from astra.orbital.constants import KEPLER_TOL, KEPLER_MAX_ITER
from astra.orbital.errors import KeplerConvergenceError, InvalidOrbitError


def solve_kepler_elliptic(mean_anomaly: float, eccentricity: float,
                          tol: float = KEPLER_TOL,
                          max_iter: int = KEPLER_MAX_ITER) -> float:
    """Solve E - e sin E = M for E."""
    if not (0.0 <= eccentricity < 1.0):
        raise InvalidOrbitError(
            f"elliptic Kepler requires 0 <= e < 1, got e={eccentricity!r}"
        )
    M = mean_anomaly
    # Reduce M into [-pi, pi] for a stable starting guess.
    M_wrapped = ((M + math.pi) % (2.0 * math.pi)) - math.pi
    # Initial guess: M for low e, pi*sign(M) for high e.
    if eccentricity < 0.8:
        E = M_wrapped
    else:
        E = math.copysign(math.pi, M_wrapped) if M_wrapped != 0.0 else 0.0
    for _ in range(max_iter):
        f = E - eccentricity * math.sin(E) - M_wrapped
        fp = 1.0 - eccentricity * math.cos(E)
        if fp == 0.0:
            break
        dE = -f / fp
        E += dE
        if abs(dE) < tol:
            return E
    raise KeplerConvergenceError(
        f"elliptic Kepler solver failed: e={eccentricity!r}, M={M!r}"
    )


def solve_kepler_hyperbolic(mean_anomaly: float, eccentricity: float,
                            tol: float = KEPLER_TOL,
                            max_iter: int = KEPLER_MAX_ITER) -> float:
    """Solve e sinh H - H = M for H."""
    if eccentricity <= 1.0:
        raise InvalidOrbitError(
            f"hyperbolic Kepler requires e > 1, got e={eccentricity!r}"
        )
    M = mean_anomaly
    # Initial guess.
    if abs(M) < 1.0:
        H = M
    else:
        H = math.copysign(
            math.log(2.0 * abs(M) / eccentricity + 1.8), M
        )
    for _ in range(max_iter):
        f = eccentricity * math.sinh(H) - H - M
        fp = eccentricity * math.cosh(H) - 1.0
        if fp == 0.0:
            break
        dH = -f / fp
        H += dH
        if abs(dH) < tol:
            return H
    raise KeplerConvergenceError(
        f"hyperbolic Kepler solver failed: e={eccentricity!r}, M={M!r}"
    )


def solve_barker(mean_anomaly: float,
                 tol: float = KEPLER_TOL,
                 max_iter: int = KEPLER_MAX_ITER) -> float:
    """Solve D + D^3/3 = M for D (Barker's equation, parabolic).

    Closed-form via the depressed cubic solution; the tol/max_iter
    arguments are accepted for interface symmetry but not used.
    """
    M = mean_anomaly
    # D^3 + 3D - 3M = 0
    # D = cbrt(3M/2 + sqrt((3M/2)^2 + 1)) + cbrt(3M/2 - sqrt((3M/2)^2 + 1))
    a = 1.5 * M
    s = math.sqrt(a * a + 1.0)
    D = math.cbrt(a + s) + math.cbrt(a - s)
    return D
