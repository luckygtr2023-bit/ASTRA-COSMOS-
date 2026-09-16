"""ASTRA Spacetime - causal structure.

Contract: causal classification is driven by the ACTIVE metric
ds^2 = g_mu_nu dx^mu dx^nu, never by hardcoded flat-Minkowski logic.

Scope note (honest approximation): for curved backgrounds a finite
coordinate separation does not have a single invariant interval; the local
interval here is the FIRST-ORDER (linearized) evaluation
ds^2 ~ g_mu_nu(x_mid) dx^mu dx^nu at the midpoint. For Minkowski it is
exact; for curved charts it is the local classification. Finite proper
times along worldlines come from geodesic integration, not from this
shortcut. Null-direction helpers support diagonal metrics (documented
limitation).
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from astra.relativity.four_vectors import SpacetimeIntervalType
from astra.spacetime.metric import MetricField, _validate_coords


def local_interval(
    metric: MetricField, coords_a: Sequence[float], coords_b: Sequence[float]
) -> float:
    """Linearized interval ds^2 ~ g_mu_nu(x_mid) dx^mu dx^nu (m^2).

    Exact for MinkowskiMetric; local first-order approximation otherwise.
    """
    xa = _validate_coords(coords_a, metric.chart)
    xb = _validate_coords(coords_b, metric.chart)
    mid = tuple(0.5 * (a + b) for a, b in zip(xa, xb))
    dx = tuple(b - a for a, b in zip(xa, xb))
    g = metric.tensor(mid)
    total = 0.0
    for mu in range(4):
        for nu in range(4):
            total += g[mu][nu] * dx[mu] * dx[nu]
    return total


def classify_interval(
    metric: MetricField, coords_a: Sequence[float], coords_b: Sequence[float],
    tolerance: float = 1.0e-9,
) -> SpacetimeIntervalType:
    """Classify a separation as TIMELIKE, SPACELIKE or NULL via the metric."""
    ds2 = local_interval(metric, coords_a, coords_b)
    if ds2 < -tolerance:
        return SpacetimeIntervalType.TIMELIKE
    if ds2 > tolerance:
        return SpacetimeIntervalType.SPACELIKE
    return SpacetimeIntervalType.NULL


def null_ray_directions(
    metric: MetricField,
    coords: Sequence[float],
    spatial_direction: Sequence[float],
) -> Tuple[Tuple[float, float, float, float], Tuple[float, float, float, float]]:
    """Future/past null tangents along a spatial direction (DIAGONAL metrics).

    For a diagonal metric, the null condition g_00 (u^0)^2 + sum_i g_ii (u^i)^2 = 0
    with u^i proportional to the given direction gives
    u^0 = sqrt( -sum_i g_ii (u^i)^2 / g_00 )  (g_00 < 0 outside horizons).

    Returns (future, past) tangent 4-tuples in chart coordinates, normalized
    so the spatial part follows ``spatial_direction``'s proportions.
    Raises NotImplementedError for non-diagonal metrics (e.g. Kerr's g_tph),
    documented limitation of this phase.
    """
    x = _validate_coords(coords, metric.chart)
    direction = tuple(float(v) for v in spatial_direction)
    if len(direction) != 3:
        from astra.spacetime.exceptions import InvalidCoordinateError
        raise InvalidCoordinateError("spatial_direction must be a 3-tuple")
    if all(v == 0.0 for v in direction):
        from astra.spacetime.exceptions import InvalidCoordinateError
        raise InvalidCoordinateError("spatial_direction must be nonzero")

    g = metric.tensor(x)
    off_diagonal = any(
        g[mu][nu] != 0.0 for mu in range(4) for nu in range(4) if mu != nu
    )
    if off_diagonal:
        raise NotImplementedError(
            "null_ray_directions currently supports diagonal metrics only "
            "(off-diagonal g_0phi present); full cone tracing is deferred."
        )

    spatial_sq = sum(g[i + 1][i + 1] * direction[i] ** 2 for i in range(3))
    if spatial_sq < 0.0 or g[0][0] >= 0.0:
        from astra.spacetime.exceptions import DegenerateMetricError
        raise DegenerateMetricError(
            "Null directions require g_00 < 0 and a positive-definite spatial block."
        )
    u0 = math.sqrt(-spatial_sq / g[0][0])
    future = (u0, direction[0], direction[1], direction[2])
    past = (-u0, direction[0], direction[1], direction[2])
    return (future, past)
