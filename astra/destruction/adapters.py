"""Concrete adapters binding destruction integration protocols to the real
ASTRA systems (core, physics, world, celestial, nbody, motion).

Every adapter here is exercised by tests/test_destruction.py against the
real systems — no simulated stand-ins are needed to use this package.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Mapping, Optional

from astra.core.entities import EntityManager
from astra.core.events import Event, EventBus
from astra.core.exceptions import AuthorityError as CoreAuthorityError
from astra.core.persistence import PersistenceManager, Snapshot
from astra.core.threading import AuthorityContext
from astra.motion.components import MotionComponent
from astra.motion.state import MotionState
from astra.nbody.bodies import NBodyBody
from astra.nbody.system import NBodySystem
from astra.physics.energy import kinetic_energy as physics_kinetic_energy
from astra.physics.momentum import linear_momentum as physics_linear_momentum
from astra.world.world import World

from .errors import AuthorityError, UnsupportedBodyError


# --------------------------------------------------------------------- core

class CoreAuthorityProvider:
    """Gates destruction mutations through core's AuthorityContext.

    Requires an active AuthorityContext on the registered simulation
    thread. Core AuthorityError is re-raised as this package's
    AuthorityError (which is a subclass of both DestructionError and the
    core error, so either except-clause still catches it).
    """

    def require(self, operation: str) -> None:
        try:
            AuthorityContext.require_authority(operation)
        except CoreAuthorityError as exc:
            raise AuthorityError(str(exc), operation=operation) from exc


class CoreEntityRegistrarAdapter:
    """Binds EntityRegistrar to a real astra.core EntityManager.

    EntityManager issues its own deterministic EntityIds
    (``entity_{tick}_{sequence}``); this adapter keeps the mapping between
    caller-chosen destruction IDs and core EntityIds. EntityManager has no
    general payload store, so payloads are held adapter-side and the kind/
    external id are encoded into the entity name and tags.
    """

    def __init__(self, entity_manager: EntityManager) -> None:
        self._em = entity_manager
        self._map: Dict[str, str] = {}
        self._payloads: Dict[str, Dict[str, Any]] = {}

    def register(self, entity_id: str, kind: str, payload: Dict[str, Any]) -> None:
        entity = self._em.create_entity(name=f"destruction:{kind}:{entity_id}")
        entity.tags.add("destruction")
        entity.tags.add(kind)
        self._map[entity_id] = entity.id.value
        self._payloads[entity_id] = dict(payload)

    def unregister(self, entity_id: str) -> None:
        core_id = self._map.pop(entity_id, None)
        self._payloads.pop(entity_id, None)
        if core_id is not None:
            self._em.destroy_entity(core_id)

    def exists(self, entity_id: str) -> bool:
        core_id = self._map.get(entity_id)
        return core_id is not None and self._em.get_entity(core_id) is not None

    def core_id_for(self, entity_id: str) -> Optional[str]:
        return self._map.get(entity_id)

    def payload_for(self, entity_id: str) -> Optional[Dict[str, Any]]:
        p = self._payloads.get(entity_id)
        return dict(p) if p is not None else None


class CoreEventPublisherAdapter:
    """Binds EventPublisher to a real astra.core EventBus.

    Events are emitted as core ``Event`` records (deterministic EventIds
    from tick + per-adapter monotonic sequence). Handler exceptions are
    collected (EventBus semantics: publish returns them) and exposed via
    ``handler_failures``.
    """

    def __init__(self, bus: EventBus, *, tick: int = 0, source: str = "astra.destruction") -> None:
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

    The destruction payload rides in ``Snapshot.engine_state`` under the
    "astra.destruction" key; Snapshot provides checksums and atomic file
    writes. Note Snapshot itself stamps a wall-clock ``timestamp`` — that
    field is core's metadata and is NOT part of the destruction payload;
    round-trip equality is asserted on the payload only.
    """

    PAYLOAD_KEY = "astra.destruction"

    def __init__(self, manager: PersistenceManager, *, tick: int = 0) -> None:
        self._pm = manager
        self._tick = int(tick)

    def save(self, key: str, payload: Dict[str, Any]) -> None:
        snapshot = Snapshot(
            schema_version="astra.destruction.v1",
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
    """In-memory reference PersistenceHook.

    Payloads are round-tripped through JSON, enforcing the
    JSON-serialisability contract that real persistence depends on.
    Deterministic; useful for tests and embedded runs.
    """

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def save(self, key: str, payload: Dict[str, Any]) -> None:
        self._store[key] = json.dumps(payload, sort_keys=True)

    def load(self, key: str) -> Optional[Dict[str, Any]]:
        raw = self._store.get(key)
        return json.loads(raw) if raw is not None else None


# -------------------------------------------------------------- world/space

class CoreWorldRegistrarAdapter:
    """Binds WorldRegistrar to a real astra.world World spatial index.

    World.index_object takes (object_id, position tuple) and has no metadata
    parameter; metadata is kept adapter-side.
    """

    def __init__(self, world: World) -> None:
        self._world = world
        self._metadata: Dict[str, Dict[str, Any]] = {}

    def register_object(self, object_id: str, position: Any, metadata: Dict[str, Any]) -> None:
        if hasattr(position, "to_tuple"):
            position = position.to_tuple()
        self._world.index_object(object_id, tuple(position))
        self._metadata[object_id] = dict(metadata)

    def unregister_object(self, object_id: str) -> None:
        self._world.unindex_object(object_id)
        self._metadata.pop(object_id, None)

    def metadata_for(self, object_id: str) -> Optional[Dict[str, Any]]:
        m = self._metadata.get(object_id)
        return dict(m) if m is not None else None


class CoreCelestialResolverAdapter:
    """Binds CelestialResolver to real celestial property blocks.

    Accepts a mapping of object_id -> CelestialObject or
    CelestialProperties. Unknown objects (exists() is False) and objects
    with physically incomplete data raise UnsupportedBodyError — the
    celestial layer's refusal to fabricate is preserved, not papered over.
    The celestial catalogue is static: velocity/position are intentionally
    NOT resolvable here (kinematics belong to motion/nbody).
    """

    def __init__(self, objects: Mapping[str, Any]) -> None:
        self._objects = objects

    def _properties(self, object_id: str) -> Any:
        obj = self._objects[object_id]
        return getattr(obj, "properties", obj)

    def get_mass_kg(self, object_id: str) -> float:
        try:
            return float(self._properties(object_id).require_mass_kg())
        except KeyError as exc:
            raise UnsupportedBodyError(f"unknown celestial object: {object_id}") from exc
        except Exception as exc:
            raise UnsupportedBodyError(
                f"celestial object {object_id} has unknown mass: {exc}"
            ) from exc

    def get_radius_m(self, object_id: str) -> float:
        try:
            return float(self._properties(object_id).require_radius_m())
        except KeyError as exc:
            raise UnsupportedBodyError(f"unknown celestial object: {object_id}") from exc
        except Exception as exc:
            raise UnsupportedBodyError(
                f"celestial object {object_id} has unknown radius: {exc}"
            ) from exc

    def exists(self, object_id: str) -> bool:
        return object_id in self._objects


# -------------------------------------------------------------------- other

class AstraPhysicsAdapter:
    """Cross-checks destruction energy/momentum against astra.physics."""

    def kinetic_energy_j(self, mass_kg: float, velocity: Any) -> float:
        return physics_kinetic_energy(mass_kg, velocity)

    def momentum_kg_m_s(self, mass_kg: float, velocity: Any) -> Any:
        return physics_linear_momentum(mass_kg, velocity)


class NBodyDebrisSink:
    """Hands destruction fragments to a real NBodySystem as new bodies.

    Fragment IDs become NBodyBody ids (unique, deterministic). Authority is
    enforced by DestructionSystem before this sink is ever invoked, so the
    nbody layer's own token requirement can stay off (its thread-registry
    enforcement remains active).
    """

    def __init__(self, nbody_system: NBodySystem) -> None:
        self._system = nbody_system

    def register_fragment(self, fragment) -> None:
        self._system.add_body(
            NBodyBody(
                id=fragment.fragment_id,
                mass=fragment.mass_kg,
                position=fragment.position,
                velocity=fragment.velocity,
            ),
            require_authority=False,
        )

    def register_fragments(self, fragments) -> int:
        count = 0
        for fragment in fragments:
            self.register_fragment(fragment)
            count += 1
        return count


def motion_component_for_fragment(fragment) -> MotionComponent:
    """Build a real MotionComponent carrying a fragment's kinematic state.

    Attach it to an entity and a MotionSystem will integrate the fragment
    with the same integrators used for any other moving object. The
    component id is set explicitly: core Component defaults its id from
    ``id(self)`` (a memory address), which would break snapshot
    determinism; the fragment id is deterministic instead.
    """
    return MotionComponent(
        id=f"motion:{fragment.fragment_id}",
        state=MotionState(
            position=fragment.position,
            velocity=fragment.velocity,
            time=fragment.created_at_s,
        ),
    )
