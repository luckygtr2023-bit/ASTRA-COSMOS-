"""ASTRA COSMOS — Long-Term Cosmic Evolution Engine (Phase 21).

Layered above Universe Evolution (which owns cosmological time, scale factor
and expansion history) and above Galactic/LSS structure (which owns Phase 20
galaxy/cluster/cosmic-web structure).  Phase 21 owns the evolution of
structures and populations within the cosmological background over timescales
from Myr to trillions of years and beyond where the configured model permits.

Architecture
------------
Universe Evolution  →  Galactic / LSS  →  Long-Term Cosmic Evolution (this package)

This package NEVER computes the scale factor from scratch, never redefines
galaxy types, never creates a second temporal engine, and never introduces a
new coordinate system.  Where an ASTRA dependency is ABSENT the engine
surfaces an explicit ``EvolutionDependencyError`` / ``LimitationState``
instead of fabricating data.
"""

from .adapters import (
    BlackHoleAdapter,
    CelestialStellarAdapter,
    CoreAuthorityAdapter,
    CoreRNGAdapter,
    MissingBlackHole,
    MissingGalactic,
    MissingMeasurement,
    MissingNBody,
    MissingObservation,
    MissingStellar,
    MissingTemporal,
    MissingUniverseEvolution,
)
from .config import EvolutionConfig, PerformanceBudget, TimestepPolicy
from .engine import CosmicEvolutionEngine
from .epoch import EpochBoundaries, EpochClassifier, EvolutionEpoch
from .errors import (
    EvolutionAuthorityError,
    EvolutionDependencyError,
    EvolutionError,
    EvolutionLimitationError,
    EvolutionNumericalError,
    EvolutionValidationError,
)
from .limitations import LimitationState
from .models import (
    EvolutionModel,
    ModelAssumption,
    ModelClassification,
    ModelRegistry,
)
from .provenance import Provenance, Quantity
from .scenarios import Scenario, ScenarioRegistry
from .state import (
    AGNActivity,
    ClusterState,
    CosmicWebState,
    EvolutionEvent,
    EvolutionEventKind,
    EvolutionState,
    GalaxyMorphology,
    GalaxyState,
    MetallicityHistory,
    PopulationState,
    StarFormationHistory,
    StellarPhase,
    StellarTransition,
    StellarTransitionTrigger,
    StructureRegime,
    VoidState,
)
from .timestep import AdaptiveTimestepController, TimestepDecision, TimestepReason

__all__ = [
    # Engine
    "CosmicEvolutionEngine",
    # Config
    "EvolutionConfig",
    "PerformanceBudget",
    "TimestepPolicy",
    # Epoch
    "EpochClassifier",
    "EpochBoundaries",
    "EvolutionEpoch",
    # State
    "EvolutionEvent",
    "EvolutionEventKind",
    "EvolutionState",
    "PopulationState",
    "StarFormationHistory",
    "MetallicityHistory",
    "StellarPhase",
    "StellarTransition",
    "StellarTransitionTrigger",
    "GalaxyMorphology",
    "GalaxyState",
    "StructureRegime",
    "AGNActivity",
    "ClusterState",
    "CosmicWebState",
    "VoidState",
    # Models
    "EvolutionModel",
    "ModelAssumption",
    "ModelClassification",
    "ModelRegistry",
    # Scenarios
    "Scenario",
    "ScenarioRegistry",
    # Timestep
    "AdaptiveTimestepController",
    "TimestepDecision",
    "TimestepReason",
    # Provenance
    "Provenance",
    "Quantity",
    # Limitations
    "LimitationState",
    # Errors
    "EvolutionError",
    "EvolutionValidationError",
    "EvolutionAuthorityError",
    "EvolutionNumericalError",
    "EvolutionDependencyError",
    "EvolutionLimitationError",
    # Adapters
    "CoreAuthorityAdapter",
    "CoreRNGAdapter",
    "CelestialStellarAdapter",
    "BlackHoleAdapter",
    "MissingUniverseEvolution",
    "MissingGalactic",
    "MissingStellar",
    "MissingBlackHole",
    "MissingNBody",
    "MissingTemporal",
    "MissingObservation",
    "MissingMeasurement",
]
