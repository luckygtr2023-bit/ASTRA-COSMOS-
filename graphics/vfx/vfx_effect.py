"""Base VFX effect class."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, List, Optional


class VFXType(Enum):
    IMPACT = auto()
    DEBRIS = auto()
    EJECTA = auto()
    DUST = auto()
    SPARKS = auto()
    EXPLOSION = auto()
    FIRE = auto()
    SMOKE = auto()
    TRAIL = auto()
    SHOCKWAVE = auto()
    ACCRETION = auto()
    LENSING = auto()
    JET = auto()
    CORONA = auto()
    FLARE = auto()
    WORMHOLE = auto()
    WARP = auto()
    ATMOSPHERE = auto()
    STARBURST = auto()
    NEBULA_GLOW = auto()
    BACKGROUND = auto()
    GENERIC = auto()


class VFXEffect:
    def __init__(self, effect_id, vfx_type=VFXType.GENERIC, position=(0.0, 0.0, 0.0), duration=-1.0):
        self.effect_id = effect_id
        self.vfx_type = vfx_type
        self.position = position
        self.duration = duration
        self._elapsed = 0.0
        self._active = True
        self._started = False
        self._params = {}
        self._tags = []

    @property
    def is_active(self):
        return self._active

    @property
    def progress(self):
        if self.duration <= 0:
            return 0.0
        return min(1.0, self._elapsed / self.duration)

    @property
    def normalized_time(self):
        return self.progress

    def start(self):
        self._started = True
        self._active = True
        self._elapsed = 0.0

    def stop(self):
        self._active = False

    def reset(self):
        self._elapsed = 0.0
        self._active = True
        self._started = False

    def update(self, dt):
        if not self._active:
            return
        self._elapsed += dt
        if self.duration > 0 and self._elapsed >= self.duration:
            self._active = False

    def set_param(self, key, value):
        self._params[key] = value

    def get_param(self, key, default=None):
        return self._params.get(key, default)

    def add_tag(self, tag):
        if tag not in self._tags:
            self._tags.append(tag)

    def has_tag(self, tag):
        return tag in self._tags

    def get_state(self):
        return {"effect_id": self.effect_id, "type": self.vfx_type.name, "position": list(self.position), "active": self._active, "progress": self.progress, "elapsed": self._elapsed}

    def to_dict(self):
        return {"effect_id": self.effect_id, "type": self.vfx_type.name, "position": list(self.position), "duration": self.duration, "active": self._active, "progress": self.progress, "params": dict(self._params), "tags": list(self._tags)}
