"""ASTRA Black-Hole - Kerr subsystem.

Contract: stationary, axisymmetric, rotating (Kerr) vacuum solution under
the test-particle approximation. Naked singularities (|a*| > 1) are
rejected at parameter validation; extremal spins (|a*| = 1) are handled
with an explicit clamp on cancellation-prone discriminants.

Scope limits (per handoff sections 1, 26):
    - Frame dragging (ZAMO angular velocity) is provided in the EQUATORIAL
      plane (theta = pi/2); arbitrary inclinations await the Spacetime phase.
    - No interior geometries; no charged (Kerr-Newman) metrics.

Geometry (lengths in metres; r_g = GM/c^2, a = a* r_g):
    Horizons:      r +/- = r_g +/- sqrt(r_g^2 - a^2)
    Static limit:  r_E(theta) = r_g + sqrt(r_g^2 - a^2 cos^2(theta))
    ZAMO omega:    omega = c * (2 r_g a r) / ((r^2 + a^2)^2 - a^2 Delta sin^2 theta)
                   with Delta = r^2 - 2 r_g r + a^2   (SI: rad/s)
    ISCO (Bardeen-Press-Teukolsky 1972), prograde/retrograde via sign of a*.
    Photon orbits: r_ph = 2 r_g (1 + cos((2/3) arccos(-+ a*))).

Deterministic pure functions; SI units.
"""

from __future__ import annotations

import math
from typing import Tuple

from astra.blackhole.exceptions import (
    CoordinateSingularityError,
    InvalidGeometryInputError,
)
from astra.blackhole.models import EXTREMAL_SPIN_TOLERANCE, NUMERICAL_HORIZON_EPSILON
from astra.blackhole.parameters import BlackHoleState
from astra.relativity.core import SPEED_OF_LIGHT


def _clamped_sqrt(discriminant: float) -> float:
    """sqrt() with extremal-Kerr protection.

    Discriminants within EXTREMAL_SPIN_TOLERANCE below zero are clamped to
    0.0 (exact extremality), so floating-point drift can never turn the
    horizon/ergosphere square roots complex or raise math domain errors.
    """
    if discriminant < 0.0:
        if discriminant > -EXTREMAL_SPIN_TOLERANCE:
            return 0.0
        raise ValueError(f"Negative discriminant {discriminant!r} beyond extremal tolerance.")
    return math.sqrt(discriminant)


def horizons(state: BlackHoleState) -> Tuple[float, float]:
    """Outer and inner event horizons (r_+, r_-) in metres.

    r_+ = r_g + sqrt(r_g^2 - a^2),  r_- = r_g - sqrt(r_g^2 - a^2).
    For a* = 0: (2 r_g, 0). For |a*| = 1: (r_g, r_g) degenerate.
    """
    r_g = state.gravitational_radius
    disc = _clamped_sqrt(r_g * r_g - state.spin_length * state.spin_length)
    return (r_g + disc, r_g - disc)


def ergosphere_radius(state: BlackHoleState, theta_rad: float) -> float:
    """Static-limit (ergosphere) radius r_E(theta) in metres.

    r_E(theta) = r_g + sqrt(r_g^2 - a^2 cos^2(theta)).

    Touches the outer horizon at the poles (theta = 0, pi) and equals
    2 r_g at the equator. For a* = 0 this is constant 2 r_g (= r_s).
    """
    if isinstance(theta_rad, bool) or not isinstance(theta_rad, (int, float)):
        raise InvalidGeometryInputError(
            f"theta must be a real number, got {type(theta_rad).__name__}"
        )
    theta = float(theta_rad)
    if math.isnan(theta) or math.isinf(theta):
        raise InvalidGeometryInputError(f"theta cannot be NaN or Infinite, got {theta_rad!r}")

    r_g = state.gravitational_radius
    cos2 = math.cos(theta) ** 2
    disc = _clamped_sqrt(r_g * r_g - state.spin_length * state.spin_length * cos2)
    return r_g + disc


