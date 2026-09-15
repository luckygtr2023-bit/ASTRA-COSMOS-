"""Warp travel. Reconciled.

Warp geometry (Alcubierre-style) is SPECULATIVE / THEORETICAL.
Never present as achieved technology. Delegates to
astra.theoretical.warp.AlcubierreMetric for metric correctness.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

from .errors import TravelNumericalError
from .types import Provenance, Vec3, _to_vec3


@dataclass(frozen=True)
class WarpBubble:
    """Alcubierre bubble parameters — SPECULATIVE model wrapper."""

    bubble_id: str
    center: Vec3
    radius_m: float
    bubble_velocity_m_s: float
    metric_parameters: Dict[str, float]
    provenance: Provenance = Provenance.THEORETICAL

    def __post_init__(self) -> None:
        if not isinstance(self.bubble_id, str) or not self.bubble_id:
            raise TravelNumericalError("bubble_id must be non-empty string")
        object.__setattr__(self, "center", _to_vec3(self.center))
        if isinstance(self.radius_m, bool) or not isinstance(self.radius_m, (int, float)):
            raise TravelNumericalError("radius_m must be numeric")
        r = float(self.radius_m)
        if math.isnan(r) or math.isinf(r) or r <= 0.0:
            raise TravelNumericalError("bubble radius must be > 0")
        object.__setattr__(self, "radius_m", r)
        if isinstance(self.bubble_velocity_m_s, bool) or not isinstance(
            self.bubble_velocity_m_s, (int, float)
        ):
            raise TravelNumericalError("bubble_velocity_m_s must be numeric")
        v = float(self.bubble_velocity_m_s)
        if math.isnan(v) or math.isinf(v) or v < 0.0:
            raise TravelNumericalError("bubble velocity magnitude must be >= 0")
        object.__setattr__(self, "bubble_velocity_m_s", v)
        if not isinstance(self.metric_parameters, dict):
            raise TravelNumericalError("metric_parameters must be dict")
        # warm-validate via AlcubierreMetric construction (wall_steepness default)
        from astra.theoretical.warp import AlcubierreMetric, MAX_WARP_WALL_STEEPNESS

        wall = float(self.metric_parameters.get("wall_steepness", 10.0))
        # clamp to safety cap — if caller supplied steeper, engine will reject via metric
        if wall > MAX_WARP_WALL_STEEPNESS:
            # keep as is; engine will raise InvalidGeometryParameterError which we map
            pass
        # validate construction (may log speculative warning)
        try:
            AlcubierreMetric(velocity=v, radius_m=r, wall_steepness=wall)
        except Exception as e:
            # map to travel error type for scaffold compatibility
            if "wall_steepness" in str(e) or "steepness" in str(e):
                raise TravelNumericalError(str(e)) from e
            raise

    def to_metric(self):
        """Return authoritative AlcubierreMetric for this bubble."""
        from astra.theoretical.warp import AlcubierreMetric

        wall = float(self.metric_parameters.get("wall_steepness", 10.0))
        return AlcubierreMetric(
            velocity=self.bubble_velocity_m_s, radius_m=self.radius_m, wall_steepness=wall
        )


@dataclass(frozen=True)
class WarpConfig:
    bubble: WarpBubble
    exotic_matter_requirement: str = "unknown"  # "calculated"|"parameterized"|"unknown"|"hypothetical"
    wall_steepness: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.bubble, WarpBubble):
            raise TravelNumericalError("bubble must be WarpBubble")
        if self.exotic_matter_requirement not in (
            "calculated",
            "parameterized",
            "unknown",
            "hypothetical",
            "speculative",
        ):
            raise TravelNumericalError(f"invalid exotic_matter_requirement {self.exotic_matter_requirement!r}")
        if self.wall_steepness is not None:
            if isinstance(self.wall_steepness, bool) or not isinstance(self.wall_steepness, (int, float)):
                raise TravelNumericalError("wall_steepness must be numeric")
            w = float(self.wall_steepness)
            if math.isnan(w) or math.isinf(w) or w <= 0:
                raise TravelNumericalError("wall_steepness must be >0")


def warp_travel_descriptor(
    config: WarpConfig,
    traveler_id: str,
    departure_coordinate_time_s: float,
    distance_m: float,
) -> Dict[str, object]:
    """Produce a descriptor; the engine integrates with Spacetime to build the worldline.

    Coordinate duration = distance / bubble_velocity. Proper duration inside
    the bubble is approximately coordinate duration (passenger at rest in
    bubble). This is scaffold-accurate; metric_proper_time would refine it.
    """
    if not isinstance(traveler_id, str) or not traveler_id:
        raise TravelNumericalError("traveler_id must be non-empty string")
    if isinstance(departure_coordinate_time_s, bool) or not isinstance(
        departure_coordinate_time_s, (int, float)
    ):
        raise TravelNumericalError("departure_coordinate_time_s must be numeric")
    dep = float(departure_coordinate_time_s)
    if math.isnan(dep) or math.isinf(dep) or dep < 0:
        raise TravelNumericalError("departure_coordinate_time_s must be finite >=0")
    if isinstance(distance_m, bool) or not isinstance(distance_m, (int, float)):
        raise TravelNumericalError("distance_m must be numeric")
    dist = float(distance_m)
    if math.isnan(dist) or math.isinf(dist) or dist < 0.0:
        raise TravelNumericalError("distance_m must be >= 0")
    if config.bubble.bubble_velocity_m_s <= 0.0:
        raise TravelNumericalError("bubble velocity must be > 0")
    # prevent overflow
    if dist > 1e30:
        raise TravelNumericalError("distance_m unphysically large")

    duration_s = dist / config.bubble.bubble_velocity_m_s
    if math.isnan(duration_s) or math.isinf(duration_s):
        raise TravelNumericalError("warp duration overflow")
    # The Alcubierre bubble interior is locally flat for the passenger:
    # proper duration ≈ coordinate duration while inside (engine may refine)
    return {
        "bubble_id": config.bubble.bubble_id,
        "traveler_id": traveler_id,
        "departure_coordinate_time_s": dep,
        "arrival_coordinate_time_s": dep + duration_s,
        "coordinate_duration_s": duration_s,
        "proper_duration_s": duration_s,  # scaffold; engine may substitute via spacetime proper
        "exotic_matter_requirement": config.exotic_matter_requirement,
        "provenance": Provenance.THEORETICAL,
        "metric": config.bubble.to_metric(),
    }
