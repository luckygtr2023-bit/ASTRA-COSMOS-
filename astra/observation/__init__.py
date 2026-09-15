"""ASTRA Observation & Cosmic History Engine.

Pipeline:
  PHYSICAL STATE → COSMIC/HISTORICAL → LIGHT PROPAGATION → OBSERVATION → OBSERVED STATE → OBSERVABLES

Reuses:
  astra.temporal (clocks, observation, causal)
  astra.spacetime (metric, causality, events)
  astra.relativity (doppler, gravitational)
  astra.procedural / astra.celestial history

This package is the authoritative consumer of those layers for
observer-dependent appearances. It never mutates authoritative state.
"""

from __future__ import annotations

from astra.observation.exceptions import (
    ObservationError,
    InvalidObserverError,
    InvalidTargetError,
    InvalidReferenceFrameError,
    HistoryUnavailableError,
    TemporalHistoryUnavailableError,
    PropagationError,
    CausalInaccessibilityError,
    UnsupportedObservationalConfigurationError,
)

from astra.observation.observer import Observer
from astra.observation.history import (
    CosmicEpoch,
    EventType,
    HistoricalSnapshot,
    TimelineEvent,
    CosmicHistory,
)
from astra.observation.redshift import RedshiftComponents, calculate_redshift, doppler_redshift, gravitational_redshift, cosmological_redshift, combine_redshifts
from astra.observation.propagation import (
    light_travel_time,
    geometric_distance,
    lookback_time_simple,
    solve_retarded_time,
    solve_retarded_time_with_observer,
    trace_light_path,
)
from astra.observation.light_cone import LightCone, LightConeKind, past_light_cone, future_light_cone, is_observable, observability_status
from astra.observation.state import ObservedState
from astra.observation.engine import ObservationEngine

__all__ = [
    # exceptions
    "ObservationError",
    "InvalidObserverError",
    "InvalidTargetError",
    "InvalidReferenceFrameError",
    "HistoryUnavailableError",
    "TemporalHistoryUnavailableError",
    "PropagationError",
    "CausalInaccessibilityError",
    "UnsupportedObservationalConfigurationError",
    # observer
    "Observer",
    # history
    "CosmicEpoch",
    "EventType",
    "HistoricalSnapshot",
    "TimelineEvent",
    "CosmicHistory",
    # redshift
    "RedshiftComponents",
    "calculate_redshift",
    "doppler_redshift",
    "gravitational_redshift",
    "cosmological_redshift",
    "combine_redshifts",
    # propagation
    "light_travel_time",
    "geometric_distance",
    "lookback_time_simple",
    "solve_retarded_time",
    "solve_retarded_time_with_observer",
    "trace_light_path",
    # light cone
    "LightCone",
    "LightConeKind",
    "past_light_cone",
    "future_light_cone",
    "is_observable",
    "observability_status",
    # state
    "ObservedState",
    # engine
    "ObservationEngine",
]

__version__ = "1.0.0"
