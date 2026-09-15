"""Wormhole visual effects."""

from __future__ import annotations

import math
from typing import Any, Dict, Tuple

from ..vfx.vfx_effect import VFXEffect, VFXType


class WormholeVFX(VFXEffect):
    def __init__(self, effect_id, position=(0.0, 0.0, 0.0), throat_radius=1.0, length=10.0, color=(0.2, 0.4, 0.9), distortion_strength=1.0):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.WORMHOLE, position=position, duration=-1.0)
        self.throat_radius = max(0.01, throat_radius)
        self.length = max(0.1, length)
        self.color = color
        self.distortion_strength = distortion_strength
        self._rotation_angle = 0.0
        self._pulse_phase = 0.0
        self._ring_count = 12
        self.add_tag("wormhole")
        self.add_tag("spacetime")

    def update(self, dt):
        super().update(dt)
        if self._active:
            self._rotation_angle += dt * 0.5
            self._pulse_phase += dt * 2.0

    @property
    def throat_cross_section(self):
        return math.pi * self.throat_radius ** 2

    @property
    def visual_radius(self):
        return self.throat_radius * 2.0

    @property
    def ring_positions(self):
        rings = []
        for i in range(self._ring_count):
            t = i / max(1, self._ring_count - 1)
            depth = (t - 0.5) * self.length
            radius_scale = 1.0 + 0.5 * math.sin(t * math.pi)
            pulse = 1.0 + 0.1 * math.sin(self._pulse_phase + t * 4.0)
            r = self.throat_radius * radius_scale * pulse
            rings.append({"depth": depth, "radius": r, "phase": t})
        return rings

    def get_state(self):
        base = super().get_state()
        base.update({"throat_radius": self.throat_radius, "length": self.length, "color": list(self.color), "distortion_strength": self.distortion_strength, "rotation_angle": self._rotation_angle, "visual_radius": self.visual_radius, "rings": self.ring_positions})
        return base


class WarpBubbleVFX(VFXEffect):
    def __init__(self, effect_id, position=(0.0, 0.0, 0.0), bubble_radius=5.0, field_strength=1.0, color=(0.1, 0.3, 0.8)):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.WARP, position=position, duration=-1.0)
        self.bubble_radius = max(0.1, bubble_radius)
        self.field_strength = field_strength
        self.color = color
        self._expansion = 0.0
        self._trail_length = 20.0
        self.add_tag("warp")
        self.add_tag("spacetime")

    def update(self, dt):
        super().update(dt)
        if self._active:
            self._expansion = min(1.0, self._expansion + dt * 2.0)

    def get_state(self):
        base = super().get_state()
        effective_radius = self.bubble_radius * self._expansion
        base.update({"bubble_radius": effective_radius, "field_strength": self.field_strength, "color": list(self.color), "expansion": self._expansion, "trail_length": self._trail_length})
        return base
