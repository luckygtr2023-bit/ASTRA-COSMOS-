"""ASTRA Interaction — observation & discovery (finite light propagation).

Integrates with temporal/observation, celestial, ingestion, scientific.
Never fabricates measurements; distinguishes observed vs current state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Any
import math

from .errors import ObservationError, DiscoveryError
from astra.scientific.classification import Classification


@dataclass(frozen=True)
class ObservationContext:
    observer_id: str
    observer_position: Tuple[float, float, float]
    observation_time_s: float
    frame_id: Optional[str] = None
    reference_frame: str = "world"
    instrument: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.observer_id, str) or not self.observer_id:
            raise ObservationError("observer_id must be non-empty string")
        if len(self.observer_position) != 3:
            raise ObservationError("observer_position must be 3-tuple")
        for v in self.observer_position:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
                raise ObservationError("observer_position non-finite")
        if isinstance(self.observation_time_s, bool) or not isinstance(self.observation_time_s, (int, float)) or math.isnan(self.observation_time_s) or math.isinf(self.observation_time_s) or self.observation_time_s < 0:
            raise ObservationError("observation_time_s must be finite >=0")
        object.__setattr__(self, "observer_position", tuple(float(x) for x in self.observer_position))

    def to_dict(self) -> Dict:
        return {
            "observer_id": self.observer_id,
            "observer_position": list(self.observer_position),
            "observation_time_s": self.observation_time_s,
            "frame_id": self.frame_id,
            "reference_frame": self.reference_frame,
            "instrument": self.instrument,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ObservationContext":
        return cls(
            observer_id=d["observer_id"],
            observer_position=tuple(d["observer_position"]),
            observation_time_s=float(d["observation_time_s"]),
            frame_id=d.get("frame_id"),
            reference_frame=d.get("reference_frame", "world"),
            instrument=d.get("instrument"),
        )


@dataclass(frozen=True)
class Discovery:
    """Structured discovery — never fabricated."""

    discovery_id: str
    target_id: str
    context: ObservationContext
    simulation_time_s: float
    observation_time_s: float
    lookback_time_s: float
    coordinates: Tuple[float, float, float]
    frame_id: Optional[str]
    measurement_data: Dict[str, Any]
    provenance: str
    classification: Classification
    uncertainty: Optional[Dict[str, Any]] = None
    source_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.discovery_id, str) or not self.discovery_id:
            raise DiscoveryError("discovery_id must be non-empty string")
        if not isinstance(self.target_id, str) or not self.target_id:
            raise DiscoveryError("target_id must be non-empty string")
        if not isinstance(self.context, ObservationContext):
            raise DiscoveryError("context must be ObservationContext")
        for name in ("simulation_time_s","observation_time_s","lookback_time_s"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v) or v < 0:
                raise DiscoveryError(f"{name} must be finite >=0")
        if not isinstance(self.classification, Classification):
            raise DiscoveryError("classification must be Classification")
        if len(self.coordinates) != 3:
            raise DiscoveryError("coordinates must be 3-tuple")
        for v in self.coordinates:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
                raise DiscoveryError("coordinates non-finite")
        object.__setattr__(self, "coordinates", tuple(float(x) for x in self.coordinates))
        object.__setattr__(self, "measurement_data", dict(self.measurement_data))
        object.__setattr__(self, "source_info", dict(self.source_info))
        object.__setattr__(self, "metadata", dict(self.metadata))
        # observed state must be earlier than current (lookback preserves)
        if self.lookback_time_s > self.observation_time_s + 1e-12:
            raise DiscoveryError("lookback_time_s cannot exceed observation_time_s")
        # Honesty: emission time derived
        emission = self.observation_time_s - self.lookback_time_s
        if emission < -1e-12:
            raise DiscoveryError("emission time negative")

    def emission_time_s(self) -> float:
        return self.observation_time_s - self.lookback_time_s

    def to_dict(self) -> Dict:
        return {
            "discovery_id": self.discovery_id,
            "target_id": self.target_id,
            "context": self.context.to_dict(),
            "simulation_time_s": self.simulation_time_s,
            "observation_time_s": self.observation_time_s,
            "lookback_time_s": self.lookback_time_s,
            "coordinates": list(self.coordinates),
            "frame_id": self.frame_id,
            "measurement_data": dict(self.measurement_data),
            "provenance": self.provenance,
            "classification": self.classification.value,
            "uncertainty": dict(self.uncertainty) if self.uncertainty else None,
            "source_info": dict(self.source_info),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Discovery":
        return cls(
            discovery_id=d["discovery_id"],
            target_id=d["target_id"],
            context=ObservationContext.from_dict(d["context"]),
            simulation_time_s=float(d["simulation_time_s"]),
            observation_time_s=float(d["observation_time_s"]),
            lookback_time_s=float(d["lookback_time_s"]),
            coordinates=tuple(d["coordinates"]),
            frame_id=d.get("frame_id"),
            measurement_data=dict(d.get("measurement_data", {})),
            provenance=d.get("provenance", "unknown"),
            classification=Classification(d.get("classification", "SIMULATED_DATA")),
            uncertainty=dict(d["uncertainty"]) if d.get("uncertainty") else None,
            source_info=dict(d.get("source_info", {})),
            metadata=dict(d.get("metadata", {})),
        )


class DiscoveryRegistry:
    """Queryable registry of discoveries — references, not duplicate DB."""

    def __init__(self):
        self._by_id: Dict[str, Discovery] = {}

    def record(self, d: Discovery) -> None:
        if d.discovery_id in self._by_id:
            raise DiscoveryError(f"discovery already recorded: {d.discovery_id!r}")
        self._by_id[d.discovery_id] = d

    def get(self, discovery_id: str) -> Optional[Discovery]:
        return self._by_id.get(discovery_id)

    def get_or_raise(self, discovery_id: str) -> Discovery:
        v = self._by_id.get(discovery_id)
        if v is None:
            raise DiscoveryError(f"discovery not found: {discovery_id!r}")
        return v

    def all(self) -> Tuple[Discovery, ...]:
        return tuple(sorted(self._by_id.values(), key=lambda x: (x.observation_time_s, x.discovery_id)))

    def for_target(self, target_id: str) -> Tuple[Discovery, ...]:
        return tuple(d for d in self.all() if d.target_id == target_id)

    def for_classification(self, c: Classification) -> Tuple[Discovery, ...]:
        return tuple(d for d in self.all() if d.classification == c)

    def clear(self) -> None:
        self._by_id.clear()

    def to_dict(self) -> list:
        return [d.to_dict() for d in self.all()]

    @classmethod
    def from_dict(cls, data: list) -> "DiscoveryRegistry":
        r = cls()
        for d in data:
            r.record(Discovery.from_dict(d))
        return r


class ObservationService:
    """Delegates to temporal observation (light propagation) when available.

    If history/provider absent, raises ObservationError (no fabrication).
    """

    def __init__(self, observation_provider=None, celestial_provider=None):
        self._obs = observation_provider
        self._celestial = celestial_provider

    def observe(self, target_id: str, ctx: ObservationContext, history=None) -> Discovery:
        """Observe via authoritative light-propagation.

        - history: astra.spacetime.Worldline or equivalent
        - observation_provider: callable wrapping astra.temporal.observation.observe
        """
        # Validate ctx
        if not isinstance(ctx, ObservationContext):
            raise ObservationError("ctx must be ObservationContext")

        # If provider and history supplied, delegate to real observation
        if self._obs is not None and history is not None:
            try:
                observed = self._obs(history, ctx.observer_position, ctx.observation_time_s, observer=ctx.observer_id)
                # observed is ObservedState from temporal/observation
                # Build discovery from it (distinguish observed vs actual)
                emission = getattr(observed, "emission_event", None)
                lookback = float(getattr(observed, "lookback_time_s", 0.0))
                sim_t = float(getattr(observed, "observation_time_s", ctx.observation_time_s))
                if emission is not None:
                    coord = (float(emission.x), float(emission.y), float(emission.z))
                    frame = getattr(emission, "chart", None)
                    # map chart to frame string
                    frame_id = str(frame) if frame else ctx.frame_id
                else:
                    coord = ctx.observer_position
                    frame_id = ctx.frame_id
                return Discovery(
                    discovery_id=f"disc-{target_id}-{int(ctx.observation_time_s*1000)}",
                    target_id=target_id,
                    context=ctx,
                    simulation_time_s=sim_t,
                    observation_time_s=ctx.observation_time_s,
                    lookback_time_s=lookback,
                    coordinates=coord,
                    frame_id=frame_id,
                    measurement_data={"emission_ct_m": getattr(emission, "ct_m", None), "actual": str(getattr(observed, "actual_state_at_observation", ""))},
                    provenance="temporal.observation",
                    classification=Classification.SIMULATED_DATA,
                    source_info={"provider": "temporal.observation"},
                )
            except Exception as e:
                # Re-raise as structured error without fabricating
                from astra.temporal.exceptions import TemporalHistoryUnavailableError, InvalidTemporalStateError, InvalidWorldlineError
                if isinstance(e, (TemporalHistoryUnavailableError, InvalidTemporalStateError, InvalidWorldlineError)):
                    raise ObservationError(str(e)) from e
                raise ObservationError(f"observation failed: {e}") from e

        # No provider/history — cannot observe distant reality instantly
        raise ObservationError("no observation history/provider available: refusing to fabricate distant state")

    def record_discovery(self, discovery: Discovery, registry: DiscoveryRegistry) -> None:
        registry.record(discovery)
