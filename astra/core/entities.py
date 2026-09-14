"""ASTRA Core entity management system."""

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Set, Any, Type, Iterator, Tuple
import threading
from copy import deepcopy

from astra.core.ids import EntityId
from astra.core.logging import get_logger
from astra.core.exceptions import EntityError, AuthorityError
from astra.core.threading import AuthorityContext, get_simulation_thread_registry


@dataclass
class Component:
    """Base component class for entities."""

    id: str = ""

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, "id", f"component_{type(self).__name__}_{id(self)}")

    def clone(self) -> "Component":
        """Create a deep copy of this component."""
        return deepcopy(self)


@dataclass
class Entity:
    """An entity in the simulation."""

    id: EntityId
    name: str = ""
    components: Dict[str, Component] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    enabled: bool = True
    tick_created: int = 0

    def add_component(self, component: Component):
        """Add a component to this entity."""
        self.components[component.id] = component

    def remove_component(self, component_id: str):
        """Remove a component from this entity."""
        if component_id in self.components:
            del self.components[component_id]

    def get_component(self, component_type: Type[Component]) -> Optional[Component]:
        """Get a component by type."""
        type_name = component_type.__name__
        for comp in self.components.values():
            if type(comp).__name__ == type_name:
                return comp
        return None

    def has_component(self, component_type: Type[Component]) -> bool:
        """Check if entity has a component of the given type."""
        return self.get_component(component_type) is not None

    def clone(self) -> "Entity":
        """Create a deep copy of this entity."""
        return Entity(
            id=self.id,
            name=self.name,
            components={k: v.clone() for k, v in self.components.items()},
            tags=self.tags.copy(),
            enabled=self.enabled,
            tick_created=self.tick_created,
        )


class Query:
    """Entity query for filtering entities."""

    def __init__(self):
        self._required_components: Set[str] = set()
        self._excluded_components: Set[str] = set()
        self._required_tags: Set[str] = set()
        self._excluded_tags: Set[str] = set()
        self._enabled_only: bool = False

    def with_component(self, component_type: Type[Component]) -> "Query":
        """Require a component of the given type."""
        self._required_components.add(component_type.__name__)
        return self

    def without_component(self, component_type: Type[Component]) -> "Query":
        """Exclude entities with a component of the given type."""
        self._excluded_components.add(component_type.__name__)
        return self

    def with_tag(self, tag: str) -> "Query":
        """Require a tag."""
        self._required_tags.add(tag)
        return self

    def without_tag(self, tag: str) -> "Query":
        """Exclude entities with a tag."""
        self._excluded_tags.add(tag)
        return self

    def enabled_only(self) -> "Query":
        """Only include enabled entities."""
        self._enabled_only = True
        return self

    def matches(self, entity: Entity) -> bool:
        """Check if an entity matches this query."""
        if self._enabled_only and not entity.enabled:
            return False

        # Check required components
        entity_component_types = {type(c).__name__ for c in entity.components.values()}
        if not self._required_components.issubset(entity_component_types):
            return False

        # Check excluded components
        if self._excluded_components & entity_component_types:
            return False

        # Check tags
        if not self._required_tags.issubset(entity.tags):
            return False
        if self._excluded_tags & entity.tags:
            return False

        return True


