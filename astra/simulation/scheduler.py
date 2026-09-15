"""Deterministic simulation-time event scheduler.

Requirements: deterministic ordering by (timestamp, priority, sequence),
cancellation, rescheduling, persistence, replay compatibility, safe handling
during large jumps. Never relies on dict/set iteration order."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .exceptions import SchedulerError, InvalidTimestampError


def _validate_time(t: Any, name: str = "time") -> float:
    if isinstance(t, bool) or not isinstance(t, (int, float)):
        raise InvalidTimestampError(f"{name} must be a number, got {type(t).__name__}", operation="scheduler.validate")
    v = float(t)
    if math.isnan(v) or math.isinf(v):
        raise InvalidTimestampError(f"{name} cannot be NaN/Inf, got {t!r}", operation="scheduler.validate")
    if v < 0.0:
        raise InvalidTimestampError(f"{name} cannot be negative, got {v!r}", operation="scheduler.validate")
    if v > 1e18:
        raise InvalidTimestampError(f"{name} overflow beyond 1e18s, got {v!r}", operation="scheduler.validate")
    return v


@dataclass(frozen=True, order=True)
class ScheduledEvent:
    """Immutable scheduled event with deterministic ordering."""

    time_s: float
    priority: int  # lower = higher priority (0 critical)
    sequence: int  # tie-breaker, insertion order
    id: str
    name: str = ""
    data: Dict[str, Any] = field(default_factory=dict, compare=False)
    cancelled: bool = field(default=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time_s": self.time_s,
            "priority": self.priority,
            "sequence": self.sequence,
            "id": self.id,
            "name": self.name,
            "data": dict(self.data),
            "cancelled": self.cancelled,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScheduledEvent":
        return cls(
            time_s=float(d["time_s"]),
            priority=int(d["priority"]),
            sequence=int(d["sequence"]),
            id=str(d["id"]),
            name=str(d.get("name", "")),
            data=dict(d.get("data", {})),
            cancelled=bool(d.get("cancelled", False)),
        )


class EventScheduler:
    """Deterministic scheduler.

    Ordering: (time_s, priority, sequence). All operations deterministic.
    Persistence via to_dict/from_dict. Replay-compatible.
    """

    def __init__(self):
        self._events: Dict[str, ScheduledEvent] = {}
        self._sequence_counter = 0
        self._time_s = 0.0

    @property
    def current_time_s(self) -> float:
        return self._time_s

    def set_time(self, t: float) -> None:
        self._time_s = _validate_time(t, "current_time")

    def schedule(self, name: str, at_time_s: float, data: Optional[Dict[str, Any]] = None, priority: int = 0, event_id: Optional[str] = None) -> ScheduledEvent:
        at = _validate_time(at_time_s, "at_time_s")
        if not isinstance(name, str) or not name:
            raise SchedulerError("event name must be non-empty string", operation="schedule")
        if not isinstance(priority, int):
            raise SchedulerError("priority must be int", operation="schedule")
        if at < self._time_s - 1e-12:
            raise SchedulerError(f"cannot schedule in the past: at {at} < current {self._time_s}", operation="schedule")
        self._sequence_counter += 1
        eid = event_id or f"evt_{at:.6f}_{self._sequence_counter:06d}"
        if eid in self._events and not self._events[eid].cancelled:
            raise SchedulerError(f"event id already exists: {eid}", operation="schedule")
        ev = ScheduledEvent(time_s=at, priority=priority, sequence=self._sequence_counter, id=eid, name=name, data=dict(data or {}))
        self._events[eid] = ev
        return ev

    def cancel(self, event_id: str) -> bool:
        if event_id not in self._events:
            return False
        ev = self._events[event_id]
        if ev.cancelled:
            return False
        self._events[event_id] = ScheduledEvent(
            time_s=ev.time_s, priority=ev.priority, sequence=ev.sequence, id=ev.id, name=ev.name, data=ev.data, cancelled=True
        )
        return True

    def reschedule(self, event_id: str, new_time_s: float) -> ScheduledEvent:
        new_t = _validate_time(new_time_s, "new_time_s")
        if event_id not in self._events:
            raise SchedulerError(f"event not found: {event_id}", operation="reschedule")
        ev = self._events[event_id]
        if ev.cancelled:
            raise SchedulerError(f"cannot reschedule cancelled event: {event_id}", operation="reschedule")
        if new_t < self._time_s - 1e-12:
            raise SchedulerError(f"cannot reschedule to past: {new_t} < {self._time_s}", operation="reschedule")
        # Preserve priority and name, but new sequence for tie-breaking? Keep original sequence to preserve determinism of original ordering? Instead assign new sequence to reflect reschedule time.
        self._sequence_counter += 1
        new_ev = ScheduledEvent(time_s=new_t, priority=ev.priority, sequence=self._sequence_counter, id=ev.id, name=ev.name, data=ev.data, cancelled=False)
        self._events[event_id] = new_ev
        return new_ev

    def peek_next(self) -> Optional[ScheduledEvent]:
        active = [e for e in self._events.values() if not e.cancelled]
        if not active:
            return None
        return min(active)  # dataclass order

    def pop_due(self, up_to_time_s: float) -> List[ScheduledEvent]:
        up_to = _validate_time(up_to_time_s, "up_to_time_s")
        due = [e for e in self._events.values() if not e.cancelled and e.time_s <= up_to + 1e-12]
        due_sorted = sorted(due)
        # Remove popped from active? For scheduler, popping means they are dispatched and should be removed
        for e in due_sorted:
            del self._events[e.id]
        # Advance current time to up_to if forward
        if up_to > self._time_s:
            self._time_s = up_to
        return due_sorted

    def advance_to(self, target_time_s: float, handler: Optional[Callable[[ScheduledEvent], None]] = None) -> List[ScheduledEvent]:
        target = _validate_time(target_time_s, "target_time_s")
        if target < self._time_s - 1e-12:
            raise SchedulerError(f"cannot advance scheduler backward: {target} < {self._time_s}", operation="advance_to")
        due = self.pop_due(target)
        if handler is not None:
            for ev in due:
                try:
                    handler(ev)
                except Exception:
                    # Scheduler must not swallow handler errors silently; re-raise
                    raise
        else:
            # If no handler, just advance time
            self._time_s = target
        return due

    def get_due_in_range(self, from_s: float, to_s: float) -> List[ScheduledEvent]:
        f = _validate_time(from_s, "from_s")
        t = _validate_time(to_s, "to_s")
        if t < f:
            raise SchedulerError("to_s cannot be before from_s", operation="get_due_in_range")
        lst = [e for e in self._events.values() if not e.cancelled and f - 1e-12 <= e.time_s <= t + 1e-12]
        return sorted(lst)

    def count(self) -> int:
        return sum(1 for e in self._events.values() if not e.cancelled)

    def clear(self) -> None:
        self._events.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_time_s": self._time_s,
            "sequence_counter": self._sequence_counter,
            "events": [e.to_dict() for e in sorted(self._events.values())],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventScheduler":
        obj = cls()
        obj._time_s = float(data.get("current_time_s", 0.0))
        obj._sequence_counter = int(data.get("sequence_counter", 0))
        for ed in data.get("events", []):
            ev = ScheduledEvent.from_dict(ed)
            obj._events[ev.id] = ev
            # ensure counter at least max sequence
            if ev.sequence > obj._sequence_counter:
                obj._sequence_counter = ev.sequence
        return obj

    def snapshot(self) -> Dict[str, Any]:
        return self.to_dict()

    def restore(self, data: Dict[str, Any]) -> None:
        other = self.from_dict(data)
        self._events = other._events
        self._sequence_counter = other._sequence_counter
        self._time_s = other._time_s
