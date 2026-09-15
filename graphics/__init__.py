"""ASTRA COSMOS Graphics & VFX Layer.

Renderer-independent graphics system providing materials, shaders,
particles, VFX, post-processing, and visual effects for all
celestial phenomena. Designed for eventual Blender integration.
"""

from .materials import Material, MaterialLibrary, Texture, TextureManager
from .shaders import ShaderProgram, ShaderLibrary, UniformBlock
from .particles import ParticleSystem, ParticleEmitter, ParticleState
from .render_state import RenderState, RenderObject, SceneGraph
from .vfx import VFXSystem, VFXEffect
from .effects import (
    BlackHoleVFX,
    WormholeVFX,
    WarpVFX,
    AtmosphereVFX,
    StellarVFX,
    SpaceVFX,
    PlanetaryVFX,
)
from .post_processing import PostProcessPipeline
from .performance import GraphicsLOD, FrustumCuller, DrawBatcher, InstanceManager

__all__ = [
    "Material",
    "MaterialLibrary",
    "Texture",
    "TextureManager",
    "ShaderProgram",
    "ShaderLibrary",
    "UniformBlock",
    "ParticleSystem",
    "ParticleEmitter",
    "ParticleState",
    "RenderState",
    "RenderObject",
    "SceneGraph",
    "VFXSystem",
    "VFXEffect",
    "BlackHoleVFX",
    "WormholeVFX",
    "WarpVFX",
    "AtmosphereVFX",
    "StellarVFX",
    "SpaceVFX",
    "PlanetaryVFX",
    "PostProcessPipeline",
    "GraphicsLOD",
    "FrustumCuller",
    "DrawBatcher",
    "InstanceManager",
]
