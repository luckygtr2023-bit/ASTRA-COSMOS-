"""ASTRA Rendering - planetary rendering architecture.

Provides renderer-independent interfaces for:
- planetary bodies (radius, rotation, surface)
- terrain
- atmosphere
- ocean
- clouds
- lighting / shadows (delegates to lighting module for implementation)

Detailed VFX is out of scope; these are parameter containers and
render-object enrichments that a future Graphics/VFX layer can consume.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from astra.mathematics import Vector3, Quaternion

from astra.rendering.exceptions import PlanetaryRenderError
from astra.rendering.render_state import RenderObject, MaterialRef
from astra.rendering.types import RenderObjectKind


def _finite(name: str, v, low=None, high=None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise PlanetaryRenderError(f"{name} must be numeric, got {type(v).__name__}")
    f = float(v)
    if math.isnan(f) or math.isinf(f):
        raise PlanetaryRenderError(f"{name} must be finite, got {v!r}")
    if low is not None and f < low:
        raise PlanetaryRenderError(f"{name} must be >= {low}, got {f}")
    if high is not None and f > high:
        raise PlanetaryRenderError(f"{name} must be <= {high}, got {f}")
    return f


def _require_vector(v: Vector3, name: str) -> Vector3:
    if not isinstance(v, Vector3):
        raise PlanetaryRenderError(f"{name} must be Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise PlanetaryRenderError(f"{name} must be finite, got {v!r}")
    return v


@dataclass
class TerrainDescriptor:
    """Renderer-independent terrain interface.

    Future Graphics/VFX will interpret height_map_ref / material to produce
    displacement, but this layer only exposes parameters.
    """

    enabled: bool = True
    height_scale_m: float = 1000.0
    base_radius_m: float = 6371000.0
    height_map_ref: Optional[str] = None  # resource handle hint
    detail_level: int = 1  # 0=low .. 4=ultra
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="terrain_default", kind="terrain_placeholder"))
    lod_bias: float = 1.0

    def __post_init__(self) -> None:
        self.height_scale_m = _finite("height_scale_m", self.height_scale_m, low=0.0)
        self.base_radius_m = _finite("base_radius_m", self.base_radius_m, low=1.0)
        if not isinstance(self.detail_level, int) or not 0 <= self.detail_level <= 8:
            raise PlanetaryRenderError(f"detail_level must be int 0..8, got {self.detail_level!r}")
        self.lod_bias = _finite("lod_bias", self.lod_bias, low=1e-6, high=1e6)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "height_scale_m": self.height_scale_m,
            "base_radius_m": self.base_radius_m,
            "height_map_ref": self.height_map_ref,
            "detail_level": self.detail_level,
            "lod_bias": self.lod_bias,
        }


@dataclass
class AtmosphereDescriptor:
    """Renderer-independent atmosphere interface."""

    enabled: bool = True
    height_m: float = 100000.0  # ~100 km for Earth-like
    rayleigh_scale_height_m: float = 8000.0
    mie_scale_height_m: float = 1200.0
    rayleigh_scattering: Tuple[float, float, float] = (5.8e-6, 13.5e-6, 33.1e-6)
    mie_scattering: float = 21e-6
    mie_anisotropy: float = 0.76
    density_falloff: float = 1.0
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="atmosphere_default", kind="atmosphere_placeholder"))

    def __post_init__(self) -> None:
        self.height_m = _finite("height_m", self.height_m, low=0.0)
        self.rayleigh_scale_height_m = _finite("rayleigh_scale_height_m", self.rayleigh_scale_height_m, low=1.0)
        self.mie_scale_height_m = _finite("mie_scale_height_m", self.mie_scale_height_m, low=1.0)
        self.mie_scattering = _finite("mie_scattering", self.mie_scattering, low=0.0)
        self.mie_anisotropy = _finite("mie_anisotropy", self.mie_anisotropy, low=-1.0, high=1.0)
        self.density_falloff = _finite("density_falloff", self.density_falloff, low=1e-6, high=1e6)
        if len(self.rayleigh_scattering) != 3:
            raise PlanetaryRenderError("rayleigh_scattering must be 3-tuple")
        for i, v in enumerate(self.rayleigh_scattering):
            _finite(f"rayleigh_scattering[{i}]", v, low=0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "height_m": self.height_m,
            "rayleigh_scale_height_m": self.rayleigh_scale_height_m,
            "mie_scale_height_m": self.mie_scale_height_m,
            "rayleigh_scattering": self.rayleigh_scattering,
            "mie_scattering": self.mie_scattering,
            "mie_anisotropy": self.mie_anisotropy,
            "density_falloff": self.density_falloff,
        }


@dataclass
class OceanDescriptor:
    """Renderer-independent ocean interface."""

    enabled: bool = True
    sea_level_m: float = 0.0
    wave_height_m: float = 2.0
    wave_choppiness: float = 1.0
    depth_m: float = 4000.0
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="ocean_default", kind="ocean_placeholder"))
    # normal map / displacement hints for future VFX
    normal_map_ref: Optional[str] = None

    def __post_init__(self) -> None:
        self.sea_level_m = _finite("sea_level_m", self.sea_level_m, low=-1e6, high=1e6)
        self.wave_height_m = _finite("wave_height_m", self.wave_height_m, low=0.0)
        self.wave_choppiness = _finite("wave_choppiness", self.wave_choppiness, low=0.0, high=10.0)
        self.depth_m = _finite("depth_m", self.depth_m, low=0.0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "sea_level_m": self.sea_level_m,
            "wave_height_m": self.wave_height_m,
            "wave_choppiness": self.wave_choppiness,
            "depth_m": self.depth_m,
            "normal_map_ref": self.normal_map_ref,
        }


@dataclass
class CloudDescriptor:
    enabled: bool = True
    coverage: float = 0.5  # 0..1
    thickness_m: float = 2000.0
    altitude_m: float = 5000.0
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="cloud_default", kind="cloud_placeholder"))

    def __post_init__(self) -> None:
        self.coverage = _finite("coverage", self.coverage, low=0.0, high=1.0)
        self.thickness_m = _finite("thickness_m", self.thickness_m, low=0.0)
        self.altitude_m = _finite("altitude_m", self.altitude_m, low=0.0)


@dataclass
class PlanetarySurfaceDescriptor:
    """Aggregates surface-adjacent render interfaces."""

    terrain: Optional[TerrainDescriptor] = None
    atmosphere: Optional[AtmosphereDescriptor] = None
    ocean: Optional[OceanDescriptor] = None
    clouds: Optional[CloudDescriptor] = None

    # rotation state for rendering (derived from motion/orbital)
    axial_tilt_rad: float = 0.0
    rotation_period_s: Optional[float] = None  # None = tidally locked / unknown
    prime_meridian_rad: float = 0.0

    def __post_init__(self) -> None:
        self.axial_tilt_rad = _finite("axial_tilt_rad", self.axial_tilt_rad, low=-math.pi, high=math.pi)
        self.prime_meridian_rad = _finite("prime_meridian_rad", self.prime_meridian_rad, low=-2*math.pi, high=2*math.pi)
        if self.rotation_period_s is not None:
            self.rotation_period_s = _finite("rotation_period_s", self.rotation_period_s, low=1e-9)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "terrain": self.terrain.to_dict() if self.terrain else None,
            "atmosphere": self.atmosphere.to_dict() if self.atmosphere else None,
            "ocean": self.ocean.to_dict() if self.ocean else None,
            "clouds": {"coverage": self.clouds.coverage} if self.clouds else None,
            "axial_tilt_rad": self.axial_tilt_rad,
            "rotation_period_s": self.rotation_period_s,
        }


@dataclass
class PlanetaryRenderDescriptor:
    """High-level planetary body render description.

    Wraps a RenderObject with planetary-specific visual data.
    """

    base: RenderObject
    radius_m: float = 6371000.0
    surface: PlanetarySurfaceDescriptor = field(default_factory=PlanetarySurfaceDescriptor)
    axial_tilt_rad: float = 0.0
    receives_shadow: bool = True

    def __post_init__(self) -> None:
        self.radius_m = _finite("radius_m", self.radius_m, low=1.0)
        if not isinstance(self.base, RenderObject):
            raise PlanetaryRenderError("base must be RenderObject")
        if self.base.kind not in (RenderObjectKind.PLANET, RenderObjectKind.MOON, RenderObjectKind.DWARF_PLANET):
            # Allow unknown for generic planetary body but warn via kind check permissive
            pass
        self.axial_tilt_rad = _finite("axial_tilt_rad", self.axial_tilt_rad, low=-math.pi, high=math.pi)

    def enrich_base(self) -> RenderObject:
        """Return base RenderObject enriched with planetary params for pipeline consumption."""
        base = self.base.clone()
        base.bounding_radius_m = self.radius_m
        base.terrain_params = self.surface.terrain.to_dict() if self.surface.terrain else None
        base.atmosphere_params = self.surface.atmosphere.to_dict() if self.surface.atmosphere else None
        base.ocean_params = self.surface.ocean.to_dict() if self.surface.ocean else None
        base.metadata = dict(base.metadata)
        base.metadata.update({
            "radius_m": self.radius_m,
            "axial_tilt_rad": self.axial_tilt_rad,
            "has_terrain": self.surface.terrain is not None and self.surface.terrain.enabled,
            "has_atmosphere": self.surface.atmosphere is not None and self.surface.atmosphere.enabled,
            "has_ocean": self.surface.ocean is not None and self.surface.ocean.enabled,
            "has_clouds": self.surface.clouds is not None and self.surface.clouds.enabled,
            "receives_shadow": self.receives_shadow,
        })
        # Store full surface dict for Blender bridge
        base.metadata["surface"] = self.surface.to_dict()
        return base

    @classmethod
    def from_celestial(
        cls,
        celestial_obj,
        world_position: Vector3,
        radius_m: Optional[float] = None,
        render_origin: Optional[Vector3] = None,
        terrain: Optional[TerrainDescriptor] = None,
        atmosphere: Optional[AtmosphereDescriptor] = None,
        ocean: Optional[OceanDescriptor] = None,
        clouds: Optional[CloudDescriptor] = None,
    ) -> "PlanetaryRenderDescriptor":
        from astra.rendering.celestial import celestial_to_render_object
        base = celestial_to_render_object(celestial_obj, world_position, render_origin=render_origin)
        # Override radius if supplied
        rad = radius_m
        if rad is None:
            rad = base.bounding_radius_m
        surface = PlanetarySurfaceDescriptor(terrain=terrain, atmosphere=atmosphere, ocean=ocean, clouds=clouds)
        return cls(base=base, radius_m=float(rad), surface=surface)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base": self.base.to_dict(),
            "radius_m": self.radius_m,
            "surface": self.surface.to_dict(),
        }
