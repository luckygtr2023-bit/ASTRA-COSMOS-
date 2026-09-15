"""White-hole interface. Reconciled.

White holes are HYPOTHETICAL / THEORETICAL solutions. Never present as
observed objects. Delegates to astra.theoretical.whitehole.WhiteHoleMetric
and to temporal white_hole_temporal_check for emissive-only policy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

from .errors import TravelNumericalError
from .types import Provenance, Vec3, _to_vec3


@dataclass(frozen=True)
class WhiteHoleConfig:
    white_hole_id: str
    position: Vec3
    mass_kg: float = 1.98847e30  # solar mass default
    causal_direction: str = "outward"  # "outward" | "inward" | "mixed"
    matter_flow_assumption: str = "unknown"
    provenance: Provenance = Provenance.HYPOTHETICAL

    def __post_init__(self) -> None:
        if not isinstance(self.white_hole_id, str) or not self.white_hole_id:
            raise TravelNumericalError("white_hole_id must be non-empty string")
        object.__setattr__(self, "position", _to_vec3(self.position))
        if isinstance(self.mass_kg, bool) or not isinstance(self.mass_kg, (int, float)):
            raise TravelNumericalError("mass_kg must be numeric")
        m = float(self.mass_kg)
        if math.isnan(m) or math.isinf(m) or m <= 0:
            raise TravelNumericalError("mass_kg must be finite >0")
        object.__setattr__(self, "mass_kg", m)
        if self.causal_direction not in ("outward", "inward", "mixed"):
            raise TravelNumericalError("invalid causal_direction")
        if not isinstance(self.matter_flow_assumption, str):
            raise TravelNumericalError("matter_flow_assumption must be string")
        if self.provenance not in (Provenance.HYPOTHETICAL, Provenance.THEORETICAL, Provenance.SPECULATIVE):
            raise TravelNumericalError("white hole provenance must be hypothetical/theoretical/speculative")

    def to_metric(self):
        """Return authoritative WhiteHoleMetric."""
        from astra.theoretical.whitehole import WhiteHoleMetric

        return WhiteHoleMetric(mass_kg=self.mass_kg)


def describe(config: WhiteHoleConfig) -> Dict[str, object]:
    return {
        "white_hole_id": config.white_hole_id,
        "position": config.position,
        "mass_kg": config.mass_kg,
        "causal_direction": config.causal_direction,
        "matter_flow_assumption": config.matter_flow_assumption,
        "provenance": config.provenance,
    }


def check_emissive(config: WhiteHoleConfig, coords, four_velocity) -> Dict[str, object]:
    """Apply emissive-only policy via WhiteHoleMetric.assert_emissive_only.

    Returns dict with allowed bool and reason. Does not bypass metric.
    """
    metric = config.to_metric()
    from astra.temporal.exotic import white_hole_temporal_check

    result = white_hole_temporal_check(metric, coords, four_velocity)
    return {"allowed": result.allowed, "reason": result.reason, "provenance": config.provenance}
