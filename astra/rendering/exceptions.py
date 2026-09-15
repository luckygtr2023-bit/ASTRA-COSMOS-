"""ASTRA Rendering - exception hierarchy.

Contract: All rendering errors derive from astra.core.exceptions.AstraError.
Validation errors additionally derive from ValueError for ergonomic catching.
Rendering errors MUST NOT propagate as simulation-state corruption.
"""

from __future__ import annotations

from astra.core.exceptions import AstraError


class RenderError(AstraError):
    """Base rendering-layer error."""


class RenderStateError(RenderError):
    """Raised for invalid render-state operations."""


class CameraError(RenderError, ValueError):
    """Raised for invalid camera parameters."""


class CoordinateConversionError(RenderError, ValueError):
    """Raised for coordinate conversion failures (non-finite, overflow)."""


class VisibilityError(RenderError):
    """Raised for visibility/culling errors."""


class LODError(RenderError, ValueError):
    """Raised for invalid LOD configuration or selection."""


class CelestialRenderError(RenderError):
    """Raised for celestial rendering failures."""


class PlanetaryRenderError(RenderError):
    """Raised for planetary rendering interface failures."""


class LightingError(RenderError, ValueError):
    """Raised for invalid lighting parameters."""


class SpacetimeRenderError(RenderError):
    """Raised for spacetime/black-hole rendering parameter failures."""


class TemporalRenderError(RenderError):
    """Raised for temporal observation rendering failures."""


class PerformanceError(RenderError):
    """Raised for performance-budget violations."""


__all__ = [
    "RenderError",
    "RenderStateError",
    "CameraError",
    "CoordinateConversionError",
    "VisibilityError",
    "LODError",
    "CelestialRenderError",
    "PlanetaryRenderError",
    "LightingError",
    "SpacetimeRenderError",
    "TemporalRenderError",
    "PerformanceError",
]
