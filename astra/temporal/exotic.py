"""ASTRA Temporal - causal analysis of exotic (theoretical) geometries.

BOUNDARY (binding for this whole layer): ANALYSIS =/= EXECUTION.

This module may DIAGNOSE the causal structure of exotic metrics; it does
NOT and MUST NOT provide transport of any kind. There is deliberately no
travel_to_past / create_time_machine / rewrite_timeline / reverse_causality
API anywhere in ASTRA, and no CTC generation: a chronology violation is
reported as a DIAGNOSTIC RESULT (data), never enabled as an operation.

Composition (no duplicated mathematics):
    - Warp cones: reuses the VALIDATED mixed-component null-direction
      sampler from the previous phase
      (astra.theoretical.energy_conditions.build_null_direction_set) and
      the spacetime classifier, so strongly tilted Alcubierre cones are
      analyzed with exactly the machinery proven there.
    - White holes: temporal checks DELEGATE to
      WhiteHoleMetric.assert_emissive_only - the existing emissive-only
      causal policy is applied, never bypassed or weakened.
    - Wormholes: proper traversal geometry reuses
      MorrisThorneMetric.proper_radial_distance; chronology diagnostics
      report what the CONFIGURED geometry implies (single-patch model:
      no mouth time-offset is representable, hence no CTC is producible
      here - stated as analysis, with the requirement for one documented).

Deterministic pure functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from astra.spacetime.causality import classify_interval
from astra.spacetime.metric import _validate_coords
from astra.theoretical.energy_conditions import build_null_direction_set
from astra.theoretical.exceptions import CausalityOrientationError
from astra.theoretical.warp import AlcubierreMetric
from astra.theoretical.whitehole import WhiteHoleMetric
from astra.theoretical.wormhole import MorrisThorneMetric
from astra.temporal.exceptions import InvalidTemporalStateError


@dataclass(frozen=True)
class ConeAnalysis:
    """Deterministic causal-structure report at a spacetime point."""

    coordinates: Tuple[float, float, float, float]
    null_direction_count: int
    tilted_cone: bool  # g_0i != 0: cones tilt (frame dragging / warp shift)
    null_directions: Tuple[Tuple[float, float, float, float], ...]

    def to_dict(self) -> Dict:
        return {
            "coordinates": self.coordinates,
            "null_direction_count": self.null_direction_count,
            "tilted_cone": self.tilted_cone,
            "null_directions": self.null_directions,
        }


def warp_cone_analysis(metric: AlcubierreMetric,
                       coordinates: Sequence[float]) -> ConeAnalysis:
    """Analyze the local light-cone structure of a warp metric.

    Uses the validated mixed-component null sampler (the plane-only slices
    are empty for strongly tilted cones - documented in the theoretical
    phase). Classification of a candidate worldline against this metric
    remains available through causal.relate/classify.
    """
    x = _validate_coords(coordinates, metric.chart)
    g = metric.tensor(x)
    tilted = any(g[0][i] != 0.0 for i in (1, 2, 3))
    directions = build_null_direction_set(g)
    return ConeAnalysis(
        coordinates=x,
        null_direction_count=len(directions),
        tilted_cone=tilted,
        null_directions=directions,
    )


@dataclass(frozen=True)
class WhiteHoleTemporalCheck:
    """Result of the emissive-only temporal policy check (delegated)."""

    coordinates: Tuple[float, float, float, float]
    allowed: bool
    reason: str

    def to_dict(self) -> Dict:
        return {"coordinates": self.coordinates, "allowed": self.allowed,
                "reason": self.reason}


def white_hole_temporal_check(metric: WhiteHoleMetric, coordinates: Sequence[float],
                              four_velocity: Sequence[float]) -> WhiteHoleTemporalCheck:
    """Apply the white hole's EXISTING emissive-only policy to a tangent.

    Delegates to ``WhiteHoleMetric.assert_emissive_only`` (the causal
    orientation policy is consumed, not reimplemented); translates the
    outcome into an analysis record. Ingoing worldlines near the horizon
    are rejected BY THE METRIC'S OWN POLICY.
    """
    x = _validate_coords(coordinates, metric.chart)
    try:
        metric.assert_emissive_only(x, four_velocity)
    except CausalityOrientationError as exc:
        return WhiteHoleTemporalCheck(coordinates=x, allowed=False, reason=str(exc))
    return WhiteHoleTemporalCheck(
        coordinates=x, allowed=True,
        reason="tangent respects the emissive-only causal orientation policy",
    )


@dataclass(frozen=True)
class WormholeChronologyDiagnostic:
    """Analysis-only chronology report for a configured wormhole.

    ``chronology_violation_possible`` is honest for THIS model: the
    single-patch Morris-Thorne implementation carries no inter-mouth time
    offset, so no CTC is representable in it. A CTC would require a
    time-shifted two-mouth embedding (Morris-Thorne-Yurtsever), which is
    NOT modeled - documented, not enabled.
    """

    throat_radius_m: float
    proper_throat_depth_at: Tuple[float, ...]
    chronology_violation_possible: bool
    analysis: str

    def to_dict(self) -> Dict:
        return {
            "throat_radius_m": self.throat_radius_m,
            "proper_throat_depth_at": self.proper_throat_depth_at,
            "chronology_violation_possible": self.chronology_violation_possible,
            "analysis": self.analysis,
        }


def wormhole_chronology_diagnostic(
    metric: MorrisThorneMetric, radii_m: Sequence[float]
) -> WormholeChronologyDiagnostic:
    """Report traversal geometry and chronology status (analysis only)."""
    depths = []
    for r in radii_m:
        if isinstance(r, bool) or not isinstance(r, (int, float)) \
                or math.isnan(float(r)) or math.isinf(float(r)):
            raise InvalidTemporalStateError(f"radii must be finite, got {r!r}")
        depths.append(metric.proper_radial_distance(float(r)))
    return WormholeChronologyDiagnostic(
        throat_radius_m=metric.throat_radius_m,
        proper_throat_depth_at=tuple(depths),
        chronology_violation_possible=False,
        analysis=(
            "Single-patch Morris-Thorne geometry: no inter-mouth time offset "
            "is representable, so no closed timelike curve can be produced by "
            "this configuration. Chronology protection analysis only - ASTRA "
            "provides no time-travel execution API."
        ),
    )
