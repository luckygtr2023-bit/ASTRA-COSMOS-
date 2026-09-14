"""ASTRA World - main world container and management.

Contract: The World is the authoritative spatial/scene organization layer.
It integrates with existing ASTRA systems (coordinates, entities, events,
persistence, temporal) without replacing them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
import threading

from astra.world.identities import WorldId, SceneId, RegionId
from astra.world.hierarchy import WorldHierarchy, WorldNode
from astra.world.scene_graph import SceneGraph, SceneNode
from astra.world.spatial import SpatialPartition, SpatialIndex, BoundingBox, SpatialRegion
from astra.world.region import WorldRegion, RegionState, RegionLifecycle
from astra.world.exceptions import (
    WorldError, SceneError, HierarchyError, 
    LifecycleError, DuplicateIdError
)
from astra.core.logging import get_logger
from astra.core.events import EventBus, Event
from astra.core.persistence import Snapshot


@dataclass
class WorldState:
    """Snapshot of world state."""
    
    world_id: str = ""
    name: str = ""
    tick: int = 0
    
    # Counts
    hierarchy_node_count: int = 0
    scene_node_count: int = 0
    region_count: int = 0
    indexed_object_count: int = 0
    
    # Origin
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    
    # Loaded regions
    loaded_regions: List[str] = field(default_factory=list)


class World:
    """The main world container.
    
    The World provides:
    - Hierarchical organization (WorldHierarchy)
    - Scene graph for transforms (SceneGraph)
    - Spatial partitioning (SpatialPartition, SpatialIndex)
    - Region lifecycle (RegionLifecycle)
    - Event integration
    - Persistence hooks
    
    It does NOT own:
    - Celestial objects (references only)
    - Entity state (references core entities)
    - Physics calculations (delegates to physics systems)
    - Rendering (independent)
    """
    
    def __init__(self, world_id: Optional[WorldId] = None, name: str = "Default World"):
        self._world_id = world_id or WorldId.from_name("default")
        self._name = name
        
        # Core systems
        self._hierarchy = WorldHierarchy()
        self._scene_graph = SceneGraph()
        self._spatial_partition = SpatialPartition()
        self._spatial_index = SpatialIndex()
        self._region_lifecycle = RegionLifecycle()
        
        # Integration
        self._event_bus: Optional[EventBus] = None
        self._current_tick = 0
        
        # State
        self._origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._scenes: Dict[str, Any] = {}  # scene_id -> scene data
        
        # Threading
        self._lock = threading.RLock()
        self._logger = get_logger("world")
    
    @property
    def world_id(self) -> WorldId:
        """Get the world ID."""
        return self._world_id
    
    @property
    def name(self) -> str:
        """Get the world name."""
        return self._name
    
    def set_event_bus(self, event_bus: EventBus) -> None:
        """Set the event bus for integration."""
        self._event_bus = event_bus
    
    def set_tick(self, tick: int) -> None:
        """Set the current simulation tick."""
        self._current_tick = tick
    
    def get_tick(self) -> int:
        """Get the current simulation tick."""
        return self._current_tick
    
    # -- Hierarchy operations -------------------------------------------------
    
    def add_hierarchy_node(self, node: WorldNode) -> None:
        """Add a node to the world hierarchy."""
        self._hierarchy.add_node(node)
        self._emit_event("world_node_added", {"node_id": node.id})
    
    def remove_hierarchy_node(self, node_id: str, cascade: bool = False) -> None:
        """Remove a node from the hierarchy."""
        self._hierarchy.remove_node(node_id, cascade=cascade)
        self._emit_event("world_node_removed", {"node_id": node_id})
    
    def get_hierarchy_node(self, node_id: str) -> Optional[WorldNode]:
        """Get a hierarchy node by ID."""
        return self._hierarchy.get_node(node_id)
    
    # -- Scene graph operations -----------------------------------------------
    
    def add_scene_node(self, node: SceneNode) -> None:
        """Add a node to the scene graph."""
        self._scene_graph.add_node(node)
        self._emit_event("scene_node_added", {"node_id": node.id})
    
    def remove_scene_node(self, node_id: str, cascade: bool = False) -> None:
        """Remove a node from the scene graph."""
        self._scene_graph.remove_node(node_id, cascade=cascade)
        self._emit_event("scene_node_removed", {"node_id": node_id})
    
    def get_scene_node(self, node_id: str) -> Optional[SceneNode]:
        """Get a scene node by ID."""
        return self._scene_graph.get_node(node_id)
    
    def get_world_position(self, node_id: str) -> Tuple[float, float, float]:
        """Get the world-space position of a scene node."""
        return self._scene_graph.get_world_position(node_id)
    
    def activate_scene_node(self, node_id: str) -> None:
        """Activate a scene node."""
        self._scene_graph.activate(node_id)
        self._emit_event("scene_node_activated", {"node_id": node_id})
    
    def deactivate_scene_node(self, node_id: str) -> None:
        """Deactivate a scene node."""
        self._scene_graph.deactivate(node_id)
        self._emit_event("scene_node_deactivated", {"node_id": node_id})
    
    # -- Spatial operations ---------------------------------------------------
    
    def add_spatial_region(self, region: SpatialRegion) -> None:
        """Add a spatial region."""
        self._spatial_partition.add_region(region)
    
    def remove_spatial_region(self, region_id: str, cascade: bool = False) -> None:
        """Remove a spatial region."""
        self._spatial_partition.remove_region(region_id, cascade=cascade)
    
    def index_object(self, object_id: str, position: Tuple[float, float, float]) -> None:
        """Index an object in the spatial index."""
        self._spatial_index.insert(object_id, position)
    
    def unindex_object(self, object_id: str) -> None:
        """Remove an object from the spatial index."""
        self._spatial_index.remove(object_id)
    
    def update_object_position(
        self, 
        object_id: str, 
        position: Tuple[float, float, float]
    ) -> None:
        """Update an object's position in the spatial index."""
        self._spatial_index.update_position(object_id, position)
    
    def query_nearest_objects(
        self, 
        point: Tuple[float, float, float], 
        k: int = 1
    ) -> List[Tuple[str, float]]:
        """Find k nearest indexed objects."""
        return self._spatial_index.nearest(point, k)
    
    def query_objects_in_radius(
        self, 
        center: Tuple[float, float, float], 
        radius: float
    ) -> List[str]:
        """Find all objects within a radius."""
        return self._spatial_index.within_radius(center, radius)
    
    # -- Region lifecycle operations ------------------------------------------
    
    def register_region(self, region_id: str, initial_state: RegionState = RegionState.UNLOADED) -> None:
        """Register a region with the lifecycle system."""
        self._region_lifecycle.register_region(region_id, initial_state)
    
    def transition_region_state(self, region_id: str, new_state: RegionState) -> None:
        """Transition a region to a new state."""
        self._region_lifecycle.transition(region_id, new_state)
        self._emit_event("region_state_changed", {
            "region_id": region_id,
            "new_state": new_state.value
        })
    
    def is_region_loaded(self, region_id: str) -> bool:
        """Check if a region is loaded."""
        return self._region_lifecycle.is_loaded(region_id)
    
    # -- Origin rebasing ------------------------------------------------------
    
    def set_origin(self, origin: Tuple[float, float, float]) -> None:
        """Set the world origin."""
        self._origin = origin
    
    def get_origin(self) -> Tuple[float, float, float]:
        """Get the current world origin."""
        return self._origin
    
    # -- Event emission -------------------------------------------------------
    
    def _emit_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Emit a world event if event bus is configured."""
        if self._event_bus is not None:
            self._event_bus.publish_sync(
                name=event_name,
                tick=self._current_tick,
                data=data,
                source="world"
            )
    
    # -- State and persistence ------------------------------------------------
    
    def get_state(self) -> WorldState:
        """Get current world state."""
        return WorldState(
            world_id=self._world_id.value,
            name=self._name,
            tick=self._current_tick,
            hierarchy_node_count=self._hierarchy.get_node_count(),
            scene_node_count=self._scene_graph.get_node_count(),
            region_count=len(self._region_lifecycle.get_all_states()),
            indexed_object_count=self._spatial_index.get_object_count(),
            origin=self._origin,
            loaded_regions=self._region_lifecycle.get_regions_in_state(RegionState.LOADED),
        )
    
    def to_snapshot(self) -> Dict[str, Any]:
        """Serialize world state for persistence."""
        with self._lock:
            return {
                "world_id": self._world_id.value,
                "name": self._name,
                "tick": self._current_tick,
                "origin": self._origin,
                "hierarchy": {
                    "nodes": [
                        {
                            "id": n.id,
                            "name": n.name,
                            "parent_id": n.parent_id,
                            "object_ref": n.object_ref,
                            "entity_ref": n.entity_ref,
                            "local_transform": n.local_transform,
                            "enabled": n.enabled,
                            "visible": n.visible,
                            "simulated": n.simulated,
                            "tags": list(n.tags),
                            "metadata": n.metadata,
                        }
                        for n in self._hierarchy.get_all_nodes().values()
                    ]
                },
                "scene_graph": {
                    "nodes": [
                        {
                            "id": n.id,
                            "name": n.name,
                            "parent_id": n.parent_id,
                            "local_position": n.local_position,
                            "enabled": n.enabled,
                            "visible": n.visible,
                            "simulated": n.simulated,
                            "object_ref": n.object_ref,
                            "entity_ref": n.entity_ref,
                            "tags": list(n.tags),
                            "metadata": n.metadata,
                        }
                        for n in self._scene_graph.get_all_nodes().values()
                    ]
                },
                "regions": {
                    rid: state.value 
                    for rid, state in self._region_lifecycle.get_all_states().items()
                },
            }
    
    def restore_from_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """Restore world state from a snapshot."""
        with self._lock:
            # Clear existing state
            self._hierarchy.clear()
            self._scene_graph.clear()
            self._region_lifecycle.clear()
            self._spatial_index.clear()
            
            # Restore basic state
            self._name = snapshot.get("name", self._name)
            self._current_tick = snapshot.get("tick", 0)
            self._origin = tuple(snapshot.get("origin", self._origin))
            
            # Restore hierarchy
            hierarchy_data = snapshot.get("hierarchy", {})
            for node_data in hierarchy_data.get("nodes", []):
                node = WorldNode(
                    id=node_data["id"],
                    name=node_data["name"],
                    parent_id=node_data.get("parent_id"),
                    object_ref=node_data.get("object_ref"),
                    entity_ref=node_data.get("entity_ref"),
                    local_transform=tuple(node_data.get("local_transform", (0.0,) * 6)),
                    enabled=node_data.get("enabled", True),
                    visible=node_data.get("visible", True),
                    simulated=node_data.get("simulated", True),
                    tags=set(node_data.get("tags", [])),
                    metadata=node_data.get("metadata", {}),
                )
                self._hierarchy.add_node(node, require_unique=False)
            
            # Restore scene graph
            scene_data = snapshot.get("scene_graph", {})
            for node_data in scene_data.get("nodes", []):
                node = SceneNode(
                    id=node_data["id"],
                    name=node_data["name"],
                    parent_id=node_data.get("parent_id"),
                    local_position=tuple(node_data.get("local_position", (0.0, 0.0, 0.0))),
                    enabled=node_data.get("enabled", True),
                    visible=node_data.get("visible", True),
                    simulated=node_data.get("simulated", True),
                    object_ref=node_data.get("object_ref"),
                    entity_ref=node_data.get("entity_ref"),
                    tags=set(node_data.get("tags", [])),
                    metadata=node_data.get("metadata", {}),
                )
                try:
                    self._scene_graph.add_node(node)
                except DuplicateIdError:
                    pass  # Node already exists
            
            # Restore regions
            regions_data = snapshot.get("regions", {})
            for rid, state_value in regions_data.items():
                state = RegionState(state_value)
                self._region_lifecycle.register_region(rid, state)
            
            self._logger.info(f"Restored world from snapshot: {self._name}")
    
    def clear(self) -> None:
        """Clear all world contents."""
        with self._lock:
            self._hierarchy.clear()
            self._scene_graph.clear()
            self._spatial_partition.clear()
            self._spatial_index.clear()
            self._region_lifecycle.clear()
            self._scenes.clear()
            self._logger.debug("Cleared world")
