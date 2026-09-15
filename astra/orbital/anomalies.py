"""Anomaly conversions: true (nu), eccentric (E), hyperbolic (H), mean (M).

Elliptic (0 <= e < 1):
    tan(E/2) = sqrt((1-e)/(1+e)) * tan(nu/2)
    M = E - e sin E
Hyperbolic (e > 1):
    tanh(H/2) = sqrt((e-1)/(e+1)) * tan(nu/2)
    M = e sinh H - H
Parabolic (e = 1):
    D = tan(nu/2)
    M = D + D^3 / 3
"""
from __future__ import annotations
import math

from astra.orbital.errors import InvalidOrbitError
from astra.orbital.constants import PARABOLIC_TOL


# ---------------------------------------------------------------------------
# Elliptic
# ---------------------------------------------------------------------------

def true_to_eccentric(true_anomaly: float, eccentricity: float) -> float:
    if eccentricity < 0.0 or eccentricity >= 1.0 - PARABOLIC_TOL:
        raise InvalidOrbitError(
            f"elliptic eccentric anomaly requires 0 <= e < 1, got e={eccentricity!r}"
        )
    half = 0.5 * true_anomaly
    x = math.sqrt((1.0 - eccentricity) / (1.0 + eccentricity)) * math.tan(half)
    return 2.0 * math.atan(x)


def eccentric_to_true(eccentric_anomaly: float, eccentricity: float) -> float:
    if eccentricity < 0.0 or eccentricity >= 1.0 - PARABOLIC_TOL:
        raise InvalidOrbitError(
            f"elliptic eccentric anomaly requires 0 <= e < 1, got e={eccentricity!r}"
        )
    half = 0.5 * eccentric_anomaly
    x = math.sqrt((1.0 + eccentricity) / (1.0 - eccentricity)) * math.tan(half)
    return 2.0 * math.atan(x)


def true_to_mean_elliptic(true_anomaly: float, eccentricity: float) -> float:
    E = true_to_eccentric(true_anomaly, eccentricity)
    return E - eccentricity * math.sin(E)


def mean_to_true_elliptic(mean_anomaly: float, eccentricity: float,
                          tol: float = 1e-12, max_iter: int = 200) -> float:
    from astra.orbital.kepler import solve_kepler_elliptic
    E = solve_kepler_elliptic(mean_anomaly, eccentricity, tol=tol, max_iter=max_iter)
    return eccentric_to_true(E, eccentricity)


# ---------------------------------------------------------------------------
# Hyperbolic
# ---------------------------------------------------------------------------

def true_to_hyperbolic(true_anomaly: float, eccentricity: float) -> float:
    if eccentricity <= 1.0 + PARABOLIC_TOL:
        raise InvalidOrbitError(
            f"hyperbolic anomaly requires e > 1, got e={eccentricity!r}"
        )
    half = 0.5 * true_anomaly
    x = math.sqrt((eccentricity - 1.0) / (eccentricity + 1.0)) * math.tan(half)
    return 2.0 * math.atanh(x)


def hyperbolic_to_true(hyperbolic_anomaly: float, eccentricity: float) -> float:
    if eccentricity <= 1.0 + PARABOLIC_TOL:
        raise InvalidOrbitError(
            f"hyperbolic anomaly requires e > 1, got e={eccentricity!r}"
        )
    half = 0.5 * hyperbolic_anomaly
    x = math.sqrt((eccentricity + 1.0) / (eccentricity - 1.0)) * math.tanh(half)
    return 2.0 * math.atan(x)


def true_to_mean_hyperbolic(true_anomaly: float, eccentricity: float) -> float:
    H = true_to_hyperbolic(true_anomaly, eccentricity)
    return eccentricity * math.sinh(H) - H


def mean_to_true_hyperbolic(mean_anomaly: float, eccentricity: float,
                            tol: float = 1e-12, max_iter: int = 200) -> float:
    from astra.orbital.kepler import solve_kepler_hyperbolic
    H = solve_kepler_hyperbolic(mean_anomaly, eccentricity, tol=tol, max_iter=max_iter)
    return hyperbolic_to_true(H, eccentricity)


# ---------------------------------------------------------------------------
# Parabolic
# ---------------------------------------------------------------------------

def true_to_mean_parabolic(true_anomaly: float) -> float:
    if abs(abs(true_anomaly) - math.pi) < 1e-14:
        raise InvalidOrbitError(
            "parabolic true anomaly must not be +/- pi (r -> infinity)"
        )
    D = math.tan(0.5 * true_anomaly)
    return D + D ** 3 / 3.0


def mean_to_true_parabolic(mean_anomaly: float,
                           tol: float = 1e-12, max_iter: int = 200) -> float:
    from astra.orbital.kepler import solve_barker
    D = solve_barker(mean_anomaly, tol=tol, max_iter=max_iter)
    return 2.0 * math.atan(D)
