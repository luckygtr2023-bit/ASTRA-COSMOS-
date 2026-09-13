"""ASTRA Core engine - main simulation orchestrator."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import threading
import time as time_module

from astra.core.logging import get_logger, LogLevel
from astra.core.config import Config
from astra.core.exceptions import AstraError, AuthorityError
from astra.core.threading import (
    SimulationThreadRegistry,
    AuthorityContext,
    get_simulation_thread_registry,
)
from astra.core.time import SimulationClock, TimeMode
from astra.core.events import EventBus, Event, EventPriority
from astra.core.rng import DeterministicRNG
from astra.core.commands import CommandDispatcher, Command
from astra.core.entities import EntityManager, Entity
from astra.core.coords import FrameRegistry, CoordinateFrame, OriginRebaser
from astra.core.scene import Scene
from astra.core.persistence import PersistenceManager, Snapshot
from astra.core.resources import ResourceManager
from astra.core.recovery import RecoveryManager, RecoveryPolicy
from astra.core.services import ServiceRegistry


class EngineState(Enum):
    """Engine lifecycle states."""

    CREATED = "created"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class EngineStatus:
    """Current engine status snapshot."""

    state: EngineState
    current_tick: int
    simulation_time: float
    entity_count: int
    fps: float = 0.0
    uptime: float = 0.0


class Engine:
    """Main ASTRA simulation engine."""

    def __init__(self, config: Optional[Config] = None):
        self._config = config or Config()
        self._state = EngineState.CREATED
        self._lock = threading.RLock()
        self._logger = get_logger("engine")

        # Initialize core systems
        self._clock = SimulationClock(
            tick_duration=self._config.default_tick_duration,
            mode=TimeMode.INTERNAL_DETERMINISTIC,
        )
        self._event_bus = EventBus()
        self._rng = DeterministicRNG(global_seed=self._config.global_seed)
        self._command_dispatcher = CommandDispatcher()
        self._scene = Scene()
        self._persistence = PersistenceManager(
            base_path=self._config.persistence_path,
            checksum_enabled=self._config.checksum_enabled,
        )
        self._resources = ResourceManager(max_handles=self._config.max_resource_handles)
        self._recovery = RecoveryManager(
            policy=RecoveryPolicy[self._config.recovery_policy],
        )
        self._services = ServiceRegistry()

        # Threading
        self._owns_thread_registration = False
        self._running = False
        self._start_time = 0.0

        # Statistics
        self._total_ticks = 0
        self._last_frame_time = 0.0
        self._fps_history: List[float] = []

        # Register internal services
        self._services.register("engine", self)
        self._services.register("clock", self._clock)
        self._services.register("event_bus", self._event_bus)
        self._services.register("rng", self._rng)
        self._services.register("commands", self._command_dispatcher)
        self._services.register("scene", self._scene)
        self._services.register("persistence", self._persistence)
        self._services.register("resources", self._resources)
        self._services.register("recovery", self._recovery)

        self._logger.info(f"ASTRA Engine created with config: {self._config.engine_name}")

    def initialize(self):
        """Initialize the engine and transition to READY state."""
        with self._lock:
            if self._state != EngineState.CREATED:
                raise AstraError(f"Cannot initialize from state: {self._state.value}")

            try:
                # Register this thread as the simulation thread
                registry = get_simulation_thread_registry()
                thread_id = threading.current_thread().ident
                if thread_id is None:
                    raise AstraError("Cannot determine thread identity during initialize")
                if registry.is_registered() and not registry.is_simulation_thread(thread_id):
                    raise AuthorityError(
                        "Engine.initialize called from a thread that is not the "
                        "registered simulation thread",
                        operation="engine.initialize",
                        context={"current_thread_id": thread_id,
                                 "registered_thread_id": registry.get_simulation_thread_id()}
                    )
                registry.register_simulation_thread(thread_id)
                self._owns_thread_registration = True

                # Perform any additional initialization
                self._logger.info("Initializing ASTRA engine...")

                # Transition to READY
                self._state = EngineState.READY
                self._logger.info("ASTRA engine initialized and ready")

                # Emit initialization event
                self._event_bus.publish_sync("engine_initialized", 0, source="engine")

            except Exception as e:
                self._state = EngineState.ERROR
                self._logger.error(f"Engine initialization failed: {e}")
                raise

    def start(self):
        """Start the simulation."""
        with self._lock:
            if self._state not in (EngineState.READY, EngineState.PAUSED):
                raise AstraError(f"Cannot start from state: {self._state.value}")

            self._running = True
            self._clock.start()
            self._start_time = time_module.time()
            self._state = EngineState.RUNNING
            self._logger.info("ASTRA engine started")

            self._event_bus.publish_sync("engine_started", self._clock.get_current_tick(), source="engine")

    def stop(self):
        """Stop the simulation."""
        with self._lock:
            if self._state not in (EngineState.RUNNING, EngineState.PAUSED):
                return

            self._running = False
            self._clock.stop()
            self._state = EngineState.STOPPED
            self._logger.info("ASTRA engine stopped")

            self._event_bus.publish_sync("engine_stopped", self._clock.get_current_tick(), source="engine")

    def pause(self):
        """Pause the simulation."""
        with self._lock:
            if self._state != EngineState.RUNNING:
                raise AstraError(f"Cannot pause from state: {self._state.value}")

            self._clock.pause()
            self._state = EngineState.PAUSED
            self._logger.debug("ASTRA engine paused")

            self._event_bus.publish_sync("engine_paused", self._clock.get_current_tick(), source="engine")

    def resume(self):
        """Resume the simulation."""
        with self._lock:
            if self._state != EngineState.PAUSED:
                raise AstraError(f"Cannot resume from state: {self._state.value}")

            self._clock.resume()
            self._state = EngineState.RUNNING
            self._logger.debug("ASTRA engine resumed")

            self._event_bus.publish_sync("engine_resumed", self._clock.get_current_tick(), source="engine")

    def step(self):
        """Execute a single simulation tick."""
        with self._lock:
            if self._state not in (EngineState.RUNNING, EngineState.PAUSED):
                raise AstraError(f"Cannot step from state: {self._state.value}")

        current_tick = self._clock.advance()
        self._total_ticks += 1

        # Update scene tick
        self._scene.set_tick(current_tick)

        # Execute pending commands
        with AuthorityContext("engine.step"):
            results = self._command_dispatcher.execute_pending(current_tick)

        # Check for failures
        for cmd, result, error in results:
            if error:
                should_continue = self._recovery.record_failure(
                    failure_type="command_error",
                    operation=cmd.name,
                    tick=current_tick,
                    message=error,
                )
                if not should_continue:
                    self._state = EngineState.ERROR
                    raise AstraError(f"Command failed: {cmd.name}: {error}")
            else:
                self._recovery.record_success(cmd.name, current_tick)

        # Update resources
        self._resources.tick()

        # Calculate FPS
        now = time_module.time()
        if self._last_frame_time > 0:
            delta = now - self._last_frame_time
            if delta > 0:
                fps = 1.0 / delta
                self._fps_history.append(fps)
                if len(self._fps_history) > 60:
                    self._fps_history.pop(0)

        self._last_frame_time = now

        return current_tick

    def run_loop(self, max_ticks: Optional[int] = None):
        """Run the simulation loop."""
        self.start()
        try:
            while self._running and self._state == EngineState.RUNNING:
                if max_ticks and self._total_ticks >= max_ticks:
                    break

                self.step()

                # Small sleep to prevent CPU spinning in realtime mode
                if self._clock.get_mode() == TimeMode.INTERNAL_REALTIME:
                    time_module.sleep(max(0, self._config.default_tick_duration - 0.001))

        except Exception as e:
            self._logger.error(f"Simulation loop error: {e}")
            self._state = EngineState.ERROR
            raise
        finally:
            self._running = False
            if self._state in (EngineState.RUNNING, EngineState.PAUSED):
                self.stop()

    def save(self, name: str) -> str:
        """Save the current simulation state."""
        with self._lock:
            snapshot = Snapshot(
                schema_version="1.0.0",
                engine_state={
                    "state": self._state.value,
                    "total_ticks": self._total_ticks,
                },
                simulation_time={
                    "tick": self._clock.get_current_tick(),
                    "time": self._clock.get_simulation_time(),
                    "mode": self._clock.get_mode().value,
                },
                entities=self._scene.entity_manager.get_state_snapshot(),
                frames={
                    fid: {
                        "id": f.id.value,
                        "name": f.name,
                        "origin": f.origin,
                        "parent_id": f.parent_id,
                    }
                    for fid, f in self._scene.frame_registry.get_all_frames().items()
                },
                rng_state={k: {"seed": v.seed, "consumed": v._values_consumed} 
                          for k, v in self._rng.get_state().items()},
                command_history=[
                    {
                        "id": c.id.value,
                        "name": c.name,
                        "tick": c.tick,
                        "sequence": c.sequence,
                        "status": c.status.value,
                    }
                    for c in self._command_dispatcher.get_history().get_history()
                ],
                event_history=[
                    {
                        "id": e.id.value,
                        "name": e.name,
                        "tick": e.tick,
                        "sequence": e.sequence,
                    }
                    for e in self._event_bus.get_history()[-100:]  # Last 100 events
                ],
                tick=self._clock.get_current_tick(),
            )

            path = self._persistence.save(snapshot, name)
            self._logger.info(f"Saved snapshot: {name}")
            return path

    def load(self, name: str):
        """Load a simulation state from a snapshot."""
        with self._lock:
            snapshot = self._persistence.load(name)

            # Restore engine state
            engine_data = snapshot.engine_state
            self._total_ticks = engine_data.get("total_ticks", 0)

            # Restore time
            time_data = snapshot.simulation_time
            self._clock.seek(time_data.get("tick", 0))

            # Restore entities
            self._scene.entity_manager.restore_from_snapshot(snapshot.entities)

            # Note: Full restoration of all systems would go here
            # This is a simplified implementation

            self._logger.info(f"Loaded snapshot: {name}")

    def get_status(self) -> EngineStatus:
        """Get current engine status."""
        return EngineStatus(
            state=self._state,
            current_tick=self._clock.get_current_tick(),
            simulation_time=self._clock.get_simulation_time(),
            entity_count=self._scene.entity_manager.get_entity_count(),
            fps=sum(self._fps_history) / len(self._fps_history) if self._fps_history else 0.0,
            uptime=time_module.time() - self._start_time if self._start_time > 0 else 0.0,
        )

    def get_state(self) -> EngineState:
        """Get current engine state."""
        return self._state

    @property
    def clock(self) -> SimulationClock:
        """Get the simulation clock."""
        return self._clock

    @property
    def event_bus(self) -> EventBus:
        """Get the event bus."""
        return self._event_bus

    @property
    def rng(self) -> DeterministicRNG:
        """Get the RNG system."""
        return self._rng

    @property
    def commands(self) -> CommandDispatcher:
        """Get the command dispatcher."""
        return self._command_dispatcher

    @property
    def scene(self) -> Scene:
        """Get the scene."""
        return self._scene

    @property
    def persistence(self) -> PersistenceManager:
        """Get the persistence manager."""
        return self._persistence

    @property
    def resources(self) -> ResourceManager:
        """Get the resource manager."""
        return self._resources

    @property
    def recovery(self) -> RecoveryManager:
        """Get the recovery manager."""
        return self._recovery

    @property
    def services(self) -> ServiceRegistry:
        """Get the service registry."""
        return self._services

    def shutdown(self):
        """Shutdown the engine completely."""
        self._logger.info("Shutting down ASTRA engine...")

        try:
            self.stop()
            self._services.clear()
            self._resources.clear()
            self._event_bus.clear_history()
            self._command_dispatcher.clear_pending()
        except Exception as e:
            self._logger.error(f"Error during shutdown: {e}")

        self._state = EngineState.STOPPED
        self._logger.info("ASTRA engine shutdown complete")
