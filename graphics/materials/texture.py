"""Texture abstraction for renderer-independent texture description.

A TextureDescriptor describes what an image resource looks like
without coupling to OpenGL texture IDs or Blender texture nodes.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional, Tuple


class TextureType(Enum):
    """Texture dimensionality and purpose."""

    TEXTURE_2D = auto()
    TEXTURE_CUBEMAP = auto()
    TEXTURE_3D = auto()
    TEXTURE_2D_ARRAY = auto()
    NORMAL_MAP = auto()
    ROUGHNESS_MAP = auto()
    METALLIC_MAP = auto()
    EMISSIVE_MAP = auto()
    OPACITY_MAP = auto()
    HEIGHT_MAP = auto()
    PROCEDURAL = auto()


class Filtering(Enum):
    NEAREST = auto()
    LINEAR = auto()
    TRILINEAR = auto()


class WrapMode(Enum):
    REPEAT = auto()
    CLAMP_TO_EDGE = auto()
    CLAMP_TO_BORDER = auto()
    MIRRORED_REPEAT = auto()


class Texture:
    """Renderer-independent texture descriptor.

    Describes a texture resource by path (or procedural parameters)
    and sampling configuration. Concrete renderers translate this
    into API-specific texture objects.
    """

    def __init__(
        self,
        name: str,
        path: Optional[str] = None,
        texture_type: TextureType = TextureType.TEXTURE_2D,
        size: Optional[Tuple[int, int]] = None,
        channels: int = 4,
        filtering: Filtering = Filtering.LINEAR,
        wrap: WrapMode = WrapMode.REPEAT,
    ):
        self.name = name
        self.path = path
        self.texture_type = texture_type
        self.size = size
        self.channels = channels
        self.filtering = filtering
        self.wrap = wrap
        self.loaded = False
        self._hash: Optional[int] = None

    @property
    def is_procedural(self) -> bool:
        return self.texture_type == TextureType.PROCEDURAL

    def compute_hash(self) -> int:
        if self._hash is None:
            parts = [
                self.name,
                self.path or "",
                self.texture_type.name,
                str(self.size),
                str(self.channels),
                self.filtering.name,
                self.wrap.name,
            ]
            self._hash = hash(tuple(parts))
        return self._hash

    def to_dict(self):
        return {
            "name": self.name,
            "path": self.path,
            "texture_type": self.texture_type.name,
            "size": list(self.size) if self.size else None,
            "channels": self.channels,
            "filtering": self.filtering.name,
            "wrap": self.wrap.name,
        }

    def __eq__(self, other):
        if not isinstance(other, Texture):
            return NotImplemented
        return self.compute_hash() == other.compute_hash()

    def __hash__(self):
        return self.compute_hash()

    def __repr__(self):
        return f"Texture(name={self.name!r}, type={self.texture_type.name})"


class TextureDescriptor:
    """Combines a Texture with slot binding information.

    Used by materials to reference textures with specific roles.
    """

    def __init__(
        self,
        texture: Texture,
        slot: str = "albedo",
        uv_set: int = 0,
        scale: Tuple[float, float] = (1.0, 1.0),
        offset: Tuple[float, float] = (0.0, 0.0),
    ):
        self.texture = texture
        self.slot = slot
        self.uv_set = uv_set
        self.scale = scale
        self.offset = offset

    def to_dict(self):
        return {
            "texture": self.texture.to_dict(),
            "slot": self.slot,
            "uv_set": self.uv_set,
            "scale": list(self.scale),
            "offset": list(self.offset),
        }
