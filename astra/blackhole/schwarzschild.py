"""ASTRA Black-Hole - Schwarzschild subsystem.

Contract: exact geometric relations of the static, spherically symmetric,
uncharged (Schwarzschild) vacuum solution under the test-particle
approximation, with strict coordinate-singularity guards at the horizon.

Mathematical continuity with ``astra.relativity.gr_foundations``: the
Schwarzschild radius and the time-dilation law delegate to the relativity
layer (single implementation), so this subsystem can never drift from the
foundational formulas.

Units: SI (m, s, kg). Deterministic pure functions.
"""

from __future__ import annotations

import math

from astra.blackhole.exceptions import CoordinateSingularityError, InvalidGeometryInputError
from astra.blackhole.models import NUMERICAL_HORIZON_EPSILON
from astra.blackhole.parameters import BlackHoleState, validate_mass_kg
from astra.relativity.gr_foundations import schwarzschild_radius, weak_field_time_dilation


def _validate_outside_horizon(r: float, horizon: float) -> float:
    """Reject non-finite radii and evaluations at/within epsilon of a horizon."""
    if isinstance(r, bool) or not isinstance(r, (int, float)):
        raise InvalidGeometryInputError(f"Radius must be a real number, got {type(r).__name__}")
    radius = float(r)
    if math.isnan(radius) or math.isinf(radius):
        raise InvalidGeometryInputError(f"Radius cannot be NaN or Infinite, got {r!r}")
    if radius <= 0.0:
        raise CoordinateSingularityError(
            "Physical singularity: r = 0 is not a valid evaluation point."
        )
    if radius <= horizon + NUMERICAL_HORIZON_EPSILON:
        raise CoordinateSingularityError(
            f"Radius {radius!r} m is at or within {NUMERICAL_HORIZON_EPSILON!r} m of the "
            f"horizon {horizon!r} m (coordinate singularity); refusing evaluation."
        )
    return radius


def schwarzschild_radius_m(mass_kg: float) -> float:
    """Event-horizon (Schwarzschild) radius r_s = 2GM/c^2 (m).

    Delegates to ``astra.relativity.gr_foundations.schwarzschild_radius``
    for exact continuity with the relativity phase.
    """
    return schwarzschild_radius(validate_mass_kg(mass_kg))


def isco_radius(mass_kg: float) -> float:
    """Innermost Stable Circular Orbit: r_ISCO = 3 r_s = 6 r_g (m)."""
    return 3.0 * schwarzschild_radius_m(mass_kg)


def photon_sphere_radius(mass_kg: float) -> float:
    """Photon sphere: r_ps = 1.5 r_s = 3 r_g (m)."""
    return 1.5 * schwarzschild_radius_m(mass_kg)


def gravitational_time_dilation(state: BlackHoleState, radius: float) -> float:
    """Static-clock time dilation dt/dtau = 1 / sqrt(1 - r_s/r) (dimensionless).

    Delegates to ``astra.relativity.gr_foundations.weak_field_time_dilation``
    after applying the black-hole horizon policy (radius must exceed
    r_s + NUMERICAL_HORIZON_EPSILON), so both layers share one formula.

    Raises CoordinateSingularityError at or inside the horizon guard.
    """
    rs = schwarzschild_radius_m(state.mass_kg)
    _validate_outside_horizon(radius, rs)
    return weak_field_time_dilation(state.mass_kg, radius)


def gravitational_redshift(
    state: BlackHoleState, r_emitter: float, r_observer: float
) -> float:
    """Gravitational redshift z between static radii (dimensionless).

        z = sqrt( (1 - r_s/r_obs) / (1 - r_s/r_em) ) - 1

    z > 0 for the observer above the emitter (photons lose energy climbing
    out), z = 0 for equal radii, z < 0 for blueshift (observer below).

    Both radii must lie outside the horizon guard. The guard also makes the
    P1 defect class impossible: an emitter infinitesimally above r_s can
    never reach the metric function's domain boundary, so no
    ``math domain error`` can occur.

    Returns:
        Redshift z (can be negative for infall/blueshift configurations).
    """
    rs = schwarzschild_radius_m(state.mass_kg)
    _validate_outside_horizon(r_emitter, rs)
    _validate_outside_horizon(r_observer, rs)

    inner_em = 1.0 - rs / r_emitter
    inner_obs = 1.0 - rs / r_observer
    # Belt-and-suspenders: the guards above keep both strictly positive;
    # the clamp only neutralizes pathological last-ulp drift.
    if inner_em < 0.0:
        inner_em = 0.0
    if inner_obs < 0.0:
        inner_obs = 0.0

    return math.sqrt(inner_obs / inner_em) - 1.0
