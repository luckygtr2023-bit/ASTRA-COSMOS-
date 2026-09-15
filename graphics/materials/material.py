"""Material abstraction for renderer-independent appearance description.

A Material defines visual properties without coupling to any specific
renderer (OpenGL, Blender, etc.). Each material maps to shader
parameters that a concrete renderer consumes.
"""

from __future__ import annotations

import copy
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class MaterialProperty(Enum):
    """Classification of material property types."""

    BASE_COLOR = auto()
    ROUGHNESS = auto()
    METALLIC = auto()
    EMISSIVE = auto()
    EMISSIVE_INTENSITY = auto()
    TRANSPARENCY = auto()
    OPACITY = auto()
    REFRACTIVE_INDEX = auto()
    ATMOSPHERE_INTERACTION = auto()
    SURFACE_DETAIL = auto()
    CUSTOM = auto()


class ObjectType(Enum):
    """Object classification for material selection."""

    PLANET = auto()
    MOON = auto()
    STAR = auto()
    BLACK_HOLE = auto()
    ASTEROID = auto()
    COMET = auto()
    NEBULA = auto()
    WORMHOLE = auto()
    SPACECRAFT = auto()
    DEBRIS = auto()
    DUST = auto()
    ATMOSPHERE = auto()
    ACCRETION_DISK = auto()
    WARP_FIELD = auto()
    GENERIC = auto()


class Material:
    """Renderer-independent material definition.

    Stores appearance parameters as a flat dictionary of typed
    properties. Concrete renderers translate these into GPU
    uniforms, Blender materials, or other format-specific data.

    Attributes:
        name: Human-readable material identifier.
        object_type: Classification for automatic shader selection.
        base_color: RGB base color in [0, 1].
        roughness: Surface roughness in [0, 1].
        metallic: Metallic factor in [0, 1].
        emissive_color: RGB emissive color in [0, 1].
        emissive_intensity: Emissive brightness multiplier.
        transparency: Transparency factor in [0, 1] (0=opaque).
        opacity: Overall opacity in [0, 1].
        refractive_index: Index of refraction.
        texture_refs: Named texture references (albedo, normal, etc.).
        shader_params: Arbitrary shader uniform overrides.
        tags: Freeform tags for filtering/categorization.
    """

    def __init__(
        self,
        name: str,
        object_type: ObjectType = ObjectType.GENERIC,
        base_color: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        roughness: float = 0.5,
        metallic: float = 0.0,
        emissive_color: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        emissive_intensity: float = 0.0,
        transparency: float = 0.0,
        opacity: float = 1.0,
        refractive_index: float = 1.0,
    ):
        self.name = name
        self.object_type = object_type
        self.base_color = tuple(float(c) for c in base_color)
        self.roughness = float(max(0.0, min(1.0, roughness)))
        self.metallic = float(max(0.0, min(1.0, metallic)))
        self.emissive_color = tuple(float(c) for c in emissive_color)
        self.emissive_intensity = float(max(0.0, emissive_intensity))
        self.transparency = float(max(0.0, min(1.0, transparency)))
        self.opacity = float(max(0.0, min(1.0, opacity)))
        self.refractive_index = float(max(1.0, refractive_index))
        self.texture_refs: Dict[str, str] = {}
        self.shader_params: Dict[str, Any] = {}
        self.tags: List[str] = []

    @property
    def is_emissive(self) -> bool:
        return self.emissive_intensity > 0.0

    @property
    def is_transparent(self) -> bool:
        return self.transparency > 0.0 or self.opacity < 1.0

    @property
    def is_metallic(self) -> bool:
        return self.metallic > 0.5

    def set_texture(self, slot: str, texture_path: str) -> None:
        """Bind a texture path to a named slot (e.g. 'albedo', 'normal')."""
        self.texture_refs[slot] = texture_path

    def set_shader_param(self, key: str, value: Any) -> None:
        """Set an arbitrary shader uniform override."""
        self.shader_params[key] = value

    def add_tag(self, tag: str) -> None:
        if tag not in self.tags:
            self.tags.append(tag)

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def clone(self, new_name: Optional[str] = None) -> "Material":
        """Create a deep copy of this material with an optional new name."""
        m = copy.deepcopy(self)
        if new_name:
            m.name = new_name
        return m

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a renderer-agnostic dictionary.

        This is the primary interface for concrete renderers and
        the future Blender bridge.
        """
        return {
            "name": self.name,
            "object_type": self.object_type.name,
            "base_color": list(self.base_color),
            "roughness": self.roughness,
            "metallic": self.metallic,
            "emissive_color": list(self.emissive_color),
            "emissive_intensity": self.emissive_intensity,
            "transparency": self.transparency,
            "opacity": self.opacity,
            "refractive_index": self.refractive_index,
            "texture_refs": dict(self.texture_refs),
            "shader_params": dict(self.shader_params),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Material":
        """Deserialize from a dictionary."""
        m = cls(
            name=data["name"],
            object_type=ObjectType[data.get("object_type", "GENERIC")],
            base_color=tuple(data.get("base_color", [1.0, 1.0, 1.0])),
            roughness=data.get("roughness", 0.5),
            metallic=data.get("metallic", 0.0),
            emissive_color=tuple(data.get("emissive_color", [0.0, 0.0, 0.0])),
            emissive_intensity=data.get("emissive_intensity", 0.0),
            transparency=data.get("transparency", 0.0),
            opacity=data.get("opacity", 1.0),
            refractive_index=data.get("refractive_index", 1.0),
        )
        m.texture_refs = data.get("texture_refs", {})
        m.shader_params = data.get("shader_params", {})
        m.tags = data.get("tags", [])
        return m

    def __repr__(self) -> str:
        return (
            f"Material(name={self.name!r}, type={self.object_type.name}, "
            f"emissive={self.is_emissive}, transparent={self.is_transparent})"
        )
