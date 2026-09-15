"""Particle renderer configuration and rendering bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .particle_emitter import ParticleEmitter
from .particle_system import ParticleSystem


@dataclass
class ParticleRenderConfig:
    global_size_multiplier: float = 1.0
    min_size: float = 0.1
    max_size: float = 100.0
    sort_to_camera: bool = True
    soft_particles: bool = False
    motion_blur: bool = False
    motion_blur_strength: float = 0.5
    fade_in: bool = True
    fade_out: bool = True
    fade_in_duration: float = 0.1
    fade_out_start: float = 0.7
    depth_sort: bool = True
    max_draw_count: int = 10000
    billboard: bool = True
    color_over_lifetime: Optional[List[Tuple[float, Tuple[float, float, float, float]]]] = None
    size_over_lifetime: Optional[List[Tuple[float, float]]] = None

    def get_life_factor(self, life):
        life = max(0.0, min(1.0, life))
        if self.fade_in and life > (1.0 - self.fade_in_duration):
            return (1.0 - life) / self.fade_in_duration
        if self.fade_out and life < self.fade_out_start:
            return life / self.fade_out_start
        return 1.0

    def interpolate_color_over_life(self, life):
        if not self.color_over_lifetime or len(self.color_over_lifetime) < 2:
            return None
        sorted_keys = sorted(self.color_over_lifetime, key=lambda x: x[0])
        for i in range(len(sorted_keys) - 1):
            t0, c0 = sorted_keys[i]
            t1, c1 = sorted_keys[i + 1]
            if t0 <= life <= t1:
                frac = (life - t0) / (t1 - t0) if t1 != t0 else 0.0
                return tuple(c0[j] + (c1[j] - c0[j]) * frac for j in range(4))
        return sorted_keys[-1][1]

    def interpolate_size_over_life(self, life):
        if not self.size_over_lifetime or len(self.size_over_lifetime) < 2:
            return None
        sorted_keys = sorted(self.size_over_lifetime, key=lambda x: x[0])
        for i in range(len(sorted_keys) - 1):
            t0, s0 = sorted_keys[i]
            t1, s1 = sorted_keys[i + 1]
            if t0 <= life <= t1:
                frac = (life - t0) / (t1 - t0) if t1 != t0 else 0.0
                return s0 + (s1 - s0) * frac
        return sorted_keys[-1][1]


class ParticleRenderer:
    def __init__(self, config=None):
        self.config = config or ParticleRenderConfig()

    def prepare_draw_calls(self, particle_system, camera_position=(0.0, 0.0, 0.0)):
        render_data = particle_system.get_render_data()
        draw_calls = []
        for emitter_id, particles in render_data.items():
            processed = []
            for p in particles:
                life = p["life"]
                if life <= 0:
                    continue
                size = p["size"] * self.config.global_size_multiplier
                size = max(self.config.min_size, min(self.config.max_size, size))
                life_factor = self.config.get_life_factor(life)
                color = p["color"]
                color_override = self.config.interpolate_color_over_life(life)
                if color_override:
                    color = color_override
                size_override = self.config.interpolate_size_over_life(life)
                if size_override:
                    size = size_override * self.config.global_size_multiplier
                final_color = (color[0], color[1], color[2], color[3] * life_factor)
                if self.config.sort_to_camera:
                    dx = p["position"][0] - camera_position[0]
                    dy = p["position"][1] - camera_position[1]
                    dz = p["position"][2] - camera_position[2]
                    dist_sq = dx * dx + dy * dy + dz * dz
                else:
                    dist_sq = 0.0
                processed.append({"position": p["position"], "size": size, "color": final_color, "life": life, "sort_distance_sq": dist_sq})
            if self.config.depth_sort:
                processed.sort(key=lambda x: -x["sort_distance_sq"])
            for p in processed[:self.config.max_draw_count]:
                draw_calls.append({"type": "point_sprite" if self.config.billboard else "point", "position": p["position"], "size": p["size"], "color": p["color"], "emitter_id": emitter_id})
        return draw_calls

    def to_dict(self):
        return {"config": {"global_size_multiplier": self.config.global_size_multiplier, "sort_to_camera": self.config.sort_to_camera, "fade_in": self.config.fade_in, "fade_out": self.config.fade_out, "max_draw_count": self.config.max_draw_count, "billboard": self.config.billboard}}
