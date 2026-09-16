"""ASTRA World - hierarchical world and scene management.

Contract: The World system provides the authoritative spatial/scene 
organization layer connecting astronomical objects, spacecraft, simulations,
and datasets. It is NOT the physics engine, celestial-object database, 
renderer, or Gaia ingestion pipeline.

This module exports the main World API.
"""

from astra.world.exceptions import (
    WorldError,
    SceneError,
    HierarchyError,
    SpatialQueryError,
    LifecycleError,
    InvalidTransformError,
    DuplicateIdError,
)
from astra.world.identities import (
    WorldId,
    SceneId,
    RegionId,
)
from astra.world.hierarchy import (
    WorldNode,
    WorldHierarchy,
)
from astra.world.scene_graph import (
    SceneNode,
    SceneGraph,
)
from astra.world.spatial import (
    SpatialRegion,
    SpatialPartition,
    SpatialIndex,
)
from astra.world.region import (
    WorldRegion,
    RegionState,
    RegionLifecycle,
)
from astra.world.world import (
    World,
    WorldState,
)

__all__ = [
    # Exceptions
    "WorldError",
    "SceneError",
    "HierarchyError",
    "SpatialQueryError",
    "LifecycleError",
    "InvalidTransformError",
    "DuplicateIdError",
    # Identities
    "WorldId",
    "SceneId",
    "RegionId",
    # Hierarchy
    "WorldNode",
    "WorldHierarchy",
    # Scene Graph
    "SceneNode",
    "SceneGraph",
    # Spatial
    "SpatialRegion",
    "SpatialPartition",
    "SpatialIndex",
    # Region
    "WorldRegion",
    "RegionState",
    "RegionLifecycle",
    # World
    "World",
    "WorldState",
]
