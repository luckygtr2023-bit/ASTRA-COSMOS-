"""ASTRA COSMOS — Phase 21: Long-Term Cosmic Evolution Engine.

Deterministic, authority-gated, provenance-aware evolution of cosmic
structures and populations across timescales from millions to trillions
of years (and, where a configured model declares validity, beyond).

Architectural position (spec 2.2) — Phase 21 sits ABOVE the cosmological
background and ABOVE galactic / large-scale structure; it never replaces
either. In THIS repository the Universe Evolution system and Phase 20 are
ABSENT (verified; see docs/evolution/DEPENDENCY_MATRIX.md): both are
consumed exclusively through fail-loud Protocol adapters
(``astra.evolution.integration`` / ``astra.evolution.adapters``). Phase 21
contains no cosmological-background mathematics and computes no expansion.

- Physics: documented reduced-order models (stellar lifecycle, population
  conveyor, one-zone galaxy, cluster aggregate, web regime), every number
  a declared parameter with a stated assumption; all outputs are
  SIMULATED_DATA / THEORETICAL_MODEL / SPECULATIVE_MODEL projections,
  never presented as observations.
- Determinism: no wall clock, no global RNG; identical configurations
  produce bit-identical results.
- Authority: every mutation passes an AuthorityProvider (fail-closed when
  absent; ``adapters.CoreAuthorityProvider`` binds core's real
  AuthorityContext).
- Temporal/causal integrity: cosmic time in Gyr with documented interop to
  astra.temporal (SI seconds); causal event chains validated by the
  ledger; finite light propagation is never bypassed (observation only via
  the ObservationProvider).

Type conventions: ``DataProvenance`` is the canonical
``astra.celestial.provenance.DataProvenance`` — this package defines no
new provenance enum (``ProjectionClass`` expresses projection DEPTH, a
dimension provenance does not cover; see ``provenance`` module docstring).
"""
from .adapters import (
    CoreAuthorityProvider,
    CoreEventPublisherAdapter,
    CorePersistenceHookAdapter,
    DictPersistenceHook,
    MissingBlackHole,
    MissingGalactic,
    MissingMeasurement,
    MissingNBody,
    MissingObservation,
    MissingStellar,
    MissingTemporal,
    MissingUniverseEvolution,
)
from .builtins import (
    BuiltinModelParams,
    CLUSTER_MODEL_ID,
    GALAXY_MODEL_ID,
    POPULATION_MODEL_ID,
    STELLAR_MODEL_ID,
    WEB_MODEL_ID,
    classify_structure_regime,
    main_sequence_lifetime_gyr,
    main_sequence_luminosity_lsun,
    make_cluster_state,
    make_galaxy_state,
    make_population_state,
    make_star_state,
    make_web_state,
    register_builtin_models,
    remnant_for_mass,
    remnant_mass_msun,
)
from .config import EvolutionConfig, PerformanceBudget, TimestepPolicy
from .engine import (
    ClusterEvolutionOutcome,
    CosmicEvolutionEngine,
    EpochAdvanceReport,
    EvolutionOutcome,
    ScenarioComparison,
)
from .epoch import (
    EpochBoundaries,
    EpochClassifier,
    EpochInputs,
    EvolutionEpoch,
    epoch_inputs_from_state,
)
from .errors import (
    EvolutionAuthorityError,
    EvolutionDependencyError,
    EvolutionError,
    EvolutionLimitationError,
    EvolutionNumericalError,
    EvolutionPersistenceError,
    EvolutionValidationError,
)
from .events import EvolutionEvent, EvolutionEventKind
from .integration import (
    AuthorityProvider,
    BlackHoleProvider,
    EventPublisher,
    GalacticProvider,
    MeasurementProvider,
    NBodyProvider,
    ObservationProvider,
    PersistenceHook,
    RNGProvider,
    StellarProvider,
    TemporalProvider,
    UniverseEvolutionProvider,
)
from .ledger import EvolutionLedger
from .limitations import LimitationState
from .models import (
    EvolutionModel,
    EvolutionStep,
    ModelAssumption,
    ModelClassification,
    ModelRegistry,
)
from .provenance import (
    DataProvenance,
    ProjectionClass,
    ProvenanceTag,
    ScientificConfidence,
)
from .quantity import Quantity
from .scenarios import Scenario, ScenarioRegistry
from .state import (
    AGNActivityState,
    EvolutionState,
    MetallicityHistory,
    MorphologyClass,
    PopulationState,
    RemnantKind,
    StarFormationHistory,
    StellarLifecyclePhase,
    StructureRegime,
)
from .timebase import gyr_to_seconds, seconds_to_gyr, temporal_state_for
from .timestep import AdaptiveTimestepController, TimestepDecision, TimestepReason

