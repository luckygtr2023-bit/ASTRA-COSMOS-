"""ASTRA COSMOS — Destruction & Impact Simulation.

Deterministic, authority-gated, persistence-compatible destruction layer.

- Physics: two-body reduced-mass kinetic energy and momentum budgets with
  documented, modelled partition fractions (all SIMULATED_DATA, never
  REAL_DATA).
- Determinism: all randomness flows through astra.core deterministic RNG
  streams; same seed + event + config => identical results. No global RNG,
  no wall-clock, no UUID-derived physics.
- Authority: every mutation is gated through an AuthorityProvider
  (fail-closed when absent; ``adapters.CoreAuthorityProvider`` binds to
  core's real AuthorityContext).
- Integration: real, tested adapters for core (entities, events, world,
  persistence), physics, celestial, nbody, motion, and orbital analysis
  live in ``astra.destruction.adapters`` / ``astra.destruction.analysis``.

Type conventions: ``Vec3`` and ``Provenance`` are documented ALIASES of the
canonical ``astra.mathematics.Vector3`` and
``astra.celestial.provenance.DataProvenance`` — this package defines no new
vector or provenance types.
"""
from .adapters import (
    AstraPhysicsAdapter,
    CoreAuthorityProvider,
    CoreCelestialResolverAdapter,
    CoreEntityRegistrarAdapter,
    CoreEventPublisherAdapter,
    CorePersistenceHookAdapter,
    CoreWorldRegistrarAdapter,
    DictPersistenceHook,
    NBodyDebrisSink,
    motion_component_for_fragment,
)
from .analysis import (
    FragmentOrbit,
    OrbitClass,
    classify_fragment_orbit,
    count_orbit_classes,
)
from .config import DestructionConfig, LimitsConfig
from .damage import DamageState, is_valid_transition, transition
from .errors import (
    AuthorityError,
    DestructionError,
    ImpactValidationError,
    LimitExceededError,
    NumericalError,
    PersistenceError,
    UnsupportedBodyError,
)
from .provenance import DataProvenance
from .system import DestructionSystem
from .types import (
    DebrisState,
    EjectaState,
    FragmentState,
    ImpactEnergy,
    ImpactEvent,
    ImpactGeometry,
    ImpactMomentum,
    ImpactResult,
    Provenance,
    Vec3,
)

__all__ = [
    # system
    "DestructionSystem",
    "DestructionConfig",
    "LimitsConfig",
    # damage
    "DamageState",
    "is_valid_transition",
    "transition",
    # types
    "ImpactEvent",
    "ImpactResult",
    "ImpactGeometry",
    "ImpactEnergy",
    "ImpactMomentum",
    "FragmentState",
    "EjectaState",
    "DebrisState",
    "Vec3",
    "Provenance",
    "DataProvenance",
    # errors
    "DestructionError",
    "ImpactValidationError",
    "NumericalError",
    "AuthorityError",
    "LimitExceededError",
    "UnsupportedBodyError",
    "PersistenceError",
    # adapters
    "CoreAuthorityProvider",
    "CoreEntityRegistrarAdapter",
    "CoreEventPublisherAdapter",
    "CorePersistenceHookAdapter",
    "CoreWorldRegistrarAdapter",
    "CoreCelestialResolverAdapter",
    "AstraPhysicsAdapter",
    "NBodyDebrisSink",
    "DictPersistenceHook",
    "motion_component_for_fragment",
    # analysis
    "FragmentOrbit",
    "OrbitClass",
    "classify_fragment_orbit",
    "count_orbit_classes",
]
