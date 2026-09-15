"""ASTRA Spacetime - metric fields.

Contract: covariant metric tensors g_mu_nu on the (-,+,+,+) signature,
index 0 temporal (ct, metres), indices 1-3 spatial. Determinant and inverse
via ``astra.mathematics.matrices.Matrix4`` (no math duplication).

Charts:
    MinkowskiMetric         : cartesian (ct, x, y, z)
    SchwarzschildMetric     : spherical (ct, r, theta, phi), ANALYTIC derivatives
    KerrMetric              : Boyer-Lindquist (ct, r, theta, phi), numeric derivatives
    NumericalMetric         : user-supplied g_mu_nu(x) field, numeric derivatives

Analytic derivatives are exact first partials d_a g_mu_nu (4x4x4, index
order [a][mu][nu]); they keep Christoffel/Riemann evaluations exact for the
analytic models. Arbitrary fields fall back to 4th-order central
differences with a relative step (h = 1e-5 * max(|x_a|, 1)).

Coordinate-patch guards: evaluation at/inside a horizon or on the polar
axis (theta = 0, sin(theta) = 0) raises DegenerateMetricError instead of
emitting inf/NaN tensors.

Deterministic pure functions; SI units; test-particle approximation (fixed
background, no backreaction).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, Sequence, Tuple

from astra.mathematics.matrices import Matrix4
from astra.blackhole.kerr import horizons as _bh_horizons
from astra.blackhole.parameters import BlackHoleState as _BlackHoleState
from astra.blackhole.schwarzschild import (
    schwarzschild_radius_m as _bh_schwarzschild_radius_m,
)
from astra.spacetime.events import CHART_CARTESIAN, CHART_SPHERICAL
from astra.spacetime.exceptions import (
    DegenerateMetricError,
    InvalidCoordinateError,
)

Coords = Tuple[float, float, float, float]
Tensor4 = Tuple[Tuple[float, float, float, float], ...]          # 4x4
DerivTensor = Tuple[Tensor4, Tensor4, Tensor4, Tensor4]          # 4x4x4

# Relative numerical-differentiation step (handoff section 15).
DIFF_STEP: float = 1.0e-5
# Determinant guard relative to the fourth power of the component scale.
DET_REL_TOL: float = 1.0e-14


class SpacetimeModel(Enum):
    """Fixed-background metric model in use."""

    MINKOWSKI = "MINKOWSKI"
    SCHWARZSCHILD = "SCHWARZSCHILD"
    KERR = "KERR"
    GENERAL_NUMERICAL = "GENERAL_NUMERICAL"


def _validate_coords(coords: Sequence[float], chart: str) -> Coords:
    if coords is None or len(tuple(coords)) != 4:
        raise InvalidCoordinateError(
            f"Coordinates must be a 4-tuple, got {coords!r}"
        )
    values = []
    for i, c in enumerate(coords):
        if isinstance(c, bool) or not isinstance(c, (int, float)):
            raise InvalidCoordinateError(f"Coordinate {i} must be a real number, got {c!r}")
        v = float(c)
        if math.isnan(v) or math.isinf(v):
            raise InvalidCoordinateError(f"Coordinate {i} cannot be NaN or Infinite")
        values.append(v)
    if chart == CHART_SPHERICAL:
        r, theta = values[1], values[2]
        if r <= 0.0:
            raise DegenerateMetricError(
                f"r = {r!r} is at/inside the physical singularity (r must be > 0)."
            )
        if theta <= 0.0 or theta >= math.pi:
            raise DegenerateMetricError(
                f"theta = {theta!r} lies on the polar axis (sin(theta) = 0, det g = 0)."
            )
    return tuple(values)


def _to_matrix4(tensor: Tensor4) -> Matrix4:
    return Matrix4(*[component for row in tensor for component in row])


class MetricField(ABC):
    """Abstract fixed-background metric field.

    Conventions: signature (-,+,+,+); coordinates x^mu = (ct, spatial);
    covariant components g_mu_nu; determinant and inverse via the ASTRA
    mathematics layer. Immutable: subclasses carry only constructor
    parameters (mass, spin, field callable).
    """

    model: SpacetimeModel
    chart: str

    @abstractmethod
    def tensor(self, coords: Sequence[float]) -> Tensor4:
        """Covariant metric g_mu_nu at the given coordinates."""

    def derivative(self, coords: Sequence[float]) -> DerivTensor:
        """First partials d_a g_mu_nu.

        Default: 4th-order central differences of :meth:`tensor`. Analytic
        models override this with exact partials.
        """
        x = _validate_coords(coords, self.chart)
        d = []
        for a in range(4):
            h = DIFF_STEP * max(abs(x[a]), 1.0)
            xp = list(x); xp[a] += h
            xm = list(x); xm[a] -= h
            x2p = list(x); x2p[a] += 2.0 * h
            x2m = list(x); x2m[a] -= 2.0 * h
            gp, gm = self.tensor(xp), self.tensor(xm)
            g2p, g2m = self.tensor(x2p), self.tensor(x2m)
            d.append(tuple(
                tuple(
                    (-g2p[mu][nu] + 8.0 * gp[mu][nu] - 8.0 * gm[mu][nu] + g2m[mu][nu])
                    / (12.0 * h)
                    for nu in range(4)
                )
                for mu in range(4)
            ))
        return tuple(d)

    def determinant(self, coords: Sequence[float]) -> float:
        """det(g_mu_nu) at the given coordinates."""
        return _to_matrix4(self.tensor(coords)).determinant()

    def inverse(self, coords: Sequence[float]) -> Tensor4:
        """Contravariant metric g^mu_nu at the given coordinates.

        Scale-invariant strategy: normalize g by D = diag(s_i) with
        s_i = sqrt(|g_ii|) so the normalized determinant is O(1) for any
        healthy metric regardless of coordinate units (r^2-type angular
        components make raw determinants unit-dependent), invert with the
        mathematics layer's Matrix4, then rescale back. This catches true
        singularities without false positives from raw component scale.
        """
        x = _validate_coords(coords, self.chart)
        t = self.tensor(x)
        max_abs = max(abs(v) for row in t for v in row)
        if max_abs == 0.0:
            raise DegenerateMetricError(f"Zero metric at coordinates {x!r}.")
        scale = []
        for i in range(4):
            s = abs(t[i][i])
            scale.append(math.sqrt(s) if s > 0.0 else math.sqrt(max_abs))
        gtilde = tuple(
            tuple(t[i][j] / (scale[i] * scale[j]) for j in range(4)) for i in range(4)
        )
        m = _to_matrix4(gtilde)
        det_t = m.determinant()
        if not math.isfinite(det_t) or abs(det_t) <= DET_REL_TOL:
            raise DegenerateMetricError(
                f"Metric determinant ~ 0 at coordinates {x!r}; cannot invert."
            )
        try:
            inv = m.inverse()
        except ValueError as exc:
            raise DegenerateMetricError(
                f"Metric is singular at coordinates {x!r}: {exc}"
            ) from exc
        tt = inv.to_tuple()
        inv_tilde = tuple(tuple(tt[r * 4 + c] for c in range(4)) for r in range(4))
        # g = D g~ D  =>  g^-1 = D^-1 g~^-1 D^-1  (rescale by DIVISION).
        return tuple(
            tuple(inv_tilde[i][j] / (scale[i] * scale[j]) for j in range(4)) for i in range(4)
        )

    def is_finite_at(self, coords: Sequence[float]) -> bool:
        try:
            t = self.tensor(coords)
        except SpacetimeError if False else Exception:
            return False
        return all(math.isfinite(v) for row in t for v in row)


class MinkowskiMetric(MetricField):
    """Flat spacetime: ds^2 = -(dct)^2 + dx^2 + dy^2 + dz^2 (everywhere)."""

    model = SpacetimeModel.MINKOWSKI
    chart = CHART_CARTESIAN

    def tensor(self, coords: Sequence[float]) -> Tensor4:
        _validate_coords(coords, self.chart)
        return (
            (-1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )

    def derivative(self, coords: Sequence[float]) -> DerivTensor:
        _validate_coords(coords, self.chart)
        zero = ((0.0,) * 4,) * 4
        return (zero, zero, zero, zero)


class SchwarzschildMetric(MetricField):
    """Static, spherically symmetric vacuum metric in (ct, r, theta, phi).

    g_tt = -(1 - r_s/r), g_rr = (1 - r_s/r)^-1, g_thth = r^2,
    g_phph = r^2 sin^2(theta); all off-diagonals zero.

    r_s comes from the black-hole layer's single implementation
    (astra.blackhole.schwarzschild.schwarzschild_radius_m) - no duplication.
    ANALYTIC derivatives (exact partials).
    """

    model = SpacetimeModel.SCHWARZSCHILD
    chart = CHART_SPHERICAL

    def __init__(self, mass_kg: float):
        self.rs_m = _bh_schwarzschild_radius_m(mass_kg)  # validates mass

    def _f(self, r: float) -> float:
        """Metric factor f = 1 - r_s/r, guarded to the coordinate patch."""
        if r <= self.rs_m:
            raise DegenerateMetricError(
                f"r = {r!r} m is at/inside the Schwarzschild horizon r_s = {self.rs_m!r} m "
                "(coordinate singularity); evaluation refused."
            )
        return 1.0 - self.rs_m / r

    def tensor(self, coords: Sequence[float]) -> Tensor4:
        ct, r, theta, phi = _validate_coords(coords, self.chart)
        f = self._f(r)
        sin2 = math.sin(theta) ** 2
        return (
            (-f, 0.0, 0.0, 0.0),
            (0.0, 1.0 / f, 0.0, 0.0),
            (0.0, 0.0, r * r, 0.0),
            (0.0, 0.0, 0.0, r * r * sin2),
        )

    def derivative(self, coords: Sequence[float]) -> DerivTensor:
        ct, r, theta, phi = _validate_coords(coords, self.chart)
        f = self._f(r)  # also guards the patch
        zero = ((0.0,) * 4,) * 4

        d00 = -self.rs_m / (r * r)                          # d_r g_tt
        d11 = -self.rs_m / (r * r * f * f)                  # d_r g_rr
        d22_r = 2.0 * r                                     # d_r g_thth
        sin_t, cos_t = math.sin(theta), math.cos(theta)
        d33_r = 2.0 * r * sin_t * sin_t                     # d_r g_phph
        d33_t = 2.0 * r * r * sin_t * cos_t                 # d_theta g_phph

        dr = ((d00, 0.0, 0.0, 0.0),
              (0.0, d11, 0.0, 0.0),
              (0.0, 0.0, d22_r, 0.0),
              (0.0, 0.0, 0.0, d33_r))
        dt = ((0.0,) * 4,) * 4
        dth = (
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, d33_t),
        )
        dph = ((0.0,) * 4,) * 4
        return (dt, dr, dth, dph)


class KerrMetric(MetricField):
    """Stationary, axisymmetric rotating vacuum metric (Boyer-Lindquist).

    Standard (-,+,+,+) components with r_g = GM/c^2, a = a* r_g,
    Sigma = r^2 + a^2 cos^2(theta), Delta = r^2 - 2 r_g r + a^2:
        g_tt    = -(1 - 2 r_g r / Sigma)
        g_rr    = Sigma / Delta
        g_thth  = Sigma
        g_tph   = -2 a r_g r sin^2(theta) / Sigma
        g_phph  = ((r^2 + a^2)^2 - a^2 Delta sin^2(theta)) sin^2(theta) / Sigma

    Limits: a = 0 reproduces Schwarzschild exactly. Derivatives are numeric
    (documented performance/precision limitation of this phase). Coordinate
    patch guard: r must exceed the outer horizon r_+.
    """

    model = SpacetimeModel.KERR
    chart = CHART_SPHERICAL

    def __init__(self, mass_kg: float, spin_param: float):
        self._state = _BlackHoleState(mass_kg=mass_kg, spin_param=spin_param)  # validates
        self.r_plus_m, _ = _bh_horizons(self._state)

    @property
    def r_g(self) -> float:
        return self._state.gravitational_radius

    @property
    def a(self) -> float:
        return self._state.spin_length

    def _delta(self, r: float) -> float:
        if r <= self.r_plus_m:
            raise DegenerateMetricError(
                f"r = {r!r} m is at/inside the outer Kerr horizon r_+ = {self.r_plus_m!r} m "
                "(coordinate singularity); evaluation refused."
            )
        return r * r - 2.0 * self.r_g * r + self.a * self.a

    def tensor(self, coords: Sequence[float]) -> Tensor4:
        ct, r, theta, phi = _validate_coords(coords, self.chart)
        delta = self._delta(r)
        sin_t, cos_t = math.sin(theta), math.cos(theta)
        sin2 = sin_t * sin_t
        sigma = r * r + self.a * self.a * cos_t * cos_t
        g_tt = -(1.0 - 2.0 * self.r_g * r / sigma)
        g_rr = sigma / delta
        g_thth = sigma
        g_tph = -2.0 * self.a * self.r_g * r * sin2 / sigma
        g_phph = ((r * r + self.a * self.a) ** 2
                  - self.a * self.a * delta * sin2) * sin2 / sigma
        return (
            (g_tt, 0.0, 0.0, g_tph),
            (0.0, g_rr, 0.0, 0.0),
            (0.0, 0.0, g_thth, 0.0),
            (g_tph, 0.0, 0.0, g_phph),
        )


class NumericalMetric(MetricField):
    """Arbitrary user-supplied covariant metric field g_mu_nu(x).

    ``field_callable`` maps a 4-tuple to a 4x4 row-major nested sequence.
    Derivatives are numeric 4th-order central differences. The chart label
    is free-form; no patch guards are implied (the determinant guard in
    :meth:`MetricField.inverse` still applies).
    """

    model = SpacetimeModel.GENERAL_NUMERICAL

    def __init__(self, field_callable: Callable[[Sequence[float]], Sequence[Sequence[float]]],
                 chart: str = CHART_CARTESIAN):
        if not callable(field_callable):
            raise InvalidCoordinateError("NumericalMetric requires a callable field")
        self._field = field_callable
        self.chart = chart

    def tensor(self, coords: Sequence[float]) -> Tensor4:
        x = _validate_coords(coords, self.chart)
        raw = self._field(x)
        rows = []
        for r in range(4):
            if len(tuple(raw[r])) != 4:
                raise InvalidCoordinateError(f"Metric row {r} must have 4 components")
            rows.append(tuple(float(v) for v in raw[r]))
            for v in rows[-1]:
                if math.isnan(v) or math.isinf(v):
                    raise InvalidCoordinateError("Metric field produced NaN/Inf components")
        return tuple(rows)
