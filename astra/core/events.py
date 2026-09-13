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


# Handler type
EventHandler = Callable[[Event], None]


@dataclass
class Subscription:
    """Represents an event subscription."""

    handler: EventHandler
    priority: EventPriority
    enabled: bool = True


class EventBus:
    """Deterministic event bus for ASTRA simulation events."""

    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._event_history: List[Event] = []
        self._lock = threading.RLock()
        self._sequence_counter = 0
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
            subscription = Subscription(handler=handler, priority=priority)
            self._subscriptions[event_name].append(subscription)
            # Keep subscriptions sorted by priority
            self._subscriptions[event_name].sort(key=lambda s: s.priority)
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
        errors = []
        subscriptions = self._subscriptions.get(event.name, [])

        # Sort subscriptions by priority for deterministic ordering
        sorted_subs = sorted(subscriptions, key=lambda s: (s.priority, id(s.handler)))

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
