"""ASTRA Simulation Time & Universe Evolution Engine.

Authoritative orchestration for simulation time, stepping, rate, scheduling,
and universe evolution. Integrates Core, Mathematics, Motion, Physics, Orbital,
N-Body, Spacecraft, Relativity, Spacetime, Temporal, Celestial, World, and
Verification without duplicating their authoritative implementations.

Exports:
  SimulationTimeEngine / UniverseEvolutionEngine / EvolutionEngine
  EvolutionConfig
  SimulationTimeState
  EventScheduler
  SubstepPolicy
  SimulationClock, TemporalClock (re-exports)
  Exceptions
"""

from __future__ import annotations

from astra.core.time import SimulationClock, TimeMode, TimeState
from astra.temporal.clock import TemporalClock
from astra.temporal.state import TemporalState

from .state import SimulationTimeState
from .substep import SubstepPolicy, validate_dt, validate_rate, subdivide, apply_rate
from .scheduler import EventScheduler, ScheduledEvent
from .evolution import (
    EvolutionConfig,
    SimulationTimeEngine,
    UniverseEvolutionEngine,
    EvolutionEngine,
)
from .exceptions import (
    SimulationTimeError,
    InvalidTimestepError,
    InvalidRateError,
    InvalidTimestampError,
    SchedulerError,
    EvolutionError,
    LargeJumpRejectedError,
)

__all__ = [
    # clocks
    "SimulationClock",
    "TimeMode",
    "TimeState",
    "TemporalClock",
    "TemporalState",
    # state & policy
    "SimulationTimeState",
    "SubstepPolicy",
    # scheduler
    "EventScheduler",
    "ScheduledEvent",
    # engine
    "EvolutionConfig",
    "SimulationTimeEngine",
    "UniverseEvolutionEngine",
    "EvolutionEngine",
    # validation helpers
    "validate_dt",
    "validate_rate",
    "subdivide",
    "apply_rate",
    # exceptions
    "SimulationTimeError",
    "InvalidTimestepError",
    "InvalidRateError",
    "InvalidTimestampError",
    "SchedulerError",
    "EvolutionError",
    "LargeJumpRejectedError",
]

__version__ = "1.0.0"
