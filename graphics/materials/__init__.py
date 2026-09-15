"""Material system for ASTRA COSMOS graphics.

Provides renderer-independent material definitions that describe
how celestial objects should appear. Materials do not determine
physical simulation - they consume simulation state.
"""

from .material import Material, MaterialProperty
from .material_library import MaterialLibrary
from .texture import Texture, TextureDescriptor
from .texture_manager import TextureManager

__all__ = [
    "Material",
    "MaterialProperty",
    "MaterialLibrary",
    "Texture",
    "TextureDescriptor",
    "TextureManager",
]
