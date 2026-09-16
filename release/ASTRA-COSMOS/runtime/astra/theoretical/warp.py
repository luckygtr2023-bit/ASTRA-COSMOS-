"""ASTRA Theoretical - Alcubierre warp geometry (SPECULATIVE mathematical model).

Metric (Alcubierre 1994), 1D shift along +x with the bubble centered at
the origin of this fixed background:

    ds^2 = -dt^2 + (dx - v_s f(r_s) dt)^2 + dy^2 + dz^2
    r_s  = sqrt(x^2 + y^2 + z^2)
    f(r_s) = [tanh(sigma (r_s + R)) - tanh(sigma (r_s - R))] / (2 tanh(sigma R))

Components (cartesian chart, x^mu = (ct, x, y, z)):
    g_tt = v_s^2 f^2 - 1,  g_tx = -v_s f (metres),  g_xx = g_yy = g_zz = 1.

Scientific boundary (handoff section 2.B, honored verbatim): v_s is a
COORDINATE parameter defining the metric deformation - the geometry
translates relative to distant observers - NOT a local massive-particle
velocity. Local light cones inside the bubble remain perfectly causal;
massive-particle speeds stay < c locally (enforced by the standard
g(u,u) = -c^2 normalization in astra.spacetime.api.cartesian_state_to_chart,
which raises LightSpeedViolation exactly as everywhere else in ASTRA).

Numerical policy: the wall steepness sigma is capped at
MAX_WARP_WALL_STEEPNESS = 1e4 (1/m). At the cap the numeric-differentiation
path of the spacetime layer still resolves the wall (step h ~ 1e-5 * scale
< wall width ~ 1/sigma); steeper requests are rejected at construction
rather than producing cancellation-poisoned Christoffel symbols.

Determinant anchor: det(g) = -1 EXACTLY for every (v_s, R, sigma)
(Lanczos form) - used as a hard invariant in the tests.

Immutable parameters; deterministic pure functions; SI units.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from astra.spacetime.metric import (
    CHART_CARTESIAN,
    MetricField,
    SpacetimeModel,
    _validate_coords,
)
from astra.theoretical.classification import (
    ScientificClassification,
    log_speculative_instantiation,
)
from astra.theoretical.exceptions import InvalidGeometryParameterError
MAX_WARP_WALL_STEEPNESS: float = 1.0e4  # 1/m


class AlcubierreMetric(MetricField):
    """Alcubierre warp-bubble mathematical model (SPECULATIVE)."""

    model = SpacetimeModel.GENERAL_NUMERICAL
    chart = CHART_CARTESIAN
    classification = ScientificClassification.SPECULATIVE

    def __init__(self, velocity: float, radius_m: float, wall_steepness: float):
        for name, value in (("velocity", velocity), ("radius_m", radius_m),
                            ("wall_steepness", wall_steepness)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or math.isnan(value) or math.isinf(value):
                raise InvalidGeometryParameterError(
                    f"{name} must be finite, got {value!r}"
                )
        if radius_m <= 0.0:
            raise InvalidGeometryParameterError(
                f"radius_m must be > 0, got {radius_m!r}"
            )
        if wall_steepness <= 0.0:
            raise InvalidGeometryParameterError(
                f"wall_steepness must be > 0, got {wall_steepness!r}"
            )
        if wall_steepness > MAX_WARP_WALL_STEEPNESS:
            raise InvalidGeometryParameterError(
                f"wall_steepness {wall_steepness!r} 1/m exceeds the numerical "
                f"safety cap MAX_WARP_WALL_STEEPNESS = {MAX_WARP_WALL_STEEPNESS!r} "
                "1/m (thinner walls produce cancellation-poisoned derivatives)."
            )
        self._v = float(velocity)
        self._r = float(radius_m)
        self._sigma = float(wall_steepness)
        log_speculative_instantiation(self)

    @property
    def velocity(self) -> float:
        return self._v

    @property
    def radius_m(self) -> float:
        return self._r

    @property
    def wall_steepness(self) -> float:
        return self._sigma

    def shape_function(self, r_s: float) -> float:
        """Top-hat f(r_s) in [0, 1]: 1 inside the bubble, 0 far outside."""
        s = self._sigma
        R = self._r
        denom = 2.0 * math.tanh(s * R)
        return (math.tanh(s * (r_s + R)) - math.tanh(s * (r_s - R))) / denom

    def bubble_radius(self, x: float, y: float, z: float) -> float:
        return math.sqrt(x * x + y * y + z * z)

    def tensor(self, coords) -> Tuple:
        ct, x, y, z = _validate_coords(coords, self.chart)
        f = self.shape_function(self.bubble_radius(x, y, z))
        vf = self._v * f
        return (
            (vf * vf - 1.0, -vf, 0.0, 0.0),
            (-vf, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )

    def to_dict(self) -> Dict[str, float]:
        """Canonical persistence: defining parameters + classification only."""
        return {"velocity": self._v, "radius_m": self._r,
                "wall_steepness": self._sigma}

    @classmethod
    def from_dict(cls, data: Dict[str, float]):
        return cls(data["velocity"], data["radius_m"], data["wall_steepness"])
