"""ASTRA World - hierarchical world structure.

Contract: Implements a strict DAG hierarchy for world organization.
Supports arbitrary depth, cycle detection, and deterministic traversal.
References celestial objects without duplicating their identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Iterator
import threading

from astra.world.identities import WorldId, SceneId, RegionId
from astra.world.exceptions import HierarchyError, DuplicateIdError
from astra.core.logging import get_logger


@dataclass
class WorldNode:
    """A node in the world hierarchy.
    
    This is a structural node that may reference external objects (celestial
    bodies, spacecraft, etc.) but does not duplicate their authoritative state.
    """

    id: str
    name: str
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    
    # External references (not owned by World)
    object_ref: Optional[str] = None  # Reference to celestial object ID
    entity_ref: Optional[str] = None  # Reference to core entity ID
    
    # Spatial placement
    local_transform: Tuple[float, float, float, float, float, float] = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)  # (x,y,z, rx,ry,rz)
    
    # State
    enabled: bool = True
    visible: bool = True
    simulated: bool = True
    
    # Metadata
    tags: set = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Node ID must be a non-empty string")
        if not self.name or not isinstance(self.name, str):
            raise ValueError("Node name must be a non-empty string")

    def set_local_transform(self, transform: Tuple[float, float, float, float, float, float]):
        """Set the local transform with validation."""
        from astra.mathematics.validation import validate_finite
        for i, val in enumerate(transform):
            try:
                validate_finite(val, f"transform[{i}]")
            except (ValueError, TypeError) as e:
                from astra.world.exceptions import InvalidTransformError
                raise InvalidTransformError(f"Invalid transform value at index {i}: {val}") from e
        object.__setattr__(self, "local_transform", transform)


class WorldHierarchy:
    """Manages the world hierarchy as a strict DAG.
    
    Features:
    - Cycle detection on parent assignment
    - Duplicate ID prevention
    - Deterministic traversal order
    - Parent-child relationship management
    """

    def __init__(self):
        self._nodes: Dict[str, WorldNode] = {}
        self._root_nodes: List[str] = []
        self._lock = threading.RLock()
        self._logger = get_logger("world_hierarchy")

    def _validate_no_cycle(self, node_id: str, new_parent_id: Optional[str]) -> None:
        """Validate that setting new_parent_id would not create a cycle."""
        if new_parent_id is None:
            return
        
        if new_parent_id not in self._nodes:
            raise HierarchyError(f"Parent node not found: {new_parent_id}")
        
        if new_parent_id == node_id:
            raise HierarchyError(f"Node cannot be its own parent: {node_id}")
        
        # Check if new_parent is a descendant of node (which would create a cycle)
        visited = set()
        stack = [new_parent_id]
        while stack:
            current = stack.pop()
            if current == node_id:
                raise HierarchyError(
                    f"Setting parent to {new_parent_id} would create a cycle "
                    f"(node {node_id} is an ancestor of {new_parent_id})"
                )
            if current in visited:
                continue
            visited.add(current)
            if current in self._nodes:
                stack.extend(self._nodes[current].children)

    def add_node(self, node: WorldNode, require_unique: bool = True) -> None:
        """Add a node to the hierarchy."""
        with self._lock:
            if node.id in self._nodes:
                if require_unique:
                    raise DuplicateIdError(f"Node already exists: {node.id}")
                return
            
            self._nodes[node.id] = node
            
            if node.parent_id is None:
                if node.id not in self._root_nodes:
                    self._root_nodes.append(node.id)
            else:
                self._validate_no_cycle(node.id, node.parent_id)
                parent = self._nodes.get(node.parent_id)
                if parent is None:
                    raise HierarchyError(f"Parent node not found: {node.parent_id}")
                if node.id not in parent.children:
                    parent.children.append(node.id)
            
            self._logger.debug(f"Added node to hierarchy: {node.id}")

    def remove_node(self, node_id: str, cascade: bool = False) -> None:
        """Remove a node from the hierarchy."""
        with self._lock:
            if node_id not in self._nodes:
                raise HierarchyError(f"Node not found: {node_id}")
            
            node = self._nodes[node_id]
            
            if cascade:
                # Remove all descendants first
                for child_id in list(node.children):
                    self.remove_node(child_id, cascade=True)
            elif node.children:
                raise HierarchyError(
                    f"Cannot remove node {node_id} with children. Use cascade=True."
                )
            
            # Remove from parent's children
            if node.parent_id and node.parent_id in self._nodes:
                parent = self._nodes[node.parent_id]
                if node_id in parent.children:
                    parent.children.remove(node_id)
            
            # Remove from root list if applicable
            if node_id in self._root_nodes:
                self._root_nodes.remove(node_id)
            
            del self._nodes[node_id]
            self._logger.debug(f"Removed node from hierarchy: {node_id}")

    def set_parent(self, node_id: str, parent_id: Optional[str]) -> None:
        """Set the parent of a node."""
        with self._lock:
            if node_id not in self._nodes:
                raise HierarchyError(f"Node not found: {node_id}")
            
            node = self._nodes[node_id]
            old_parent_id = node.parent_id
            
            # Validate no cycle
            self._validate_no_cycle(node_id, parent_id)
            
            # Remove from old parent
            if old_parent_id and old_parent_id in self._nodes:
                old_parent = self._nodes[old_parent_id]
                if node_id in old_parent.children:
                    old_parent.children.remove(node_id)
            
            # Add to new parent
            node.parent_id = parent_id
            if parent_id is None:
                if node_id not in self._root_nodes:
                    self._root_nodes.append(node_id)
            else:
                if node_id in self._root_nodes:
                    self._root_nodes.remove(node_id)
                parent = self._nodes[parent_id]
                if node_id not in parent.children:
                    parent.children.append(node_id)
            
            self._logger.debug(f"Set parent of {node_id} to {parent_id}")

    def get_node(self, node_id: str) -> Optional[WorldNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_node_or_raise(self, node_id: str) -> WorldNode:
        """Get a node by ID or raise an error."""
        node = self._nodes.get(node_id)
        if node is None:
            raise HierarchyError(f"Node not found: {node_id}")
        return node

    def get_children(self, node_id: str) -> List[WorldNode]:
        """Get all children of a node."""
        node = self.get_node_or_raise(node_id)
        return [self._nodes[cid] for cid in node.children if cid in self._nodes]

    def get_parent(self, node_id: str) -> Optional[WorldNode]:
        """Get the parent of a node."""
        node = self.get_node_or_raise(node_id)
        if node.parent_id is None:
            return None
        return self._nodes.get(node.parent_id)

    def get_root_nodes(self) -> List[WorldNode]:
        """Get all root nodes."""
        return [self._nodes[nid] for nid in self._root_nodes if nid in self._nodes]

    def traverse_dfs(self, start_id: Optional[str] = None) -> Iterator[WorldNode]:
        """Traverse the hierarchy depth-first."""
        with self._lock:
            if start_id is None:
                roots = list(self._root_nodes)
            else:
                roots = [start_id]
            
            stack = list(reversed(roots))
            visited = set()
            
            while stack:
                node_id = stack.pop()
                if node_id in visited:
                    continue
                if node_id not in self._nodes:
                    continue
                    
                visited.add(node_id)
                yield self._nodes[node_id]
                
                # Add children in reverse for deterministic order
                node = self._nodes[node_id]
                for child_id in reversed(node.children):
                    if child_id not in visited:
                        stack.append(child_id)

    def traverse_bfs(self, start_id: Optional[str] = None) -> Iterator[WorldNode]:
        """Traverse the hierarchy breadth-first."""
        with self._lock:
            if start_id is None:
                queue = list(self._root_nodes)
            else:
                queue = [start_id]
            
            visited = set()
            
            while queue:
                node_id = queue.pop(0)
                if node_id in visited:
                    continue
                if node_id not in self._nodes:
                    continue
                
                visited.add(node_id)
                yield self._nodes[node_id]
                
                node = self._nodes[node_id]
                for child_id in node.children:
                    if child_id not in visited:
                        queue.append(child_id)

    def get_all_nodes(self) -> Dict[str, WorldNode]:
        """Get all nodes."""
        with self._lock:
            return dict(self._nodes)

    def get_node_count(self) -> int:
        """Get the number of nodes."""
        with self._lock:
            return len(self._nodes)

    def clear(self) -> None:
        """Clear all nodes."""
        with self._lock:
            self._nodes.clear()
            self._root_nodes.clear()
            self._logger.debug("Cleared hierarchy")
