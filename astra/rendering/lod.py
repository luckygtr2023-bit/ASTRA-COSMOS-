"""ASTRA Rendering - Level of Detail (deterministic, visual-only).

LOD changes visual complexity only; simulation behavior is untouched.
Selection is deterministic given distance / radius / importance / quality.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional

from astra.rendering.exceptions import LODError
from astra.rendering.types import LODLevel, QualityLevel, RenderObjectKind


def _finite(name: str, v, low=None, high=None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise LODError(f"{name} must be numeric, got {type(v).__name__}")
    f = float(v)
    if math.isnan(f) or math.isinf(f):
        raise LODError(f"{name} must be finite, got {v!r}")
    if low is not None and f < low:
        raise LODError(f"{name} must be >= {low}, got {f}")
    if high is not None and f > high:
        raise LODError(f"{name} must be <= {high}, got {f}")
    return f


@dataclass
class LODConfig:
    """Thresholds guiding LOD selection (meters, radians, factors)."""

    # distance thresholds (meters) for roughly spacecraft/asteroid scale
    # Larger objects use apparent size instead; these are fallbacks for point objects
    ultra_distance_m: float = 1e4      # <10 km ultra
    high_distance_m: float = 1e5       # <100 km high
    medium_distance_m: float = 1e6     # <1000 km medium
    low_distance_m: float = 1e7        # <10000 km low, beyond -> impostor
    cull_distance_m: float = 1e12      # beyond -> culled (star system scale)

    # apparent angular size thresholds (radians)
    # Overrides distance for extended objects
    ultra_angular_rad: float = 0.5     # >28 deg ultra
    high_angular_rad: float = 0.1
    medium_angular_rad: float = 0.01
    low_angular_rad: float = 0.001
    impostor_angular_rad: float = 0.0001  # below -> impostor; tiny -> cull

    # per-kind importance bias (multiplier on distance; higher = stays detailed farther)
    kind_bias: Dict[str, float] = field(default_factory=lambda: {
        RenderObjectKind.STAR.value: 100.0,
        RenderObjectKind.GALAXY.value: 1000.0,
        RenderObjectKind.PLANET.value: 10.0,
        RenderObjectKind.MOON.value: 5.0,
        RenderObjectKind.SPACECRAFT.value: 2.0,
        RenderObjectKind.ASTEROID.value: 1.0,
    })

    # quality bias (higher quality -> more detailed at same distance)
    quality_bias: Dict[str, float] = field(default_factory=lambda: {
        QualityLevel.LOW.value: 0.5,
        QualityLevel.MEDIUM.value: 1.0,
        QualityLevel.HIGH.value: 1.5,
        QualityLevel.ULTRA.value: 2.0,
        QualityLevel.AUTO.value: 1.0,
    })

    # global scale factor (e.g. modest hardware)
    global_bias: float = 1.0

    def __post_init__(self) -> None:
        self.ultra_distance_m = _finite("ultra_distance_m", self.ultra_distance_m, low=1.0)
        self.high_distance_m = _finite("high_distance_m", self.high_distance_m, low=self.ultra_distance_m)
        self.medium_distance_m = _finite("medium_distance_m", self.medium_distance_m, low=self.high_distance_m)
        self.low_distance_m = _finite("low_distance_m", self.low_distance_m, low=self.medium_distance_m)
        self.cull_distance_m = _finite("cull_distance_m", self.cull_distance_m, low=self.low_distance_m)
        self.ultra_angular_rad = _finite("ultra_angular_rad", self.ultra_angular_rad, low=1e-9, high=math.pi)
        self.high_angular_rad = _finite("high_angular_rad", self.high_angular_rad, low=1e-9, high=self.ultra_angular_rad)
        self.medium_angular_rad = _finite("medium_angular_rad", self.medium_angular_rad, low=1e-9, high=self.high_angular_rad)
        self.low_angular_rad = _finite("low_angular_rad", self.low_angular_rad, low=1e-9, high=self.medium_angular_rad)
        self.impostor_angular_rad = _finite("impostor_angular_rad", self.impostor_angular_rad, low=1e-12, high=self.low_angular_rad)
        self.global_bias = _finite("global_bias", self.global_bias, low=1e-6, high=1e6)
        # validate bias maps
        for k, v in self.kind_bias.items():
            _finite(f"kind_bias[{k}]", v, low=1e-6, high=1e6)
        for k, v in self.quality_bias.items():
            _finite(f"quality_bias[{k}]", v, low=1e-6, high=1e6)

    def clone(self) -> "LODConfig":
        return LODConfig(
            ultra_distance_m=self.ultra_distance_m,
            high_distance_m=self.high_distance_m,
            medium_distance_m=self.medium_distance_m,
            low_distance_m=self.low_distance_m,
            cull_distance_m=self.cull_distance_m,
            ultra_angular_rad=self.ultra_angular_rad,
            high_angular_rad=self.high_angular_rad,
            medium_angular_rad=self.medium_angular_rad,
            low_angular_rad=self.low_angular_rad,
            impostor_angular_rad=self.impostor_angular_rad,
            kind_bias=dict(self.kind_bias),
            quality_bias=dict(self.quality_bias),
            global_bias=self.global_bias,
        )

    def effective_distance(self, distance_m: float, kind: RenderObjectKind, quality: QualityLevel) -> float:
        """Bias-adjusted distance for threshold comparison (smaller = more detailed)."""
        bias = self.kind_bias.get(kind.value, 1.0) * self.quality_bias.get(quality.value, 1.0) * self.global_bias
        # Higher bias means object should appear closer (more detailed) -> divide
        return distance_m / max(1e-9, bias)


class LODSelector:
    """Deterministic LOD selection.

    No global RNG; no wall clock; pure function of inputs.
    """

    def __init__(self, config: Optional[LODConfig] = None):
        self.config = config or LODConfig()

    def select(
        self,
        distance_m: float,
        bounding_radius_m: float = 1.0,
        apparent_size_rad: Optional[float] = None,
        kind: RenderObjectKind = RenderObjectKind.UNKNOWN,
        quality: QualityLevel = QualityLevel.MEDIUM,
        importance: float = 1.0,
    ) -> LODLevel:
        """Select LOD level deterministically.

        Priority: apparent size (if provided and finite) overrides distance.
        """
        distance_m = _finite("distance_m", distance_m, low=0.0)
        bounding_radius_m = _finite("bounding_radius_m", bounding_radius_m, low=0.0)
        importance = _finite("importance", importance, low=0.0, high=1.0)
        if not isinstance(kind, RenderObjectKind):
            raise LODError(f"kind must be RenderObjectKind, got {kind!r}")
        if not isinstance(quality, QualityLevel):
            raise LODError(f"quality must be QualityLevel, got {quality!r}")

        imp_bias = 0.5 + importance  # 0.5 to 1.5
        eff_dist = self.config.effective_distance(distance_m, kind, quality) / max(1e-9, imp_bias)

        # If apparent size is available, it takes precedence over pure distance
        if apparent_size_rad is not None:
            if isinstance(apparent_size_rad, bool) or not isinstance(apparent_size_rad, (int, float)):
                raise LODError(f"apparent_size_rad must be numeric or None")
            a = float(apparent_size_rad)
            if math.isnan(a) or math.isinf(a) or a < 0.0:
                raise LODError(f"apparent_size_rad must be finite >=0, got {apparent_size_rad!r}")
            # Very tiny -> keep stars/galaxies as impostor, otherwise may cull
            if a < self.config.impostor_angular_rad * 0.5:
                if kind in (RenderObjectKind.STAR, RenderObjectKind.GALAXY):
                    return LODLevel.IMPOSTOR
                if importance > 0.9:
                    return LODLevel.IMPOSTOR
                if eff_dist >= self.config.cull_distance_m:
                    return LODLevel.CULLED
                return LODLevel.CULLED
            if a >= self.config.ultra_angular_rad:
                return LODLevel.ULTRA
            if a >= self.config.high_angular_rad:
                return LODLevel.HIGH
            if a >= self.config.medium_angular_rad:
                return LODLevel.MEDIUM
            if a >= self.config.low_angular_rad:
                return LODLevel.LOW
            if a >= self.config.impostor_angular_rad:
                return LODLevel.IMPOSTOR
            # Between tiny*0.5 and impostor threshold, treat as impostor but respect culling for non-star small objects
            if eff_dist >= self.config.cull_distance_m:
                if kind in (RenderObjectKind.STAR, RenderObjectKind.GALAXY) or importance > 0.9:
                    return LODLevel.IMPOSTOR
                return LODLevel.CULLED
            return LODLevel.IMPOSTOR

        # Pure distance-based fallback
        if eff_dist >= self.config.cull_distance_m:
            return LODLevel.CULLED
        if eff_dist < self.config.ultra_distance_m:
            return LODLevel.ULTRA
        if eff_dist < self.config.high_distance_m:
            return LODLevel.HIGH
        if eff_dist < self.config.medium_distance_m:
            return LODLevel.MEDIUM
        if eff_dist < self.config.low_distance_m:
            return LODLevel.LOW
        return LODLevel.IMPOSTOR

    def select_for_object(
        self,
        distance_m: float,
        apparent_size_rad: Optional[float],
        kind: RenderObjectKind,
        quality: QualityLevel,
        importance: float,
        bounding_radius_m: float = 1.0,
    ) -> LODLevel:
        return self.select(distance_m, bounding_radius_m, apparent_size_rad, kind, quality, importance)

    def is_visible(self, lod: LODLevel) -> bool:
        return lod != LODLevel.CULLED
