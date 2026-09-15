"""Particle emitter types and configuration."""

from __future__ import annotations

import math
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

from .particle_state import ParticleData, ParticleState


class EmitterType(Enum):
    POINT = auto()
    SPHERE = auto()
    DISC = auto()
    CONE = auto()
    LINE = auto()
    RING = auto()
    PLANE = auto()
    CUSTOM = auto()


class ParticleEmitter:
    """Configurable particle emitter with deterministic generation."""

    def __init__(
        self,
        emitter_id: str,
        emitter_type: EmitterType = EmitterType.POINT,
        position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        rate: float = 10.0,
        burst_count: int = 0,
        lifetime: float = 2.0,
        lifetime_variance: float = 0.5,
        initial_size: float = 1.0,
        size_variance: float = 0.2,
        initial_speed: float = 5.0,
        speed_variance: float = 1.0,
        color: Tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),
        color_variance: float = 0.1,
        gravity: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        drag: float = 0.0,
        max_particles: int = 1000,
        duration: float = -1.0,
        loop: bool = True,
    ):
        self.emitter_id = emitter_id
        self.emitter_type = emitter_type
        self.position = position
        self.rate = rate
        self.burst_count = burst_count
        self.lifetime = lifetime
        self.lifetime_variance = lifetime_variance
        self.initial_size = initial_size
        self.size_variance = size_variance
        self.initial_speed = initial_speed
        self.speed_variance = speed_variance
        self.color = color
        self.color_variance = color_variance
        self.gravity = gravity
        self.drag = drag
        self.max_particles = max_particles
        self.duration = duration
        self.loop = loop
        self._accumulator = 0.0
        self._elapsed = 0.0
        self._active = True
        self._emitted_total = 0
        self._shape_params: Dict[str, Any] = {}

    @property
    def is_active(self):
        return self._active

    @property
    def emitted_total(self):
        return self._emitted_total

    def set_shape_param(self, key, value):
        self._shape_params[key] = value

    def get_shape_param(self, key, default=None):
        return self._shape_params.get(key, default)

    def reset(self):
        self._accumulator = 0.0
        self._elapsed = 0.0
        self._active = True
        self._emitted_total = 0

    def update(self, dt, particle_state, count_override=None):
        if not self._active:
            return 0
        self._elapsed += dt
        if self.duration > 0 and self._elapsed >= self.duration:
            if self.loop:
                self._elapsed = 0.0
            else:
                self._active = False
                return 0
        to_emit = 0
        if count_override is not None:
            to_emit = count_override
        else:
            self._accumulator += self.rate * dt
            to_emit = int(self._accumulator)
            self._accumulator -= to_emit
        if self.burst_count > 0 and self._emitted_total == 0:
            to_emit += self.burst_count
            self.burst_count = 0
        spawned = 0
        for _ in range(to_emit):
            if self._emitted_total >= self.max_particles:
                break
            idx = particle_state.data.first_free_index()
            if idx is None:
                break
            self._spawn_particle(idx, particle_state)
            spawned += 1
            self._emitted_total += 1
        return spawned

    def _spawn_particle(self, index, state):
        pos = self._compute_spawn_position(state)
        vel = self._compute_spawn_velocity(state)
        lt = max(0.01, state.random_uniform(self.lifetime - self.lifetime_variance, self.lifetime + self.lifetime_variance))
        sz = max(0.01, state.random_uniform(self.initial_size - self.size_variance, self.initial_size + self.size_variance))
        c = self._compute_color(state)
        state.data.spawn(index=index, position=pos, velocity=vel, size=sz, lifetime=lt, color=c, mass=1.0, acceleration=self.gravity)

    def _compute_spawn_position(self, state):
        px, py, pz = self.position
        if self.emitter_type == EmitterType.POINT:
            return (px, py, pz)
        elif self.emitter_type == EmitterType.SPHERE:
            radius = self.get_shape_param("radius", 1.0)
            angle1 = state.random_uniform(0, 2 * math.pi)
            angle2 = state.random_uniform(0, math.pi)
            r = radius * (state.random_uniform(0, 1) ** (1.0 / 3.0))
            return (px + r * math.sin(angle2) * math.cos(angle1), py + r * math.sin(angle2) * math.sin(angle1), pz + r * math.cos(angle2))
        elif self.emitter_type == EmitterType.DISC:
            disc_radius = self.get_shape_param("radius", 1.0)
            angle = state.random_uniform(0, 2 * math.pi)
            r = disc_radius * math.sqrt(state.random_uniform(0, 1))
            return (px + r * math.cos(angle), py, pz + r * math.sin(angle))
        elif self.emitter_type == EmitterType.RING:
            ring_radius = self.get_shape_param("radius", 1.0)
            angle = state.random_uniform(0, 2 * math.pi)
            return (px + ring_radius * math.cos(angle), py, pz + ring_radius * math.sin(angle))
        elif self.emitter_type == EmitterType.LINE:
            line_length = self.get_shape_param("length", 1.0)
            t = state.random_uniform(-0.5, 0.5) * line_length
            return (px + t, py, pz)
        elif self.emitter_type == EmitterType.PLANE:
            plane_size = self.get_shape_param("size", 1.0)
            return (px + state.random_uniform(-plane_size / 2, plane_size / 2), py, pz + state.random_uniform(-plane_size / 2, plane_size / 2))
        return (px, py, pz)

    def _compute_spawn_velocity(self, state):
        speed = max(0.0, state.random_uniform(self.initial_speed - self.speed_variance, self.initial_speed + self.speed_variance))
        if self.emitter_type == EmitterType.CONE:
            direction = self.get_shape_param("direction", (0.0, 1.0, 0.0))
            half_angle = self.get_shape_param("half_angle", 0.3)
            return state.random_vector_cone(direction, half_angle, speed)
        elif self.emitter_type in (EmitterType.SPHERE, EmitterType.POINT):
            if self.initial_speed == 0:
                return (0.0, 0.0, 0.0)
            theta = state.random_uniform(0, 2 * math.pi)
            phi = state.random_uniform(0, math.pi)
            return (speed * math.sin(phi) * math.cos(theta), speed * math.sin(phi) * math.sin(theta), speed * math.cos(phi))
        return (0.0, speed, 0.0)

    def _compute_color(self, state):
        v = self.color_variance
        return (
            max(0.0, min(1.0, state.random_uniform(self.color[0] - v, self.color[0] + v))),
            max(0.0, min(1.0, state.random_uniform(self.color[1] - v, self.color[1] + v))),
            max(0.0, min(1.0, state.random_uniform(self.color[2] - v, self.color[2] + v))),
            self.color[3],
        )

    def to_dict(self):
        return {
            "emitter_id": self.emitter_id, "type": self.emitter_type.name,
            "position": list(self.position), "rate": self.rate,
            "lifetime": self.lifetime, "speed": self.initial_speed,
            "color": list(self.color), "max_particles": self.max_particles,
            "active": self._active, "emitted_total": self._emitted_total,
        }
