"""Post-processing pipeline for ASTRA COSMOS."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class PostProcessEffect(Enum):
    BLOOM = auto()
    TONE_MAPPING = auto()
    EXPOSURE = auto()
    MOTION_BLUR = auto()
    DEPTH_OF_FIELD = auto()
    ATMOSPHERIC_DISTORTION = auto()
    LENS_FLARE = auto()
    CHROMATIC_ABERRATION = auto()
    VIGNETTE = auto()
    FXAA = auto()
    FILM_GRAIN = auto()


class PostProcessPipeline:
    def __init__(self):
        self._effects = []
        self._enabled = {}
        self._params = {}
        self._quality_level = 2
        self._max_quality = 3
        self._initialize_defaults()

    def _initialize_defaults(self):
        self.add_effect(PostProcessEffect.TONE_MAPPING, enabled=True)
        self.set_params(PostProcessEffect.TONE_MAPPING, {"mode": "aces", "white_point": 1.0})
        self.add_effect(PostProcessEffect.EXPOSURE, enabled=True)
        self.set_params(PostProcessEffect.EXPOSURE, {"exposure": 1.0, "auto_exposure": True, "adaptation_speed": 1.0})
        self.add_effect(PostProcessEffect.BLOOM, enabled=True)
        self.set_params(PostProcessEffect.BLOOM, {"threshold": 0.8, "intensity": 0.3, "radius": 4, "quality": "medium"})
        self.add_effect(PostProcessEffect.FXAA, enabled=True)
        self.set_params(PostProcessEffect.FXAA, {"subpixel_quality": 0.75})
        self.add_effect(PostProcessEffect.VIGNETTE, enabled=False)
        self.set_params(PostProcessEffect.VIGNETTE, {"intensity": 0.3, "smoothness": 0.5})
        self.add_effect(PostProcessEffect.LENS_FLARE, enabled=False)
        self.set_params(PostProcessEffect.LENS_FLARE, {"intensity": 0.5, "samples": 8})
        self.add_effect(PostProcessEffect.MOTION_BLUR, enabled=False)
        self.set_params(PostProcessEffect.MOTION_BLUR, {"samples": 8, "strength": 0.5})
        self.add_effect(PostProcessEffect.CHROMATIC_ABERRATION, enabled=False)
        self.set_params(PostProcessEffect.CHROMATIC_ABERRATION, {"intensity": 0.003})
        self.add_effect(PostProcessEffect.FILM_GRAIN, enabled=False)
        self.set_params(PostProcessEffect.FILM_GRAIN, {"intensity": 0.05, "speed": 1.0})
        self.add_effect(PostProcessEffect.ATMOSPHERIC_DISTORTION, enabled=False)
        self.set_params(PostProcessEffect.ATMOSPHERIC_DISTORTION, {"intensity": 0.1})
        self.add_effect(PostProcessEffect.DEPTH_OF_FIELD, enabled=False)
        self.set_params(PostProcessEffect.DEPTH_OF_FIELD, {"focus_distance": 10.0, "aperture": 1.4, "max_blur": 5.0})

    def add_effect(self, effect, enabled=True, priority=0):
        entry = {"effect": effect, "priority": priority}
        self._effects.append(entry)
        self._effects.sort(key=lambda x: -x["priority"])
        self._enabled[effect.name] = enabled

    def enable(self, effect):
        self._enabled[effect.name] = True

    def disable(self, effect):
        self._enabled[effect.name] = False

    def is_enabled(self, effect):
        return self._enabled.get(effect.name, False)

    def set_params(self, effect, params):
        self._params[effect.name] = params

    def get_params(self, effect):
        return self._params.get(effect.name, {})

    def set_quality_level(self, level):
        self._quality_level = max(0, min(self._max_quality, level))
        self._apply_quality()

    def _apply_quality(self):
        if self._quality_level == 0:
            self.disable(PostProcessEffect.BLOOM)
            self.disable(PostProcessEffect.MOTION_BLUR)
            self.disable(PostProcessEffect.DEPTH_OF_FIELD)
            self.disable(PostProcessEffect.ATMOSPHERIC_DISTORTION)
            self.disable(PostProcessEffect.LENS_FLARE)
            self.disable(PostProcessEffect.CHROMATIC_ABERRATION)
            self.disable(PostProcessEffect.FILM_GRAIN)
        elif self._quality_level == 1:
            self.disable(PostProcessEffect.MOTION_BLUR)
            self.disable(PostProcessEffect.DEPTH_OF_FIELD)
            self.disable(PostProcessEffect.ATMOSPHERIC_DISTORTION)
        elif self._quality_level == 2:
            self.enable(PostProcessEffect.BLOOM)
            self.enable(PostProcessEffect.FXAA)
        elif self._quality_level >= 3:
            self.enable(PostProcessEffect.BLOOM)
            self.enable(PostProcessEffect.MOTION_BLUR)
            self.enable(PostProcessEffect.LENS_FLARE)

    @property
    def quality_level(self):
        return self._quality_level

    def get_enabled_effects(self):
        return [e["effect"] for e in self._effects if self._enabled.get(e["effect"].name, False)]

    def get_all_effects(self):
        return [e["effect"] for e in self._effects]

    def to_dict(self):
        return {
            "quality_level": self._quality_level,
            "effects": [
                {"name": e["effect"].name, "enabled": self._enabled.get(e["effect"].name, False), "params": self._params.get(e["effect"].name, {})}
                for e in self._effects
            ],
        }

    def apply(self, frame_data=None):
        # CPU-side no-op; concrete renderer would execute
        return {"applied": [e.name for e in self.get_enabled_effects()], "frame_data": frame_data}

    def clear(self):
        self._effects.clear()
        self._enabled.clear()
        self._params.clear()
        self._initialize_defaults()

    def __repr__(self):
        enabled = [e.name for e in self.get_enabled_effects()]
        return f"PostProcessPipeline(quality={self._quality_level}, enabled={enabled})"
