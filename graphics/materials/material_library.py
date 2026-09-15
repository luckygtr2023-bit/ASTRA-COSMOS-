"""Predefined material library for common celestial objects.

Provides factory methods that create physically plausible materials
based on object classification and known astronomical properties.
"""

from __future__ import annotations

from typing import Dict, Optional

from .material import Material, ObjectType


class MaterialLibrary:
    """Registry of named materials with factory methods for common types.

    Materials are created on demand and cached. The library never
    hard-codes individual astronomical objects; instead it provides
    templates keyed by object classification.
    """

    def __init__(self) -> None:
        self._materials: Dict[str, Material] = {}

    def get(self, name: str) -> Optional[Material]:
        return self._materials.get(name)

    def register(self, material: Material) -> None:
        self._materials[material.name] = material

    def remove(self, name: str) -> bool:
        if name in self._materials:
            del self._materials[name]
            return True
        return False

    def list_names(self):
        return list(self._materials.keys())

    def create_planet_material(
        self,
        name: str,
        surface_color: tuple = (0.4, 0.35, 0.3),
        roughness: float = 0.8,
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.PLANET,
            base_color=surface_color,
            roughness=roughness,
            metallic=0.0,
        )
        m.add_tag("planet")
        m.add_tag("solid_surface")
        self.register(m)
        return m

    def create_ocean_material(
        self,
        name: str,
        ocean_color: tuple = (0.05, 0.15, 0.45),
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.PLANET,
            base_color=ocean_color,
            roughness=0.1,
            metallic=0.2,
            transparency=0.3,
        )
        m.add_tag("ocean")
        m.add_tag("liquid")
        m.set_shader_param("fresnel_power", 5.0)
        self.register(m)
        return m

    def create_star_material(
        self,
        name: str,
        temperature: float = 5778.0,
        luminosity: float = 1.0,
        **kwargs,
    ) -> Material:
        r, g, b = self._temperature_to_rgb(temperature)
        intensity = min(luminosity, 100.0)
        m = Material(
            name=name,
            object_type=ObjectType.STAR,
            base_color=(r, g, b),
            emissive_color=(r, g, b),
            emissive_intensity=intensity,
            roughness=0.0,
            metallic=0.0,
        )
        m.add_tag("star")
        m.add_tag("emissive")
        m.set_shader_param("temperature", temperature)
        m.set_shader_param("luminosity", luminosity)
        self.register(m)
        return m

    def create_black_hole_material(
        self,
        name: str,
        mass: float = 1e31,
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.BLACK_HOLE,
            base_color=(0.0, 0.0, 0.0),
            roughness=0.0,
            metallic=0.0,
            transparency=1.0,
        )
        m.add_tag("black_hole")
        m.add_tag("gravity")
        m.set_shader_param("mass", mass)
        m.set_shader_param("event_horizon_radius", self._schwarzschild_radius(mass))
        self.register(m)
        return m

    def create_accretion_disk_material(
        self,
        name: str,
        temperature_inner: float = 1_000_000.0,
        temperature_outer: float = 10_000.0,
        **kwargs,
    ) -> Material:
        r, g, b = self._temperature_to_rgb(temperature_inner)
        m = Material(
            name=name,
            object_type=ObjectType.ACCRETION_DISK,
            base_color=(r, g, b),
            emissive_color=(r, g, b),
            emissive_intensity=50.0,
            roughness=0.0,
            metallic=0.0,
            transparency=0.5,
        )
        m.add_tag("accretion_disk")
        m.add_tag("emissive")
        m.set_shader_param("temperature_inner", temperature_inner)
        m.set_shader_param("temperature_outer", temperature_outer)
        self.register(m)
        return m

    def create_nebula_material(
        self,
        name: str,
        color: tuple = (0.3, 0.1, 0.5),
        density: float = 0.5,
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.NEBULA,
            base_color=color,
            emissive_color=color,
            emissive_intensity=0.3,
            transparency=density,
            roughness=0.0,
        )
        m.add_tag("nebula")
        m.add_tag("volumetric")
        m.set_shader_param("density", density)
        self.register(m)
        return m

    def create_atmosphere_material(
        self,
        name: str,
        scatter_color: tuple = (0.3, 0.5, 0.9),
        density: float = 1.0,
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.ATMOSPHERE,
            base_color=scatter_color,
            transparency=0.8,
            opacity=0.3,
            refractive_index=1.0003,
        )
        m.add_tag("atmosphere")
        m.add_tag("scattering")
        m.set_shader_param("density", density)
        m.set_shader_param("rayleigh_coefficient", scatter_color)
        m.set_shader_param("mie_coefficient", (0.001, 0.001, 0.001))
        self.register(m)
        return m

    def create_wormhole_material(
        self,
        name: str,
        throat_radius: float = 1.0,
        color: tuple = (0.2, 0.4, 0.9),
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.WORMHOLE,
            base_color=color,
            emissive_color=color,
            emissive_intensity=2.0,
            transparency=0.9,
        )
        m.add_tag("wormhole")
        m.add_tag("spacetime")
        m.set_shader_param("throat_radius", throat_radius)
        self.register(m)
        return m

    def create_warp_field_material(
        self,
        name: str,
        field_strength: float = 1.0,
        color: tuple = (0.1, 0.3, 0.8),
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.WARP_FIELD,
            base_color=color,
            emissive_color=color,
            emissive_intensity=1.5,
            transparency=0.95,
        )
        m.add_tag("warp")
        m.add_tag("spacetime")
        m.set_shader_param("field_strength", field_strength)
        self.register(m)
        return m

    def create_debris_material(
        self,
        name: str,
        color: tuple = (0.5, 0.45, 0.4),
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.DEBRIS,
            base_color=color,
            roughness=0.9,
            metallic=0.1,
        )
        m.add_tag("debris")
        m.add_tag("particle")
        self.register(m)
        return m

    def create_comet_material(
        self,
        name: str,
        coma_color: tuple = (0.6, 0.8, 1.0),
        **kwargs,
    ) -> Material:
        m = Material(
            name=name,
            object_type=ObjectType.COMET,
            base_color=(0.6, 0.6, 0.6),
            emissive_color=coma_color,
            emissive_intensity=0.5,
            roughness=0.7,
            transparency=0.4,
        )
        m.add_tag("comet")
        m.add_tag("ice")
        m.add_tag("coma")
        self.register(m)
        return m

    @staticmethod
    def _temperature_to_rgb(temp: float):
        """Convert stellar temperature to approximate RGB color."""
        temp = max(1000.0, min(40000.0, temp))
        t = temp / 100.0
        if t <= 66:
            r = 1.0
        else:
            r = max(0.0, min(1.0, 1.2929361861389791 * ((t - 60) ** -0.1332047592)))
        if t <= 66:
            g = max(0.0, min(1.0, 0.390081582351272 * (t - 46)))
        else:
            g = max(0.0, min(1.0, 1.1298914554071346 * ((t - 60) ** -0.0755148492)))
        if t >= 66:
            b = 0.0
        elif t <= 19:
            b = 0.0
        else:
            b = max(0.0, min(1.0, 0.5432067891123172 * (t - 10)))
        return (r, g, b)

    @staticmethod
    def _schwarzschild_radius(mass: float) -> float:
        """Compute Schwarzschild radius from mass in kg."""
        from config.constants import GRAVITATIONAL_CONSTANT, SPEED_OF_LIGHT
        return (2.0 * GRAVITATIONAL_CONSTANT * mass) / (SPEED_OF_LIGHT ** 2)
