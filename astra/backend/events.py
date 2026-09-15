"""
ASTRA Backend — event integration (no global duplication).

Wraps astra.core.events.EventBus as the single bus.
Backend creates scoped publishers/subscribers that integrate with
engine lifecycle, recovery, and diagnostics without creating a
second bus or breaking ownership/lifecycle.

Spec §9:
  - Integrates with existing event infrastructure (string-named events)
  - Clear ownership and lifecycle (subscribe returns handle with unsubscribe)
  - No duplication of event buses
  - Tested: event integration
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Union

from astra.core.events import EventBus, Event, EventPriority

from astra.backend.exceptions import EventIntegrationError


@dataclass
class SubscriptionHandle:
    """Ownership handle for a subscription; caller must retain and close."""
    id: str
    event_names: Set[str]
    label: str
    _bus: Any = field(repr=False, compare=False)
    _handlers: Dict[str, Any] = field(repr=False, default_factory=dict)  # name -> handler
    _active: bool = field(default=True, repr=False)

    def unsubscribe(self) -> bool:
        if not self._active:
            return False
        ok_any = False
        for name, handler in list(self._handlers.items()):
            try:
                # core EventBus.unsubscribe(event_name, handler)
                self._bus.unsubscribe(name, handler)
                ok_any = True
            except Exception:
                pass
        self._active = False
        return ok_any or True  # consider unsubscribed even if no handler matched

    @property
    def active(self) -> bool:
        return self._active


class BackendEventHub:
    """
    Scoped facade over the single authoritative EventBus.

    - Owns no bus: it *references* the engine/persistence-provided bus.
    - Tracks subscriptions for lifecycle cleanup.
    - Emits diagnostics / counts for health.
    - Thread-safe.
    - Compatible with core EventBus (string event names) and legacy
      EventType-style enums (coerced to string value).
    """

    def __init__(self, bus: Optional[EventBus] = None, *, owner: str = "backend"):
        self._bus: EventBus = bus if bus is not None else EventBus()
        self._owner = owner
        self._subs: Dict[str, SubscriptionHandle] = {}
        self._lock = threading.Lock()
        self._published = 0
        self._received = 0
        self._errors = 0

    @property
    def bus(self) -> EventBus:
        return self._bus

    @property
    def owner(self) -> str:
        return self._owner

    # -- helpers --

    @staticmethod
    def _coerce_name(x: Any) -> str:
        if isinstance(x, str):
            if not x:
                raise EventIntegrationError("event name must be non-empty string", operation="subscribe", resource=str(x))
            return x
        # Enum-like with .value
        if hasattr(x, "value") and isinstance(getattr(x, "value"), str):
            v = getattr(x, "value")
            if not v:
                raise EventIntegrationError("event enum value must be non-empty string", operation="subscribe", resource=str(x))
            return v
        raise EventIntegrationError(f"event type must be str or Enum, got {x!r}", operation="subscribe", resource=str(x))

    # -- subscription with lifecycle --

    def subscribe(
        self,
        event_names: Union[str, List[Any], Set[Any]],
        handler: Callable[[Event], None],
        *,
        label: str = "",
        priority: EventPriority = EventPriority.NORMAL,
    ) -> SubscriptionHandle:
        # Normalize to set of names
        if isinstance(event_names, str):
            names = {self._coerce_name(event_names)}
        elif isinstance(event_names, (list, set, tuple)):
            if not event_names:
                raise EventIntegrationError("subscribe requires at least one event name", operation="subscribe", resource=label)
            names = {self._coerce_name(x) for x in event_names}
        else:
            raise EventIntegrationError(f"event_names must be str or list/set, got {type(event_names).__name__}", operation="subscribe", resource=label)

        if not callable(handler):
            raise EventIntegrationError("handler must be callable", operation="subscribe", resource=label)

        lab = label or f"{self._owner}.sub.{uuid.uuid4().hex[:6]}"
        handle_id = uuid.uuid4().hex

        # Wrap handler to count receives/errors without swallowing
        def _wrapped(event: Event) -> None:
            with self._lock:
                self._received += 1
            try:
                handler(event)
            except Exception as e:
                with self._lock:
                    self._errors += 1
                raise

        # Subscribe per-name (core bus expects one name per call)
        handlers: Dict[str, Any] = {}
        try:
            for name in names:
                self._bus.subscribe(name, _wrapped, priority)
                handlers[name] = _wrapped
        except Exception as e:
            # rollback partial subscriptions
            for n, h in handlers.items():
                try:
                    self._bus.unsubscribe(n, h)
                except Exception:
                    pass
            raise EventIntegrationError(f"subscribe failed: {e}", operation="subscribe", resource=lab, cause=e)

        handle = SubscriptionHandle(id=handle_id, event_names=set(names), label=lab, _bus=self._bus, _handlers=handlers)
        with self._lock:
            self._subs[handle_id] = handle
        return handle

    def unsubscribe(self, handle: SubscriptionHandle) -> bool:
        if not isinstance(handle, SubscriptionHandle):
            raise EventIntegrationError("unsubscribe requires SubscriptionHandle", operation="unsubscribe")
        with self._lock:
            existed = handle.id in self._subs
        ok = handle.unsubscribe()
        if existed:
            with self._lock:
                self._subs.pop(handle.id, None)
        return ok

    def unsubscribe_all(self, owner_prefix: Optional[str] = None) -> int:
        with self._lock:
            handles = list(self._subs.values())
        n = 0
        for h in handles:
            if owner_prefix and not h.label.startswith(owner_prefix):
                continue
            if h.unsubscribe():
                n += 1
            with self._lock:
                self._subs.pop(h.id, None)
        return n

    def active_subscriptions(self) -> List[Dict[str, Any]]:
        with self._lock:
            out = []
            for h in self._subs.values():
                out.append({
                    "id": h.id,
                    "label": h.label,
                    "types": sorted(h.event_names),
                    "active": h.active,
                })
            return out

    # -- publish (delegates to bus, tracks) --

    def publish(
        self,
        event_name: Union[str, Any],
        payload: Optional[Dict[str, Any]] = None,
        *,
        tick: int = 0,
        priority: EventPriority = EventPriority.NORMAL,
        source: Optional[str] = None,
    ) -> List[Exception]:
        name = self._coerce_name(event_name)
        src = source or self._owner
        try:
            errors: List[Exception] = self._bus.publish_sync(name, tick, payload or {}, priority, source=src)
        except Exception as e:
            raise EventIntegrationError(f"publish failed: {e}", operation="publish", resource=name, cause=e)
        with self._lock:
            self._published += 1
        return errors

    def publish_event(self, event: Event) -> List[Exception]:
        """Publish a pre-built Event via bus.publish(event)."""
        try:
            errors = self._bus.publish(event)
        except Exception as e:
            raise EventIntegrationError(f"publish_event failed: {e}", operation="publish_event", resource=getattr(event, 'name', ''), cause=e)
        with self._lock:
            self._published += 1
        return errors

    # -- diagnostics --

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            subs = len(self._subs)
            published = self._published
            received = self._received
            errors = self._errors
        bus_stats = {}
        try:
            # core has no get_stats; provide history size and failure counts
            history = self._bus.get_history()
            bus_stats = {
                "history_size": len(history),
                "failed_handlers": self._bus.get_failed_handler_count(),
                "sequence": self._bus.get_sequence_counter(),
            }
        except Exception:
            pass
        return {
            "owner": self._owner,
            "active_subscriptions": subs,
            "published_via_hub": published,
            "received_via_hub": received,
            "handler_errors": errors,
            "bus": bus_stats,
        }

    def shutdown(self) -> None:
        """Lifecycle: unsubscribe all owned subscriptions. Does NOT shutdown bus."""
        self.unsubscribe_all()
