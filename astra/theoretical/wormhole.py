"""ASTRA Theoretical - wormhole geometries (mathematical models).

Morris-Thorne metric (SPECULATIVE):
    ds^2 = -e^{2 Phi(r)} dt^2 + (1 - b(r)/r)^-1 dr^2 + r^2 dOmega^2
    b(r): shape function (b(r0) = r0 at the throat, flare-out b'(r0) < 1);
    Phi(r): redshift function (finite). Validation follows Morris & Thorne
    (Am. J. Phys. 56, 395 (1988)).

    Coordinate patch: standard coordinates are singular at the throat
    (g_rr -> inf as r -> r0). Evaluation at or below r0 (including float
    under-penetration r0 - k*ulp) raises DegenerateMetricError. Proper
    radial distance l(r) = int_{r0}^{r} dr'/sqrt(1 - b(r')/r') is provided
    as a deterministic utility (Simpson quadrature on a fixed grid); a full
    l-chart integrator is deferred to the manifold phase.

Einstein-Rosen bridge (THEORETICAL, non-traversable):
    The maximal Schwarzschild extension at a moment of time symmetry. The
    bridge pinches off faster than any causal signal can traverse; the
    implementation delegates the metric to the spacetime layer's
    SchwarzschildMetric (single mathematical implementation) and carries
    THEORETICAL classification plus the non-traversability annotation.
    Its horizon guard applies unchanged.

All models: immutable parameters, deterministic pure functions, SI units.
"""

from __future__ import annotations

import math
from typing import Callable, Dict, Tuple

from astra.spacetime.exceptions import DegenerateMetricError
from astra.spacetime.metric import (
    CHART_SPHERICAL,
    MetricField,
    SpacetimeModel,
    _validate_coords,
)
from astra.theoretical.classification import (
    CLASSIFICATION_NOTES,
    ScientificClassification,
    log_speculative_instantiation,
)
from astra.theoretical.exceptions import (
    FlareOutViolation,
    InvalidGeometryParameterError,
)

# Throat coordinate-singularity band (absolute, metres).
NUMERICAL_THROAT_EPSILON: float = 1.0e-12
# Proper-distance quadrature resolution (deterministic, fixed grid).
PROPER_DISTANCE_STEPS: int = 512


def _validate_callable(fn, name: str) -> Callable[[float], float]:
    if not callable(fn):
        raise InvalidGeometryParameterError(f"{name} must be callable r -> float")
    return fn


def _check_finite_output(fn: Callable[[float], float], r: float, name: str) -> float:
    v = float(fn(r))
    if math.isnan(v) or math.isinf(v):
        raise DegenerateMetricError(
            f"{name}({r!r}) = {v!r} is non-finite; refusing metric evaluation."
        )
    return v


