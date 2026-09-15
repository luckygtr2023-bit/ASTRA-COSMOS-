"""Shader system for ASTRA COSMOS graphics.

Provides renderer-independent shader abstractions. Since the current
architecture is Python-based without guaranteed GPU access, shaders
are represented as parameterized CPU-side descriptions that concrete
renderers can translate to GLSL, Blender nodes, or software rendering.
"""

from .shader_program import ShaderProgram, ShaderStage, ShaderSource
from .shader_library import ShaderLibrary
from .uniform import UniformBlock, UniformType
from .vertex_format import VertexAttribute, VertexFormat

__all__ = [
    "ShaderProgram",
    "ShaderStage",
    "ShaderSource",
    "ShaderLibrary",
    "UniformBlock",
    "UniformType",
    "VertexAttribute",
    "VertexFormat",
]
