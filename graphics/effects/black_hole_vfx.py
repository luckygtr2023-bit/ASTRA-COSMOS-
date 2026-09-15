"""Black hole visual effects."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..vfx.vfx_effect import VFXEffect, VFXType
from config.constants import GRAVITATIONAL_CONSTANT, SPEED_OF_LIGHT


class BlackHoleVFX(VFXEffect):
    def __init__(self, effect_id, position=(0.0, 0.0, 0.0), mass=1e31, spin=0.0):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.LENSING, position=position, duration=-1.0)
        self.mass = mass
        self.spin = max(-1.0, min(1.0, spin))
        self.add_tag("black_hole")
        self.add_tag("gravity")
        self.schwarzschild_radius = self._compute_schwarzschild_radius()
        self.isco_radius = self._compute_isco()
        self.photon_sphere_radius = 1.5 * self.schwarzschild_radius
        self.shadow_radius = self._compute_shadow_radius()
        self._accretion_disk_active = True
        self._jet_active = abs(spin) > 0.1
        self._lensing_strength = self._compute_lensing_strength()

    def _compute_schwarzschild_radius(self):
        return (2.0 * GRAVITATIONAL_CONSTANT * self.mass) / (SPEED_OF_LIGHT ** 2)

    def _compute_isco(self):
        if self.spin >= 0:
            z1 = 1 + (1 - self.spin ** 2) ** (1.0 / 3.0) * ((1 + self.spin) ** (1.0 / 3.0) + (1 - self.spin) ** (1.0 / 3.0))
            z2 = (3 * self.spin ** 2 + z1 ** 2) ** 0.5
            r_ms = 3 + z2 - ((3 - z1) * (3 + z1 + 2 * z2)) ** 0.5 if self.spin >= 0 else 6.0
        else:
            r_ms = 6.0
        return max(3.0, r_ms) * self.schwarzschild_radius

    def _compute_shadow_radius(self):
        return math.sqrt(27.0) * self.schwarzschild_radius

    def _compute_lensing_strength(self):
        return min(1.0, self.mass / 1e33)

    @property
    def event_horizon_color(self):
        return (0.0, 0.0, 0.0)

    @property
    def photon_ring_color(self):
        intensity = 0.3 + 0.7 * self._lensing_strength
        return (intensity, intensity * 0.9, intensity * 0.7)

    def get_state(self):
        base = super().get_state()
        base.update({"mass": self.mass, "spin": self.spin, "schwarzschild_radius": self.schwarzschild_radius, "isco_radius": self.isco_radius, "photon_sphere_radius": self.photon_sphere_radius, "shadow_radius": self.shadow_radius, "lensing_strength": self._lensing_strength, "accretion_disk_active": self._accretion_disk_active, "jet_active": self._jet_active, "event_horizon_color": list(self.event_horizon_color), "photon_ring_color": list(self.photon_ring_color)})
        return base


class AccretionDiskVFX(VFXEffect):
    def __init__(self, effect_id, black_hole_effect_id, inner_radius=3.0, outer_radius=100.0, temperature_inner=1_000_000.0, temperature_outer=10_000.0, inclination=0.0):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.ACCRETION, duration=-1.0)
        self.black_hole_effect_id = black_hole_effect_id
        self.inner_radius = inner_radius
        self.outer_radius = outer_radius
        self.temperature_inner = temperature_inner
        self.temperature_outer = temperature_outer
        self.inclination = inclination
        self._angular_velocity = 1.0
        self._disk_thickness = 0.1
        self._turbulence = 0.2
        self.add_tag("accretion_disk")

    def update(self, dt):
        super().update(dt)
        if self._active:
            self._angular_velocity += dt * 0.1

    def get_state(self):
        base = super().get_state()
        base.update({"black_hole_effect_id": self.black_hole_effect_id, "inner_radius": self.inner_radius, "outer_radius": self.outer_radius, "temperature_inner": self.temperature_inner, "temperature_outer": self.temperature_outer, "inclination": self.inclination, "angular_velocity": self._angular_velocity, "disk_thickness": self._disk_thickness, "turbulence": self._turbulence})
        return base


class BlackHoleJetVFX(VFXEffect):
    def __init__(self, effect_id, spin=0.9, jet_length=1000.0, jet_radius=5.0, color=(0.3, 0.5, 1.0)):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.JET, duration=-1.0)
        self.spin = max(-1.0, min(1.0, spin))
        self.jet_length = jet_length
        self.jet_radius = jet_radius
        self.color = color
        self._pulsation = 0.0
        self.add_tag("jet")
        self.add_tag("relativistic")

    def update(self, dt):
        super().update(dt)
        if self._active:
            self._pulsation += dt * 2.0

    def get_state(self):
        base = super().get_state()
        intensity = abs(self.spin)
        pulsation = 0.9 + 0.1 * math.sin(self._pulsation)
        base.update({"spin": self.spin, "jet_length": self.jet_length * intensity, "jet_radius": self.jet_radius, "color": list(self.color), "intensity": intensity * pulsation})
        return base
