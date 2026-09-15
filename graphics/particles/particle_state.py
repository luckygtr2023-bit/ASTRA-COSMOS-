"""Particle data storage and state management."""

from __future__ import annotations

import random
from typing import List, Optional, Tuple


class ParticleData:
    """Raw particle attribute arrays (Structure-of-Arrays)."""

    __slots__ = (
        "positions", "velocities", "accelerations", "sizes",
        "lifetimes", "ages", "colors", "masses", "rotations",
        "alive", "count", "max_count",
    )

    def __init__(self, max_count: int = 10000):
        self.max_count = max_count
        self.count = 0
        self.positions: List[Tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * max_count
        self.velocities: List[Tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * max_count
        self.accelerations: List[Tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * max_count
        self.sizes: List[float] = [1.0] * max_count
        self.lifetimes: List[float] = [1.0] * max_count
        self.ages: List[float] = [0.0] * max_count
        self.colors: List[Tuple[float, float, float, float]] = [(1.0, 1.0, 1.0, 1.0)] * max_count
        self.masses: List[float] = [1.0] * max_count
        self.rotations: List[float] = [0.0] * max_count
        self.alive: List[bool] = [False] * max_count

    def spawn(self, index, position, velocity, size, lifetime, color, mass=1.0, acceleration=(0.0, 0.0, 0.0)):
        if index < 0 or index >= self.max_count:
            return False
        self.positions[index] = position
        self.velocities[index] = velocity
        self.accelerations[index] = acceleration
        self.sizes[index] = size
        self.lifetimes[index] = lifetime
        self.ages[index] = 0.0
        self.colors[index] = color
        self.masses[index] = mass
        self.rotations[index] = 0.0
        self.alive[index] = True
        self.count += 1
        return True

    def kill(self, index):
        if 0 <= index < self.max_count and self.alive[index]:
            self.alive[index] = False
            self.count -= 1

    def first_free_index(self):
        for i in range(self.max_count):
            if not self.alive[i]:
                return i
        return None

    def compact(self):
        write = 0
        for read in range(self.max_count):
            if self.alive[read]:
                if write != read:
                    self.positions[write] = self.positions[read]
                    self.velocities[write] = self.velocities[read]
                    self.accelerations[write] = self.accelerations[read]
                    self.sizes[write] = self.sizes[read]
                    self.lifetimes[write] = self.lifetimes[read]
                    self.ages[write] = self.ages[read]
                    self.colors[write] = self.colors[read]
                    self.masses[write] = self.masses[read]
                    self.rotations[write] = self.rotations[read]
                    self.alive[write] = True
                write += 1
        for i in range(write, self.max_count):
            self.alive[i] = False
        self.count = write

    def get_alive_indices(self):
        return [i for i in range(self.max_count) if self.alive[i]]


class ParticleState:
    """Deterministic particle state with seeded RNG."""

    def __init__(self, seed: int = 42, max_particles: int = 10000):
        self.seed = seed
        self._rng = random.Random(seed)
        self._data = ParticleData(max_particles)
        self._emitter_states = {}

    @property
    def data(self):
        return self._data

    @property
    def alive_count(self):
        return self._data.count

    @property
    def max_particles(self):
        return self._data.max_count

    def reset(self):
        self._rng = random.Random(self.seed)
        self._data = ParticleData(self._data.max_count)
        self._emitter_states.clear()

    def set_emitter_state(self, emitter_id, state):
        self._emitter_states[emitter_id] = state

    def get_emitter_state(self, emitter_id):
        return self._emitter_states.get(emitter_id, {})

    def random_uniform(self, low=0.0, high=1.0):
        return self._rng.uniform(low, high)

    def random_gaussian(self, mean=0.0, sigma=1.0):
        return self._rng.gauss(mean, sigma)

    def random_vector_sphere(self, radius=1.0):
        import math
        theta = self._rng.uniform(0, 2 * math.pi)
        phi = self._rng.uniform(0, math.pi)
        r = radius * (self._rng.uniform(0, 1) ** (1.0 / 3.0))
        return (r * math.sin(phi) * math.cos(theta), r * math.sin(phi) * math.sin(theta), r * math.cos(phi))

    def random_vector_cone(self, direction, half_angle, length=1.0):
        import math
        angle = self._rng.uniform(0, half_angle)
        phi = self._rng.uniform(0, 2 * math.pi)
        dx = math.sin(angle) * math.cos(phi)
        dy = math.sin(angle) * math.sin(phi)
        dz = math.cos(angle)
        return (dx * length, dy * length, dz * length)

    def serialize(self):
        return {
            "seed": self.seed,
            "alive_count": self.alive_count,
            "emitter_states": dict(self._emitter_states),
        }
