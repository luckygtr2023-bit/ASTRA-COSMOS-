"""ASTRA Theoretical - white hole geometry (mathematical model).

A white hole is the time-reverse of a black hole: the maximal
Schwarzschild extension's past horizon, out of which matter can only
EMERGE and into which nothing can fall.

Honest scope (documented): the EXTERIOR metric tensor of a white hole is
bit-identical to Schwarzschild's - static geometry knows nothing of causal
orientation; orientation is a property of the extension's identification.
The mathematics is therefore delegated to
``astra.spacetime.metric.SchwarzschildMetric`` (single implementation).
The white-hole semantics live in the CAUSAL-ORIENTATION POLICY:

    assert_emissive_only(coords, four_velocity)
        - rejects spacelike tangents (not physical worldline directions),
        - rejects future-directed tangents with ingoing radial coordinate
          velocity within the near-horizon band (nothing may fall in),
        - outgoing (emergent) tangents pass.

Deterministic pure functions; SI units.
"""

from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple

from astra.spacetime.metric import (
    CHART_SPHERICAL,
    MetricField,
    SchwarzschildMetric,
    SpacetimeModel,
    _validate_coords,
)
from astra.theoretical.classification import ScientificClassification
from astra.theoretical.exceptions import (
    CausalityOrientationError,
    InvalidGeometryParameterError,
)

# Width of the causal-policy band above the horizon (relative to r_s).
EMISSIVE_BAND_RELATIVE: float = 0.5


class WhiteHoleMetric(MetricField):
    """White-hole exterior mathematical model (THEORETICAL)."""

    model = SpacetimeModel.SCHWARZSCHILD
    chart = CHART_SPHERICAL
    classification = ScientificClassification.THEORETICAL

    def __init__(self, mass_kg: float):
        if isinstance(mass_kg, bool) or not isinstance(mass_kg, (int, float)) \
                or math.isnan(mass_kg) or math.isinf(mass_kg) or mass_kg <= 0.0:
            raise InvalidGeometryParameterError(
                f"mass_kg must be finite and > 0, got {mass_kg!r}"
            )
        self._schw = SchwarzschildMetric(mass_kg)

    @property
    def schwarzschild_delegate(self) -> SchwarzschildMetric:
        return self._schw

    @property
    def rs_m(self) -> float:
        return self._schw.rs_m

    def tensor(self, coords) -> Tuple:
        # Identical exterior geometry (documented); all guards inherited.
        return self._schw.tensor(coords)

    def assert_emissive_only(
        self, coords: Sequence[float], four_velocity: Sequence[float]
    ) -> None:
        """Causal-orientation policy: emergence only, no infall.

        - The tangent must be a physical worldline direction (null or
          timelike w.r.t. the metric); spacelike tangents raise
          CausalityOrientationError (they are not trajectories).
        - Within the near-horizon band r < r_s (1 + band), future-directed
          tangents must have u^r >= 0: the white hole emits and cannot
          absorb. Ingoing configurations raise CausalityOrientationError.
        """
        x = _validate_coords(coords, self.chart)
        u = tuple(float(v) for v in four_velocity)
        if len(u) != 4:
            raise InvalidGeometryParameterError("four_velocity must be a 4-tuple")
        if any(math.isnan(v) or math.isinf(v) for v in u):
            raise InvalidGeometryParameterError("four_velocity contains non-finite components")

        g = self.tensor(x)
        norm = sum(g[a][b] * u[a] * u[b] for a in range(4) for b in range(4))
        if norm > 0.0:
            raise CausalityOrientationError(
                f"Spacelike tangent (g(u,u) = {norm!r} > 0) is not a worldline; "
                "blocked from crossing the causal barrier."
            )

        rs = self._schw.rs_m
        r = x[1]
        if r < rs * (1.0 + EMISSIVE_BAND_RELATIVE) and u[1] < 0.0:
            # Future-directed: g_00 < 0 outside the horizon, so u^0 > 0
            # (u^0 < 0 is past-directed and equally blocked by the physics
            # of the policy below).
            if u[0] > 0.0:
                raise CausalityOrientationError(
                    f"Ingoing future-directed worldline (u^r = {u[1]!r}) at "
                    f"r = {r!r} m inside the emissive band of the white-hole "
                    "horizon: matter can only emerge, never enter."
                )

    def to_dict(self) -> Dict[str, float]:
        return {"mass_kg": self._schw_mass()}

    @classmethod
    def from_dict(cls, data: Dict[str, float]):
        return cls(data["mass_kg"])

    def _schw_mass(self) -> float:
        from astra.relativity.core import C_SQUARED
        from astra.physics.constants import GRAVITATIONAL_CONSTANT
        return self._schw.rs_m * C_SQUARED / (2.0 * GRAVITATIONAL_CONSTANT)
