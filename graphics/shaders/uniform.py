"""Uniform block and type definitions for shader parameters."""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


class UniformType(Enum):
    """Supported uniform data types."""

    FLOAT = auto()
    INT = auto()
    BOOL = auto()
    VEC2 = auto()
    VEC3 = auto()
    VEC4 = auto()
    IVEC2 = auto()
    IVEC3 = auto()
    IVEC4 = auto()
    MAT3 = auto()
    MAT4 = auto()
    SAMPLER_2D = auto()
    SAMPLER_CUBE = auto()
    FLOAT_ARRAY = auto()
    VEC3_ARRAY = auto()


class UniformBlock:
    """Named collection of typed uniforms."""

    def __init__(self, name: str):
        self.name = name
        self._types: Dict[str, UniformType] = {}
        self._values: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}
        self._dirty: set = set()

    def add(self, name: str, utype: UniformType, default: Any = None) -> None:
        self._types[name] = utype
        self._defaults[name] = default
        self._values[name] = default
        if default is not None:
            self._dirty.add(name)

    def set(self, name: str, value: Any) -> None:
        if name not in self._types:
            raise KeyError(f"Uniform '{name}' not declared in block '{self.name}'")
        self._values[name] = value
        self._dirty.add(name)

    def get(self, name: str) -> Any:
        return self._values.get(name)

    def get_type(self, name: str) -> Optional[UniformType]:
        return self._types.get(name)

    def reset_to_defaults(self) -> None:
        for name, default in self._defaults.items():
            self._values[name] = default
            self._dirty.add(name)

    def clear_dirty(self) -> None:
        self._dirty.clear()

    @property
    def dirty_uniforms(self) -> List[str]:
        return list(self._dirty)

    @property
    def is_dirty(self) -> bool:
        return len(self._dirty) > 0

    @property
    def names(self) -> List[str]:
        return list(self._types.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "uniforms": {
                name: {
                    "type": self._types[name].name,
                    "value": self._serialize_value(self._values.get(name)),
                    "default": self._serialize_value(self._defaults.get(name)),
                }
                for name in self._types
            },
        }

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float, bool, str)):
            return value
        if isinstance(value, (list, tuple)):
            return list(value)
        return str(value)

    def merge(self, other: "UniformBlock") -> None:
        for name in other._types:
            self._types[name] = other._types[name]
            if name in other._values:
                self._values[name] = other._values[name]
                self._dirty.add(name)
            if name in other._defaults:
                self._defaults[name] = other._defaults[name]

    def __contains__(self, name: str) -> bool:
        return name in self._types

    def __len__(self) -> int:
        return len(self._types)

    def __repr__(self):
        return (
            f"UniformBlock(name={self.name!r}, uniforms={len(self._types)}, "
            f"dirty={len(self._dirty)})"
        )
