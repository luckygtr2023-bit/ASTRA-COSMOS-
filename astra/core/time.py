"""ASTRA Core simulation time system."""

from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from enum import Enum
import threading
import time as time_module

from astra.core.logging import get_logger
from astra.core.exceptions import TimeError


class TimeMode(Enum):
    """Time synchronization modes."""

    INTERNAL_REALTIME = "internal_realtime"  # Sim time tracks wall clock
    INTERNAL_DETERMINISTIC = "internal_deterministic"  # Sim time advances by fixed steps
    EXTERNAL_SYNC = "external_sync"  # Sim time follows external timestamps


@dataclass
class TimeState:
    """Snapshot of time system state."""

    mode: TimeMode
    current_tick: int
    simulation_time: float
    real_time: float
    tick_duration: float
    is_paused: bool
    is_running: bool


class SimulationClock:
    """Manages simulation time and ticking."""

    def __init__(
        self,
        tick_duration: float = 1.0 / 60.0,
        mode: TimeMode = TimeMode.INTERNAL_DETERMINISTIC,
    ):
        self._tick_duration = tick_duration
        self._mode = mode
        self._current_tick = 0
        self._simulation_time = 0.0
        self._real_time_start = 0.0
        self._is_paused = False
        self._is_running = False
        self._lock = threading.RLock()
        self._logger = get_logger("simulation_clock")
        self._tick_callbacks: list = []
        self._pause_callbacks: list = []
        self._resume_callbacks: list = []

    def start(self):
        """Start the simulation clock."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._is_paused = False
            self._real_time_start = time_module.time()
            self._logger.info(f"Simulation clock started in mode {self._mode.value}")

    def stop(self):
        """Stop the simulation clock."""
        with self._lock:
            self._is_running = False
            self._is_paused = False
            self._logger.info("Simulation clock stopped")

    def pause(self):
        """Pause the simulation clock."""
        with self._lock:
            if not self._is_running:
                raise TimeError("Cannot pause: clock not running", "pause")
            self._is_paused = True
            self._logger.debug("Simulation clock paused")
            for callback in self._pause_callbacks:
                try:
                    callback(self._current_tick)
                except Exception as e:
                    self._logger.error(f"Pause callback failed: {e}")

    def resume(self):
        """Resume the simulation clock."""
        with self._lock:
            if not self._is_running:
                raise TimeError("Cannot resume: clock not running", "resume")
            self._is_paused = False
            self._real_time_start = time_module.time() - self._simulation_time
            self._logger.debug("Simulation clock resumed")
            for callback in self._resume_callbacks:
                try:
                    callback(self._current_tick)
                except Exception as e:
                    self._logger.error(f"Resume callback failed: {e}")

    def advance(self) -> int:
        """Advance simulation by one tick. Returns the new tick number."""
        with self._lock:
            if not self._is_running:
                raise TimeError("Cannot advance: clock not running", "advance")
            if self._is_paused:
                raise TimeError("Cannot advance: clock is paused", "advance")

            self._current_tick += 1
            self._simulation_time += self._tick_duration

            # Execute tick callbacks
            for callback in self._tick_callbacks:
                try:
                    callback(self._current_tick)
                except Exception as e:
                    self._logger.error(f"Tick callback failed: {e}")

            return self._current_tick

    def seek(self, target_tick: int):
        """Seek to a specific tick (for replay/timeline control).
        
        Note: This is timeline seeking, NOT physical time travel.
        The simulation state must be reset/reloaded appropriately.
        """
        with self._lock:
            if target_tick < 0:
                raise TimeError(
                    "Invalid seek: negative tick",
                    "seek",
                    float(target_tick),
                )
            if target_tick < self._current_tick and self._mode == TimeMode.EXTERNAL_SYNC:
                self._logger.warning(
                    f"Backward seek in EXTERNAL_SYNC mode: {self._current_tick} -> {target_tick}"
                )

            self._current_tick = target_tick
            self._simulation_time = target_tick * self._tick_duration
            self._logger.info(f"Simulation clock seeked to tick {target_tick}")

    def set_mode(self, mode: TimeMode):
        """Set the time synchronization mode."""
        with self._lock:
            old_mode = self._mode
            self._mode = mode
            self._logger.info(f"Time mode changed: {old_mode.value} -> {mode.value}")

    def set_external_timestamp(self, timestamp: float):
        """Set simulation time from an external timestamp.
        
        Only valid in EXTERNAL_SYNC mode. Timestamps must be monotonic.
        """
        with self._lock:
            if self._mode != TimeMode.EXTERNAL_SYNC:
                raise TimeError(
                    "External timestamps only valid in EXTERNAL_SYNC mode",
                    "set_external_timestamp",
                    timestamp,
                )

            # Convert timestamp to tick
            target_tick = int(timestamp / self._tick_duration)

            # Check monotonicity (warn but allow for initialization)
            if target_tick < self._current_tick:
                self._logger.warning(
                    f"Non-monotonic external timestamp: {timestamp} (tick {target_tick})"
                )

            self._current_tick = target_tick
            self._simulation_time = timestamp

    def on_tick(self, callback: Callable[[int], None]):
        """Register a callback for tick events."""
        self._tick_callbacks.append(callback)

    def on_pause(self, callback: Callable[[int], None]):
        """Register a callback for pause events."""
        self._pause_callbacks.append(callback)

    def on_resume(self, callback: Callable[[int], None]):
        """Register a callback for resume events."""
        self._resume_callbacks.append(callback)

    def get_current_tick(self) -> int:
        """Get the current simulation tick."""
        return self._current_tick

    def get_simulation_time(self) -> float:
        """Get the current simulation time in seconds."""
        return self._simulation_time

    def get_real_time(self) -> float:
        """Get elapsed real time in seconds."""
        if not self._is_running:
            return 0.0
        return time_module.time() - self._real_time_start

    def get_tick_duration(self) -> float:
        """Get the tick duration in seconds."""
        return self._tick_duration

    def set_tick_duration(self, duration: float):
        """Set the tick duration in seconds."""
        if duration <= 0:
            raise TimeError("Tick duration must be positive", "set_tick_duration", duration)
        with self._lock:
            self._tick_duration = duration
            self._logger.debug(f"Tick duration set to {duration}s")

    def get_mode(self) -> TimeMode:
        """Get the current time mode."""
        return self._mode

    def is_paused(self) -> bool:
        """Check if the clock is paused."""
        return self._is_paused

    def is_running(self) -> bool:
        """Check if the clock is running."""
        return self._is_running

    def get_state(self) -> TimeState:
        """Get a snapshot of the clock state."""
        return TimeState(
            mode=self._mode,
            current_tick=self._current_tick,
            simulation_time=self._simulation_time,
            real_time=self.get_real_time(),
            tick_duration=self._tick_duration,
            is_paused=self._is_paused,
            is_running=self._is_running,
        )

    def reset(self):
        """Reset the clock to initial state."""
        with self._lock:
            self._current_tick = 0
            self._simulation_time = 0.0
            self._real_time_start = 0.0
            self._is_paused = False
            self._is_running = False
            self._logger.debug("Simulation clock reset")
