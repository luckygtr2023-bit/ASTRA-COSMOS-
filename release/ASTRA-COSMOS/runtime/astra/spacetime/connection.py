"""ASTRA Spacetime - Levi-Civita connection (Christoffel symbols).

Contract: Gamma^rho_{mu nu} = 1/2 g^{rho sigma}
(d_mu g_{sigma nu} + d_nu g_{sigma mu} - d_sigma g_{mu nu}), torsion-free,
metric-compatible. Built generically from a MetricField's (analytic or
numeric) derivative tensor, so analytic models stay exact and arbitrary
fields fall back to 4th-order central differences.

Also provides the numerically differentiated Christoffel field
(d_gamma Gamma^rho_{mu nu}) required by the curvature engine.
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from astra.spacetime.metric import DIFF_STEP, Coords, MetricField, _validate_coords

Gamma = Tuple[Tuple[Tuple[float, float, float, float], ...], ...]  # 4x4x4


def christoffel_symbols(metric: MetricField, coords: Sequence[float]) -> Gamma:
    """Gamma^rho_{mu nu} at the given coordinates (4x4x4, symmetric in mu/nu).

    Raises DegenerateMetricError / InvalidCoordinateError through the metric
    evaluation when the point lies outside the coordinate patch.
    """
    x = _validate_coords(coords, metric.chart)
    g_up = metric.inverse(x)          # raises on singular metric
    dg = metric.derivative(x)

    gamma = [[[0.0] * 4 for _ in range(4)] for _ in range(4)]
    for rho in range(4):
        for mu in range(4):
            for nu in range(mu, 4):
                acc = 0.0
                for sigma in range(4):
                    acc += g_up[rho][sigma] * (
                        dg[mu][sigma][nu] + dg[nu][sigma][mu] - dg[sigma][mu][nu]
                    )
                acc *= 0.5
                gamma[rho][mu][nu] = acc
                gamma[rho][nu][mu] = acc
    return tuple(tuple(tuple(row) for row in plane) for plane in gamma)


def christoffel_derivative(
    metric: MetricField, coords: Sequence[float]
) -> Tuple[Gamma, Gamma, Gamma, Gamma]:
    """Partial derivatives d_gamma Gamma^rho_{mu nu} (index order [gamma]).

    4th-order central differences of the Christoffel field with a relative
    step (h = DIFF_STEP * max(|x_gamma|, 1)). For analytic models the field
    itself is exact, so only this differentiation step introduces truncation
    error; documented and bounded by the curvature tests.
    """
    x = _validate_coords(coords, metric.chart)
    out = []
    for a in range(4):
        h = DIFF_STEP * max(abs(x[a]), 1.0)

        def gamma_at(offset: float) -> Gamma:
            xp = list(x)
            xp[a] += offset
            return christoffel_symbols(metric, xp)

        gp, gm = gamma_at(h), gamma_at(-h)
        g2p, g2m = gamma_at(2.0 * h), gamma_at(-2.0 * h)
        plane = [[[0.0] * 4 for _ in range(4)] for _ in range(4)]
        for rho in range(4):
            for mu in range(4):
                for nu in range(4):
                    plane[rho][mu][nu] = (
                        -g2p[rho][mu][nu] + 8.0 * gp[rho][mu][nu]
                        - 8.0 * gm[rho][mu][nu] + g2m[rho][mu][nu]
                    ) / (12.0 * h)
        out.append(tuple(tuple(tuple(row) for row in p) for p in plane))
    return tuple(out)