class MorrisThorneMetric(MetricField):
    """Traversable-wormhole mathematical model (SPECULATIVE).

    Physical meaning of parameters:
        throat_radius_m: r0, areal radius of the throat (> 0).
        shape_func: b(r) with b(r0) = r0 (enforced to 1e-9 relative) and
            the flare-out condition b'(r0) < 1 (checked numerically);
            also requires b(r) < r for r > r0 (no horizon of the b-metric).
        redshift_func: Phi(r), finite; default Phi = 0 (zero-tidal-force).

    Scientific status: Requires exotic matter (NEC violation at the
    throat); see astra.theoretical.energy_conditions for the diagnostic.
    """

    model = SpacetimeModel.GENERAL_NUMERICAL
    chart = CHART_SPHERICAL
    classification = ScientificClassification.SPECULATIVE

    def __init__(self, throat_radius_m: float, shape_func: Callable[[float], float],
                 redshift_func: Callable[[float], float] = lambda r: 0.0):
        if isinstance(throat_radius_m, bool) or not isinstance(throat_radius_m, (int, float)) \
                or math.isnan(throat_radius_m) or math.isinf(throat_radius_m) \
                or throat_radius_m <= 0.0:
            raise InvalidGeometryParameterError(
                f"throat_radius_m must be finite and > 0, got {throat_radius_m!r}"
            )
        self._r0 = float(throat_radius_m)
        self._b = _validate_callable(shape_func, "shape_func")
        self._phi = _validate_callable(redshift_func, "redshift_func")
        self._validate_shape_function()
        log_speculative_instantiation(self)

    # -- public read-only views ------------------------------------------
    @property
    def throat_radius_m(self) -> float:
        return self._r0

    @property
    def shape_func(self) -> Callable[[float], float]:
        return self._b

    @property
    def redshift_func(self) -> Callable[[float], float]:
        return self._phi

    # -- model mathematics -------------------------------------------------
    def _validate_shape_function(self) -> None:
        r0 = self._r0
        b0_raw = float(self._b(r0))
        if math.isnan(b0_raw) or math.isinf(b0_raw):
            # Construction-phase failure: caller bug, not a runtime patch issue.
            raise InvalidGeometryParameterError(
                f"b(r0) = {b0_raw!r} is non-finite; shape function invalid."
            )
        b0 = b0_raw
        if abs(b0 - r0) > 1e-9 * r0:
            raise InvalidGeometryParameterError(
                f"Throat condition violated: b(r0) = {b0!r} != r0 = {r0!r}."
            )
        # Numeric flare-out check: b'(r0) < 1 (central difference).
        h = 1e-6 * r0
        bp = (self._b(r0 + h) - self._b(r0 - h)) / (2.0 * h)
        if math.isnan(bp) or math.isinf(bp):
            raise InvalidGeometryParameterError(f"b(r) is not finite near the throat")
        if bp >= 1.0:
            raise FlareOutViolation(
                f"Flare-out violated: b'(r0) = {bp!r} >= 1 (throat would slant outward)."
            )
        # No-trapped-region admissibility away from the throat (sampled).
        for frac in (1.5, 2.0, 5.0, 20.0):
            r = frac * r0
            br = _check_finite_output(self._b, r, "b(r)")
            if br >= r:
                raise InvalidGeometryParameterError(
                    f"b({r!r}) = {br!r} >= r: trapped surface outside the throat."
                )

    def _guard_radius(self, r: float) -> float:
        if r <= self._r0 + NUMERICAL_THROAT_EPSILON:
            raise DegenerateMetricError(
                f"r = {r!r} m is at/inside the throat r0 = {self._r0!r} m "
                "(coordinate singularity of g_rr; float under-penetration is "
                "rejected identically)."
            )
        return r

    def tensor(self, coords) -> Tuple:
        ct, r, theta, phi = _validate_coords(coords, self.chart)
        self._guard_radius(r)
        phi_r = _check_finite_output(self._phi, r, "Phi(r)")
        if abs(phi_r) > 50.0:
            raise DegenerateMetricError(
                f"Redshift function Phi({r!r}) = {phi_r!r} out of analytic range."
            )
        b_r = _check_finite_output(self._b, r, "b(r)")
        one_minus = 1.0 - b_r / r
        if one_minus <= 0.0:
            raise DegenerateMetricError(
                f"1 - b(r)/r = {one_minus!r} <= 0 at r = {r!r}: trapped region."
            )
        g_rr = 1.0 / one_minus
        sin2 = math.sin(theta) ** 2
        return (
            (-math.exp(2.0 * phi_r), 0.0, 0.0, 0.0),
            (0.0, g_rr, 0.0, 0.0),
            (0.0, 0.0, r * r, 0.0),
            (0.0, 0.0, 0.0, r * r * sin2),
        )

    def proper_radial_distance(self, r: float) -> float:
        """l(r) = integral_{r0}^{r} dr'/sqrt(1 - b(r')/r') (m), r >= r0.

        Deterministic composite Simpson quadrature on a fixed 512-node
        grid; the integrand's integrable 1/sqrt singularity at r0 is
        handled by a substitution u = sqrt(r' - r0) documented in the
        phase report. l(r0) = 0 exactly.
        """
        if isinstance(r, bool) or not isinstance(r, (int, float)) \
                or math.isnan(r) or math.isinf(r) or r < self._r0:
            raise InvalidGeometryParameterError(
                f"proper_radial_distance requires r >= r0, got {r!r}"
            )
        if r == self._r0:
            return 0.0

        def integrand(r_prime: float) -> float:
            one_minus = 1.0 - self._b(r_prime) / r_prime
            if one_minus <= 0.0:
                raise DegenerateMetricError(
                    f"1 - b(r)/r <= 0 at r = {r_prime!r}: no proper distance."
                )
            return 1.0 / math.sqrt(one_minus)

        # Simpson on substituted variable u in [0, sqrt(r - r0)]:
        # r'(u) = r0 + u^2, dr' = 2u du. The integrand's 1/u singularity
        # cancels EXACTLY in 2u * integrand, leaving the finite limit
        # g(0) = 2 sqrt(r0 / (1 - b'(r0))) - it must NOT be zeroed.
        h_b = 1e-6 * self._r0
        bp0 = (self._b(self._r0 + h_b) - self._b(self._r0 - h_b)) / (2.0 * h_b)
        g0 = 2.0 * math.sqrt(self._r0 / max(1e-30, 1.0 - bp0))

        def g(u: float) -> float:
            if u == 0.0:
                return g0
            return 2.0 * u * integrand(self._r0 + u * u)

        n = PROPER_DISTANCE_STEPS
        if n % 2:
            n += 1
        u_max = math.sqrt(r - self._r0)
        h = u_max / n
        total = g(0.0) + g(u_max)
        for i in range(1, n):
            total += (4.0 if i % 2 else 2.0) * g(i * h)
        return total * h / 3.0

    def to_dict(self) -> Dict[str, float]:
        """Canonical persistence: defining parameters only (callables are
        factory-supplied and reconstructed by name at the call site)."""
        return {"throat_radius_m": self._r0}

    @classmethod
    def from_dict(cls, data: Dict[str, float], shape_func, redshift_func=None):
        return cls(data["throat_radius_m"], shape_func, redshift_func or (lambda r: 0.0))

    @property
    def classification_note(self) -> str:
        return CLASSIFICATION_NOTES[self.classification]


