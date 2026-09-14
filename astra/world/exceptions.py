"""ASTRA World - exception classes.

Contract: All World-layer errors derive from astra.core.exceptions.AstraError.
Data-validation errors additionally derive from ValueError.
"""

from astra.core.exceptions import AstraError


class WorldError(AstraError):
    """Base World-layer error."""


class SceneError(WorldError):
    """Raised when a scene operation fails."""


class HierarchyError(WorldError):
    """Raised when a hierarchy operation fails (cycle, invalid parent, etc.)."""


class SpatialQueryError(WorldError):
    """Raised when a spatial query fails or returns invalid results."""


class LifecycleError(WorldError):
    """Raised when a lifecycle transition is invalid."""


class InvalidTransformError(WorldError, ValueError):
    """Raised when a transform contains invalid values (NaN/Inf)."""


class DuplicateIdError(WorldError, ValueError):
    """Raised when the same ID is registered twice."""
