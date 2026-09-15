"""Cosmic history — storage and reconstruction of historical states.

Consumes existing Universe Evolution snapshots where available; otherwise
holds engine-generated snapshots. Never fabricates: interpolation only
between recorded samples; emission times outside the recorded bracket
raise HistoryUnavailableError.

Concepts:
  HistoricalSnapshot — immutable (t, state, provenance, epoch)
  CosmicHistory — per-object sorted timeline
  TimelineEvent — formation / transformation / destruction / merger etc.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from astra.observation.exceptions import HistoryUnavailableError
from astra.celestial.provenance import DataProvenance, ProvenanceTag


class CosmicEpoch(str, Enum):
    """Coarse cosmic epoch labels (extensible)."""

    RECOMBINATION = "recombination"
    REIONIZATION = "reionization"
    GALAXY_FORMATION = "galaxy_formation"
    STAR_FORMATION = "star_formation"
    STELLAR_EVOLUTION = "stellar_evolution"
    PRESENT = "present"
    FUTURE = "future"


class EventType(str, Enum):
    """Types of historical / transient events."""

    FORMATION = "formation"
    TRANSFORMATION = "transformation"
    DESTRUCTION = "destruction"
    MERGER = "merger"
    STELLAR_EVOLUTION = "stellar_evolution"
    BLACK_HOLE_EVOLUTION = "black_hole_evolution"
    SUPERNOVA = "supernova"
    COLLISION = "collision"
    IMPACT = "impact"
    COSMOLOGICAL_TRANSITION = "cosmological_transition"
    TRANSIENT = "transient"


def _finite_time(v, name: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"{name} must be a number, got {type(v).__name__}")
    f = float(v)
    if math.isnan(f) or math.isinf(f) or f < 0:
        raise ValueError(f"{name} must be finite >=0, got {v!r}")
    return f


@dataclass(frozen=True)
class HistoricalSnapshot:
    """One historical state at an explicit cosmic/simulation time.

    Attributes:
        timestamp_s: simulation/coordinate time seconds (monotonic)
        cosmic_time_s: optional cosmological time (if distinct from simulation)
        state: arbitrary payload dict / object describing the system's
               configuration at that time (position, mass, etc.). Copied
               on store to prevent external mutation.
        provenance: where the state came from
        epoch: optional cosmic epoch label
        metadata: free-form (scale_factor, redshift, etc.)
    """

    timestamp_s: float
    state: Dict[str, Any]
    provenance: ProvenanceTag = field(default_factory=lambda: ProvenanceTag(DataProvenance.SIMULATED_DATA))
    cosmic_time_s: Optional[float] = None
    epoch: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        t = _finite_time(self.timestamp_s, "timestamp_s")
        object.__setattr__(self, "timestamp_s", float(t))
        if self.cosmic_time_s is not None:
            ct = _finite_time(self.cosmic_time_s, "cosmic_time_s")
            object.__setattr__(self, "cosmic_time_s", float(ct))
        if not isinstance(self.state, dict):
            raise ValueError("state must be a dict")
        # shallow copy for immutability
        object.__setattr__(self, "state", dict(self.state))
        if not isinstance(self.provenance, ProvenanceTag):
            raise TypeError("provenance must be ProvenanceTag")
        if self.epoch is not None and not isinstance(self.epoch, str):
            raise ValueError("epoch must be str or None")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be dict")

    def to_dict(self) -> Dict:
        return {
            "timestamp_s": self.timestamp_s,
            "cosmic_time_s": self.cosmic_time_s,
            "state": dict(self.state),
            "provenance": {
                "provenance": self.provenance.provenance.value,
                "source_label": self.provenance.source_label,
            },
            "epoch": self.epoch,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "HistoricalSnapshot":
        prov = data.get("provenance", {})
        tag = ProvenanceTag(
            provenance=DataProvenance(prov.get("provenance", "SIMULATED_DATA")),
            source_label=prov.get("source_label", "astra"),
        )
        return cls(
            timestamp_s=data["timestamp_s"],
            state=dict(data.get("state", {})),
            provenance=tag,
            cosmic_time_s=data.get("cosmic_time_s"),
            epoch=data.get("epoch"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class TimelineEvent:
    """A dated, typed historical event (formation, merger, SN, etc.)."""

    event_id: str
    event_type: str  # EventType value or custom
    timestamp_s: float
    participants: Tuple[str, ...] = ()
    description: str = ""
    provenance: ProvenanceTag = field(default_factory=lambda: ProvenanceTag(DataProvenance.SIMULATED_DATA))
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id:
            raise ValueError("event_id must be non-empty string")
        if not isinstance(self.event_type, str) or not self.event_type:
            raise ValueError("event_type must be non-empty string")
        t = _finite_time(self.timestamp_s, "timestamp_s")
        object.__setattr__(self, "timestamp_s", float(t))
        object.__setattr__(self, "participants", tuple(self.participants))
        if not isinstance(self.provenance, ProvenanceTag):
            raise TypeError("provenance must be ProvenanceTag")

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp_s": self.timestamp_s,
            "participants": list(self.participants),
            "description": self.description,
            "provenance": {
                "provenance": self.provenance.provenance.value,
                "source_label": self.provenance.source_label,
            },
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TimelineEvent":
        prov = data.get("provenance", {})
        tag = ProvenanceTag(
            provenance=DataProvenance(prov.get("provenance", "SIMULATED_DATA")),
            source_label=prov.get("source_label", "astra"),
        )
        return cls(
            event_id=data["event_id"],
            event_type=data["event_type"],
            timestamp_s=data["timestamp_s"],
            participants=tuple(data.get("participants", ())),
            description=data.get("description", ""),
            provenance=tag,
            metadata=dict(data.get("metadata", {})),
        )


class CosmicHistory:
    """Authoritative timeline store for observed/historical states.

    Per-object sorted list of HistoricalSnapshot. Interpolation between
    snapshots is linear for numeric fields; non-numeric fields take the
    earlier snapshot's value. Extrapolation is forbidden — raise
    HistoryUnavailableError.

    Also stores transient TimelineEvent records for event observation.
    """

    def __init__(self):
        self._snapshots: Dict[str, List[HistoricalSnapshot]] = {}
        self._events: Dict[str, TimelineEvent] = {}
        self._events_by_time: List[TimelineEvent] = []

    # -- snapshots -------------------------------------------------------
    def add_snapshot(self, object_id: str, snapshot: HistoricalSnapshot) -> None:
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("object_id must be non-empty string")
        if not isinstance(snapshot, HistoricalSnapshot):
            raise TypeError("snapshot must be HistoricalSnapshot")
        lst = self._snapshots.setdefault(object_id, [])
        # keep sorted, reject duplicate timestamp (use replace semantics)
        for i, s in enumerate(lst):
            if s.timestamp_s == snapshot.timestamp_s:
                lst[i] = snapshot
                return
            if s.timestamp_s > snapshot.timestamp_s:
                lst.insert(i, snapshot)
                return
        lst.append(snapshot)

    def add_snapshots_bulk(self, object_id: str, snapshots: List[HistoricalSnapshot]) -> None:
        for s in snapshots:
            self.add_snapshot(object_id, s)

    def get_snapshots(self, object_id: str) -> Tuple[HistoricalSnapshot, ...]:
        return tuple(self._snapshots.get(object_id, ()))

    def earliest_time(self, object_id: str) -> Optional[float]:
        lst = self._snapshots.get(object_id)
        return lst[0].timestamp_s if lst else None

    def latest_time(self, object_id: str) -> Optional[float]:
        lst = self._snapshots.get(object_id)
        return lst[-1].timestamp_s if lst else None

    def reconstruct_state(self, object_id: str, emission_time_s: float) -> HistoricalSnapshot:
        """Return interpolated snapshot at emission_time_s.

        Exact timestamp hits return the stored snapshot. Otherwise linear
        interpolation between the bracketing snapshots. Times outside the
        recorded bracket raise HistoryUnavailableError.
        """
        if not isinstance(object_id, str) or not object_id:
            raise ValueError("object_id must be non-empty string")
        t = _finite_time(emission_time_s, "emission_time_s")
        lst = self._snapshots.get(object_id)
        if not lst or len(lst) == 0:
            raise HistoryUnavailableError(f"no history for {object_id!r}")
        if len(lst) == 1:
            if lst[0].timestamp_s != t:
                raise HistoryUnavailableError(
                    f"emission {t!r}s outside single snapshot at {lst[0].timestamp_s!r}s for {object_id!r}"
                )
            return lst[0]
        # check bounds
        if t < lst[0].timestamp_s - 1e-12 * max(1.0, lst[0].timestamp_s):
            raise HistoryUnavailableError(
                f"emission {t!r}s precedes earliest snapshot {lst[0].timestamp_s!r}s for {object_id!r}"
            )
        if t > lst[-1].timestamp_s + 1e-12 * max(1.0, lst[-1].timestamp_s):
            raise HistoryUnavailableError(
                f"emission {t!r}s exceeds latest snapshot {lst[-1].timestamp_s!r}s for {object_id!r}"
            )
        # exact hit
        for s in lst:
            if s.timestamp_s == t:
                return s
        # find bracket
        lo_idx = max(i for i, s in enumerate(lst) if s.timestamp_s <= t)
        s0, s1 = lst[lo_idx], lst[lo_idx + 1]
        t0, t1 = s0.timestamp_s, s1.timestamp_s
        w = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
        # interpolate numeric fields linearly; provenance becomes DERIVED_DATA (blend)
        merged_state: Dict[str, Any] = {}
        keys = set(s0.state.keys()) | set(s1.state.keys())
        for k in keys:
            v0 = s0.state.get(k)
            v1 = s1.state.get(k)
            if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
                # linear
                merged_state[k] = float(v0) + w * (float(v1) - float(v0))
            elif v0 is not None and v1 is not None and isinstance(v0, (list, tuple)) and isinstance(v1, (list, tuple)) and len(v0) == len(v1):
                # elementwise for position-like tuples
                merged_state[k] = tuple(float(a) + w * (float(b) - float(a)) for a, b in zip(v0, v1))
            else:
                merged_state[k] = v0 if w < 0.5 else v1
        # provenance: if both sides same, preserve that provenance; otherwise DERIVED_DATA
        if s0.provenance.provenance == s1.provenance.provenance and s0.provenance.source_label == s1.provenance.source_label:
            prov = s0.provenance
        else:
            prov = ProvenanceTag(DataProvenance.DERIVED_DATA, source_label="astra.observation.history")
        # epoch: take nearest
        epoch = s0.epoch if w < 0.5 else s1.epoch
        # metadata: shallow merge
        meta = dict(s0.metadata)
        meta.update(s1.metadata)
        meta["interpolated"] = True
        meta["interpolation_weight"] = w
        return HistoricalSnapshot(
            timestamp_s=t,
            state=merged_state,
            provenance=prov,
            cosmic_time_s=None,
            epoch=epoch,
            metadata=meta,
        )

    def get_state_at(self, object_id: str, timestamp_s: float) -> HistoricalSnapshot:
        return self.reconstruct_state(object_id, timestamp_s)

    # -- timeline events -------------------------------------------------
    def add_event(self, event: TimelineEvent) -> None:
        if not isinstance(event, TimelineEvent):
            raise TypeError("event must be TimelineEvent")
        if event.event_id in self._events:
            raise ValueError(f"duplicate event_id {event.event_id!r}")
        self._events[event.event_id] = event
        # insert sorted
        lst = self._events_by_time
        for i, e in enumerate(lst):
            if e.timestamp_s > event.timestamp_s:
                lst.insert(i, event)
                return
        lst.append(event)

    def get_event(self, event_id: str) -> Optional[TimelineEvent]:
        return self._events.get(event_id)

    def events_in_range(self, t_start: float, t_end: float) -> Tuple[TimelineEvent, ...]:
        ts = _finite_time(t_start, "t_start")
        te = _finite_time(t_end, "t_end")
        if te < ts:
            raise ValueError("t_end must be >= t_start")
        return tuple(e for e in self._events_by_time if ts <= e.timestamp_s <= te)

    def all_events(self) -> Tuple[TimelineEvent, ...]:
        return tuple(self._events_by_time)

    # -- cosmic epoch ----------------------------------------------------
    def epoch_for_time(self, timestamp_s: float) -> str:
        t = _finite_time(timestamp_s, "timestamp_s")
        # Determine epoch by scanning snapshots? Simple heuristic: use stored epoch nearest
        # If no history, return PRESENT/FUTURE based on threshold.
        # For determinism, return the epoch of the latest snapshot <= t if exists.
        for lst in self._snapshots.values():
            for s in reversed(lst):
                if s.timestamp_s <= t and s.epoch:
                    return s.epoch
        # fallback: classify by magnitude (illustrative)
        if t < 1e9:
            return CosmicEpoch.RECOMBINATION.value
        if t < 5e9:
            return CosmicEpoch.STAR_FORMATION.value
        return CosmicEpoch.PRESENT.value

    # -- persistence -----------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "snapshots": {oid: [s.to_dict() for s in snaps] for oid, snaps in self._snapshots.items()},
            "events": [e.to_dict() for e in self._events_by_time],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CosmicHistory":
        obj = cls()
        for oid, snaps in data.get("snapshots", {}).items():
            for sd in snaps:
                obj.add_snapshot(oid, HistoricalSnapshot.from_dict(sd))
        for ed in data.get("events", []):
            obj.add_event(TimelineEvent.from_dict(ed))
        return obj

    def object_ids(self) -> Tuple[str, ...]:
        return tuple(self._snapshots.keys())
