"""Shader program abstraction.

Represents a complete shader program (vertex + fragment + optional
geometry/tessellation stages) as a renderer-independent description.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

from .uniform import UniformBlock, UniformType


class ShaderStage(Enum):
    """Shader pipeline stages."""

    VERTEX = auto()
    FRAGMENT = auto()
    GEOMETRY = auto()
    TESS_CONTROL = auto()
    TESS_EVALUATION = auto()
    COMPUTE = auto()


class ShaderSource:
    """Source code or description for a single shader stage."""

    def __init__(
        self,
        stage: ShaderStage,
        glsl_source: Optional[str] = None,
        entry_point: str = "main",
        defines: Optional[Dict[str, str]] = None,
    ):
        self.stage = stage
        self.glsl_source = glsl_source
        self.entry_point = entry_point
        self.defines = defines or {}

    @property
    def has_glsl(self) -> bool:
        return self.glsl_source is not None and len(self.glsl_source) > 0

    def to_dict(self):
        return {
            "stage": self.stage.name,
            "has_glsl": self.has_glsl,
            "entry_point": self.entry_point,
            "defines": self.defines,
        }


class ShaderProgram:
    """Renderer-independent shader program.

    A shader program bundles multiple stages and their uniform
    interface. Concrete renderers compile this into GPU programs
    or execute it on the CPU.
    """

    class BlendMode(Enum):
        OPAQUE = auto()
        ALPHA = auto()
        ADDITIVE = auto()
        MULTIPLY = auto()
        PREMULTIPLIED_ALPHA = auto()

    def __init__(
        self,
        name: str,
        blend_mode: BlendMode = BlendMode.OPAQUE,
        depth_test: bool = True,
        depth_write: bool = True,
        two_sided: bool = False,
    ):
        self.name = name
        self.stages: Dict[ShaderStage, ShaderSource] = {}
        self.uniforms = UniformBlock(name=f"{name}_uniforms")
        self.blend_mode = blend_mode
        self.depth_test = depth_test
        self.depth_write = depth_write
        self.two_sided = two_sided
        self._compiled = False
        self._handle: Any = None

    def add_stage(self, source: ShaderSource) -> None:
        self.stages[source.stage] = source

    def set_vertex_source(self, glsl: str, defines: Optional[Dict[str, str]] = None) -> None:
        self.add_stage(ShaderSource(ShaderStage.VERTEX, glsl, defines=defines))

    def set_fragment_source(self, glsl: str, defines: Optional[Dict[str, str]] = None) -> None:
        self.add_stage(ShaderSource(ShaderStage.FRAGMENT, glsl, defines=defines))

    def set_geometry_source(self, glsl: str, defines: Optional[Dict[str, str]] = None) -> None:
        self.add_stage(ShaderSource(ShaderStage.GEOMETRY, glsl, defines=defines))

    def add_uniform(self, name: str, utype: UniformType, default: Any = None) -> None:
        self.uniforms.add(name, utype, default)

    def set_uniform(self, name: str, value: Any) -> None:
        self.uniforms.set(name, value)

    def get_uniform(self, name: str) -> Any:
        return self.uniforms.get(name)

    @property
    def is_compiled(self) -> bool:
        return self._compiled

    def compile(self, backend: Optional[Any] = None) -> bool:
        if backend is not None and hasattr(backend, "compile_shader"):
            result = backend.compile_shader(self)
            self._compiled = result is not None
            self._handle = result
        else:
            self._compiled = True
        return self._compiled

    @property
    def has_gpu_source(self) -> bool:
        return any(s.has_glsl for s in self.stages.values())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "stages": {s.name: src.to_dict() for s, src in self.stages.items()},
            "blend_mode": self.blend_mode.name,
            "depth_test": self.depth_test,
            "depth_write": self.depth_write,
            "two_sided": self.two_sided,
            "uniforms": self.uniforms.to_dict(),
        }

    def __repr__(self):
        stage_names = [s.name for s in self.stages]
        return (
            f"ShaderProgram(name={self.name!r}, stages={stage_names}, "
            f"compiled={self._compiled})"
        )
