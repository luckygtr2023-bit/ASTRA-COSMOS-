"""Space background visual effects."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from ..vfx.vfx_effect import VFXEffect, VFXType


class SpaceVFX(VFXEffect):
    def __init__(self, effect_id, starfield_density=1.0, nebula_density=0.3, cosmic_dust_density=0.1, background_brightness=0.02, star_count=10000, seed=42):
        super().__init__(effect_id=effect_id, vfx_type=VFXType.BACKGROUND, duration=-1.0)
        self.starfield_density = max(0.0, min(1.0, starfield_density))
        self.nebula_density = max(0.0, min(1.0, nebula_density))
        self.cosmic_dust_density = max(0.0, min(1.0, cosmic_dust_density))
        self.background_brightness = background_brightness
        self.star_count = star_count
        self._seed = seed
        self._nebulae = []
        self._dust_clouds = []
        self._galaxies = []
        self.add_tag("space_background")
        self._generate_starfield()
        self._generate_nebulae()

    def _generate_starfield(self):
        import random
        rng = random.Random(self._seed)
        self._stars = []
        for _ in range(self.star_count):
            self._stars.append({"position": (rng.uniform(-180, 180), rng.uniform(-90, 90)), "brightness": rng.uniform(0.2, 1.0), "temperature": rng.uniform(3000, 30000), "size": rng.uniform(0.5, 2.0)})

    def _generate_nebulae(self):
        import random
        rng = random.Random(self._seed + 1)
        nebula_count = max(1, int(10 * self.nebula_density))
        for i in range(nebula_count):
            self._nebulae.append({"id": f"nebula_{i}", "position": (rng.uniform(-1000, 1000), rng.uniform(-500, 500), rng.uniform(-1000, 1000)), "radius": rng.uniform(50, 300), "color": (rng.uniform(0.1, 0.8), rng.uniform(0.05, 0.5), rng.uniform(0.2, 0.9)), "density": rng.uniform(0.1, 0.8), "type": rng.choice(["emission", "reflection", "dark"])})

    def add_nebula(self, position, radius=100.0, color=(0.3, 0.1, 0.5), density=0.5, nebula_type="emission"):
        self._nebulae.append({"id": f"nebula_{len(self._nebulae)}", "position": position, "radius": radius, "color": color, "density": density, "type": nebula_type})

    def add_galaxy(self, position, size=100.0, spiral_arms=4, rotation_speed=0.001):
        self._galaxies.append({"id": f"galaxy_{len(self._galaxies)}", "position": position, "size": size, "spiral_arms": spiral_arms, "rotation_speed": rotation_speed})

    @property
    def visible_nebula_count(self):
        return len(self._nebulae)

    def get_state(self):
        base = super().get_state()
        base.update({"starfield_density": self.starfield_density, "star_count": self.star_count, "background_brightness": self.background_brightness, "nebulae": self._nebulae, "nebula_count": len(self._nebulae), "galaxies": self._galaxies, "cosmic_dust_density": self.cosmic_dust_density})
        return base