def frame_dragging_angular_velocity(
    state: BlackHoleState, radius: float, theta_rad: float = math.pi / 2
) -> float:
    """ZAMO angular velocity omega (rad/s) at (r, theta).

    omega = c * (2 r_g a r) / ((r^2 + a^2)^2 - a^2 Delta sin^2(theta)),
    Delta = r^2 - 2 r_g r + a^2.

    Zero for a* = 0, sign follows the spin, diverges towards the horizon
    limit omega_+ = c a / (r_+^2 + a^2). Radius must lie outside the outer
    horizon guard. (Equatorial-plane API; see module scope limits.)
    """
    if isinstance(radius, bool) or not isinstance(radius, (int, float)):
        raise InvalidGeometryInputError(f"Radius must be a real number, got {type(radius).__name__}")
    r = float(radius)
    if math.isnan(r) or math.isinf(r):
        raise InvalidGeometryInputError(f"Radius cannot be NaN or Infinite, got {radius!r}")

    r_plus, _ = horizons(state)
    if r <= r_plus + NUMERICAL_HORIZON_EPSILON:
        raise CoordinateSingularityError(
            f"Radius {r!r} m is at or within {NUMERICAL_HORIZON_EPSILON!r} m of the "
            f"outer horizon {r_plus!r} m; frame dragging undefined on/inside the horizon."
        )

    r_g = state.gravitational_radius
    a = state.spin_length
    sin2 = math.sin(theta_rad) ** 2
    delta = r * r - 2.0 * r_g * r + a * a
    if delta < 0.0 and delta > -EXTREMAL_SPIN_TOLERANCE * (r_g * r_g):
        delta = 0.0
    denom = (r * r + a * a) ** 2 - a * a * delta * sin2
    return SPEED_OF_LIGHT * (2.0 * r_g * a * r) / denom


def isco_prograde(state: BlackHoleState) -> float:
    """Equatorial prograde ISCO radius (m), Bardeen-Press-Teukolsky formula.

    r_isco = r_g (3 + Z2 - sqrt((3 - Z1)(3 + Z1 + 2 Z2))),
    Z1 = 1 + (1 - a*^2)^(1/3) ((1 + a*)^(1/3) + (1 - a*)^(1/3)),
    Z2 = sqrt(3 a*^2 + Z1^2).
    Limits: a* = 0 -> 6 r_g, a* = 1 -> r_g (maximal prograde shrinking).

    NOTE: Z1 and Z2 are even in a*, so the orbit family is selected by the
    SIGN OF THE SQUARE ROOT (minus = prograde), not by the spin sign.
    """
    return _isco(state, -1.0)


def isco_retrograde(state: BlackHoleState) -> float:
    """Equatorial retrograde ISCO radius (m). Limits: a* = 0 -> 6 r_g,
    |a*| = 1 -> 9 r_g (orbits against the spin are least stable)."""
    return _isco(state, +1.0)


def _isco(state: BlackHoleState, root_sign: float) -> float:
    a_star = state.spin_param
    a2 = a_star * a_star
    z1 = 1.0 + (1.0 - a2) ** (1.0 / 3.0) * (
        (1.0 + a_star) ** (1.0 / 3.0) + (1.0 - a_star) ** (1.0 / 3.0)
    )
    z2 = math.sqrt(3.0 * a2 + z1 * z1)
    root = _clamped_sqrt((3.0 - z1) * (3.0 + z1 + 2.0 * z2))
    return state.gravitational_radius * (3.0 + z2 + root_sign * root)


def photon_orbit_prograde(state: BlackHoleState) -> float:
    """Equatorial prograde circular photon-orbit radius (m).

    r_ph = 2 r_g (1 + cos((2/3) arccos(-a*))). Limits: a*=0 -> 3 r_g,
    a*=1 -> r_g."""
    return _photon_orbit(state, state.spin_param)


def photon_orbit_retrograde(state: BlackHoleState) -> float:
    """Equatorial retrograde circular photon-orbit radius (m).

    Limits: a*=0 -> 3 r_g, |a*|=1 -> 4 r_g."""
    return _photon_orbit(state, -state.spin_param)


def _photon_orbit(state: BlackHoleState, a_star: float) -> float:
    return 2.0 * state.gravitational_radius * (
        1.0 + math.cos((2.0 / 3.0) * math.acos(-a_star))
    )


def static_time_dilation_equatorial(state: BlackHoleState, radius: float) -> float:
    """Static-clock time dilation in Kerr's equatorial plane (dimensionless).

    g_tt = -(1 - 2 r_g r / Sigma); at theta = pi/2, Sigma = r^2, giving the
    Schwarzschild form dt/dtau = 1/sqrt(1 - 2 r_g/r). Static worldlines do
    NOT exist inside the ergosphere (r <= 2 r_g at the equator), so radii
    at or within epsilon of the EQUATORIAL ERGOSPHERE raise
    CoordinateSingularityError - a physical, not merely coordinate,
    prohibition.
    """
    if isinstance(radius, bool) or not isinstance(radius, (int, float)):
        raise InvalidGeometryInputError(f"Radius must be a real number, got {type(radius).__name__}")
    r = float(radius)
    if math.isnan(r) or math.isinf(r):
        raise InvalidGeometryInputError(f"Radius cannot be NaN or Infinite, got {radius!r}")

    ergo_equator = ergosphere_radius(state, math.pi / 2)
    if r <= ergo_equator + NUMERICAL_HORIZON_EPSILON:
        raise CoordinateSingularityError(
            f"Radius {r!r} m is inside or within epsilon of the equatorial "
            f"ergosphere {ergo_equator!r} m; no static observers exist there."
        )
    return 1.0 / math.sqrt(1.0 - 2.0 * state.gravitational_radius / r)
