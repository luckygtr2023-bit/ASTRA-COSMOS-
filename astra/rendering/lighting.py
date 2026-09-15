"""ASTRA Rendering - lighting and shadow architecture.

Renderer-independent abstractions; no shader code.
Supports celestial lighting (star as directional/point), planetary
lighting, shadows, and eclipses as data for future Graphics/VFX.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from astra.mathematics import Vector3
from astra.rendering.exceptions import LightingError
from astra.rendering.types import LightType


def _finite(name: str, v, low=None, high=None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise LightingError(f"{name} must be numeric, got {type(v).__name__}")
    f = float(v)
    if math.isnan(f) or math.isinf(f):
        raise LightingError(f"{name} must be finite, got {v!r}")
    if low is not None and f < low:
        raise LightingError(f"{name} must be >= {low}, got {f}")
    if high is not None and f > high:
        raise LightingError(f"{name} must be <= {high}, got {f}")
    return f


def _require_vector(v: Vector3, name: str) -> Vector3:
    if not isinstance(v, Vector3):
        raise LightingError(f"{name} must be Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise LightingError(f"{name} must be finite, got {v!r}")
    return v


@dataclass
class LightSource:
    """Renderer-independent light."""

    id: str
    type: LightType = LightType.DIRECTIONAL
    position: Optional[Vector3] = None  # for POINT; None => directional/ambient
    direction: Optional[Vector3] = None  # for DIRECTIONAL (unit, points FROM source TOWARD scene)
    intensity: float = 1.0  # linear, arbitrary renderer units (exposure handled by VFX)
    color: Tuple[float, float, float] = (1.0, 1.0, 1.0)  # linear RGB
    range_m: Optional[float] = None  # for POINT
    casts_shadow: bool = False
    source_ref: Optional[str] = None  # e.g. celestial star id

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise LightingError("LightSource.id must be non-empty string")
        if not isinstance(self.type, LightType):
            raise LightingError(f"type must be LightType, got {self.type!r}")
        self.intensity = _finite("intensity", self.intensity, low=0.0)
        if len(self.color) != 3:
            raise LightingError("color must be 3-tuple")
        for i, c in enumerate(self.color):
            _finite(f"color[{i}]", c, low=0.0, high=10.0)  # allow HDR >1
        if self.type == LightType.DIRECTIONAL:
            if self.direction is None:
                raise LightingError("DIRECTIONAL light requires direction")
            self.direction = _require_vector(self.direction, "direction")
            n = self.direction.magnitude()
            if n < 1e-12:
                raise LightingError("direction must not be zero vector")
            self.direction = self.direction * (1.0 / n)
            if self.position is not None:
                self.position = _require_vector(self.position, "position")
        elif self.type == LightType.POINT:
            if self.position is None:
                raise LightingError("POINT light requires position")
            self.position = _require_vector(self.position, "position")
            if self.range_m is not None:
                self.range_m = _finite("range_m", self.range_m, low=1e-9)
            if self.direction is not None:
                self.direction = _require_vector(self.direction, "direction")
        elif self.type == LightType.AMBIENT:
            # ambient has no direction/position
            pass
        if self.source_ref is not None and not isinstance(self.source_ref, str):
            raise LightingError("source_ref must be string or None")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "position": self.position.to_tuple() if self.position is not None else None,
            "direction": self.direction.to_tuple() if self.direction is not None else None,
            "intensity": self.intensity,
            "color": self.color,
            "casts_shadow": self.casts_shadow,
            "source_ref": self.source_ref,
        }


@dataclass
class ShadowConfig:
    """Shadow mapping configuration (data only)."""

    enabled: bool = True
    resolution: int = 2048
    bias: float = 0.001
    max_distance_m: float = 1e7
    cascade_count: int = 4
    softness: float = 0.5

    def __post_init__(self) -> None:
        if not isinstance(self.resolution, int) or self.resolution not in (512, 1024, 2048, 4096, 8192):
            raise LightingError(f"resolution must be one of 512/1024/2048/4096/8192, got {self.resolution!r}")
        self.bias = _finite("bias", self.bias, low=0.0, high=0.1)
        self.max_distance_m = _finite("max_distance_m", self.max_distance_m, low=1.0)
        if not isinstance(self.cascade_count, int) or not 1 <= self.cascade_count <= 8:
            raise LightingError(f"cascade_count must be 1..8, got {self.cascade_count!r}")
        self.softness = _finite("softness", self.softness, low=0.0, high=1.0)


@dataclass
class EclipseParams:
    """Eclipse / occultation data for planetary lighting."""

    light_id: str
    occluder_id: str
    receiver_id: str
    umbra_factor: float = 0.0  # 0 = no eclipse, 1 = total
    penumbra_factor: float = 0.0
    occluder_angular_radius_rad: float = 0.01
    light_angular_radius_rad: float = 0.01

    def __post_init__(self) -> None:
        for name in ("light_id", "occluder_id", "receiver_id"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v:
                raise LightingError(f"{name} must be non-empty string")
        self.umbra_factor = _finite("umbra_factor", self.umbra_factor, low=0.0, high=1.0)
        self.penumbra_factor = _finite("penumbra_factor", self.penumbra_factor, low=0.0, high=1.0)
        self.occluder_angular_radius_rad = _finite("occluder_angular_radius_rad", self.occluder_angular_radius_rad, low=0.0, high=math.pi)
        self.light_angular_radius_rad = _finite("light_angular_radius_rad", self.light_angular_radius_rad, low=0.0, high=math.pi)


@dataclass
class LightingState:
    """Aggregate lighting for a frame (renderer-independent)."""

    lights: List[LightSource] = field(default_factory=list)
    shadow: ShadowConfig = field(default_factory=ShadowConfig)
    ambient_intensity: float = 0.02
    ambient_color: Tuple[float, float, float] = (0.05, 0.05, 0.1)
    eclipses: List[EclipseParams] = field(default_factory=list)
    exposure: float = 1.0

    def __post_init__(self) -> None:
        self.ambient_intensity = _finite("ambient_intensity", self.ambient_intensity, low=0.0, high=1.0)
        for i, c in enumerate(self.ambient_color):
            _finite(f"ambient_color[{i}]", c, low=0.0, high=1.0)
        self.exposure = _finite("exposure", self.exposure, low=1e-6, high=1e6)
        # ensure unique light ids
        seen = set()
        for light in self.lights:
            if not isinstance(light, LightSource):
                raise LightingError(f"lights[{light!r}] must be LightSource")
            if light.id in seen:
                raise LightingError(f"duplicate light id: {light.id}")
            seen.add(light.id)

    def add_light(self, light: LightSource) -> None:
        if not isinstance(light, LightSource):
            raise LightingError("light must be LightSource")
        if any(l.id == light.id for l in self.lights):
            raise LightingError(f"light id already exists: {light.id}")
        self.lights.append(light)

    def remove_light(self, light_id: str) -> None:
        orig = len(self.lights)
        self.lights = [l for l in self.lights if l.id != light_id]
        if len(self.lights) == orig:
            raise LightingError(f"light not found: {light_id}")

    def get_star_lights(self) -> List[LightSource]:
        return [l for l in self.lights if l.source_ref is not None and l.type == LightType.DIRECTIONAL]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lights": [l.to_dict() for l in self.lights],
            "ambient_intensity": self.ambient_intensity,
            "ambient_color": self.ambient_color,
            "shadow": {"enabled": self.shadow.enabled, "resolution": self.shadow.resolution},
            "eclipses": [
                {"light_id": e.light_id, "occluder_id": e.occluder_id, "receiver_id": e.receiver_id, "umbra": e.umbra_factor}
                for e in self.eclipses
            ],
        }

    @classmethod
    def from_star(
        cls,
        star_position: Vector3,
        star_id: str = "star_sun",
        intensity: float = 1.0,
        color: Tuple[float, float, float] = (1.0, 1.0, 0.95),
        casts_shadow: bool = True,
    ) -> "LightingState":
        """Convenience: single directional light from a star position."""
        # Direction FROM star TOWARD origin (i.e., opposite of star position if origin at scene center)
        # Use star_position as point; for directional we need direction toward scene.
        # If observer near origin, direction is -normalized(star_position) (light travels from star to scene)
        star_position = _require_vector(star_position, "star_position")
        m = star_position.magnitude()
        if m < 1e-12:
            dir_vec = Vector3(0.0, 0.0, -1.0)
        else:
            dir_vec = Vector3(-star_position.x / m, -star_position.y / m, -star_position.z / m)
        light = LightSource(
            id=f"light_{star_id}",
            type=LightType.DIRECTIONAL,
            direction=dir_vec,
            position=star_position,
            intensity=_finite("intensity", intensity, low=0.0),
            color=color,
            casts_shadow=casts_shadow,
            source_ref=star_id,
        )
        return cls(lights=[light], shadow=ShadowConfig(enabled=casts_shadow))

    def clone(self) -> "LightingState":
        return LightingState(
            lights=[LightSource(id=l.id, type=l.type, position=Vector3(l.position.x, l.position.y, l.position.z) if l.position else None, direction=Vector3(l.direction.x, l.direction.y, l.direction.z) if l.direction else None, intensity=l.intensity, color=l.color, range_m=l.range_m, casts_shadow=l.casts_shadow, source_ref=l.source_ref) for l in self.lights],
            shadow=ShadowConfig(enabled=self.shadow.enabled, resolution=self.shadow.resolution, bias=self.shadow.bias, max_distance_m=self.shadow.max_distance_m, cascade_count=self.shadow.cascade_count, softness=self.shadow.softness),
            ambient_intensity=self.ambient_intensity,
            ambient_color=self.ambient_color,
            eclipses=list(self.eclipses),
            exposure=self.exposure,
        )
