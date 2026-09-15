"""Vertex format definitions for shader input layout."""

from __future__ import annotations

from enum import Enum, auto
from typing import List, Optional, Tuple


class VertexAttributeType(Enum):
    FLOAT = auto()
    VEC2 = auto()
    VEC3 = auto()
    VEC4 = auto()
    INT = auto()
    IVEC2 = auto()
    IVEC3 = auto()
    IVEC4 = auto()
    UBYTE4 = auto()


class VertexAttribute:
    """Describes a single vertex attribute."""

    def __init__(
        self,
        name: str,
        attr_type: VertexAttributeType,
        location: int,
        normalized: bool = False,
        offset: int = 0,
    ):
        self.name = name
        self.attr_type = attr_type
        self.location = location
        self.normalized = normalized
        self.offset = offset

    @property
    def component_count(self) -> int:
        counts = {
            VertexAttributeType.FLOAT: 1,
            VertexAttributeType.VEC2: 2,
            VertexAttributeType.VEC3: 3,
            VertexAttributeType.VEC4: 4,
            VertexAttributeType.INT: 1,
            VertexAttributeType.IVEC2: 2,
            VertexAttributeType.IVEC3: 3,
            VertexAttributeType.IVEC4: 4,
            VertexAttributeType.UBYTE4: 4,
        }
        return counts.get(self.attr_type, 0)

    @property
    def byte_size(self) -> int:
        type_sizes = {
            VertexAttributeType.FLOAT: 4,
            VertexAttributeType.VEC2: 8,
            VertexAttributeType.VEC3: 12,
            VertexAttributeType.VEC4: 16,
            VertexAttributeType.INT: 4,
            VertexAttributeType.IVEC2: 8,
            VertexAttributeType.IVEC3: 12,
            VertexAttributeType.IVEC4: 16,
            VertexAttributeType.UBYTE4: 4,
        }
        return type_sizes.get(self.attr_type, 0)


class VertexFormat:
    """Complete vertex input layout for a shader program."""

    def __init__(self, attributes: Optional[List[VertexAttribute]] = None):
        self.attributes: List[VertexAttribute] = attributes or []
        self._compute_offsets()

    def _compute_offsets(self) -> None:
        offset = 0
        for attr in self.attributes:
            attr.offset = offset
            offset += attr.byte_size

    @property
    def stride(self) -> int:
        return sum(a.byte_size for a in self.attributes)

    def add(
        self,
        name: str,
        attr_type: VertexAttributeType,
        location: Optional[int] = None,
        normalized: bool = False,
    ) -> "VertexFormat":
        loc = location if location is not None else len(self.attributes)
        attr = VertexAttribute(name, attr_type, loc, normalized)
        self.attributes.append(attr)
        self._compute_offsets()
        return self

    def get_attribute(self, name: str) -> Optional[VertexAttribute]:
        for a in self.attributes:
            if a.name == name:
                return a
        return None

    def to_dict(self):
        return {
            "stride": self.stride,
            "attributes": [
                {
                    "name": a.name,
                    "type": a.attr_type.name,
                    "location": a.location,
                    "normalized": a.normalized,
                    "offset": a.offset,
                }
                for a in self.attributes
            ],
        }


POSITION_ONLY = VertexFormat([
    VertexAttribute("position", VertexAttributeType.VEC3, 0),
])

POSITION_NORMAL = VertexFormat([
    VertexAttribute("position", VertexAttributeType.VEC3, 0),
    VertexAttribute("normal", VertexAttributeType.VEC3, 1),
])

POSITION_NORMAL_UV = VertexFormat([
    VertexAttribute("position", VertexAttributeType.VEC3, 0),
    VertexAttribute("normal", VertexAttributeType.VEC3, 1),
    VertexAttribute("uv", VertexAttributeType.VEC2, 2),
])

POSITION_NORMAL_UV_TANGENT = VertexFormat([
    VertexAttribute("position", VertexAttributeType.VEC3, 0),
    VertexAttribute("normal", VertexAttributeType.VEC3, 1),
    VertexAttribute("uv", VertexAttributeType.VEC2, 2),
    VertexAttribute("tangent", VertexAttributeType.VEC3, 3),
])

PARTICLE_VERTEX = VertexFormat([
    VertexAttribute("position", VertexAttributeType.VEC3, 0),
    VertexAttribute("velocity", VertexAttributeType.VEC3, 1),
    VertexAttribute("size", VertexAttributeType.FLOAT, 2),
    VertexAttribute("life", VertexAttributeType.FLOAT, 3),
    VertexAttribute("color", VertexAttributeType.VEC4, 4),
])
