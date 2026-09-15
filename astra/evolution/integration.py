"""ASTRA COSMOS — Phase 21: integration protocols.

These Protocols declare the exact integration surface between the
evolution engine and the rest of ASTRA. Concrete, tested adapters for the
systems that actually exist live in ``astra.evolution.adapters``; systems
that are ABSENT from this repository are declared here and bound to the
fail-loud ``Missing*`` adapters — they are never imported and never
reimplemented (dependency reconciliation matrix, docs/evolution).

Verified dependency status (see docs/evolution/DEPENDENCY_MATRIX.md):

    AuthorityProvider      PRESENT  (core threading; adapters.CoreAuthorityProvider)
    RNGProvider            PRESENT  (core rng; satisfied directly by RNGStream.next_float)
    EventPublisher         PRESENT  (core events; adapters.CoreEventPublisherAdapter)
    PersistenceHook        PRESENT  (core persistence; adapters.CorePersistenceHookAdapter)
    UniverseEvolutionProvider  ABSENT in repo (Protocol only; MissingUniverseEvolution)
    GalacticProvider           ABSENT in repo (Protocol only; MissingGalactic)
    StellarProvider            PARTIAL (celestial layer is a static taxonomy;
                               protocol declared, MissingStellar adapter)
    BlackHoleProvider          PARTIAL (geometry exists in astra.blackhole;
                               no mutable population objects; protocol only)
    NBodyProvider              PRESENT (not consumed by Phase 21; protocol
                               kept for cluster-regime callers)
    TemporalProvider           PRESENT (conventions reused; protocol for event/
                               clock interop callers)
    ObservationProvider        PARTIAL (astra.temporal.observation covers
                               worldline lookback only; protocol declared)
    MeasurementProvider        ABSENT in repo (Protocol only; MissingMeasurement)
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol, runtime_checkable


@runtime_checkable
class AuthorityProvider(Protocol):
    """Mutation gate. Implementations raise on denial (fail-closed)."""

    def require(self, operation: str) -> None: ...


@runtime_checkable
class RNGProvider(Protocol):
    """Deterministic uniform stream. Satisfied by astra.core.rng.RNGStream."""

    def next_float(self) -> float: ...


@runtime_checkable
class UniverseEvolutionProvider(Protocol):
    """Contract with the (currently ABSENT) Universe Evolution system.

    Phase 21 NEVER computes the cosmological background from first
    principles. Every method here is a consumption contract: when no
    provider is injected the engine refuses the corresponding capability
    with EvolutionDependencyError instead of deriving the value itself.
    """

    def scale_factor(self, cosmic_time_gyr: float) -> float: ...

    def cosmic_time_gyr(self, scale_factor: float) -> float: ...

    def hubble_parameter(self, cosmic_time_gyr: float) -> float: ...

    def lookback_time_gyr(self, cosmic_time_gyr: float) -> float: ...


@runtime_checkable
class GalacticProvider(Protocol):
    """Contract with the (currently ABSENT) Phase 20 galactic /
    large-scale-structure system. Until a Phase 20 exists, galaxy, group,
    cluster, supercluster and cosmic-web objects live as explicitly tagged
    evolution-layer states; this protocol is where such a system binds in
    later without touching the engine."""

    def get_galaxy(self, galaxy_id: str) -> Any: ...

    def get_cluster(self, cluster_id: str) -> Any: ...

    def get_cosmic_web(self, web_id: str) -> Any: ...


@runtime_checkable
class StellarProvider(Protocol):
    """Contract with the celestial/stellar layer. astra.celestial provides
    immutable taxonomy + properties (no lifecycle physics), so lifecycle
    state lives in the evolution layer; this protocol is the seam where a
    future stellar-physics system binds in."""

    def get_star(self, star_id: str) -> Any: ...


@runtime_checkable
class BlackHoleProvider(Protocol):
    """Contract with astra.blackhole (geometry authority). Population-level
    BH mass growth is Phase 21's own reduced-order state; geometry queries
    of a specific BH belong to the existing black-hole layer."""

    def get_black_hole(self, black_hole_id: str) -> Any: ...


@runtime_checkable
class NBodyProvider(Protocol):
    """Contract with astra.nbody for callers that analyze cluster regimes
    from real dynamics. Phase 21 itself computes no forces."""

    def potential_energy(self) -> float: ...


@runtime_checkable
class TemporalProvider(Protocol):
    """Contract with astra.temporal for causal bookkeeping interop."""

    def register_event(self, event: Any) -> None: ...


@runtime_checkable
class ObservationProvider(Protocol):
    """Contract with an observation system. Phase 21 never bypasses finite
    light propagation: observed states of evolved objects can only come
    from such a provider (astra.temporal.observation semantics)."""

    def lookback_state(self, observer: Any, object_id: str, at_cosmic_time_gyr: float) -> Any: ...


@runtime_checkable
class MeasurementProvider(Protocol):
    """Contract with an (currently ABSENT) observatory & measurement layer."""

    def measure(self, observer: Any, object_id: str) -> Any: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Publishes evolution lifecycle events to the core event bus."""

    def publish(self, topic: str, payload: Dict[str, Any]) -> None: ...


@runtime_checkable
class PersistenceHook(Protocol):
    """Persists/restores evolution payloads (JSON-serializable dicts)."""

    def save(self, key: str, payload: Dict[str, Any]) -> None: ...

    def load(self, key: str) -> Optional[Dict[str, Any]]: ...


__all__ = [
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
]
