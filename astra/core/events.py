"""ASTRA Core event system."""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional, Set
from enum import IntEnum
import threading
from collections import defaultdict

from astra.core.ids import EventId
from astra.core.logging import get_logger
from astra.core.exceptions import AstraError


class EventPriority(IntEnum):
    """Event priority levels for deterministic ordering."""

    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    DEFERRED = 4


_EVENT_HISTORY_CAP = 100_000


@dataclass
class Event:
    """Base event class for ASTRA simulation events."""

    id: EventId
    name: str
    tick: int
    sequence: int
    priority: EventPriority = EventPriority.NORMAL
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""

    def __post_init__(self):
        if not isinstance(self.id, EventId):
            object.__setattr__(self, "id", EventId(self.id))

    @classmethod
    def create(
        cls,
        name: str,
        tick: int,
        sequence: int,
        priority: EventPriority = EventPriority.NORMAL,
        data: Optional[Dict[str, Any]] = None,
        source: str = "",
    ) -> "Event":
        """Create a new event with a generated ID."""
        event_id = EventId.generate(tick, sequence)
        return cls(
            id=event_id,
            name=name,
            tick=tick,
            sequence=sequence,
            priority=priority,
            data=data or {},
            source=source,
        )

    def __lt__(self, other: "Event") -> bool:
        """Compare events for sorting (deterministic ordering)."""
        # Sort by priority first, then by tick, sequence
        if self.priority != other.priority:
            return self.priority < other.priority
        if self.tick != other.tick:
            return self.tick < other.tick
        return self.sequence < other.sequence

    def to_serializable(self) -> dict:
        """Serialize event to a dictionary for persistence."""
        # Use deterministic value string, not repr
        id_val = self.id.value if isinstance(self.id, EventId) else str(self.id)
        return {
            "id": id_val,
            "name": self.name,
            "tick": self.tick,
            "sequence": self.sequence,
            "priority": int(self.priority),
            "source": self.source,
            "data": self.data,
        }

    @classmethod
    def from_serializable(cls, data: dict) -> "Event":
        """Deserialize event from a dictionary."""
        raw_id = data["id"]
        # Back-compat: handle previously persisted double-wrapped str(EventId)
        if isinstance(raw_id, str) and raw_id.startswith("EventId("):
            # Extract inner value e.g. EventId(value='evt_...')
            try:
                # crude extraction: find first 'evt_' or 'cmd_' etc.
                import re

                m = re.search(r"evt_[0-9_]+|cmd_[0-9_]+|entity_[0-9_]+", raw_id)
                if m:
                    raw_id = m.group(0)
                else:
                    # fallback: try to parse value='...'
                    m2 = re.search(r"value='([^']+)'", raw_id)
                    if m2:
                        raw_id = m2.group(1)
            except Exception:
                pass
        return cls(
            id=EventId(raw_id) if not isinstance(raw_id, EventId) else raw_id,
            name=data["name"],
            tick=data["tick"],
            sequence=data["sequence"],
            priority=EventPriority(data["priority"]),
            source=data.get("source", ""),
            data=data.get("data", {}),
        )


# Handler type
EventHandler = Callable[[Event], None]


@dataclass
class Subscription:
    """Represents an event subscription."""

    handler: EventHandler
    priority: EventPriority
    enabled: bool = True
    registration_index: int = 0


class EventBus:
    """Deterministic event bus for ASTRA simulation events."""

    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._event_history: List[Event] = []
        self._lock = threading.RLock()
        self._sequence_counter = 0
        self._subscription_counter = 0
        self._logger = get_logger("event_bus")
        self._failed_handlers: Dict[str, int] = defaultdict(int)

    def subscribe(
        self,
        event_name: str,
        handler: EventHandler,
        priority: EventPriority = EventPriority.NORMAL,
    ):
        """Subscribe to an event type."""
        with self._lock:
            self._subscription_counter += 1
            subscription = Subscription(
                handler=handler, priority=priority, registration_index=self._subscription_counter
            )
            self._subscriptions[event_name].append(subscription)
            # Keep subscriptions sorted by priority and registration_index
            self._subscriptions[event_name].sort(
                key=lambda s: (s.priority, s.registration_index)
            )
            self._logger.debug(f"Subscribed to {event_name} with priority {priority}")

    def unsubscribe(self, event_name: str, handler: EventHandler):
        """Unsubscribe from an event type."""
        with self._lock:
            subscriptions = self._subscriptions.get(event_name, [])
            self._subscriptions[event_name] = [
                s for s in subscriptions if s.handler != handler
            ]
            self._logger.debug(f"Unsubscribed from {event_name}")

    def publish(self, event: Event) -> List[Exception]:
        """Publish an event to all subscribers. Returns list of handler exceptions."""
        with self._lock:
            errors = []
            subscriptions = self._subscriptions.get(event.name, [])

            # Sort subscriptions by priority and registration_index for deterministic ordering
            sorted_subs = sorted(
                subscriptions, key=lambda s: (s.priority, s.registration_index)
            )

            for sub in sorted_subs:
                if not sub.enabled:
                    continue
                try:
                    sub.handler(event)
                except Exception as e:
                    errors.append(e)
                    self._failed_handlers[event.name] += 1
                    self._logger.error(f"Handler failed for event {event.name}: {e}")

            # Record event in history
            self._event_history.append(event)

            # Apply history cap
            if len(self._event_history) > _EVENT_HISTORY_CAP:
                del self._event_history[: _EVENT_HISTORY_CAP // 2]

            return errors

    def publish_sync(
        self,
        name: str,
        tick: int,
        data: Optional[Dict[str, Any]] = None,
        priority: EventPriority = EventPriority.NORMAL,
        source: str = "",
    ) -> List[Exception]:
        """Synchronously publish an event."""
        with self._lock:
            self._sequence_counter += 1
            event = Event.create(
                name=name,
                tick=tick,
                sequence=self._sequence_counter,
                priority=priority,
                data=data,
                source=source,
            )
            return self.publish(event)

    def get_history(
        self,
        event_name: Optional[str] = None,
        from_tick: int = 0,
        to_tick: Optional[int] = None,
    ) -> List[Event]:
        """Get event history, optionally filtered."""
        with self._lock:
            result = self._event_history.copy()

        if event_name:
            result = [e for e in result if e.name == event_name]
        if from_tick > 0:
            result = [e for e in result if e.tick >= from_tick]
        if to_tick is not None:
            result = [e for e in result if e.tick <= to_tick]

        return sorted(result)

    def clear_history(self):
        """Clear the event history."""
        with self._lock:
            self._event_history.clear()

    def get_failed_handler_count(self, event_name: Optional[str] = None) -> int:
        """Get count of failed handlers."""
        if event_name:
            return self._failed_handlers.get(event_name, 0)
        return sum(self._failed_handlers.values())

    def reset_failure_counts(self):
        """Reset failure counts."""
        self._failed_handlers.clear()

    def get_sequence_counter(self) -> int:
        """Get the current sequence counter."""
        with self._lock:
            return self._sequence_counter

    def set_sequence_counter(self, value: int):
        """Set the sequence counter (for restore)."""
        with self._lock:
            self._sequence_counter = value

    def restore_from_snapshot(self, events_data: list):
        """Restore event history from a snapshot."""
        with self._lock:
            self._event_history = [Event.from_serializable(d) for d in events_data]
            if self._event_history:
                max_seq = max(e.sequence for e in self._event_history)
                self._sequence_counter = max(self._sequence_counter, max_seq)
