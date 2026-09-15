"""Destruction & impact visual effects integration."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..vfx.vfx_effect import VFXEffect, VFXType
from ..particles.particle_emitter import ParticleEmitter, EmitterType
from ..particles.particle_system import ParticleSystem


class DestructionVFX:
    def __init__(self, particle_system, seed=42):
        self._particle_system = particle_system
        self._seed = seed
        self._active_events = {}
        self._fragment_effects = {}
        self._ejecta_emitters = {}
        self._debris_emitters = {}

    def create_impact_vfx(self, event_id, position, impact_velocity, impactor_mass, target_mass, angle_of_impact=0.0, material_color=(0.5, 0.4, 0.35)):
        effects = []
        intensity = min(1.0, (impact_velocity / 10000.0) * (impactor_mass / 1e10) ** 0.3)
        impact_flash = VFXEffect(effect_id=f"{event_id}_flash", vfx_type=VFXType.EXPLOSION, position=position, duration=max(0.1, 1.0 - intensity * 0.5))
        impact_flash.set_param("intensity", intensity)
        impact_flash.set_param("color", (1.0, 0.9, 0.6))
        impact_flash.set_param("flash_radius", 100.0 * intensity)
        impact_flash.add_tag("impact_flash")
        effects.append(impact_flash)
        ejecta_emitter = ParticleEmitter(emitter_id=f"{event_id}_ejecta", emitter_type=EmitterType.CONE, position=position, rate=0, burst_count=min(500, int(50 * intensity)), lifetime=3.0 + intensity * 5.0, lifetime_variance=1.0, initial_size=0.5 + intensity, size_variance=0.3, initial_speed=impact_velocity * 0.01 * intensity, speed_variance=impact_velocity * 0.005, color=(*material_color, 1.0), color_variance=0.15, gravity=(0.0, -9.81, 0.0), max_particles=1000, loop=False)
        ejecta_emitter.set_shape_param("direction", (0.0, 1.0, 0.0))
        ejecta_emitter.set_shape_param("half_angle", 0.8)
        self._particle_system.create_emitter(ejecta_emitter)
        self._ejecta_emitters[event_id] = ejecta_emitter
        debris_emitter = ParticleEmitter(emitter_id=f"{event_id}_debris", emitter_type=EmitterType.SPHERE, position=position, rate=0, burst_count=min(200, int(30 * intensity)), lifetime=5.0 + intensity * 10.0, lifetime_variance=2.0, initial_size=0.3 + intensity * 0.5, size_variance=0.2, initial_speed=impact_velocity * 0.005 * intensity, speed_variance=impact_velocity * 0.002, color=(0.4, 0.35, 0.3, 1.0), color_variance=0.1, gravity=(0.0, -4.905, 0.0), max_particles=500, loop=False)
        debris_emitter.set_shape_param("radius", 10.0)
        self._particle_system.create_emitter(debris_emitter)
        self._debris_emitters[event_id] = debris_emitter
        dust_emitter = ParticleEmitter(emitter_id=f"{event_id}_dust", emitter_type=EmitterType.SPHERE, position=position, rate=0, burst_count=min(300, int(80 * intensity)), lifetime=8.0 + intensity * 15.0, lifetime_variance=3.0, initial_size=1.0 + intensity * 3.0, size_variance=0.5, initial_speed=50.0 * intensity, speed_variance=20.0, color=(0.6, 0.55, 0.45, 0.6), color_variance=0.1, gravity=(0.0, -1.0, 0.0), drag=0.5, max_particles=1000, loop=False)
        dust_emitter.set_shape_param("radius", 5.0)
        self._particle_system.create_emitter(dust_emitter)
        crater_vfx = VFXEffect(effect_id=f"{event_id}_crater", vfx_type=VFXType.IMPACT, position=position, duration=30.0)
        crater_radius = 100.0 * (impactor_mass / 1e8) ** 0.3 * intensity
        crater_vfx.set_param("crater_radius", crater_radius)
        crater_vfx.set_param("crater_depth", crater_radius * 0.2)
        crater_vfx.set_param("ejecta_radius", crater_radius * 3.0)
        crater_vfx.set_param("thermal_intensity", intensity)
        crater_vfx.add_tag("crater")
        effects.append(crater_vfx)
        self._active_events[event_id] = {"position": position, "intensity": intensity, "effects": [e.effect_id for e in effects]}
        return effects

    def create_fragmentation_vfx(self, event_id, fragments, fragmentation_energy):
        effects = []
        for i, fragment in enumerate(fragments[:100]):
            frag_id = f"{event_id}_frag_{i}"
            frag_vfx = VFXEffect(effect_id=frag_id, vfx_type=VFXType.DEBRIS, position=fragment.get("position", (0, 0, 0)), duration=30.0)
            frag_vfx.set_param("velocity", fragment.get("velocity", (0, 0, 0)))
            frag_vfx.set_param("size", fragment.get("size", 1.0))
            frag_vfx.set_param("mass", fragment.get("mass", 1.0))
            frag_vfx.set_param("spin", fragment.get("spin", (0, 0, 0)))
            frag_vfx.add_tag("fragment")
            effects.append(frag_vfx)
        if fragmentation_energy > 0:
            explosion_vfx = VFXEffect(effect_id=f"{event_id}_explosion", vfx_type=VFXType.EXPLOSION, position=fragments[0].get("position", (0, 0, 0)) if fragments else (0, 0, 0), duration=2.0)
            explosion_vfx.set_param("energy", fragmentation_energy)
            explosion_vfx.set_param("intensity", min(1.0, fragmentation_energy / 1e15))
            explosion_vfx.add_tag("explosion")
            effects.append(explosion_vfx)
        return effects

    def create_secondary_impact_vfx(self, event_id, primary_event_id, position, fragment_velocity, fragment_mass):
        return self.create_impact_vfx(event_id=event_id, position=position, impact_velocity=fragment_velocity, impactor_mass=fragment_mass, target_mass=0, material_color=(0.45, 0.4, 0.35))

    def update(self, dt):
        pass

    def get_all_states(self):
        return dict(self._active_events)