class EinsteinRosenMetric(MetricField):
    """Einstein-Rosen bridge at time symmetry (THEORETICAL).

    Mathematically the Schwarzschild exterior; the 'bridge' is the maximal
    extension's throat, which pinches off faster than light - nothing can
    traverse. Delegates ALL mathematics to
    ``astra.spacetime.metric.SchwarzschildMetric`` (single implementation);
    horizon/axis guards and coordinate patch apply unchanged.
    """

    model = SpacetimeModel.SCHWARZSCHILD
    chart = CHART_SPHERICAL
    classification = ScientificClassification.THEORETICAL

    def __init__(self, mass_kg: float):
        from astra.spacetime.metric import SchwarzschildMetric
        self._schw = SchwarzschildMetric(mass_kg)  # validates mass

    @property
    def mass_kg(self) -> float:
        return self._schw_mass()

    def _schw_mass(self) -> float:
        return self._schw.rs_m * astra_c_squared() / (2.0 * astra_big_g())

    @property
    def schwarzschild_delegate(self) -> "SchwarzschildMetric":
        return self._schw

    @property
    def non_traversable(self) -> bool:
        """True: the bridge pinches off before any signal can cross."""
        return True

    def tensor(self, coords) -> Tuple:
        return self._schw.tensor(coords)

    def to_dict(self) -> Dict[str, float]:
        return {"mass_kg": self._schw_mass()}

    @classmethod
    def from_dict(cls, data: Dict[str, float]):
        return cls(data["mass_kg"])


def astra_c_squared() -> float:
    from astra.relativity.core import C_SQUARED
    return C_SQUARED


def astra_big_g() -> float:
    from astra.physics.constants import GRAVITATIONAL_CONSTANT
    return GRAVITATIONAL_CONSTANT
