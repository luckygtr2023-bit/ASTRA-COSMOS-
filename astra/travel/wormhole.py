"""Wormhole travel. Reconciled.

Wormholes are HYPOTHETICAL in the standard model. Time-shifted two-mouth
configurations (Morris-Thorne-Yurtsever) allow CTC analysis where the
mouths carry a relative time offset. This module models mouth temporal
offsets and diagnoses chronology violation when external light-travel vs
time-shift permits a closed timelike loop.

Integration: uses MorrisThorneMetric / EinsteinRosenMetric where needed,
but retains the single-patch throat geometry for local traversal; the
time-shift is a global topology parameter beyond the local metric.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Tuple

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

    Mouth time offset = mouth_b.coordinate_time_s - mouth_a.coordinate_time_s
    represents the global time shift between mouths. When non-zero, external
    light travel vs shift determines CTC possibility (Morris-Thorne-Yurtsever).
    Local metric still uses MorrisThorne throat parameters.
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
            raise TravelNumericalError("wormhole provenance must be HYPOTHETICAL or SPECULATIVE")

    @property
    def time_shift_s(self) -> float:
        """Global time offset between mouths (B - A). Negative means B is in the past."""
        return float(self.mouth_b.coordinate_time_s - self.mouth_a.coordinate_time_s)

    @property
    def mouth_separation_m(self) -> float:
        return (self.mouth_b.position - self.mouth_a.position).norm()

    def chronology_violation_possible(self) -> Tuple[bool, str]:
        """Determine if this time-shifted wormhole permits a CTC.

        Classic condition: if |time_shift| + traversal_duration < external_light_travel_time,
        you can exit B in the past and return to A via external space before you left,
        forming a closed timelike loop.

        For non-time-shifted wormholes (|Δt| ≈ 0), no CTC is possible in single-patch.
        """
        from astra.relativity.core import SPEED_OF_LIGHT

        d = self.mouth_separation_m
        dt_external = d / SPEED_OF_LIGHT if SPEED_OF_LIGHT != 0 else float("inf")
        time_shift = self.time_shift_s
        # Traversal is assumed to be near-instant for CTC analysis (proper distance dominates)
        total_shift = abs(time_shift) - self.traversal_duration_s
        # If time shift magnitude exceeds external light travel + traversal, CTC possible
        if abs(time_shift) > 1e-12 and (abs(time_shift) > dt_external + self.traversal_duration_s):
            return True, (
                f"Time shift |Δt|={abs(time_shift):.3g}s exceeds external light travel "
                f"{dt_external:.3g}s + traversal {self.traversal_duration_s:.3g}s — "
                "Morris-Thorne-Yurtsever CTC possible (diagnostic only, not traversable execution)."
            )
        if abs(time_shift) < 1e-12:
            return False, (
                "Single-patch Morris-Thorne geometry: no inter-mouth time offset is configured, "
                "so no closed timelike curve can be produced by this configuration. "
                "Chronology protection analysis only — ASTRA provides no time-travel execution API."
            )
        return False, (
            f"Time shift |Δt|={abs(time_shift):.3g}s + traversal {self.traversal_duration_s:.3g}s "
            f"does not exceed external light travel {dt_external:.3g}s — no CTC in this configuration."
        )


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
    """Create a wormhole with validated MorrisThorne geometry."""
    from astra.theoretical.wormhole import MorrisThorneMetric

    if shape_func is None:
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
    """Traversal descriptor — respects mouth time offset.

    Arrival = departure + traversal_duration + time_shift (B - A).
    This captures backward time travel when B is in the past (negative shift).
    Worldline construction still requires a finite worldline (engine builds it).
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

    time_shift = wormhole.time_shift_s
    arrival_coordinate_time_s = dep + wormhole.traversal_duration_s + time_shift

    if arrival_coordinate_time_s < 0:
        # Arrival in negative time would be before simulation epoch — treat as causal violation
        # but we allow it for CTC representation and let engine's causality check handle it
        pass

    # Proper duration is traversal_duration for zero-tidal model; time shift does not affect proper
    # (shift is coordinate, passenger proper is invariant)
    proper_duration = wormhole.traversal_duration_s

    # Determine causal status hint
    causal_hint = CausalStatus.UNKNOWN
    if time_shift < -1e-9 and arrival_coordinate_time_s < dep:
        causal_hint = CausalStatus.CTC
    elif arrival_coordinate_time_s < dep - 1e-9:
        causal_hint = CausalStatus.CAUSALLY_INVALID

    ctc_possible, analysis = wormhole.chronology_violation_possible()

    return {
        "wormhole_id": wormhole.wormhole_id,
        "traveler_id": traveler_id,
        "departure_position": wormhole.mouth_a.position,
        "arrival_position": wormhole.mouth_b.position,
        "departure_coordinate_time_s": dep,
        "arrival_coordinate_time_s": arrival_coordinate_time_s,
        "proper_duration_s": proper_duration,
        "mechanism": Mechanism.WORMHOLE,
        "causal_status": causal_hint,
        "provenance": Provenance.HYPOTHETICAL,
        "metric_parameters": dict(wormhole.metric_parameters),
        "time_shift_s": time_shift,
        "ctc_possible": ctc_possible,
        "chronology_analysis": analysis,
    }


def wormhole_chronology_diagnostic(wormhole: Wormhole) -> Dict[str, object]:
    """Detailed chronology diagnostic using Wormhole's own time-shift logic."""
    possible, analysis = wormhole.chronology_violation_possible()
    return {
        "wormhole_id": wormhole.wormhole_id,
        "throat_radius_m": wormhole.metric_parameters.get("throat_radius_m"),
        "mouth_separation_m": wormhole.mouth_separation_m,
        "time_shift_s": wormhole.time_shift_s,
        "traversal_duration_s": wormhole.traversal_duration_s,
        "chronology_violation_possible": possible,
        "analysis": analysis,
        "provenance": Provenance.HYPOTHETICAL,
    }
