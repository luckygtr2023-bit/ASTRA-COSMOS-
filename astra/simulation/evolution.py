"""Universe Evolution Engine — authoritative simulation-time orchestration.

Owns:
  simulation time, stepping, rate, scheduling, evolution coordination.

Does NOT own:
  physics/orbital/relativity/spacetime/celestial equations (delegates).

Pipeline (deterministic, testable):
  REQUEST → VALIDATE → TARGET → SUBSTEPS → TEMPORAL → PHYSICAL → ORBITAL/NBODY/SPACECRAFT → EVENTS → CELESTIAL → WORLD → VERIFICATION → COMMIT

Update order is explicit and documented (see EvolutionEngine.ORDER).

Large jumps use safe substepping (SubstepPolicy) or analytical hook; never one huge physics step.
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from astra.core.time import SimulationClock, TimeMode, TimeState
from astra.core.threading import AuthorityContext

from astra.temporal.clock import TemporalClock
from astra.temporal.state import TemporalState

from .exceptions import (
    SimulationTimeError,
    InvalidTimestepError,
    InvalidRateError,
    InvalidTimestampError,
    LargeJumpRejectedError,
    EvolutionError,
)
from .state import SimulationTimeState, _validate_finite_nonneg
from .substep import SubstepPolicy, validate_dt, validate_rate, subdivide, apply_rate
from .scheduler import EventScheduler, ScheduledEvent


@dataclass
class EvolutionConfig:
    """Configuration for evolution engine."""

    tick_duration_s: float = 1.0 / 60.0
    max_step_s: float = 3600.0  # safe physics substep
    min_step_s: float = 1e-9
    max_substeps: int = 1_000_000
    rate: float = 1.0
    start_time_s: float = 0.0
    observer: str = "simulation"
    allow_analytical: bool = False
    verify_after_step: bool = False


class SimulationTimeEngine:
    """Authoritative simulation-time engine.

    Wraps SimulationClock (core) + TemporalClock (temporal) + EventScheduler.
    Provides deterministic advancement with rate/substep separation, pause/resume,
    single-step, scheduling, persistence, and hooks for subsystem evolution.
    """

    # Explicit deterministic update order — testable, documented
    # Pipeline: TEMPORAL → PHYSICAL → ORBITAL/NBODY/SPACECRAFT → EVENTS → CELESTIAL → WORLD → VERIFICATION
    ORDER = [
        "temporal",
        "physics",
        "motion",
        "orbital",
        "nbody",
        "spacecraft",
        "relativity",
        "spacetime",
        "events",
        "celestial",
        "world",
        "verification",
    ]

    def __init__(
        self,
        config: Optional[EvolutionConfig] = None,
        *,
        clock: Optional[SimulationClock] = None,
        temporal_clock: Optional[TemporalClock] = None,
        scheduler: Optional[EventScheduler] = None,
        # Subsystem hooks — each is Callable[[dt], None] or object with step(dt)
        hooks: Optional[Dict[str, Callable[[float], Any]]] = None,
        # Optional Engine for persistence integration
        engine: Optional[Any] = None,
    ):
        self._config = config or EvolutionConfig()
        self._lock = threading.RLock()
        self._clock = clock or SimulationClock(
            tick_duration=self._config.tick_duration_s, mode=TimeMode.INTERNAL_DETERMINISTIC
        )
        # Ensure clock tick_duration matches config
        try:
            if abs(self._clock.get_tick_duration() - self._config.tick_duration_s) > 1e-12:
                self._clock.set_tick_duration(self._config.tick_duration_s)
        except Exception:
            pass

        self._temporal = temporal_clock or TemporalClock(
            observer=self._config.observer,
            simulation_time_s=self._config.start_time_s,
            coordinate_time_s=self._config.start_time_s,
            proper_time_s=self._config.start_time_s,
        )
        self._scheduler = scheduler or EventScheduler()
        self._scheduler.set_time(self._config.start_time_s)
        self._hooks: Dict[str, Callable[[float], Any]] = dict(hooks or {})
        self._engine = engine  # optional, for save/load integration

        self._rate = validate_rate(self._config.rate)
        self._start_time_s = _validate_finite_nonneg(self._config.start_time_s, "start_time_s")
        self._policy = SubstepPolicy(
            max_step_s=self._config.max_step_s,
            min_step_s=self._config.min_step_s,
            max_substeps=self._config.max_substeps,
            allow_analytical=self._config.allow_analytical,
        )
        # Internal state
        self._simulation_time_s = self._config.start_time_s
        self._elapsed_s = 0.0
        self._tick = self._clock.get_current_tick()
        # For transactional rollback
        self._last_committed_state: Optional[Dict[str, Any]] = None

    # -- properties ---------------------------------------------------------

    @property
    def clock(self) -> SimulationClock:
        return self._clock

    @property
    def temporal_clock(self) -> TemporalClock:
        return self._temporal

    @property
    def scheduler(self) -> EventScheduler:
        return self._scheduler

    @property
    def rate(self) -> float:
        with self._lock:
            return self._rate

    @property
    def simulation_time_s(self) -> float:
        with self._lock:
            return self._simulation_time_s

    @property
    def tick(self) -> int:
        with self._lock:
            return self._tick

    # -- configuration -----------------------------------------------------

    def set_rate(self, rate: float, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("simulation.set_rate")
        r = validate_rate(rate)
        with self._lock:
            self._rate = r

    def set_tick_duration(self, duration: float, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("simulation.set_tick_duration")
        d = _validate_finite_nonneg(duration, "tick_duration_s", allow_zero=False)
        with self._lock:
            self._clock.set_tick_duration(d)
            self._policy = SubstepPolicy(
                max_step_s=self._policy.max_step_s,
                min_step_s=self._policy.min_step_s,
                max_substeps=self._policy.max_substeps,
                allow_analytical=self._policy.allow_analytical,
            )

    # -- lifecycle ----------------------------------------------------------

    def initialize(self, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("simulation.initialize")
        with self._lock:
            # Ensure clocks are consistent
            self._simulation_time_s = self._start_time_s
            self._elapsed_s = 0.0
            self._tick = 0
            try:
                self._clock.reset()
            except Exception:
                pass
            try:
                self._temporal.reset(
                    simulation_time_s=self._start_time_s,
                    coordinate_time_s=self._start_time_s,
                    proper_time_s=self._start_time_s,
                    require_authority=False,
                )
            except Exception:
                pass
            self._scheduler.set_time(self._start_time_s)
            self._scheduler.clear()

    def start(self, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("simulation.start")
        with self._lock:
            self._clock.start()

    def stop(self, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("simulation.stop")
        with self._lock:
            self._clock.stop()

    def pause(self, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("simulation.pause")
        with self._lock:
            self._clock.pause()

    def resume(self, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("simulation.resume")
        with self._lock:
            self._clock.resume()

    def is_paused(self) -> bool:
        return self._clock.is_paused()

    def is_running(self) -> bool:
        return self._clock.is_running()

    # -- hooks --------------------------------------------------------------

    def register_hook(self, name: str, fn: Callable[[float], Any]) -> None:
        if name not in self.ORDER:
            # Allow custom but warn; we still keep deterministic order by ORDER + sorted custom
            pass
        self._hooks[name] = fn

    def unregister_hook(self, name: str) -> None:
        self._hooks.pop(name, None)

    # -- state --------------------------------------------------------------

    def get_state(self) -> SimulationTimeState:
        with self._lock:
            return SimulationTimeState(
                simulation_time_s=self._simulation_time_s,
                coordinate_time_s=self._temporal.coordinate_time_s,
                proper_time_s=self._temporal.proper_time_s,
                elapsed_s=self._elapsed_s,
                tick=self._tick,
                tick_duration_s=self._clock.get_tick_duration(),
                rate=self._rate,
                mode=self._clock.get_mode().value,
                is_paused=self._clock.is_paused(),
                is_running=self._clock.is_running(),
                start_time_s=self._start_time_s,
                observer=self._temporal.observer,
            )

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self.get_state().to_dict(),
                "scheduler": self._scheduler.to_dict(),
                "config": {
                    "tick_duration_s": self._config.tick_duration_s,
                    "max_step_s": self._config.max_step_s,
                    "min_step_s": self._config.min_step_s,
                    "max_substeps": self._config.max_substeps,
                    "rate": self._rate,
                    "start_time_s": self._start_time_s,
                    "observer": self._temporal.observer,
                    "allow_analytical": self._config.allow_analytical,
                },
                "clock": {
                    "tick": self._clock.get_current_tick(),
                    "simulation_time": self._clock.get_simulation_time(),
                    "tick_duration": self._clock.get_tick_duration(),
                    "mode": self._clock.get_mode().value,
                    "is_paused": self._clock.is_paused(),
                    "is_running": self._clock.is_running(),
                },
            }

    def from_dict(self, data: Dict[str, Any], require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("simulation.restore")
        st = SimulationTimeState.from_dict(data.get("state", {}))
        with self._lock:
            self._simulation_time_s = st.simulation_time_s
            self._elapsed_s = st.elapsed_s
            self._tick = st.tick
            self._rate = st.rate
            self._start_time_s = st.start_time_s
            # Restore clocks
            try:
                self._clock.restore_state(
                    tick=st.tick,
                    simulation_time=st.simulation_time_s,
                    mode=TimeMode(st.mode),
                    tick_duration=st.tick_duration_s,
                    is_running=st.is_running,
                    is_paused=st.is_paused,
                )
            except Exception:
                # Fallback seek
                try:
                    self._clock.seek(st.tick, force=True)
                except Exception:
                    pass
            try:
                self._temporal.reset(
                    simulation_time_s=st.simulation_time_s,
                    coordinate_time_s=st.coordinate_time_s,
                    proper_time_s=st.proper_time_s,
                    require_authority=False,
                )
                # Restore rate for proper time
                try:
                    # Derive rate from state if needed
                    if st.proper_time_s != st.coordinate_time_s and st.coordinate_time_s != 0:
                        # Not reliable; just keep 1.0
                        pass
                except Exception:
                    pass
            except Exception:
                pass
            # Restore scheduler
            try:
                self._scheduler.restore(data.get("scheduler", {}))
                self._scheduler.set_time(st.simulation_time_s)
            except Exception:
                pass

    # -- scheduling ---------------------------------------------------------

    def schedule_event(self, name: str, at_time_s: float, data: Optional[Dict[str, Any]] = None, priority: int = 0, event_id: Optional[str] = None) -> ScheduledEvent:
        with self._lock:
            # Validate against current simulation time
            if at_time_s < self._simulation_time_s - 1e-12:
                raise InvalidTimestampError(f"cannot schedule in the past: {at_time_s} < {self._simulation_time_s}", operation="schedule_event")
            return self._scheduler.schedule(name, at_time_s, data, priority, event_id)

    def cancel_event(self, event_id: str) -> bool:
        with self._lock:
            return self._scheduler.cancel(event_id)

    def reschedule_event(self, event_id: str, new_time_s: float) -> ScheduledEvent:
        with self._lock:
            if new_time_s < self._simulation_time_s - 1e-12:
                raise InvalidTimestampError(f"cannot reschedule to past: {new_time_s} < {self._simulation_time_s}", operation="reschedule_event")
            return self._scheduler.reschedule(event_id, new_time_s)

    # -- advancement --------------------------------------------------------

    def _validate_advance(self, delta_s: float) -> float:
        return validate_dt(delta_s, "delta_s")

    def _execute_substep(self, dt: float) -> None:
        """Execute one deterministic substep in ORDER.

        Transactional: if any hook fails, caller should rollback.
        Order: temporal (already) → physics/motion/orbital/nbody/spacecraft/relativity/spacetime
               → events (pop due) → celestial/world/verification
        """
        # Temporal first (proper time accumulation)
        with AuthorityContext("simulation.substep"):
            # Temporal clock advance
            try:
                self._temporal.advance(dt, require_authority=False)
            except Exception as e:
                raise EvolutionError(f"temporal advance failed: {e}", operation="temporal_advance", details={"dt": dt})
            # Pre-event hooks
            pre_names = ["physics", "motion", "orbital", "nbody", "spacecraft", "relativity", "spacetime"]
            for name in pre_names:
                hook = self._hooks.get(name)
                if hook is None:
                    continue
                try:
                    if callable(hook):
                        hook(dt)
                    elif hasattr(hook, "step"):
                        hook.step(dt)  # type: ignore
                    elif hasattr(hook, "tick"):
                        hook.tick(dt)  # type: ignore
                except Exception as e:
                    raise EvolutionError(f"subsystem {name} failed at dt={dt}: {e}", operation=f"evolution.{name}", details={"dt": dt, "subsystem": name, "error": str(e)})
            # Events due up to new simulation time
            new_time = self._simulation_time_s + dt
            try:
                due = self._scheduler.pop_due(new_time)
                # Dispatch via events hook if present (e.g., EventBus publish)
                ev_hook = self._hooks.get("events")
                if ev_hook is not None and due:
                    # If hook is callable expecting list, call; if it's EventBus, publish each
                    try:
                        if callable(ev_hook):
                            # Try calling with due list
                            try:
                                ev_hook(due)  # type: ignore
                            except TypeError:
                                for ev in due:
                                    ev_hook(ev)  # type: ignore
                    except Exception as e:
                        raise EvolutionError(f"event dispatch failed: {e}", operation="evolution.events", details={"dt": dt})
            except EvolutionError:
                raise
            except Exception as e:
                raise EvolutionError(f"event scheduling failed: {e}", operation="evolution.events", details={"dt": dt})
            # Post-event hooks
            for name in ["celestial", "world", "verification"]:
                hook = self._hooks.get(name)
                if hook is None:
                    continue
                try:
                    if callable(hook):
                        hook(dt)
                    elif hasattr(hook, "step"):
                        hook.step(dt)  # type: ignore
                    elif hasattr(hook, "tick"):
                        hook.tick(dt)  # type: ignore
                except Exception as e:
                    raise EvolutionError(f"subsystem {name} post-event failed: {e}", operation=f"evolution.{name}", details={"dt": dt})

    def advance(self, delta_s: float, require_authority: bool = True) -> SimulationTimeState:
        """Advance simulation time by delta_s (SI seconds, simulation time).

        Implements safe substepping. Deterministic: same delta + same policy → same substeps.
        Fails safely: on subsystem failure, rolls back to pre-advance state.
        Respects pause: if paused, raises unless single-step is used.
        """
        if require_authority:
            AuthorityContext.require_authority("simulation.advance")
        delta = self._validate_advance(delta_s)
        if delta == 0.0:
            return self.get_state()
        with self._lock:
            if self._clock.is_paused():
                raise SimulationTimeError("cannot advance while paused; use single_step or resume", subsystem="simulation", operation="advance")
            if not self._clock.is_running():
                raise SimulationTimeError("clock not running; call start()", subsystem="simulation", operation="advance")
            # Snapshot for rollback
            pre_state = self.to_dict()
            pre_sim_time = self._simulation_time_s
            pre_tick = self._tick
            pre_elapsed = self._elapsed_s
            # Determine substeps
            try:
                steps = subdivide(delta, self._policy)
            except LargeJumpRejectedError:
                raise
            except Exception as e:
                raise InvalidTimestepError(f"subdivide failed: {e}")
            # Execute substeps
            accumulated = 0.0
            try:
                for dt in steps:
                    self._execute_substep(dt)
                    accumulated += dt
                    self._simulation_time_s += dt
                    self._elapsed_s += dt
                    # Advance core clock (tick accounting) — one tick per substep? Or per delta?
                    # For deterministic mapping, each substep advances core tick by 1
                    try:
                        self._clock.advance()
                    except Exception:
                        # If clock not running, ignore
                        pass
                    self._tick = self._clock.get_current_tick()
                    # Sync scheduler time
                    self._scheduler.set_time(self._simulation_time_s)
            except Exception as e:
                # Rollback to pre_state
                try:
                    self.from_dict(pre_state, require_authority=False)
                except Exception:
                    # Best effort: restore scalar fields
                    self._simulation_time_s = pre_sim_time
                    self._tick = pre_tick
                    self._elapsed_s = pre_elapsed
                raise e
            return self.get_state()

    def advance_by_real_time(self, delta_real_s: float, require_authority: bool = True) -> SimulationTimeState:
        """Advance by real time scaled by rate (separate rate from step)."""
        if require_authority:
            AuthorityContext.require_authority("simulation.advance_by_real_time")
        dr = validate_dt(delta_real_s, "delta_real_s")
        with self._lock:
            r = self._rate
            delta_sim = dr * r
            if not math.isfinite(delta_sim):
                raise InvalidTimestepError(f"delta_sim overflow: {dr}*{r}")
            # Delegate to advance (which will substep)
            # Need to release lock to avoid deadlock? advance also acquires lock (RLock so okay)
            return self.advance(delta_sim, require_authority=False)

    def advance_to(self, target_time_s: float, require_authority: bool = True) -> SimulationTimeState:
        """Advance to absolute simulation time."""
        if require_authority:
            AuthorityContext.require_authority("simulation.advance_to")
        target = _validate_finite_nonneg(target_time_s, "target_time_s")
        with self._lock:
            if target < self._simulation_time_s - 1e-12:
                raise InvalidTimestampError(f"cannot advance backward: target {target} < current {self._simulation_time_s}", operation="advance_to")
            delta = target - self._simulation_time_s
            if delta < 1e-12:
                return self.get_state()
            return self.advance(delta, require_authority=False)

    def single_step(self, require_authority: bool = True) -> SimulationTimeState:
        """Single deterministic step of tick_duration (allowed even when paused)."""
        if require_authority:
            AuthorityContext.require_authority("simulation.single_step")
        with self._lock:
            dt = self._clock.get_tick_duration()
            pre_state = self.to_dict()
            try:
                self._execute_substep(dt)
                self._simulation_time_s += dt
                self._elapsed_s += dt
                try:
                    self._clock.advance()
                except Exception:
                    pass
                self._tick = self._clock.get_current_tick()
                self._scheduler.set_time(self._simulation_time_s)
            except Exception as e:
                try:
                    self.from_dict(pre_state, require_authority=False)
                except Exception:
                    pass
                raise e
            return self.get_state()

    # -- large jump API -----------------------------------------------------

    def large_jump(self, delta_s: float, *, analytical_hook: Optional[Callable[[float], Any]] = None, require_authority: bool = True) -> SimulationTimeState:
        """Handle large jump safely: substep or analytical or reject."""
        if require_authority:
            AuthorityContext.require_authority("simulation.large_jump")
        delta = self._validate_advance(delta_s)
        with self._lock:
            steps = None
            try:
                steps = subdivide(delta, self._policy)
            except LargeJumpRejectedError as e:
                if analytical_hook is not None and self._config.allow_analytical:
                    # Use analytical hook for entire delta (one step)
                    pre_state = self.to_dict()
                    try:
                        # Analytical hook is expected to update subsystems appropriately
                        analytical_hook(delta)
                        self._simulation_time_s += delta
                        self._elapsed_s += delta
                        # Advance scheduler and temporal clock analytically
                        try:
                            self._temporal.advance(delta, require_authority=False)
                        except Exception:
                            pass
                        # Advance core clock proportionally? For analytical, we set tick to target time / tick_duration
                        try:
                            target_tick = int(self._simulation_time_s / self._clock.get_tick_duration())
                            self._clock.seek(target_tick, force=True)
                            self._tick = target_tick
                        except Exception:
                            pass
                        self._scheduler.set_time(self._simulation_time_s)
                        # Pop due events up to new time
                        try:
                            self._scheduler.pop_due(self._simulation_time_s)
                        except Exception:
                            pass
                        return self.get_state()
                    except Exception as ae:
                        try:
                            self.from_dict(pre_state, require_authority=False)
                        except Exception:
                            pass
                        raise EvolutionError(f"analytical large jump failed: {ae}", operation="large_jump")
                raise e
            # If subdivide succeeded, delegate to advance
            if steps is not None:
                return self.advance(delta, require_authority=False)
            raise LargeJumpRejectedError("large jump handling fell through")

    # -- persistence --------------------------------------------------------

    def save_snapshot(self) -> Dict[str, Any]:
        return self.to_dict()

    def load_snapshot(self, data: Dict[str, Any], require_authority: bool = True) -> None:
        self.from_dict(data, require_authority=require_authority)


# Alias for compatibility
UniverseEvolutionEngine = SimulationTimeEngine
EvolutionEngine = SimulationTimeEngine

__all__ = [
    "EvolutionConfig",
    "SimulationTimeEngine",
    "UniverseEvolutionEngine",
    "EvolutionEngine",
]
