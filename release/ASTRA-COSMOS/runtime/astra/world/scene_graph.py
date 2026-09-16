"""ASTRA World - scene graph for spatial transforms.

Contract: Implements a deterministic scene graph with parent-child 
relationships, local/world coordinate transforms, and lifecycle state.
Independent of rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Iterator
import threading
import math

from astra.world.identities import SceneId
from astra.world.exceptions import SceneError, InvalidTransformError, DuplicateIdError
from astra.core.logging import get_logger


def _validate_transform(transform: Tuple[float, float, float]) -> None:
    """Validate that transform values are finite."""
    for i, val in enumerate(transform):
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            raise InvalidTransformError(f"Transform[{i}] must be finite, got {val!r}")


@dataclass
class SceneNode:
    """A node in the scene graph with spatial transform.
    
    This represents the spatial placement of an object in the scene.
    It references authoritative object state but does not own it.
    """

    id: str
    name: str
    parent_id: Optional[str] = None
    
    # Local transform relative to parent (position only for now)
    local_position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    
    # State flags
    enabled: bool = True
    visible: bool = True
    simulated: bool = True
    
    # External references
    object_ref: Optional[str] = None  # Celestial object ID
    entity_ref: Optional[str] = None  # Core entity ID
    
    # Metadata
    tags: set = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Scene node ID must be a non-empty string")
        _validate_transform(self.local_position)

    def set_local_position(self, pos: Tuple[float, float, float]) -> None:
        """Set local position with validation."""
        _validate_transform(pos)
        object.__setattr__(self, "local_position", pos)


class SceneGraph:
    """Deterministic scene graph with transform propagation.
    
    Features:
    - Parent-child relationships
    - Local and world coordinate transforms
    - Hierarchy traversal
    - Object lookup by reference
    - Lifecycle management (activate/deactivate)
    """

    def __init__(self):
        self._nodes: Dict[str, SceneNode] = {}
        self._children: Dict[str, List[str]] = {}  # parent_id -> [child_ids]
        self._object_refs: Dict[str, str] = {}  # object_id -> node_id
        self._entity_refs: Dict[str, str] = {}  # entity_id -> node_id
        self._lock = threading.RLock()
        self._logger = get_logger("scene_graph")

    def add_node(self, node: SceneNode) -> None:
        """Add a node to the scene graph."""
        with self._lock:
            if node.id in self._nodes:
                raise DuplicateIdError(f"Scene node already exists: {node.id}")
            
            self._nodes[node.id] = node
            self._children[node.id] = []
            
            # Set up parent relationship
            if node.parent_id is not None:
                if node.parent_id not in self._nodes:
                    del self._nodes[node.id]
                    del self._children[node.id]
                    raise SceneError(f"Parent node not found: {node.parent_id}")
                self._children[node.parent_id].append(node.id)
            
            # Register references
            if node.object_ref:
                if node.object_ref in self._object_refs:
                    self._logger.warning(
                        f"Object ref {node.object_ref} already registered, "
                        f"overwriting from {self._object_refs[node.object_ref]}"
                    )
                self._object_refs[node.object_ref] = node.id
            
            if node.entity_ref:
                if node.entity_ref in self._entity_refs:
                    self._logger.warning(
                        f"Entity ref {node.entity_ref} already registered, "
                        f"overwriting from {self._entity_refs[node.entity_ref]}"
                    )
                self._entity_refs[node.entity_ref] = node.id
            
            self._logger.debug(f"Added scene node: {node.id}")

    def remove_node(self, node_id: str, cascade: bool = False) -> None:
        """Remove a node from the scene graph."""
        with self._lock:
            if node_id not in self._nodes:
                raise SceneError(f"Scene node not found: {node_id}")
            
            node = self._nodes[node_id]
            
            if cascade:
                # Remove children first
                for child_id in list(self._children.get(node_id, [])):
                    self.remove_node(child_id, cascade=True)
            elif self._children.get(node_id):
                raise SceneError(
                    f"Cannot remove node {node_id} with children. Use cascade=True."
                )
            
            # Remove from parent's children
            if node.parent_id and node.parent_id in self._children:
                if node_id in self._children[node.parent_id]:
                    self._children[node.parent_id].remove(node_id)
            
            # Unregister references
            if node.object_ref and node.object_ref in self._object_refs:
                del self._object_refs[node.object_ref]
            if node.entity_ref and node.entity_ref in self._entity_refs:
                del self._entity_refs[node.entity_ref]
            
            del self._nodes[node_id]
            del self._children[node_id]
            self._logger.debug(f"Removed scene node: {node_id}")

    def get_node(self, node_id: str) -> Optional[SceneNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_node_or_raise(self, node_id: str) -> SceneNode:
        """Get a node by ID or raise an error."""
        node = self._nodes.get(node_id)
        if node is None:
            raise SceneError(f"Scene node not found: {node_id}")
        return node

    def get_node_by_object_ref(self, object_ref: str) -> Optional[SceneNode]:
        """Get a node by its object reference."""
        node_id = self._object_refs.get(object_ref)
        if node_id:
            return self._nodes.get(node_id)
        return None

    def get_node_by_entity_ref(self, entity_ref: str) -> Optional[SceneNode]:
        """Get a node by its entity reference."""
        node_id = self._entity_refs.get(entity_ref)
        if node_id:
            return self._nodes.get(node_id)
        return None

    def get_children(self, node_id: str) -> List[SceneNode]:
        """Get all children of a node."""
        child_ids = self._children.get(node_id, [])
        return [self._nodes[cid] for cid in child_ids if cid in self._nodes]

    def get_parent(self, node_id: str) -> Optional[SceneNode]:
        """Get the parent of a node."""
        node = self.get_node_or_raise(node_id)
        if node.parent_id is None:
            return None
        return self._nodes.get(node.parent_id)

    def get_world_position(self, node_id: str) -> Tuple[float, float, float]:
        """Calculate the world-space position of a node."""
        node = self.get_node_or_raise(node_id)
        
        x, y, z = node.local_position
        
        # Walk up the hierarchy accumulating positions
        current_parent_id = node.parent_id
        while current_parent_id is not None:
            parent = self._nodes.get(current_parent_id)
            if parent is None:
                break
            px, py, pz = parent.local_position
            x += px
            y += py
            z += pz
            current_parent_id = parent.parent_id
        
        return (x, y, z)

    def set_parent(self, node_id: str, parent_id: Optional[str]) -> None:
        """Set the parent of a node."""
        with self._lock:
            if node_id not in self._nodes:
                raise SceneError(f"Scene node not found: {node_id}")
            
            node = self._nodes[node_id]
            old_parent_id = node.parent_id
            
            # Remove from old parent
            if old_parent_id and old_parent_id in self._children:
                if node_id in self._children[old_parent_id]:
                    self._children[old_parent_id].remove(node_id)
            
            # Add to new parent
            node.parent_id = parent_id
            if parent_id is not None:
                if parent_id not in self._nodes:
                    node.parent_id = old_parent_id  # Rollback
                    raise SceneError(f"Parent node not found: {parent_id}")
                self._children[parent_id].append(node_id)
            
            self._logger.debug(f"Set parent of {node_id} to {parent_id}")

    def activate(self, node_id: str) -> None:
        """Activate a node (enable participation)."""
        with self._lock:
            node = self.get_node_or_raise(node_id)
            node.enabled = True
            self._logger.debug(f"Activated scene node: {node_id}")

    def deactivate(self, node_id: str) -> None:
        """Deactivate a node."""
        with self._lock:
            node = self.get_node_or_raise(node_id)
            node.enabled = False
            self._logger.debug(f"Deactivated scene node: {node_id}")

    def set_visibility(self, node_id: str, visible: bool) -> None:
        """Set visibility state."""
        with self._lock:
            node = self.get_node_or_raise(node_id)
            node.visible = visible

    def set_simulated(self, node_id: str, simulated: bool) -> None:
        """Set simulation participation state."""
        with self._lock:
            node = self.get_node_or_raise(node_id)
            node.simulated = simulated

    def traverse_dfs(self, start_id: Optional[str] = None) -> Iterator[SceneNode]:
        """Traverse depth-first."""
        with self._lock:
            if start_id is None:
                # Find root nodes (nodes without parents)
                roots = [nid for nid, n in self._nodes.items() if n.parent_id is None]
            else:
                roots = [start_id]
            
            stack = list(reversed(roots))
            visited = set()
            
            while stack:
                node_id = stack.pop()
                if node_id in visited or node_id not in self._nodes:
                    continue
                
                visited.add(node_id)
                yield self._nodes[node_id]
                
                # Add children in reverse for deterministic order
                for child_id in reversed(self._children.get(node_id, [])):
                    if child_id not in visited:
                        stack.append(child_id)

    def traverse_bfs(self, start_id: Optional[str] = None) -> Iterator[SceneNode]:
        """Traverse breadth-first."""
        with self._lock:
            if start_id is None:
                queue = [nid for nid, n in self._nodes.items() if n.parent_id is None]
            else:
                queue = [start_id]
            
            visited = set()
            
            while queue:
                node_id = queue.pop(0)
                if node_id in visited or node_id not in self._nodes:
                    continue
                
                visited.add(node_id)
                yield self._nodes[node_id]
                
                for child_id in self._children.get(node_id, []):
                    if child_id not in visited:
                        queue.append(child_id)

    def get_all_nodes(self) -> Dict[str, SceneNode]:
        """Get all nodes."""
        with self._lock:
            return dict(self._nodes)

    def get_node_count(self) -> int:
        """Get node count."""
        with self._lock:
            return len(self._nodes)

    def clear(self) -> None:
        """Clear all nodes."""
        with self._lock:
            self._nodes.clear()
            self._children.clear()
            self._object_refs.clear()
            self._entity_refs.clear()
            self._logger.debug("Cleared scene graph")
