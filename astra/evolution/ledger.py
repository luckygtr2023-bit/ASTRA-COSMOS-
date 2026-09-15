"""ASTRA COSMOS — Phase 21: evolution ledger (events, histories, causality).

The ledger is the engine's append-only record of evolutionary events and
per-object state samples. It enforces:

- causal integrity: every causal_parent_event_id must reference a known
  event, and cosmic time must be NON-DECREASING along a causal chain
  (cosmic time is a global order in the cosmological background) —
  violations raise ``EvolutionLimitationError(CAUSAL_INCONSISTENCY)``;
- deterministic ordering: events are recorded in execution order with
  sequential ids; per-object histories are ordered by recording time;
- bounded memory: per-object history is deterministically decimated
  (kept every 2nd sample) when the configured sample budget is reached;
  every decimation is counted and reported in diagnostics — it is a
  documented approximation, never a silent drop.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .config import PerformanceBudget
from .errors import EvolutionLimitationError, EvolutionValidationError
from .events import EvolutionEvent
from .limitations import LimitationState
from .state import EvolutionState


class EvolutionLedger:
    """Append-only event + history store with causal validation."""

    def __init__(self) -> None:
        self._events: List[EvolutionEvent] = []
        self._event_index: Dict[str, EvolutionEvent] = {}
        self._histories: Dict[str, List[EvolutionState]] = {}
        self._decimations: Dict[str, int] = {}
        self._steps: int = 0

    # ------------------------------------------------------------- events
    def record_event(self, event: EvolutionEvent) -> None:
        if not isinstance(event, EvolutionEvent):
            raise EvolutionValidationError("ledger.record_event requires an EvolutionEvent")
        if event.event_id in self._event_index:
            raise EvolutionValidationError(f"duplicate event_id {event.event_id}")
        if event.causal_parent_event_id is not None:
            parent = self._event_index.get(event.causal_parent_event_id)
            if parent is None:
                raise EvolutionLimitationError(
                    LimitationState.CAUSAL_INCONSISTENCY,
                    f"event {event.event_id} references unknown causal parent "
                    f"{event.causal_parent_event_id}",
                )
            if event.cosmic_time_gyr < parent.cosmic_time_gyr:
                raise EvolutionLimitationError(
                    LimitationState.CAUSAL_INCONSISTENCY,
                    f"event {event.event_id} at {event.cosmic_time_gyr} precedes its "
                    f"causal parent at {parent.cosmic_time_gyr}; causal chains must be "
                    "non-decreasing in cosmic time",
                )
        self._events.append(event)
        self._event_index[event.event_id] = event

    def last_event_id_for(self, object_id: str) -> Optional[str]:
        """Most recent event involving the object (source or resulting)."""
        for event in reversed(self._events):
            if object_id in event.source_object_ids or object_id in event.resulting_object_ids:
                return event.event_id
        return None

    def events(self) -> Tuple[EvolutionEvent, ...]:
        return tuple(self._events)

    def events_for(self, object_id: str) -> Tuple[EvolutionEvent, ...]:
        return tuple(
            e for e in self._events
            if object_id in e.source_object_ids or object_id in e.resulting_object_ids
        )

    # ----------------------------------------------------------- histories
    def record_sample(self, state: EvolutionState, budget: PerformanceBudget) -> None:
        if not isinstance(state, EvolutionState):
            raise EvolutionValidationError("ledger.record_sample requires an EvolutionState")
        self._steps += 1
        history = self._histories.setdefault(state.object_id, [])
        history.append(state)
        cap = budget.max_history_samples_per_object
        if len(history) > cap:
            # Deterministic decimation: keep every 2nd sample; count it.
            del history[1::2]
            self._decimations[state.object_id] = self._decimations.get(state.object_id, 0) + 1

    def history(self, object_id: str) -> Tuple[EvolutionState, ...]:
        return tuple(self._histories.get(object_id, ()))

    def object_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._histories.keys()))

    def decimations(self) -> Dict[str, int]:
        return dict(sorted(self._decimations.items()))

    @property
    def steps(self) -> int:
        return self._steps

    # ---------------------------------------------------------- validation
    def validate(self) -> Tuple[int, int]:
        """Full causal sweep: known parents, non-decreasing chain times,
        duplicate ids. Returns (event_count, chain_edges_checked)."""
        checked = 0
        for event in self._events:
            if event.causal_parent_event_id is not None:
                parent = self._event_index.get(event.causal_parent_event_id)
                if parent is None:
                    raise EvolutionLimitationError(
                        LimitationState.CAUSAL_INCONSISTENCY,
                        f"event {event.event_id} references unknown causal parent",
                    )
                if event.cosmic_time_gyr < parent.cosmic_time_gyr:
                    raise EvolutionLimitationError(
                        LimitationState.CAUSAL_INCONSISTENCY,
                        f"event {event.event_id} precedes its causal parent",
                    )
                checked += 1
        return len(self._events), checked

    # --------------------------------------------------------- persistence
    def to_dict(self) -> Dict[str, object]:
        return {
            "events": [e.to_dict() for e in self._events],
            "histories": {
                oid: [s.to_dict() for s in self._histories[oid]]
                for oid in sorted(self._histories.keys())
            },
            "decimations": dict(sorted(self._decimations.items())),
            "steps": self._steps,
        }

    def load_dict(self, d: Dict[str, object]) -> None:
        if self._events or self._histories:
            raise EvolutionValidationError("ledger.load_dict requires an empty ledger")
        for e in d.get("events", []):
            self.record_event(EvolutionEvent.from_dict(e))
        for oid, samples in d.get("histories", {}).items():
            self._histories[str(oid)] = [EvolutionState.from_dict(s) for s in samples]
        for oid, count in d.get("decimations", {}).items():
            self._decimations[str(oid)] = int(count)
        self._steps = int(d.get("steps", 0))


__all__ = ["EvolutionLedger"]
