"""Particle system manager."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .particle_emitter import ParticleEmitter
from .particle_state import ParticleData, ParticleState


class ParticleSystem:
    """Manages all particle emitters and the shared particle buffer."""

    def __init__(self, seed=42, max_particles=50000, max_effects=128):
        self.state = ParticleState(seed=seed, max_particles=max_particles)
        self.max_effects = max_effects
        self._emitters: Dict[str, ParticleEmitter] = {}
        self._groups: Dict[str, List[str]] = {}
        self._global_gravity = (0.0, 0.0, 0.0)
        self._global_drag = 0.0
        self._pre_update_hooks = []
        self._post_update_hooks = []

    @property
    def alive_count(self):
        return self.state.alive_count

    @property
    def emitter_count(self):
        return len(self._emitters)

    def set_global_gravity(self, gravity):
        self._global_gravity = gravity

    def set_global_drag(self, drag):
        self._global_drag = drag

    def add_pre_update_hook(self, hook):
        self._pre_update_hooks.append(hook)

    def add_post_update_hook(self, hook):
        self._post_update_hooks.append(hook)

    def create_emitter(self, emitter):
        if len(self._emitters) >= self.max_effects:
            raise RuntimeError(f"Maximum emitter count ({self.max_effects}) reached.")
        self._emitters[emitter.emitter_id] = emitter

    def remove_emitter(self, emitter_id):
        if emitter_id in self._emitters:
            del self._emitters[emitter_id]
            for group_emitters in self._groups.values():
                if emitter_id in group_emitters:
                    group_emitters.remove(emitter_id)
            return True
        return False

    def get_emitter(self, emitter_id):
        return self._emitters.get(emitter_id)

    def create_group(self, group_name):
        if group_name not in self._groups:
            self._groups[group_name] = []

    def add_to_group(self, group_name, emitter_id):
        if group_name not in self._groups:
            self.create_group(group_name)
        self._groups[group_name].append(emitter_id)

    def remove_group(self, group_name):
        self._groups.pop(group_name, None)

    def get_group_emitters(self, group_name):
        ids = self._groups.get(group_name, [])
        return [self._emitters[eid] for eid in ids if eid in self._emitters]

    def reset_group(self, group_name):
        for emitter in self.get_group_emitters(group_name):
            emitter.reset()

    def reset_all(self):
        self.state.reset()
        for emitter in self._emitters.values():
            emitter.reset()

    def update(self, dt):
        for hook in self._pre_update_hooks:
            hook(dt)
        total_spawned = 0
        for emitter in self._emitters.values():
            spawned = emitter.update(dt, self.state)
            total_spawned += spawned
        data = self.state.data
        for i in range(data.max_count):
            if not data.alive[i]:
                continue
            data.ages[i] += dt
            if data.ages[i] >= data.lifetimes[i]:
                data.kill(i)
                continue
            vx, vy, vz = data.velocities[i]
            ax, ay, az = data.accelerations[i]
            gx, gy, gz = self._global_gravity
            new_vx = vx + (ax + gx) * dt
            new_vy = vy + (ay + gy) * dt
            new_vz = vz + (az + gz) * dt
            if self._global_drag > 0:
                drag_factor = max(0.0, 1.0 - self._global_drag * dt)
                new_vx *= drag_factor
                new_vy *= drag_factor
                new_vz *= drag_factor
            data.velocities[i] = (new_vx, new_vy, new_vz)
            px, py, pz = data.positions[i]
            data.positions[i] = (px + new_vx * dt, py + new_vy * dt, pz + new_vz * dt)
        for hook in self._post_update_hooks:
            hook(dt)
        if data.count < data.max_count * 0.5:
            data.compact()
        return total_spawned

    def get_render_data(self):
        result = {}
        for emitter_id, emitter in self._emitters.items():
            if not emitter.is_active and emitter.emitted_total == 0:
                continue
            particles = []
            data = self.state.data
            for i in range(data.max_count):
                if not data.alive[i]:
                    continue
                age = data.ages[i]
                lt = data.lifetimes[i]
                life = max(0.0, 1.0 - (age / lt)) if lt > 0 else 0.0
                particles.append({
                    "position": data.positions[i], "velocity": data.velocities[i],
                    "size": data.sizes[i], "life": life, "color": data.colors[i],
                })
            if particles:
                result[emitter_id] = particles
        return result

    def serialize(self):
        return {
            "seed": self.state.seed,
            "emitters": {eid: em.to_dict() for eid, em in self._emitters.items()},
            "groups": dict(self._groups),
            "global_gravity": self._global_gravity,
            "global_drag": self._global_drag,
        }

    def __repr__(self):
        return f"ParticleSystem(emitters={len(self._emitters)}, alive={self.alive_count}/{self.state.max_particles})"