__all__ = [
    # engine + results
    "CosmicEvolutionEngine",
    "EvolutionOutcome",
    "ClusterEvolutionOutcome",
    "EpochAdvanceReport",
    "ScenarioComparison",
    # state
    "EvolutionState",
    "PopulationState",
    "StarFormationHistory",
    "MetallicityHistory",
    "StellarLifecyclePhase",
    "RemnantKind",
    "AGNActivityState",
    "StructureRegime",
    "MorphologyClass",
    "Quantity",
    # events + ledger
    "EvolutionEvent",
    "EvolutionEventKind",
    "EvolutionLedger",
    # models
    "EvolutionModel",
    "EvolutionStep",
    "ModelAssumption",
    "ModelClassification",
    "ModelRegistry",
    # epochs
    "EvolutionEpoch",
    "EpochBoundaries",
    "EpochClassifier",
    "EpochInputs",
    "epoch_inputs_from_state",
    # scenarios
    "Scenario",
    "ScenarioRegistry",
    # timesteps
    "AdaptiveTimestepController",
    "TimestepDecision",
    "TimestepReason",
    "TimestepPolicy",
    # config
    "EvolutionConfig",
    "PerformanceBudget",
    # provenance + limitations
    "DataProvenance",
    "ProvenanceTag",
    "ProjectionClass",
    "ScientificConfidence",
    "LimitationState",
    # built-in models
    "BuiltinModelParams",
    "STELLAR_MODEL_ID",
    "POPULATION_MODEL_ID",
    "GALAXY_MODEL_ID",
    "CLUSTER_MODEL_ID",
    "WEB_MODEL_ID",
    "register_builtin_models",
    "make_star_state",
    "make_population_state",
    "make_galaxy_state",
    "make_cluster_state",
    "make_web_state",
    "classify_structure_regime",
    "main_sequence_lifetime_gyr",
    "main_sequence_luminosity_lsun",
    "remnant_for_mass",
    "remnant_mass_msun",
    # errors
    "EvolutionError",
    "EvolutionValidationError",
    "EvolutionNumericalError",
    "EvolutionAuthorityError",
    "EvolutionDependencyError",
    "EvolutionLimitationError",
    "EvolutionPersistenceError",
    # integration protocols + adapters
    "AuthorityProvider",
    "RNGProvider",
    "UniverseEvolutionProvider",
    "GalacticProvider",
    "StellarProvider",
    "BlackHoleProvider",
    "NBodyProvider",
    "TemporalProvider",
    "ObservationProvider",
    "MeasurementProvider",
    "EventPublisher",
    "PersistenceHook",
    "CoreAuthorityProvider",
    "CoreEventPublisherAdapter",
    "CorePersistenceHookAdapter",
    "DictPersistenceHook",
    "MissingUniverseEvolution",
    "MissingGalactic",
    "MissingStellar",
    "MissingBlackHole",
    "MissingNBody",
    "MissingTemporal",
    "MissingObservation",
    "MissingMeasurement",
    # time interop
    "gyr_to_seconds",
    "seconds_to_gyr",
    "temporal_state_for",
]
