"""
ASTRA Backend — runtime implementation with underlying infrastructure
integration (§13).

Respects Engine lifecycle (START → INITIALIZE → RUN → PAUSE/RESUME → SHUTDOWN → RECOVERY).
Never duplicates the engine's tick loop; it *coordinates* delivery,
cache, events, persistence, diagnostics around it.

All lifecycle transitions are:
  - explicit (no hidden side-effects)
  - validated (illegal transitions raise with operation/resource)
  - bounded (no unbounded buffering of ticks)
  - thread-safe
  - integrated with RecoveryManager + DiagnosticsCollector
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from astra.core.engine import Engine, EngineState
from astra.core.recovery import RecoveryManager, RecoveryPolicy
from astra.core.events import EventBus

from astra.backend.config import AstraBackendConfig
from astra.backend.persistence import BackendPersistence
from astra.backend.events import BackendEventHub
from astra.backend.cache import BoundedCache, CacheRegistry
from astra.backend.diagnostics import DiagnosticsCollector, HealthStatus
from astra.backend.exceptions import RuntimeError_
from astra.backend.security import backend_operation


class RuntimeState(str, Enum):
    CREATED = "CREATED"
    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


@dataclass
class RuntimeStats:
    state: RuntimeState
    tick: int
    uptime_s: float
    deliveries: int
    cache_hit_rate: float
    health: str


class BackendRuntime:
    """
    Orchestrates backend/runtime coordination.

    Does NOT own the simulation tick loop — Engine does.
    Provides hooks the caller wires to engine events:
      on_tick(tick, sim_time, world_objects) -> produce render/graphics frames
      on_checkpoint(label, payload)          -> persist via BackendPersistence
      on_recovery(failure_record)            -> invalidate caches, emit diagnostics

    Lifecycle (§13, tested):
      runtime.initialize()  -> may load config checkpoint
      runtime.start()       -> subscribes to engine events, enables delivery
      runtime.pause() / resume()
      runtime.shutdown()    -> unsubscribes, flushes persistence, clears transient caches
      runtime.recover()     -> explicit recovery entry (also wired to RecoveryManager)
    """

    def __init__(
        self,
        engine: Optional[Engine] = None,
        config: Optional[AstraBackendConfig] = None,
        persistence: Optional[BackendPersistence] = None,
        event_hub: Optional[BackendEventHub] = None,
        diagnostics: Optional[DiagnosticsCollector] = None,
        cache_registry: Optional[CacheRegistry] = None,
        render_delivery: Optional[Any] = None,
        graphics_delivery: Optional[Any] = None,
    ):
        self._engine: Optional[Engine] = engine
        self._config: AstraBackendConfig = (config.clone() if config else AstraBackendConfig())
        self._persistence: BackendPersistence = persistence or BackendPersistence()
        bus = None
        if event_hub is not None:
            bus = event_hub.bus
        elif engine is not None:
            try:
                bus = engine.event_bus
            except Exception:
                bus = None
        self._hub: BackendEventHub = event_hub or BackendEventHub(bus=bus, owner="backend.runtime")
        self._diag: DiagnosticsCollector = diagnostics or DiagnosticsCollector(max_entries=self._config.diagnostics.max_log_entries)
        self._caches: CacheRegistry = cache_registry or CacheRegistry()
        self._render_delivery = render_delivery
        self._graphics_delivery = graphics_delivery

        self._state = RuntimeState.CREATED
        self._lock = threading.RLock()
        self._tick = 0
        self._started_monotonic: Optional[float] = None
        self._pause_monotonic: Optional[float] = None
        self._deliveries = 0
        self._recovery: RecoveryManager = RecoveryManager(policy=self._config.runtime.recovery_policy)
        self._recovery.set_max_retry_attempts(self._config.runtime.max_retry_attempts)
        self._subs: List[Any] = []

    @property
    def state(self) -> RuntimeState:
        with self._lock:
            return self._state

    @property
    def config(self) -> AstraBackendConfig:
        return self._config.clone()

    @property
    def diagnostics(self) -> DiagnosticsCollector:
        return self._diag

    @property
    def event_hub(self) -> BackendEventHub:
        return self._hub

    @property
    def persistence(self) -> BackendPersistence:
        return self._persistence

    # -- lifecycle --

    def initialize(self, *, load_config_checkpoint: Optional[str] = None) -> None:
        with self._lock:
            if self._state != RuntimeState.CREATED:
                raise RuntimeError_("initialize only from CREATED", operation="initialize", resource=self._state.value)
            with backend_operation("runtime.initialize"):
                if load_config_checkpoint:
                    loaded = self._persistence.load_backend_config(load_config_checkpoint)
                    if loaded is not None:
                        self._config = loaded
                        self._diag.info("runtime", "initialize", f"loaded config checkpoint {load_config_checkpoint}", {"fingerprint": loaded.fingerprint()})
                self._recovery.set_policy(self._config.runtime.recovery_policy)
                self._recovery.set_max_retry_attempts(self._config.runtime.max_retry_attempts)
                self._diag.set_health("runtime", HealthStatus.HEALTHY)
                self._state = RuntimeState.INITIALIZED
                self._diag.info("runtime", "initialize", "initialized", {"schema_version": self._config.schema_version})

    def start(self) -> None:
        with self._lock:
            if self._state not in (RuntimeState.INITIALIZED, RuntimeState.PAUSED, RuntimeState.STOPPED):
                raise RuntimeError_("start only from INITIALIZED/PAUSED/STOPPED", operation="start", resource=self._state.value)
            with backend_operation("runtime.start"):
                self._started_monotonic = time.monotonic()
                if self._engine is not None:
                    # Subscribe to engine lifecycle events (string names)
                    for evt_name in ["engine_started", "engine_paused", "engine_initialized"]:
                        try:
                            h = self._hub.subscribe(evt_name, self._on_engine_event, label=f"runtime.{evt_name}")
                            self._subs.append(h)
                        except Exception:
                            pass
                self._state = RuntimeState.RUNNING
                self._diag.info("runtime", "start", "running")
                try:
                    self._hub.publish("runtime_started", {"tick": self._tick, "source": "backend.runtime"}, tick=self._tick)
                except Exception:
                    pass

    def pause(self) -> None:
        with self._lock:
            if self._state != RuntimeState.RUNNING:
                raise RuntimeError_("pause only from RUNNING", operation="pause", resource=self._state.value)
            with backend_operation("runtime.pause"):
                self._pause_monotonic = time.monotonic()
                self._state = RuntimeState.PAUSED
                self._diag.info("runtime", "pause", "paused")

    def resume(self) -> None:
        with self._lock:
            if self._state != RuntimeState.PAUSED:
                raise RuntimeError_("resume only from PAUSED", operation="resume", resource=self._state.value)
            with backend_operation("runtime.resume"):
                self._state = RuntimeState.RUNNING
                self._diag.info("runtime", "resume", "resumed")

    def shutdown(self, *, clear_transient_caches: bool = True) -> None:
        with self._lock:
            if self._state in (RuntimeState.CREATED, RuntimeState.STOPPED):
                if self._state == RuntimeState.CREATED:
                    self._state = RuntimeState.STOPPED
                    return
                return
            with backend_operation("runtime.shutdown"):
                for h in list(self._subs):
                    try:
                        h.unsubscribe()
                    except Exception:
                        pass
                self._subs.clear()
                try:
                    self._hub.unsubscribe_all("runtime.")
                except Exception:
                    pass
                if clear_transient_caches:
                    try:
                        self._caches.clear_all()
                    except Exception:
                        pass
                    if self._render_delivery:
                        try:
                            self._render_delivery.invalidate_all()
                        except Exception:
                            pass
                    if self._graphics_delivery:
                        try:
                            self._graphics_delivery.invalidate_all()
                        except Exception:
                            pass
                self._state = RuntimeState.STOPPED
                self._diag.info("runtime", "shutdown", "stopped")
                self._diag.set_health("runtime", HealthStatus.UNKNOWN)

    def recover(self, failure_type: str, operation: str, tick: int, message: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Explicit recovery entry: delegates to RecoveryManager, invalidates caches
        for the failed tick, emits diagnostics. Returns True if caller should retry.
        """
        with self._lock:
            with backend_operation("runtime.recover"):
                should_retry = self._recovery.record_failure(failure_type, operation, tick, message, context)
                if self._render_delivery:
                    try:
                        self._render_delivery.invalidate_tick(tick)
                    except Exception:
                        pass
                if self._graphics_delivery:
                    try:
                        self._graphics_delivery.invalidate_tick(tick)
                    except Exception:
                        pass
                if should_retry:
                    self._diag.warning("runtime", "recover", f"recovering {operation} at tick {tick}: {message}", {"failure_type": failure_type, "tick": tick, "retry": True})
                    self._diag.set_health("runtime", HealthStatus.DEGRADED)
                else:
                    self._diag.error("runtime", "recover", f"recovery failed for {operation} at tick {tick}: {message}", {"failure_type": failure_type, "tick": tick})
                    self._state = RuntimeState.FAILED
                    self._diag.set_health("runtime", HealthStatus.UNHEALTHY)
                return should_retry

    # -- tick coordination (called by integrator, not by background thread) --

    def on_tick_derived(self, tick: int, simulation_time_s: float, world_objects: List[Dict[str, Any]], **kwargs) -> Optional[Dict[str, Any]]:
        """
        Called after authoritative engine tick completed.
        Produces render + graphics frames (if deliveries configured),
        records diagnostics. Never mutates world_objects.

        Returns diagnostic dict with frame identities; caller may persist.
        """
        with self._lock:
            if self._state != RuntimeState.RUNNING:
                raise RuntimeError_("on_tick_derived only while RUNNING", operation="on_tick_derived", resource=self._state.value)
            self._tick = int(tick)
            self._deliveries += 1
        result: Dict[str, Any] = {"tick": tick, "simulation_time_s": simulation_time_s}
        if self._render_delivery is not None:
            try:
                frame = self._render_delivery.derive(tick=tick, simulation_time_s=simulation_time_s, world_objects=world_objects, **kwargs)
                result["render"] = {"count": frame.render_state.count(), "provenance": frame.render_state.provenance}
                if self._graphics_delivery is not None:
                    try:
                        gstate = self._graphics_delivery.derive(frame.render_state)
                        result["graphics"] = {"count": gstate.count(), "provenance": gstate.provenance}
                    except Exception as ge:
                        self._diag.warning("runtime", "on_tick_derived", f"graphics derive degraded: {ge}")
                        result["graphics_error"] = str(ge)
            except Exception as e:
                should_retry = self.recover("render_derive", "runtime.on_tick_derived", tick, str(e), {"simulation_time_s": simulation_time_s})
                result["render_error"] = str(e)
                result["should_retry"] = should_retry
                return result
        self._recovery.record_success("runtime.on_tick_derived", tick)
        self._diag.debug("runtime", "on_tick_derived", f"tick {tick} derived", result)
        return result

    def _on_engine_event(self, event: Any) -> None:
        try:
            payload = getattr(event, "data", None) or getattr(event, "payload", {}) or {}
            if isinstance(payload, dict) and "tick" in payload:
                with self._lock:
                    self._tick = int(payload["tick"])
            self._diag.debug("runtime", "engine_event", f"engine event {getattr(event, 'name', getattr(event, 'event_type', '?'))}", {"payload": payload})
        except Exception:
            pass

    # -- stats & health --

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            uptime = (time.monotonic() - self._started_monotonic) if self._started_monotonic else 0.0
            state = self._state
            tick = self._tick
            deliveries = self._deliveries
        hit_rate = 0.0
        try:
            if self._render_delivery:
                s = self._render_delivery.stats()
                total = s.get("deliveries", 0) + s.get("cache_hits", 0)
                if total:
                    hit_rate = s.get("cache_hits", 0) / total
        except Exception:
            pass
        return {
            "state": state.value,
            "tick": tick,
            "uptime_s": uptime,
            "deliveries": deliveries,
            "cache_hit_rate": hit_rate,
            "health": self._diag.overall_health().value,
            "recovery": {
                "policy": self._recovery.get_policy().value,
                "consecutive_failures": self._recovery.get_state().consecutive_failures,
                "total_failures": self._recovery.get_state().total_failures,
            },
        }

    def health_summary(self) -> Dict[str, Any]:
        return {
            "runtime": self._diag.get_health("runtime"),
            "overall": self._diag.overall_health().value,
            "hub": self._hub.stats(),
            "caches": self._caches.stats_summary(),
            "render": self._render_delivery.stats() if self._render_delivery and hasattr(self._render_delivery, "stats") else {},
            "graphics": self._graphics_delivery.stats() if self._graphics_delivery and hasattr(self._graphics_delivery, "stats") else {},
        }
