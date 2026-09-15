"""Wormhole travel. Reconciled.

Wormholes are HYPOTHETICAL in the standard model of known physics.
All outputs must be classified accordingly. Never present as confirmed.

Integration: uses MorrisThorneMetric / EinsteinRosenMetric from
astra.theoretical.wormhole where a MetricField is needed. The scaffold
Wormhole dataclass is retained for API compatibility and wraps the
theoretical metric for physics-aware traversal.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

from .errors import TravelNumericalError, TravelUnsupportedError
from .types import CausalStatus, Mechanism, Provenance, Vec3, _to_vec3


@dataclass(frozen=True)
class WormholeMouth:
    mouth_id: str
    position: Vec3
    coordinate_time_s: float
    reference_frame: str = "world"

    def __post_init__(self) -> None:
        if not isinstance(self.mouth_id, str) or not self.mouth_id:
            raise TravelNumericalError("mouth_id must be non-empty string")
        object.__setattr__(self, "position", _to_vec3(self.position))
        if isinstance(self.coordinate_time_s, bool) or not isinstance(
            self.coordinate_time_s, (int, float)
        ):
            raise TravelNumericalError("coordinate_time_s must be numeric")
        ct = float(self.coordinate_time_s)
        if math.isnan(ct) or math.isinf(ct) or ct < 0:
            raise TravelNumericalError("coordinate_time_s must be finite >=0")
        object.__setattr__(self, "coordinate_time_s", ct)
        if not isinstance(self.reference_frame, str) or not self.reference_frame:
            raise TravelNumericalError("reference_frame must be non-empty string")


@dataclass(frozen=True)
class Wormhole:
    """Traversable wormhole descriptor — hypothetical.

    For physics-aware use, construct via create_traversable_wormhole()
    which validates the underlying MorrisThorneMetric geometry.
    """

    wormhole_id: str
    mouth_a: WormholeMouth
    mouth_b: WormholeMouth
    stability: float  # 0..1
    traversal_duration_s: float
    metric_parameters: Dict[str, float]
    provenance: Provenance = Provenance.HYPOTHETICAL

    def __post_init__(self) -> None:
        if not isinstance(self.wormhole_id, str) or not self.wormhole_id:
            raise TravelNumericalError("wormhole_id must be non-empty string")
        if not isinstance(self.mouth_a, WormholeMouth) or not isinstance(self.mouth_b, WormholeMouth):
            raise TravelNumericalError("mouths must be WormholeMouth")
        if isinstance(self.stability, bool) or not isinstance(self.stability, (int, float)):
            raise TravelNumericalError("stability must be numeric")
        s = float(self.stability)
        if math.isnan(s) or math.isinf(s) or not (0.0 <= s <= 1.0):
            raise TravelNumericalError("wormhole stability must be in [0,1]")
        object.__setattr__(self, "stability", s)
        if isinstance(self.traversal_duration_s, bool) or not isinstance(
            self.traversal_duration_s, (int, float)
        ):
            raise TravelNumericalError("traversal_duration_s must be numeric")
        td = float(self.traversal_duration_s)
        if math.isnan(td) or math.isinf(td) or td < 0.0:
            raise TravelNumericalError("traversal_duration_s must be >= 0")
        object.__setattr__(self, "traversal_duration_s", td)
        if not isinstance(self.metric_parameters, dict):
            raise TravelNumericalError("metric_parameters must be dict")
        if self.provenance != Provenance.HYPOTHETICAL and self.provenance != Provenance.SPECULATIVE:
            # enforce hypothetical/speculative for wormholes — never allow REAL
            raise TravelNumericalError("wormhole provenance must be HYPOTHETICAL or SPECULATIVE")


def create_traversable_wormhole(
    wormhole_id: str,
    mouth_a: WormholeMouth,
    mouth_b: WormholeMouth,
    throat_radius_m: float,
    stability: float = 0.5,
    traversal_duration_s: float = 1.0,
    shape_func=None,
    redshift_func=None,
) -> tuple[Wormhole, object]:
    """Create a wormhole with validated MorrisThorne geometry.

    Returns (Wormhole descriptor, MorrisThorneMetric). Raises on invalid
    geometry (flare-out violation etc.) via the theoretical layer.
    """
    from astra.theoretical.wormhole import MorrisThorneMetric

    if shape_func is None:
        # default shape function for a simple wormhole: b(r)=r0^2/r
        r0 = float(throat_radius_m)

        def _shape(r: float) -> float:
            return (r0 * r0) / r if r != 0 else r0

        shape_func = _shape
    if redshift_func is None:
        redshift_func = lambda r: 0.0

    metric = MorrisThorneMetric(throat_radius_m, shape_func, redshift_func)
    wh = Wormhole(
        wormhole_id=wormhole_id,
        mouth_a=mouth_a,
        mouth_b=mouth_b,
        stability=float(stability),
        traversal_duration_s=float(traversal_duration_s),
        metric_parameters={"throat_radius_m": float(throat_radius_m)},
        provenance=Provenance.HYPOTHETICAL,
    )
    return wh, metric


def traverse(
    wormhole: Wormhole,
    traveler_id: str,
    departure_coordinate_time_s: float,
) -> Dict[str, object]:
    """Scaffold traversal — returns descriptor without teleport shortcut.

    Validates stability and temporal ordering; the engine turns the
    descriptor into a worldline through the spacetime provider.  Does NOT
    teleport — a worldline with proper duration is still constructed.
    """
    if not isinstance(wormhole, Wormhole):
        raise TravelNumericalError("wormhole must be Wormhole")
    if not isinstance(traveler_id, str) or not traveler_id:
        raise TravelNumericalError("traveler_id must be non-empty string")
    if isinstance(departure_coordinate_time_s, bool) or not isinstance(
        departure_coordinate_time_s, (int, float)
    ):
        raise TravelNumericalError("departure_coordinate_time_s must be numeric")
    dep = float(departure_coordinate_time_s)
    if math.isnan(dep) or math.isinf(dep) or dep < 0:
        raise TravelNumericalError("departure_coordinate_time_s must be finite >=0")
    if wormhole.stability <= 0.0:
        raise TravelUnsupportedError("wormhole is unstable / not traversable")
    if dep < wormhole.mouth_a.coordinate_time_s - 1e-9:
        raise TravelUnsupportedError("departure before mouth A exists")

    arrival_coordinate_time_s = dep + wormhole.traversal_duration_s
    # proper duration is traversal_duration for zero-tidal model; more
    # generally would integrate via MorrisThorne proper distance, but we keep
    # deterministic scaffold value here and allow engine to substitute metric_proper
    return {
        "wormhole_id": wormhole.wormhole_id,
        "traveler_id": traveler_id,
        "departure_position": wormhole.mouth_a.position,
        "arrival_position": wormhole.mouth_b.position,
        "departure_coordinate_time_s": dep,
        "arrival_coordinate_time_s": arrival_coordinate_time_s,
        "proper_duration_s": wormhole.traversal_duration_s,
        "mechanism": Mechanism.WORMHOLE,
        "causal_status": CausalStatus.UNKNOWN,
        "provenance": Provenance.HYPOTHETICAL,
        "metric_parameters": dict(wormhole.metric_parameters),
    }
