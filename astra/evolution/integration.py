"""ASTRA Evolution — integration Protocols (dependency inversion).

Each Protocol mirrors the public surface of an existing ASTRA subsystem.
Phase 21 consumes these via injection; where the real subsystem is ABSENT
the :mod:`astra.evolution.adapters` module provides a failing adapter that
raises :class:`~astra.evolution.errors.EvolutionDependencyError` on use
— never a silent stub.

Reconciliation (§1.4) against the actual repository as of 2026-09-15:

- PRESENT: astra.core (coords, time, rng, events, threading), astra.mathematics,
  astra.celestial (definitions only), astra.physics, astra.temporal,
  astra.blackhole, astra.spacetime, astra.world, astra.nbody, astra.orbital,
  astra.relativity, astra.motion, astra.ingestion, astra.destruction,
  astra.theoretical
- PARTIAL: astra.temporal.observation (flat-spacetime only), astra.celestial (no evolution)
- ABSENT: Universe Evolution / cosmology (no scale_factor, expansion history),
  Galactic / Large-Scale Structure (Phase 20 galaxy/cluster/supercluster/cosmic-web),
  Observatory & Measurement, cosmological dark matter halo beyond celestial definitions

Protocols use ``runtime_checkable`` so ``isinstance`` guards work in adapters
and engine diagnostics without importing the real module.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuthorityProvider(Protocol):
    """Simulation-thread authority (wraps ``astra.core.threading.AuthorityContext``)."""

    def require(self, operation: str) -> None: ...

    def has_authority(self, operation: str) -> bool: ...


@runtime_checkable
class RNGProvider(Protocol):
    """Deterministic RNG (wraps ``astra.core.rng.DeterministicRNG``)."""

    def uniform(self, a: float = 0.0, b: float = 1.0) -> float: ...

    def random(self) -> float: ...

    def state(self) -> Any: ...


@runtime_checkable
class UniverseEvolutionProvider(Protocol):
    """Cosmological background — owned by Universe Evolution (ABSENT in this repo).

    Phase 21 NEVER computes these from first principles; it consumes them.
    Where this provider is absent the engine exposes
    ``LimitationState.MISSING_REQUIRED_DATA``.
    """

    def scale_factor(self, cosmic_time_gyr: float) -> float: ...

    def cosmic_time_gyr(self, scale_factor: float) -> float: ...

    def hubble_parameter(self, cosmic_time_gyr: float) -> float: ...

    def lookback_time_gyr(self, cosmic_time_gyr: float) -> float: ...

    def comoving_distance_mpc(self, z: float) -> float: ...

    def luminosity_distance_mpc(self, z: float) -> float: ...


@runtime_checkable
class GalacticProvider(Protocol):
    """Galactic / Large-Scale Structure (Phase 20, ABSENT in this repo)."""

    def get_galaxy(self, galaxy_id: str) -> Any: ...

    def get_group(self, group_id: str) -> Any: ...

    def get_cluster(self, cluster_id: str) -> Any: ...

    def get_supercluster(self, supercluster_id: str) -> Any: ...

    def get_cosmic_web(self, web_id: str) -> Any: ...

    def replace_galaxy(self, galaxy: Any) -> None: ...

    def replace_cluster(self, cluster: Any) -> None: ...


@runtime_checkable
class StellarProvider(Protocol):
    """Celestial / Stellar evolution interface (PRESENT as definitions, PARTIAL for evolution)."""

    def get_star(self, star_id: str) -> Any: ...

    def get_population(self, population_id: str) -> Any: ...

    def advance_star(self, star_id: str, dt_gyr: float) -> Any: ...


@runtime_checkable
class BlackHoleProvider(Protocol):
    """Black-Hole Physics (PRESENT)."""

    def get_black_hole(self, black_hole_id: str) -> Any: ...

    def grow_by_accretion(self, black_hole_id: str, mass_kg: float) -> Any: ...

    def merge(self, bh_a_id: str, bh_b_id: str) -> Any: ...


@runtime_checkable
class NBodyProvider(Protocol):
    """N-Body / Gravity (PRESENT)."""

    def add_body(self, body_id: str, mass_kg: float, position: Any, velocity: Any) -> None: ...

    def remove_body(self, body_id: str) -> None: ...

    def potential_at(self, position: Any) -> float: ...

    def gravity_at(self, position: Any) -> Any: ...


@runtime_checkable
class TemporalProvider(Protocol):
    """Temporal & Causality (PRESENT)."""

    def register_event(self, event: Any) -> None: ...

    def check_causal_order(self, a: Any, b: Any) -> Any: ...

    def observe(self, history: Any, observer_position: Any, observation_time_s: float) -> Any: ...


@runtime_checkable
class ObservationProvider(Protocol):
    """Observation & Cosmic History (PARTIAL — flat-spacetime only)."""

    def lookback_state(self, observer: Any, object_id: str, at_cosmic_time_gyr: float) -> Any: ...


@runtime_checkable
class MeasurementProvider(Protocol):
    """Observatory & Measurement (ABSENT)."""

    def measure(self, observer: Any, object_id: str) -> Any: ...


@runtime_checkable
class PhysicsProvider(Protocol):
    """Physics (PRESENT)."""

    def kinetic_energy_j(self, mass_kg: float, velocity: Any) -> float: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Event publication (wraps ``astra.core.events.EventBus``)."""

    def publish(self, topic: str, payload: dict) -> None: ...


@runtime_checkable
class PersistenceHook(Protocol):
    """Persistence extension point."""

    def save(self, key: str, payload: dict) -> None: ...

    def load(self, key: str) -> dict | None: ...
