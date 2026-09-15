"""ASTRA Rendering - shared types and enums.

Pure data definitions with no I/O, no wall-clock, deterministic.
All enums are string-backed for serialization stability.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple


class ProjectionType(str, Enum):
    PERSPECTIVE = "PERSPECTIVE"
    ORTHOGRAPHIC = "ORTHOGRAPHIC"


class QualityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ULTRA = "ULTRA"
    AUTO = "AUTO"


class LODLevel(str, Enum):
    ULTRA = "ULTRA"          # full detail
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    IMPOSTOR = "IMPOSTOR"    # billboard / point
    CULLED = "CULLED"        # not rendered


class VisibilityState(str, Enum):
    VISIBLE = "VISIBLE"
    HIDDEN = "HIDDEN"
    CULLED_FRUSTUM = "CULLED_FRUSTUM"
    CULLED_DISTANCE = "CULLED_DISTANCE"
    CULLED_CATEGORY = "CULLED_CATEGORY"
    DISABLED = "DISABLED"


class TemporalRenderMode(str, Enum):
    CURRENT = "CURRENT"                  # authoritative present
    OBSERVED = "OBSERVED"                # light-delay corrected
    HISTORICAL = "HISTORICAL"            # explicit past emission


class DamageVisualState(str, Enum):
    INTACT = "INTACT"
    DAMAGED = "DAMAGED"
    FRACTURED = "FRACTURED"
    FRAGMENTED = "FRAGMENTED"
    DESTROYED = "DESTROYED"


class LightType(str, Enum):
    DIRECTIONAL = "DIRECTIONAL"   # e.g. star at effectively infinite distance
    POINT = "POINT"               # local point source
    AMBIENT = "AMBIENT"           # uniform


class RenderObjectKind(str, Enum):
    """Coarse render classification (renderer-independent)."""

    UNKNOWN = "UNKNOWN"
    STAR = "STAR"
    PLANET = "PLANET"
    MOON = "MOON"
    DWARF_PLANET = "DWARF_PLANET"
    ASTEROID = "ASTEROID"
    COMET = "COMET"
    SPACECRAFT = "SPACECRAFT"
    STATION = "STATION"
    DEBRIS = "DEBRIS"
    GALAXY = "GALAXY"
    NEBULA = "NEBULA"
    STAR_CLUSTER = "STAR_CLUSTER"
    BLACK_HOLE = "BLACK_HOLE"
    WORMHOLE = "WORMHOLE"
    WARP_BUBBLE = "WARP_BUBBLE"
    TERRAIN_PATCH = "TERRAIN_PATCH"
    ATMOSPHERE = "ATMOSPHERE"
    OCEAN = "OCEAN"
    FRAGMENT = "FRAGMENT"
    EJECTA = "EJECTA"


@dataclass(frozen=True)
class Viewport:
    """Renderer-independent viewport description (pixels)."""

    x: int = 0
    y: int = 0
    width: int = 1920
    height: int = 1080

    def __post_init__(self) -> None:
        if not isinstance(self.width, int) or not isinstance(self.height, int):
            raise ValueError("Viewport dimensions must be integers")
        if self.width <= 0 or self.height <= 0:
            raise ValueError(f"Viewport dimensions must be positive, got {self.width}x{self.height}")
        if self.width > 16384 or self.height > 16384:
            raise ValueError(f"Viewport dimensions excessive: {self.width}x{self.height}")

    @property
    def aspect(self) -> float:
        return self.width / float(self.height)


# Quality presets for performance scaling
QUALITY_PRESETS = {
    QualityLevel.LOW:    {"max_visible": 1000, "lod_bias": 1.5, "shadow": False},
    QualityLevel.MEDIUM: {"max_visible": 5000, "lod_bias": 1.0, "shadow": True},
    QualityLevel.HIGH:   {"max_visible": 20000, "lod_bias": 0.75, "shadow": True},
    QualityLevel.ULTRA:  {"max_visible": 100000, "lod_bias": 0.5, "shadow": True},
    QualityLevel.AUTO:   {"max_visible": 5000, "lod_bias": 1.0, "shadow": True},
}

LOD_ORDER = {
    LODLevel.ULTRA: 0,
    LODLevel.HIGH: 1,
    LODLevel.MEDIUM: 2,
    LODLevel.LOW: 3,
    LODLevel.IMPOSTOR: 4,
    LODLevel.CULLED: 5,
}


def lod_more_detailed(a: LODLevel, b: LODLevel) -> bool:
    return LOD_ORDER[a] < LOD_ORDER[b]


__all__ = [
    "ProjectionType",
    "QualityLevel",
    "LODLevel",
    "VisibilityState",
    "TemporalRenderMode",
    "DamageVisualState",
    "LightType",
    "RenderObjectKind",
    "Viewport",
    "QUALITY_PRESETS",
    "LOD_ORDER",
    "lod_more_detailed",
]
