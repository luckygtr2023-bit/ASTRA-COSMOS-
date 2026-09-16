"""ASTRA Temporal - proper time and time dilation.

Contract: proper time is derived from machinery that ALREADY exists in
ASTRA - this module computes nothing new about metrics:

    - Flat/inertial worldlines: segment-wise
      ``astra.relativity.four_vectors.SpacetimeEvent.proper_time_to``
      (the established relativity convention: ds^2 = -(c dt)^2 + dx^2,
      dtau = sqrt(-ds^2)/c). Null segments contribute exactly 0;
      spacelike segments raise the relativity layer's
      SpacelikeIntervalError (proper time is undefined there).
    - Curved backgrounds: ``astra.spacetime.geodesics.integrate_geodesic``
      parameterized by proper time (u.mu u^mu = -c^2 enforcement built in);
      the geodesic's parameter IS dtau.
    - Velocity dilation: dtau = dt / gamma via
      ``astra.relativity.core.lorentz_factor`` (v < c enforced there).
    - Gravitational dilation: dtau = dt * sqrt(1 - r_s/r) via
      ``astra.relativity.gr_foundations.weak_field_time_dilation``
      (dt/dtau = 1/sqrt(1 - r_s/r)); horizon guards inherited.

Anchors (tested): low v -> tau -> t; inertial flat matches the relativity
convention exactly; null worldline tau = 0; spacelike rejected.

Deterministic pure functions; SI seconds.
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from astra.relativity.core import SPEED_OF_LIGHT, lorentz_factor
from astra.relativity.exceptions import LightSpeedViolation
from astra.relativity.four_vectors import FourVector, SpacetimeEvent
from astra.relativity.gr_foundations import weak_field_time_dilation
from astra.spacetime.events import CHART_CARTESIAN, SpacetimeEvent as ChartEvent
from astra.spacetime.events import Worldline
from astra.temporal.exceptions import InvalidWorldlineError


def _to_relativity_event(event: ChartEvent) -> SpacetimeEvent:
    """Reuse path: spacetime chart event -> relativity FourVector event.

    Cartesian charts map directly (both store ct in metres). Spherical
    charts are converted through the spacetime layer's own transforms.
    """
    if event.chart == CHART_CARTESIAN:
        return SpacetimeEvent(event.ct_m, event.x, event.y, event.z)
    from astra.spacetime.events import spherical_to_cartesian
    x, y, z = spherical_to_cartesian(event.x, event.y, event.z)
    return SpacetimeEvent(event.ct_m, x, y, z)


def flat_proper_time(worldline: Worldline) -> float:
    """Total proper time (s) along a recorded cartesian worldline.

    Sums exact segment proper times using the relativity layer's
    established flat-spacetime convention. Null segments contribute 0.0;
    any spacelike segment raises ``SpacelikeIntervalError`` (proper time
    undefined - never silently clamped).

    Raises:
        InvalidWorldlineError: fewer than 2 samples.
        SpacelikeIntervalError: spacelike segment (via the relativity API).
    """
    if not isinstance(worldline, Worldline):
        raise InvalidWorldlineError("flat_proper_time requires an astra.spacetime.Worldline")
    events = worldline.events
    if len(events) < 2:
        raise InvalidWorldlineError(
            f"worldline needs >= 2 samples for proper time, got {len(events)}"
        )
    total = 0.0
    for a, b in zip(events, events[1:]):
        rel_a = _to_relativity_event(a)
        rel_b = _to_relativity_event(b)
        total += rel_a.proper_time_to(rel_b)  # null -> 0, spacelike -> raises
    return total


def metric_proper_time(
    metric, initial_coords: Sequence[float], initial_four_velocity: Sequence[float],
    proper_time_limit_s: float, steps: int = 400,
):
    """Proper time accumulated along a geodesic of the ACTIVE metric.

    Delegates to ``astra.spacetime.geodesics.integrate_geodesic`` (which
    normalizes u.mu u^mu = -c^2 and integrates in proper time); returns
    the full immutable GeodesicSolution - ``.parameters`` IS dtau, and the
    final chart coordinates allow coordinate-time cross-checks. Horizon
    guards and HorizonCrossingError semantics are inherited unchanged.
    """
    from astra.spacetime.geodesics import integrate_geodesic as _integrate_chart
    return _integrate_chart(
        metric, initial_coords, initial_four_velocity,
        float(proper_time_limit_s), steps=steps,
    )


def velocity_time_dilation(coordinate_time_s: float, velocity_mps) -> float:
    """dtau = dt / gamma for a classical velocity (float magnitude or
    Vector3). Delegates to ``astra.relativity.core.lorentz_factor`` with
    its low-beta Taylor branch (stable for v -> 0) and its
    LightSpeedViolation for v >= c. Deterministic."""
    if isinstance(coordinate_time_s, bool) or not isinstance(coordinate_time_s, (int, float)) \
            or math.isnan(float(coordinate_time_s)) or math.isinf(float(coordinate_time_s)) \
            or float(coordinate_time_s) < 0.0:
        from astra.temporal.exceptions import InvalidTemporalStateError
        raise InvalidTemporalStateError(
            f"coordinate_time_s must be finite >= 0, got {coordinate_time_s!r}"
        )
    gamma = lorentz_factor(velocity_mps)
    return float(coordinate_time_s) / gamma


def gravitational_time_dilation(coordinate_time_s: float, mass_kg: float,
                                radius_m: float) -> float:
    """dtau = dt * sqrt(1 - r_s/r) for a static clock at radius r.

    Delegates to ``astra.relativity.gr_foundations.weak_field_time_``
    ``dilation`` (dt/dtau); horizon/degenerate guards are inherited and
    raise ``DegenerateMetricError`` unchanged.
    """
    if isinstance(coordinate_time_s, bool) or not isinstance(coordinate_time_s, (int, float)) \
            or math.isnan(float(coordinate_time_s)) or math.isinf(float(coordinate_time_s)) \
            or float(coordinate_time_s) < 0.0:
        from astra.temporal.exceptions import InvalidTemporalStateError
        raise InvalidTemporalStateError(
            f"coordinate_time_s must be finite >= 0, got {coordinate_time_s!r}"
        )
    dilation_dt_dtau = weak_field_time_dilation(mass_kg, radius_m)
    return float(coordinate_time_s) / dilation_dt_dtau