class EntityManager:
    """Manages entities in the simulation."""

    def __init__(self):
        self._entities: Dict[str, Entity] = {}
        self._next_sequence = 0
        self._lock = threading.RLock()
        self._logger = get_logger("entity_manager")
        self._current_tick = 0
        self._registry = get_simulation_thread_registry()

    def _require_authority_if_needed(self, operation: str):
        """Require simulation thread identity if a simulation thread is registered.
        
        This enforces that only the registered simulation thread may mutate,
        but does not require an AuthorityContext token, allowing direct
        creation on the simulation thread outside a token context.
        """
        if self._registry.is_registered() and not self._registry.is_simulation_thread():
            raise AuthorityError(
                f"Operation '{operation}' requires simulation thread",
                operation=operation,
                context={
                    "current_thread_id": threading.current_thread().ident,
                    "registered_thread_id": self._registry.get_simulation_thread_id(),
                },
            )

    def set_current_tick(self, tick: int):
        """Set the current simulation tick."""
        self._current_tick = tick

    def create_entity(self, name: str = "", require_authority: bool = False) -> Entity:
        """Create a new entity."""
        if require_authority:
            AuthorityContext.require_authority("entity.create")
        else:
            # Enforce if registry is active
            self._require_authority_if_needed("entity.create")
        with self._lock:
            entity_id = EntityId.generate(self._current_tick, self._next_sequence)
            self._next_sequence += 1

            entity = Entity(
                id=entity_id,
                name=name or f"entity_{self._next_sequence}",
                tick_created=self._current_tick,
            )
            self._entities[entity_id.value] = entity
            self._logger.debug(f"Created entity: {entity_id.value}")
            return entity

    def destroy_entity(self, entity_id: str, require_authority: bool = False):
        """Destroy an entity."""
        if require_authority:
            AuthorityContext.require_authority("entity.destroy")
        else:
            self._require_authority_if_needed("entity.destroy")
        with self._lock:
            if entity_id not in self._entities:
                raise EntityError(f"Entity not found: {entity_id}", entity_id, "destroy")
            del self._entities[entity_id]
            self._logger.debug(f"Destroyed entity: {entity_id}")

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID."""
        return self._entities.get(entity_id)

    def get_entity_or_raise(self, entity_id: str) -> Entity:
        """Get an entity by ID or raise an error."""
        entity = self._entities.get(entity_id)
        if entity is None:
            raise EntityError(f"Entity not found: {entity_id}", entity_id, "get")
        return entity

    def update_entity(self, entity: Entity, require_authority: bool = False):
        """Update an existing entity."""
        if require_authority:
            AuthorityContext.require_authority("entity.update")
        else:
            self._require_authority_if_needed("entity.update")
        with self._lock:
            if entity.id.value not in self._entities:
                raise EntityError(
                    f"Entity not found: {entity.id.value}", entity.id.value, "update"
                )
            self._entities[entity.id.value] = entity

    def query(self, query: Query) -> List[Entity]:
        """Execute a query and return matching entities."""
        with self._lock:
            # Create a snapshot to avoid holding lock during iteration
            entities_snapshot = list(self._entities.values())

        # Filter outside the lock
        return [e for e in entities_snapshot if query.matches(e)]

    def query_iterator(self, query: Query) -> Iterator[Entity]:
        """Iterate over matching entities safely."""
        with self._lock:
            entities_snapshot = list(self._entities.values())

        for entity in entities_snapshot:
            if query.matches(entity):
                yield entity

    def get_all_entities(self) -> List[Entity]:
        """Get all entities (snapshot)."""
        with self._lock:
            return list(self._entities.values())

    def get_entity_count(self) -> int:
        """Get the number of entities."""
        with self._lock:
            return len(self._entities)

    def clear(self, require_authority: bool = False):
        """Clear all entities."""
        if require_authority:
            AuthorityContext.require_authority("entity.clear")
        else:
            # Allow clear without authority if no registry, but enforce if registered
            # For engine reset, we need to allow clear even without authority, so only enforce when explicitly requested
            if require_authority:
                self._require_authority_if_needed("entity.clear")
        with self._lock:
            self._entities.clear()
            self._next_sequence = 0
            self._logger.debug("Cleared all entities")

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get a serializable state snapshot."""
        with self._lock:
            return {
                "entities": {
                    eid: {
                        "id": e.id.value,
                        "name": e.name,
                        "components": {
                            cid: {"type": type(c).__name__, "data": deepcopy(c.__dict__)}
                            for cid, c in e.components.items()
                        },
                        "tags": list(e.tags),
                        "enabled": e.enabled,
                        "tick_created": e.tick_created,
                    }
                    for eid, e in self._entities.items()
                },
                "next_sequence": self._next_sequence,
                "current_tick": self._current_tick,
            }

    def restore_from_snapshot(self, snapshot: Dict[str, Any]):
        """Restore state from a snapshot with component preservation."""
        with self._lock:
            self._entities.clear()
            for eid, edata in snapshot.get("entities", {}).items():
                entity = Entity(
                    id=EntityId(edata["id"]),
                    name=edata["name"],
                    tags=set(edata.get("tags", [])),
                    enabled=edata.get("enabled", True),
                    tick_created=edata.get("tick_created", 0),
                )
                # Restore components
                for cid, cdata in edata.get("components", {}).items():
                    try:
                        comp_type = cdata.get("type", "Component")
                        comp_data = cdata.get("data", {})
                        # Create base component and restore its dict
                        comp = Component(id=comp_data.get("id", cid))
                        # Restore all saved attributes
                        for k, v in comp_data.items():
                            try:
                                setattr(comp, k, v)
                            except Exception:
                                pass
                        entity.components[cid] = comp
                    except Exception as ce:
                        self._logger.warning(f"Failed to restore component {cid}: {ce}")
                self._entities[eid] = entity

            self._next_sequence = snapshot.get("next_sequence", 0)
            self._current_tick = snapshot.get("current_tick", 0)
