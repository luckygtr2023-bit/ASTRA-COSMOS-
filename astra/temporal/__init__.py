"""ASTRA Temporal & Causality layer.

Dependency direction:
    CORE -> MATHEMATICS -> MOTION -> PHYSICS -> ORBITAL -> N-BODY
         -> SPACECRAFT -> RELATIVITY -> BLACK-HOLE -> SPACETIME
         -> THEORETICAL -> TEMPORAL

A composition layer over existing ASTRA time/metric machinery. It defines
NO new metric mathematics, NO new vector mathematics, and NO new
integrators:

    - proper time   : relativity FourVector convention (flat) +
                      spacetime geodesic proper-time parameterization.
    - classification: spacetime.causality on the ACTIVE metric
                      (signature (-,+,+,+), x^mu = (ct, ...)).
    - dilation      : relativity lorentz_factor + weak-field
                      dt/dtau (single implementations, reused).
    - exotic cones  : theoretical mixed-component null sampler (reused).
    - white holes   : the existing emissive-only policy (delegated).
    - authority     : astra.core.threading.AuthorityContext (the real
                      mechanism; the TemporalClock is the single mutable
                      object and requires authority to advance).

TEMPORAL CONVENTIONS
    All times SI seconds. simulation/coordinate/proper time are explicit,
    separate fields (TemporalState); observers are explicit labels; rates
    are dtau/dt. No wall clock, no datetime.now(), no global mutable
    temporal state, no RNG anywhere in this layer.

OBSERVATION VS ACTUAL STATE
    Observation returns an immutable ObservedState: the emission event a
    distant observer literally receives (flat null propagation, retarded
    time solved by deterministic bisection). Lookback NEVER mutates the
    actual state, NEVER fabricates history - unavailable history raises
    TemporalHistoryUnavailableError explicitly.

TIME-TRAVEL BOUNDARY (binding)
    ANALYSIS =/= EXECUTION. This layer diagnoses causal structure
    (relations, cone regions, chronology diagnostics). It contains and
    must never contain: travel_to_past, create_time_machine,
    rewrite_timeline, reverse_causality, CTC generation, or any FTL
    transport API. Chronology-violating configurations are REPORTED as
    diagnostics, never operationalized.

Determinism: 100% deterministic - identical inputs, identical outputs.
"""
from astra.temporal.exceptions import (
    TemporalError,
    InvalidTemporalStateError,
    InvalidWorldlineError,
    TemporalHistoryUnavailableError,
)
from astra.temporal.state import TemporalState, TemporalInterval
from astra.temporal.clock import TemporalClock
from astra.temporal.proper_time import (
    flat_proper_time,
    metric_proper_time,
    velocity_time_dilation,
    gravitational_time_dilation,
)
from astra.temporal.causal import (
    CausalRelation,
    LightConeRegion,
    classify,
    relate,
    light_cone_region,
    is_causally_accessible,
    cone_null_generators,
)
from astra.temporal.observation import ObservedState, lookback_time, observe
from astra.temporal.exotic import (
    ConeAnalysis,
    WhiteHoleTemporalCheck,
    WormholeChronologyDiagnostic,
    warp_cone_analysis,
    white_hole_temporal_check,
    wormhole_chronology_diagnostic,
)

__all__ = [
    # exceptions
    "TemporalError", "InvalidTemporalStateError", "InvalidWorldlineError",
    "TemporalHistoryUnavailableError",
    # state & clock
    "TemporalState", "TemporalInterval", "TemporalClock",
    # proper time & dilation
    "flat_proper_time", "metric_proper_time", "velocity_time_dilation",
    "gravitational_time_dilation",
    # causal analysis
    "CausalRelation", "LightConeRegion", "classify", "relate",
    "light_cone_region", "is_causally_accessible", "cone_null_generators",
    # observation & lookback
    "ObservedState", "lookback_time", "observe",
    # exotic analysis (analysis only - no execution APIs)
    "ConeAnalysis", "WhiteHoleTemporalCheck", "WormholeChronologyDiagnostic",
    "warp_cone_analysis", "white_hole_temporal_check",
    "wormhole_chronology_diagnostic",
]
