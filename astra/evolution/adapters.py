"""ASTRA COSMOS — Phase 21: concrete integration adapters.

Two families live here:

1. REAL adapters binding the engine to systems that exist in this
   repository (authority, events, persistence, in-memory persistence),
   following the ``astra.destruction.adapters`` pattern. Each is exercised
   by tests/test_evolution_integration.py against the real core systems.

2. MISSING-dependency adapters for systems that DO NOT exist in this
   repository (universe evolution, galactic structure, observatory...).
   Every attribute access raises ``EvolutionDependencyError``: the failure
   is loud, immediate, and names the absent system. Nothing is ever
   silently substituted.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from astra.core.events import Event, EventBus
from astra.core.exceptions import AuthorityError as CoreAuthorityError
from astra.core.persistence import PersistenceManager, Snapshot
from astra.core.threading import AuthorityContext

from .errors import EvolutionAuthorityError, EvolutionDependencyError


# --------------------------------------------------------------------------
# Real adapters (present systems)
# --------------------------------------------------------------------------
class CoreAuthorityProvider:
    """Gates evolution mutations through core's AuthorityContext.

    Requires an active AuthorityContext on the registered simulation
    thread. Core AuthorityError is re-raised as this package's
    EvolutionAuthorityError (which subclasses both, so either except
    clause catches it).
    """

    def require(self, operation: str) -> None:
        try:
            AuthorityContext.require_authority(operation)
        except CoreAuthorityError as exc:
            raise EvolutionAuthorityError(str(exc), operation=operation) from exc


class CoreEventPublisherAdapter:
    """Binds EventPublisher to a real astra.core EventBus."""

    def __init__(self, bus: EventBus, *, tick: int = 0, source: str = "astra.evolution") -> None:
        self._bus = bus
        self._tick = int(tick)
        self._source = source
        self._sequence = 0
        self.handler_failures: list = []

    def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        self._sequence += 1
        event = Event.create(
            name=topic,
            tick=self._tick,
            sequence=self._sequence,
            data=dict(payload),
            source=self._source,
        )
        failures = self._bus.publish(event)
        if failures:
            self.handler_failures.extend(failures)


class CorePersistenceHookAdapter:
    """Binds PersistenceHook to a real astra.core PersistenceManager.

    The evolution payload rides in ``Snapshot.engine_state`` under the
    "astra.evolution" key; Snapshot provides checksums and atomic writes.
    Snapshot's own wall-clock ``timestamp`` is core metadata and is NOT
    part of the evolution payload; round-trip equality is asserted on the
    payload only.
    """

    PAYLOAD_KEY = "astra.evolution"

    def __init__(self, manager: PersistenceManager, *, tick: int = 0) -> None:
        self._pm = manager
        self._tick = int(tick)

    def save(self, key: str, payload: Dict[str, Any]) -> None:
        snapshot = Snapshot(
            schema_version="astra.evolution.v1",
            engine_state={self.PAYLOAD_KEY: payload},
            simulation_time={},
            entities={},
            frames={},
            rng_state={},
            command_history=[],
            event_history=[],
            tick=self._tick,
        )
        self._pm.save(snapshot, key)

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        if not self._pm.exists(key):
            return None
        snapshot = self._pm.load(key)
        payload = snapshot.engine_state.get(self.PAYLOAD_KEY)
        return payload if payload is None else dict(payload)


class DictPersistenceHook:
    """In-memory reference PersistenceHook; payloads round-trip through
    JSON, enforcing JSON-serializability. Deterministic."""

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def save(self, key: str, payload: Dict[str, Any]) -> None:
        self._store[key] = json.dumps(payload, sort_keys=True)

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        raw = self._store.get(key)
        return json.loads(raw) if raw is not None else None


# --------------------------------------------------------------------------
# Missing-dependency adapters (absent systems — fail loud, never substitute)
# --------------------------------------------------------------------------
class _MissingDependency:
    """Every attribute use raises EvolutionDependencyError naming the absent
    system. Instances are accepted anywhere the corresponding Protocol is
    expected, so a caller can wire the adapter explicitly and get honest
    failures instead of silent no-ops."""

    _module_name: str = "unknown"
    _capability: str = "unspecified"

    def __getattr__(self, name: str):
        raise EvolutionDependencyError(
            f"dependency '{self._module_name}' is not present in this repository "
            f"(capability: {self._capability}); cannot access '{name}'"
        )

    def __repr__(self) -> str:  # deterministic, informative
        return f"<MissingDependency {self._module_name} ({self._capability})>"


class MissingUniverseEvolution(_MissingDependency):
    _module_name = "universe evolution (cosmological background)"
    _capability = "scale factor, Hubble rate, lookback time"


class MissingGalactic(_MissingDependency):
    _module_name = "galactic / large-scale structure (Phase 20)"
    _capability = "galaxy, cluster, cosmic-web object store"


class MissingStellar(_MissingDependency):
    _module_name = "stellar physics (lifecycle engine)"
    _capability = "physical stellar lifecycle state machine"


class MissingBlackHole(_MissingDependency):
    _module_name = "black-hole population system"
    _capability = "mutable black-hole population objects"


class MissingNBody(_MissingDependency):
    _module_name = "n-body dynamics provider"
    _capability = "cluster potential/dynamics queries"


class MissingTemporal(_MissingDependency):
    _module_name = "temporal provider"
    _capability = "temporal-layer event registration"


class MissingObservation(_MissingDependency):
    _module_name = "observation system"
    _capability = "lookback / observed states of evolved objects"


class MissingMeasurement(_MissingDependency):
    _module_name = "observatory & measurement layer"
    _capability = "measurement of evolved objects"


__all__ = [
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
]
