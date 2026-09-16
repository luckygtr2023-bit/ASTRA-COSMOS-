"""ASTRA Interaction — structured exploration history (deterministic, serializable, provenance-aware)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import math

from .errors import InvalidInteractionError
from astra.scientific.classification import Classification


class HistoryEventKind(str, Enum):
    LOCATION_VISITED = "LOCATION_VISITED"
    OBJECT_OBSERVED = "OBJECT_OBSERVED"
    MEASUREMENT_PERFORMED = "MEASUREMENT_PERFORMED"
    DISCOVERY_MADE = "DISCOVERY_MADE"
    TRAVEL_EVENT = "TRAVEL_EVENT"
    PHENOMENON_ENCOUNTERED = "PHENOMENON_ENCOUNTERED"
    SPACECRAFT_TRANSITION = "SPACECRAFT_TRANSITION"
    INTERACTION_EVENT = "INTERACTION_EVENT"
    STATE_TRANSITION = "STATE_TRANSITION"
    NAVIGATION = "NAVIGATION"
    OBSERVATION = "OBSERVATION"
    TARGETING = "TARGETING"


@dataclass(frozen=True)
class ExplorationEvent:
    event_id: str
    kind: HistoryEventKind
    tick: int
    simulation_time_s: float
    target_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    classification: Classification = Classification.SIMULATED_DATA
    provenance: str = "astra.interaction"
    # reference to chain node if available

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id:
            raise InvalidInteractionError("event_id must be non-empty string")
        if not isinstance(self.kind, HistoryEventKind):
            raise InvalidInteractionError("kind must be HistoryEventKind")
        if not isinstance(self.tick, int) or self.tick < 0:
            raise InvalidInteractionError("tick must be int >=0")
        if isinstance(self.simulation_time_s, bool) or not isinstance(self.simulation_time_s, (int, float)) or math.isnan(self.simulation_time_s) or math.isinf(self.simulation_time_s) or self.simulation_time_s < 0:
            raise InvalidInteractionError("simulation_time_s must be finite >=0")
        if not isinstance(self.classification, Classification):
            raise InvalidInteractionError("classification must be Classification")
        object.__setattr__(self, "data", dict(self.data))

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "kind": self.kind.value,
            "tick": self.tick,
            "simulation_time_s": self.simulation_time_s,
            "target_id": self.target_id,
            "data": dict(self.data),
            "classification": self.classification.value,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ExplorationEvent":
        return cls(
            event_id=d["event_id"],
            kind=HistoryEventKind(d["kind"]),
            tick=int(d["tick"]),
            simulation_time_s=float(d["simulation_time_s"]),
            target_id=d.get("target_id"),
            data=dict(d.get("data", {})),
            classification=Classification(d.get("classification", "SIMULATED_DATA")),
            provenance=d.get("provenance", "astra.interaction"),
        )


class ExplorationHistory:
    """Deterministic, append-only history."""

    def __init__(self):
        self._events: List[ExplorationEvent] = []
        self._ids: set[str] = set()
        self._seq: int = 0

    def append(self, ev: ExplorationEvent) -> None:
        if ev.event_id in self._ids:
            raise InvalidInteractionError(f"duplicate event_id {ev.event_id!r}")
        self._events.append(ev)
        self._ids.add(ev.event_id)
        # Note: deterministic ordering is provided by all() sorting, not per-append sort (performance)

    def next_id(self, prefix: str = "ev") -> str:
        self._seq += 1
        return f"{prefix}-{self._seq:06d}"

    def emit(self, kind: HistoryEventKind, tick: int, sim_s: float,
             target_id: Optional[str] = None, data: Optional[Dict] = None,
             classification: Classification = Classification.SIMULATED_DATA,
             provenance: str = "astra.interaction") -> ExplorationEvent:
        eid = self.next_id(prefix=kind.value.lower())
        ev = ExplorationEvent(event_id=eid, kind=kind, tick=tick, simulation_time_s=sim_s,
                              target_id=target_id, data=data or {}, classification=classification, provenance=provenance)
        self.append(ev)
        return ev

    def all(self) -> Tuple[ExplorationEvent, ...]:
        return tuple(sorted(self._events, key=lambda e: (e.tick, e.event_id)))

    def for_kind(self, kind: HistoryEventKind) -> Tuple[ExplorationEvent, ...]:
        return tuple(e for e in self._events if e.kind == kind)

    def for_target(self, target_id: str) -> Tuple[ExplorationEvent, ...]:
        return tuple(e for e in self._events if e.target_id == target_id)

    def between(self, t0: int, t1: int) -> Tuple[ExplorationEvent, ...]:
        return tuple(e for e in self._events if t0 <= e.tick <= t1)

    def count(self) -> int:
        return len(self._events)

    def clear(self) -> None:
        self._events.clear()
        self._ids.clear()
        self._seq = 0

    def to_dict(self) -> list:
        return [e.to_dict() for e in self._events]

    @classmethod
    def from_dict(cls, data: list) -> "ExplorationHistory":
        h = cls()
        for d in data:
            h.append(ExplorationEvent.from_dict(d))
        # restore seq to max
        if h._events:
            try:
                h._seq = max(int(e.event_id.split("-")[-1]) for e in h._events if "-" in e.event_id and e.event_id.split("-")[-1].isdigit())
            except ValueError:
                h._seq = len(h._events)
        return h
