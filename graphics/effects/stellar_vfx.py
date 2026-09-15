"""Stellar visual effects."""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

from ..vfx.vfx_effect import VFXEffect, VFXType


class StellarVFX(VFXEffect):
    def __init__(self, effect_id, position=(0.0, 0.0, 0.0), temperature=5778.0, luminosity=1.0, radius=696340000.0, corona_intensity=0.5, flare_probability=0.01, prominence_scale=0.1):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.CORONA, position=position, duration=-1.0)
        self.temperature = temperature
        self.luminosity = luminosity
        self.radius = radius
        self.corona_intensity = corona_intensity
        self.flare_probability = flare_probability
        self.prominence_scale = prominence_scale
        self._color = self._temperature_to_rgb(temperature)
        self._flare_timer = 0.0
        self._current_flare = None
        self._granulation_phase = 0.0
        self.add_tag("star")
        self.add_tag("corona")
        self.add_tag("emissive")

    @property
    def color(self):
        return self._color

    @property
    def surface_brightness(self):
        return min(1.0, self.luminosity * 0.5)

    @property
    def corona_radius(self):
        return self.radius * (1.0 + self.corona_intensity * 0.3)

    def _temperature_to_rgb(self, temp):
        temp = max(1000.0, min(40000.0, temp))
        t = temp / 100.0
        if t <= 66: r = 1.0
        else: r = max(0.0, min(1.0, 1.2929361861389791 * ((t - 60) ** -0.1332047592)))
        if t <= 66: g = max(0.0, min(1.0, 0.390081582351272 * (t - 46)))
        else: g = max(0.0, min(1.0, 1.1298914554071346 * ((t - 60) ** -0.0755148492)))
        if t >= 66: b = 0.0
        elif t <= 19: b = 0.0
        else: b = max(0.0, min(1.0, 0.5432067891123172 * (t - 10)))
        return (r, g, b)

    def update(self, dt):
        super().update(dt)
        if self._active:
            self._granulation_phase += dt * 0.5
            self._flare_timer += dt
            if self._current_flare is None and self._flare_timer > 5.0:
                if self.flare_probability > 0:
                    self._flare_timer = 0.0
                    self._current_flare = {"intensity": 2.0 + self.luminosity, "duration": 3.0, "elapsed": 0.0}
            if self._current_flare is not None:
                self._current_flare["elapsed"] += dt
                if self._current_flare["elapsed"] >= self._current_flare["duration"]:
                    self._current_flare = None

    def get_state(self):
        base = super().get_state()
        flare_state = None
        if self._current_flare:
            progress = self._current_flare["elapsed"] / self._current_flare["duration"]
            flare_state = {"intensity": self._current_flare["intensity"] * (1.0 - progress), "progress": progress}
        base.update({"temperature": self.temperature, "luminosity": self.luminosity, "color": list(self._color), "surface_brightness": self.surface_brightness, "corona_intensity": self.corona_intensity, "corona_radius": self.corona_radius, "granulation_phase": self._granulation_phase, "current_flare": flare_state, "prominence_scale": self.prominence_scale})
        return base
