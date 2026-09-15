"""ASTRA Spacetime - curvature tensors.

Contract: Riemann, Ricci, Ricci scalar, Einstein tensor and the geodesic-
deviation (tidal) operator, all derived from the Levi-Civita connection.

Sign conventions (documented, ASTRA-standard):
    R^rho_{sigma mu nu} = d_mu Gamma^rho_{nu sigma} - d_nu Gamma^rho_{mu sigma}
                          + Gamma^rho_{mu lam} Gamma^lam_{nu sigma}
                          - Gamma^rho_{nu lam} Gamma^lam_{mu sigma}
    Ricci: R_{mu nu} = R^lambda_{mu lambda nu}
    Einstein: G_{mu nu} = R_{mu nu} - 1/2 R g_{mu nu}
    Geodesic deviation: D^2 X^mu / dtau^2 = -R^mu_{nu rho sigma} U^nu X^rho U^sigma
    (positive radial curvature focuses/stretch geodesics; vacuum checks:
    Schwarzschild R_mu_nu = 0, R = 0 while R^rho_{sigma mu nu} != 0).

All tensors are immutable nested tuples; indices (mu, nu, ...) in 0..3.
Validation anchors: Kretschmann scalar K = R_{rho sigma mu nu} R^{rho sigma mu nu}
= 12 r_s^2 / r^6 for Schwarzschild (exact analytic reference).
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple

from astra.spacetime.connection import Gamma, christoffel_derivative, christoffel_symbols
from astra.spacetime.metric import Coords, MetricField, _validate_coords

Tensor4 = Tuple[Tuple[float, float, float, float], ...]
RiemannTensor = Tuple[Tensor4, Tensor4, Tensor4, Tensor4]  # 4x4x4x4 [rho][sigma][mu][nu]


def riemann_tensor(metric: MetricField, coords: Sequence[float]) -> RiemannTensor:
    """R^rho_{sigma mu nu} at the given coordinates."""
    x = _validate_coords(coords, metric.chart)
    gamma = christoffel_symbols(metric, x)
    dgamma = christoffel_derivative(metric, x)

    r = [[[[0.0] * 4 for _ in range(4)] for _ in range(4)] for _ in range(4)]
    for rho in range(4):
        for sigma in range(4):
            for mu in range(4):
                for nu in range(4):
                    acc = dgamma[mu][rho][nu][sigma] - dgamma[nu][rho][mu][sigma]
                    for lam in range(4):
                        acc += (gamma[rho][mu][lam] * gamma[lam][nu][sigma]
                                - gamma[rho][nu][lam] * gamma[lam][mu][sigma])
                    r[rho][sigma][mu][nu] = acc
    return tuple(tuple(tuple(tuple(q) for q in plane) for plane in block) for block in r)


def riemann_all_lower(metric: MetricField, coords: Sequence[float]) -> RiemannTensor:
    """Fully covariant Riemann R_{rho sigma mu nu} = g_{rho lam} R^lam_{sigma mu nu}."""
    x = _validate_coords(coords, metric.chart)
    r_up = riemann_tensor(metric, x)
    g_dn = metric.tensor(x)
    out = [[[[0.0] * 4 for _ in range(4)] for _ in range(4)] for _ in range(4)]
    for rho in range(4):
        for sigma in range(4):
            for mu in range(4):
                for nu in range(4):
                    acc = 0.0
                    for lam in range(4):
                        acc += g_dn[rho][lam] * r_up[lam][sigma][mu][nu]
                    out[rho][sigma][mu][nu] = acc
    return tuple(tuple(tuple(tuple(q) for q in plane) for plane in block) for block in out)


def ricci_tensor(metric: MetricField, coords: Sequence[float]) -> Tensor4:
    """Ricci tensor R_{mu nu} = R^lambda_{mu lambda nu}."""
    x = _validate_coords(coords, metric.chart)
    r = riemann_tensor(metric, x)
    return tuple(
        tuple(sum(r[lam][mu][lam][nu] for lam in range(4)) for nu in range(4))
        for mu in range(4)
    )


def ricci_scalar(metric: MetricField, coords: Sequence[float]) -> float:
    """Ricci scalar R = g^{mu nu} R_{mu nu}."""
    x = _validate_coords(coords, metric.chart)
    r_down = ricci_tensor(metric, x)
    g_up = metric.inverse(x)
    return sum(
        g_up[mu][nu] * r_down[mu][nu] for mu in range(4) for nu in range(4)
    )


def einstein_tensor(metric: MetricField, coords: Sequence[float]) -> Tensor4:
    """Einstein tensor G_{mu nu} = R_{mu nu} - 1/2 R g_{mu nu}.

    Vacuum anchor: identically zero for Schwarzschild/Kerr exteriors.
    """
    x = _validate_coords(coords, metric.chart)
    r_down = ricci_tensor(metric, x)
    big_r = ricci_scalar(metric, x)
    g_dn = metric.tensor(x)
    return tuple(
        tuple(r_down[mu][nu] - 0.5 * big_r * g_dn[mu][nu] for nu in range(4))
        for mu in range(4)
    )


def kretschmann_scalar(metric: MetricField, coords: Sequence[float]) -> float:
    """K = R_{rho sigma mu nu} R^{rho sigma mu nu}.

    Schwarzschild exact reference: K = 12 r_s^2 / r^6 (used by the tests to
    validate the whole connection->curvature chain). Indices are raised
    SEQUENTIALLY, one slot at a time (slot 0, then 1, then 2, then 3);
    raising the same slot repeatedly would leave metric factors in the
    other slots and corrupt the invariant.
    """
    x = _validate_coords(coords, metric.chart)
    r_dddd = riemann_all_lower(metric, x)
    g_up = metric.inverse(x)

    t = r_dddd
    for slot in range(4):
        out = [[[[0.0] * 4 for _ in range(4)] for _ in range(4)] for _ in range(4)]
        for i0 in range(4):
            for i1 in range(4):
                for i2 in range(4):
                    for i3 in range(4):
                        idx = (i0, i1, i2, i3)
                        acc = 0.0
                        for lam in range(4):
                            s0, s1, s2, s3 = idx[:slot] + (lam,) + idx[slot + 1:]
                            acc += g_up[idx[slot]][lam] * t[s0][s1][s2][s3]
                        out[i0][i1][i2][i3] = acc
        t = tuple(tuple(tuple(tuple(q) for q in plane) for plane in block) for block in out)

    return sum(
        r_dddd[i0][i1][i2][i3] * t[i0][i1][i2][i3]
        for i0 in range(4) for i1 in range(4)
        for i2 in range(4) for i3 in range(4)
    )


def tidal_acceleration(
    metric: MetricField,
    coords: Sequence[float],
    four_velocity: Sequence[float],
    separation: Sequence[float],
) -> Tuple[float, float, float, float]:
    """Instantaneous geodesic-deviation acceleration (relative motion).

    A^mu = -R^mu_{nu rho sigma} U^nu X^rho U^sigma, where U is the fiducial
    4-velocity (ct-units: m/s along x^0) and X the separation vector
    (coordinate components). Positive radial coefficient = stretching.
    """
    x = _validate_coords(coords, metric.chart)
    u = tuple(float(v) for v in four_velocity)
    xi = tuple(float(v) for v in separation)
    if len(u) != 4 or len(xi) != 4:
        from astra.spacetime.exceptions import InvalidCoordinateError
        raise InvalidCoordinateError("four_velocity and separation must be 4-tuples")

    r_up = riemann_tensor(metric, x)
    return tuple(
        -sum(
            r_up[mu][nu][rho][sigma] * u[nu] * xi[rho] * u[sigma]
            for nu in range(4)
            for rho in range(4)
            for sigma in range(4)
        )
        for mu in range(4)
    )
