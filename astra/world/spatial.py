"""ASTRA World - spatial partitioning and queries.

Contract: Provides scalable spatial organization for efficient queries.
Uses existing ASTRA coordinate architecture without creating competing systems.
Supports hierarchical spatial partitioning appropriate for universe-scale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Iterator, Set
import threading
import math

from astra.world.exceptions import SpatialQueryError
from astra.core.logging import get_logger
from astra.core.coords import FrameRegistry, CoordinateFrame


@dataclass
class BoundingBox:
    """Axis-aligned bounding box."""
    
    min_corner: Tuple[float, float, float]
    max_corner: Tuple[float, float, float]
    
    def contains_point(self, point: Tuple[float, float, float]) -> bool:
        """Check if a point is inside the box."""
        x, y, z = point
        xmin, ymin, zmin = self.min_corner
        xmax, ymax, zmax = self.max_corner
        return (xmin <= x <= xmax and ymin <= y <= ymax and zmin <= z <= zmax)
    
    def intersects(self, other: "BoundingBox") -> bool:
        """Check if this box intersects another."""
        # No overlap if one box is completely to one side of the other
        if self.max_corner[0] < other.min_corner[0]:
            return False
        if self.min_corner[0] > other.max_corner[0]:
            return False
        if self.max_corner[1] < other.min_corner[1]:
            return False
        if self.min_corner[1] > other.max_corner[1]:
            return False
        if self.max_corner[2] < other.min_corner[2]:
            return False
        if self.min_corner[2] > other.max_corner[2]:
            return False
        return True
    
    def get_center(self) -> Tuple[float, float, float]:
        """Get the center of the box."""
        return tuple(
            (a + b) / 2.0 
            for a, b in zip(self.min_corner, self.max_corner)
        )
    
    def get_size(self) -> Tuple[float, float, float]:
        """Get the size of the box."""
        return tuple(
            b - a for a, b in zip(self.min_corner, self.max_corner)
        )


@dataclass
class SpatialRegion:
    """A spatial region containing objects."""
    
    id: str
    name: str
    bounds: BoundingBox
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    object_ids: Set[str] = field(default_factory=set)
    
    # State
    enabled: bool = True
    loaded: bool = True  # For streaming support
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class SpatialPartition:
    """Hierarchical spatial partition for universe-scale organization.
    
    Supports:
    - Nested regions (hierarchical)
    - Object membership tracking
    - Region queries
    """
    
    def __init__(self):
        self._regions: Dict[str, SpatialRegion] = {}
        self._root_regions: List[str] = []
        self._object_to_region: Dict[str, Set[str]] = {}  # object_id -> set of region_ids
        self._lock = threading.RLock()
        self._logger = get_logger("spatial_partition")
    
    def add_region(self, region: SpatialRegion) -> None:
        """Add a spatial region."""
        with self._lock:
            if region.id in self._regions:
                raise SpatialQueryError(f"Region already exists: {region.id}")
            
            self._regions[region.id] = region
            
            if region.parent_id is None:
                self._root_regions.append(region.id)
            else:
                if region.parent_id not in self._regions:
                    del self._regions[region.id]
                    raise SpatialQueryError(f"Parent region not found: {region.parent_id}")
                parent = self._regions[region.parent_id]
                parent.children.append(region.id)
            
            self._logger.debug(f"Added spatial region: {region.id}")
    
    def remove_region(self, region_id: str, cascade: bool = False) -> None:
        """Remove a spatial region."""
        with self._lock:
            if region_id not in self._regions:
                raise SpatialQueryError(f"Region not found: {region_id}")
            
            region = self._regions[region_id]
            
            if cascade:
                for child_id in list(region.children):
                    self.remove_region(child_id, cascade=True)
            elif region.children:
                raise SpatialQueryError(
                    f"Cannot remove region {region_id} with children. Use cascade=True."
                )
            
            # Remove from parent
            if region.parent_id and region.parent_id in self._regions:
                parent = self._regions[region.parent_id]
                if region_id in parent.children:
                    parent.children.remove(region_id)
            
            # Remove from root list
            if region_id in self._root_regions:
                self._root_regions.remove(region_id)
            
            # Clean up object mappings
            for obj_id in region.object_ids:
                if obj_id in self._object_to_region:
                    self._object_to_region[obj_id].discard(region_id)
            
            del self._regions[region_id]
            self._logger.debug(f"Removed spatial region: {region_id}")
    
    def add_object_to_region(self, object_id: str, region_id: str) -> None:
        """Add an object to a region."""
        with self._lock:
            if region_id not in self._regions:
                raise SpatialQueryError(f"Region not found: {region_id}")
            
            region = self._regions[region_id]
            region.object_ids.add(object_id)
            
            if object_id not in self._object_to_region:
                self._object_to_region[object_id] = set()
            self._object_to_region[object_id].add(region_id)
    
    def remove_object_from_region(self, object_id: str, region_id: str) -> None:
        """Remove an object from a region."""
        with self._lock:
            if region_id not in self._regions:
                raise SpatialQueryError(f"Region not found: {region_id}")
            
            region = self._regions[region_id]
            region.object_ids.discard(object_id)
            
            if object_id in self._object_to_region:
                self._object_to_region[object_id].discard(region_id)
    
    def get_region(self, region_id: str) -> Optional[SpatialRegion]:
        """Get a region by ID."""
        return self._regions.get(region_id)
    
    def get_regions_for_object(self, object_id: str) -> Set[str]:
        """Get all regions containing an object."""
        return self._object_to_region.get(object_id, set()).copy()
    
    def query_point(self, point: Tuple[float, float, float]) -> List[SpatialRegion]:
        """Find all regions containing a point."""
        result = []
        with self._lock:
            for region in self._regions.values():
                if region.enabled and region.bounds.contains_point(point):
                    result.append(region)
        return result
    
    def query_box(self, box: BoundingBox) -> List[SpatialRegion]:
        """Find all regions intersecting a bounding box."""
        result = []
        with self._lock:
            for region in self._regions.values():
                if region.enabled and region.bounds.intersects(box):
                    result.append(region)
        return result
    
    def query_radius(
        self, 
        center: Tuple[float, float, float], 
        radius: float
    ) -> List[SpatialRegion]:
        """Find all regions within a radius of a point."""
        # Create a bounding box for the sphere
        box = BoundingBox(
            min_corner=tuple(c - radius for c in center),
            max_corner=tuple(c + radius for c in center),
        )
        return self.query_box(box)
    
    def get_objects_in_region(self, region_id: str) -> Set[str]:
        """Get all objects in a region."""
        with self._lock:
            region = self._regions.get(region_id)
            if region is None:
                raise SpatialQueryError(f"Region not found: {region_id}")
            return region.object_ids.copy()
    
    def get_all_regions(self) -> Dict[str, SpatialRegion]:
        """Get all regions."""
        with self._lock:
            return dict(self._regions)
    
    def clear(self) -> None:
        """Clear all regions."""
        with self._lock:
            self._regions.clear()
            self._root_regions.clear()
            self._object_to_region.clear()
            self._logger.debug("Cleared spatial partition")


class SpatialIndex:
    """Spatial index for efficient nearest-object and range queries.
    
    This is a simple implementation that can be extended with more
    sophisticated structures (octree, k-d tree, BVH) as needed.
    """
    
    def __init__(self):
        self._objects: Dict[str, Tuple[float, float, float]] = {}  # object_id -> position
        self._lock = threading.RLock()
        self._logger = get_logger("spatial_index")
    
    def insert(self, object_id: str, position: Tuple[float, float, float]) -> None:
        """Insert an object at a position."""
        with self._lock:
            self._objects[object_id] = position
    
    def remove(self, object_id: str) -> None:
        """Remove an object."""
        with self._lock:
            self._objects.pop(object_id, None)
    
    def update_position(self, object_id: str, position: Tuple[float, float, float]) -> None:
        """Update an object's position."""
        with self._lock:
            if object_id not in self._objects:
                raise SpatialQueryError(f"Object not found in index: {object_id}")
            self._objects[object_id] = position
    
    def nearest(
        self, 
        point: Tuple[float, float, float], 
        k: int = 1
    ) -> List[Tuple[str, float]]:
        """Find k nearest objects to a point.
        
        Returns list of (object_id, distance) tuples.
        """
        with self._lock:
            if not self._objects:
                return []
            
            # Calculate distances
            distances = []
            for obj_id, pos in self._objects.items():
                dx = pos[0] - point[0]
                dy = pos[1] - point[1]
                dz = pos[2] - point[2]
                dist_sq = dx * dx + dy * dy + dz * dz
                distances.append((obj_id, math.sqrt(dist_sq)))
            
            # Sort by distance
            distances.sort(key=lambda x: x[1])
            
            return distances[:k]
    
    def within_radius(
        self, 
        center: Tuple[float, float, float], 
        radius: float
    ) -> List[str]:
        """Find all objects within a radius of a point."""
        radius_sq = radius * radius
        result = []
        
        with self._lock:
            for obj_id, pos in self._objects.items():
                dx = pos[0] - center[0]
                dy = pos[1] - center[1]
                dz = pos[2] - center[2]
                dist_sq = dx * dx + dy * dy + dz * dz
                
                if dist_sq <= radius_sq:
                    result.append(obj_id)
        
        return result
    
    def within_box(self, box: BoundingBox) -> List[str]:
        """Find all objects within a bounding box."""
        result = []
        
        with self._lock:
            for obj_id, pos in self._objects.items():
                if box.contains_point(pos):
                    result.append(obj_id)
        
        return result
    
    def get_all_objects(self) -> Dict[str, Tuple[float, float, float]]:
        """Get all indexed objects."""
        with self._lock:
            return dict(self._objects)
    
    def get_object_count(self) -> int:
        """Get the number of indexed objects."""
        with self._lock:
            return len(self._objects)
    
    def clear(self) -> None:
        """Clear the index."""
        with self._lock:
            self._objects.clear()
            self._logger.debug("Cleared spatial index")
