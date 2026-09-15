"""Atmosphere visual effects."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..vfx.vfx_effect import VFXEffect, VFXType


class AtmosphereVFX(VFXEffect):
    def __init__(self, effect_id, planet_radius=6371000.0, atmosphere_height=100000.0, rayleigh_scale_height=8500.0, mie_scale_height=1200.0, rayleigh_coefficient=(5.8e-6, 13.5e-6, 33.1e-6), mie_coefficient=21e-6, mie_g=0.758, sun_intensity=20.0, scatter_color=(0.3, 0.5, 0.9), density=1.0, cloud_density=0.3, cloud_color=(0.9, 0.95, 1.0)):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.ATMOSPHERE, duration=-1.0)
        self.planet_radius = planet_radius
        self.atmosphere_height = atmosphere_height
        self.rayleigh_scale_height = rayleigh_scale_height
        self.mie_scale_height = mie_scale_height
        self.rayleigh_coefficient = rayleigh_coefficient
        self.mie_coefficient = mie_coefficient
        self.mie_g = max(-1.0, min(1.0, mie_g))
        self.sun_intensity = sun_intensity
        self.scatter_color = scatter_color
        self.density = max(0.0, min(2.0, density))
        self.cloud_density = max(0.0, min(1.0, cloud_density))
        self.cloud_color = cloud_color
        self._cloud_coverage = 0.5
        self._cloud_speed = 0.01
        self._turbulence_octaves = 4
        self._day_night_blend = 1.0
        self.add_tag("atmosphere")
        self.add_tag("scattering")

    @property
    def outer_radius(self):
        return self.planet_radius + self.atmosphere_height

    @property
    def scattering_strength(self):
        return self.density * self.sun_intensity

    @property
    def horizon_color(self):
        return (self.scatter_color[0] * 0.7, self.scatter_color[1] * 0.8, self.scatter_color[2])

    def compute_scattering(self, view_direction, sun_direction):
        vd = view_direction
        sd = sun_direction
        vd_len = max(1e-8, math.sqrt(vd[0]**2 + vd[1]**2 + vd[2]**2))
        sd_len = max(1e-8, math.sqrt(sd[0]**2 + sd[1]**2 + sd[2]**2))
        vn = (vd[0]/vd_len, vd[1]/vd_len, vd[2]/vd_len)
        sn = (sd[0]/sd_len, sd[1]/sd_len, sd[2]/sd_len)
        cos_theta = max(0.0, vn[0]*sn[0] + vn[1]*sn[1] + vn[2]*sn[2])
        rayleigh = (1.0 + cos_theta ** 2) * 0.5
        phase_mie = ((1.0 - self.mie_g**2) / (4.0 * math.pi * (1.0 + self.mie_g**2 - 2.0*self.mie_g*cos_theta)**1.5))
        intensity = self.scattering_strength * self.density
        r = self.rayleigh_coefficient[0] * rayleigh * intensity + self.mie_coefficient * phase_mie * intensity
        g = self.rayleigh_coefficient[1] * rayleigh * intensity + self.mie_coefficient * phase_mie * intensity
        b = self.rayleigh_coefficient[2] * rayleigh * intensity + self.mie_coefficient * phase_mie * intensity
        max_val = max(r, g, b, 1e-8)
        if max_val > 1.0:
            r /= max_val; g /= max_val; b /= max_val
        return (r, g, b)

    def set_cloud_coverage(self, coverage):
        self._cloud_coverage = max(0.0, min(1.0, coverage))

    def update(self, dt):
        super().update(dt)

    def get_state(self):
        base = super().get_state()
        base.update({"planet_radius": self.planet_radius, "atmosphere_height": self.atmosphere_height, "outer_radius": self.outer_radius, "rayleigh_scale_height": self.rayleigh_scale_height, "mie_scale_height": self.mie_scale_height, "rayleigh_coefficient": list(self.rayleigh_coefficient), "mie_coefficient": self.mie_coefficient, "mie_g": self.mie_g, "sun_intensity": self.sun_intensity, "scatter_color": list(self.scatter_color), "density": self.density, "scattering_strength": self.scattering_strength, "cloud_density": self.cloud_density, "cloud_color": list(self.cloud_color), "cloud_coverage": self._cloud_coverage, "horizon_color": list(self.horizon_color)})
        return base
