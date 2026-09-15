"""Planetary visual effects."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..vfx.vfx_effect import VFXEffect, VFXType


class PlanetaryVFX(VFXEffect):
    def __init__(self, effect_id, position=(0.0, 0.0, 0.0), radius=6371000.0, has_atmosphere=True, has_ocean=True, has_ice_caps=True, cloud_coverage=0.5, cloud_speed=0.01, rotation_speed=7.2921e-5, axial_tilt=0.4085):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.GENERIC, position=position, duration=-1.0)
        self.radius = radius
        self.has_atmosphere = has_atmosphere
        self.has_ocean = has_ocean
        self.has_ice_caps = has_ice_caps
        self.cloud_coverage = max(0.0, min(1.0, cloud_coverage))
        self.cloud_speed = cloud_speed
        self.rotation_speed = rotation_speed
        self.axial_tilt = axial_tilt
        self._rotation_angle = 0.0
        self._cloud_offset = 0.0
        self._weather_systems = []
        self._geological_features = []
        self.add_tag("planet")

    @property
    def visible_radius(self):
        return self.radius

    @property
    def cloud_layer_height(self):
        return self.radius * 1.01 if self.has_atmosphere else 0.0

    def add_weather_system(self, latitude, longitude, size=100000.0, intensity=0.5, system_type="storm"):
        self._weather_systems.append({"latitude": latitude, "longitude": longitude, "size": size, "intensity": intensity, "type": system_type})

    def add_geological_feature(self, latitude, longitude, feature_type="mountain", elevation=1000.0, radius=50000.0):
        self._geological_features.append({"latitude": latitude, "longitude": longitude, "type": feature_type, "elevation": elevation, "radius": radius})

    def update(self, dt):
        super().update(dt)
        if self._active:
            self._rotation_angle += self.rotation_speed * dt * 1000
            self._cloud_offset += self.cloud_speed * dt

    def get_state(self):
        base = super().get_state()
        base.update({"radius": self.radius, "has_atmosphere": self.has_atmosphere, "has_ocean": self.has_ocean, "has_ice_caps": self.has_ice_caps, "cloud_coverage": self.cloud_coverage, "cloud_offset": self._cloud_offset, "rotation_angle": self._rotation_angle, "axial_tilt": self.axial_tilt, "weather_systems": self._weather_systems, "geological_features": self._geological_features})
        return base


class ImpactCraterVFX(VFXEffect):
    def __init__(self, effect_id, position=(0.0, 0.0, 0.0), crater_radius=1000.0, depth=200.0, ejecta_radius=5000.0, thermal_intensity=1.0):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.IMPACT, position=position, duration=10.0)
        self.crater_radius = crater_radius
        self.depth = depth
        self.ejecta_radius = ejecta_radius
        self.thermal_intensity = thermal_intensity
        self._cooling_rate = 0.1
        self.add_tag("crater")
        self.add_tag("impact")

    def update(self, dt):
        super().update(dt)
        if self._active:
            self.thermal_intensity = max(0.0, self.thermal_intensity - self._cooling_rate * dt)

    def get_state(self):
        base = super().get_state()
        base.update({"crater_radius": self.crater_radius, "depth": self.depth, "ejecta_radius": self.ejecta_radius, "thermal_intensity": self.thermal_intensity})
        return base
