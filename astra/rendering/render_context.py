"""ASTRA Rendering - render context (extensible, renderer-independent).

RenderContext bundles everything a renderer needs to produce a frame
without acquiring simulation authority. It is a derived view, not
authoritative state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from astra.mathematics import Vector3
from astra.rendering.camera import Camera
from astra.rendering.render_state import RenderState
from astra.rendering.exceptions import RenderStateError
from astra.rendering.types import QualityLevel, Viewport, TemporalRenderMode
from astra.rendering.lod import LODConfig


@dataclass
class RenderingConstraints:
    """Constraints guiding quality / performance trade-offs."""

    max_visible_objects: int = 5000
    max_draw_calls: int = 10000
    max_memory_mb: float = 512.0
    min_frame_time_ms: float = 16.6
    allow_shadows: bool = True
    allow_transparency: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.max_visible_objects, int) or self.max_visible_objects <= 0:
            raise RenderStateError("max_visible_objects must be int >0")
        if not isinstance(self.max_draw_calls, int) or self.max_draw_calls <= 0:
            raise RenderStateError("max_draw_calls must be int >0")
        if not isinstance(self.max_memory_mb, (int, float)) or self.max_memory_mb <= 0 or math.isnan(float(self.max_memory_mb)) or math.isinf(float(self.max_memory_mb)):
            raise RenderStateError("max_memory_mb must be finite >0")
        if math.isnan(float(self.min_frame_time_ms)) or math.isinf(float(self.min_frame_time_ms)) or float(self.min_frame_time_ms) <= 0:
            raise RenderStateError("min_frame_time_ms must be finite >0")


@dataclass
class RenderContext:
    """Extensible context for a single render frame.

    Contains references (copied or cloned where isolation required).
    """

    camera: Camera
    viewport: Viewport = field(default_factory=Viewport)
    render_state: Optional[RenderState] = None

    # coordinate frame identity (which simulation frame this render is anchored to)
    coordinate_frame: str = "world"
    render_origin: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))

    # observation / temporal
    observation_state: TemporalRenderMode = TemporalRenderMode.CURRENT
    observation_time_s: float = 0.0
    observer_id: str = "default_observer"

    # quality / LOD
    quality: QualityLevel = QualityLevel.MEDIUM
    lod_config: LODConfig = field(default_factory=lambda: LODConfig())  # type: ignore
    constraints: RenderingConstraints = field(default_factory=RenderingConstraints)

    # optional extensions for future Graphics/VFX bridge
    extensions: Dict[str, Any] = field(default_factory=dict)

    # deterministic seed for any visual randomness (e.g. dithering)
    visual_seed: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.camera, Camera):
            raise RenderStateError(f"camera must be Camera, got {type(self.camera).__name__}")
        if not isinstance(self.viewport, Viewport):
            raise RenderStateError("viewport must be Viewport")
        if self.render_state is not None and not isinstance(self.render_state, RenderState):
            raise RenderStateError("render_state must be RenderState or None")
        if not isinstance(self.coordinate_frame, str) or not self.coordinate_frame:
            raise RenderStateError("coordinate_frame must be non-empty string")
        if not isinstance(self.render_origin, Vector3):
            raise RenderStateError("render_origin must be Vector3")
        if not self.render_origin.is_finite():
            raise RenderStateError(f"render_origin must be finite, got {self.render_origin!r}")
        if not isinstance(self.observation_state, TemporalRenderMode):
            raise RenderStateError(f"observation_state must be TemporalRenderMode")
        if isinstance(self.observation_time_s, bool) or not isinstance(self.observation_time_s, (int, float)):
            raise RenderStateError("observation_time_s must be numeric")
        t = float(self.observation_time_s)
        if math.isnan(t) or math.isinf(t) or t < 0:
            raise RenderStateError(f"observation_time_s must be finite >=0, got {t!r}")
        self.observation_time_s = t
        if not isinstance(self.quality, QualityLevel):
            raise RenderStateError("quality must be QualityLevel")
        if not isinstance(self.visual_seed, int):
            raise RenderStateError("visual_seed must be int")
        if not isinstance(self.observer_id, str) or not self.observer_id:
            raise RenderStateError("observer_id must be non-empty string")

    def clone(self) -> "RenderContext":
        """Isolated copy (camera & render_state cloned)."""
        return RenderContext(
            camera=self.camera.clone(),
            viewport=Viewport(self.viewport.x, self.viewport.y, self.viewport.width, self.viewport.height),
            render_state=self.render_state.clone() if self.render_state is not None else None,
            coordinate_frame=self.coordinate_frame,
            render_origin=Vector3(self.render_origin.x, self.render_origin.y, self.render_origin.z),
            observation_state=self.observation_state,
            observation_time_s=self.observation_time_s,
            observer_id=self.observer_id,
            quality=self.quality,
            lod_config=self.lod_config.clone() if hasattr(self.lod_config, "clone") else self.lod_config,
            constraints=RenderingConstraints(
                max_visible_objects=self.constraints.max_visible_objects,
                max_draw_calls=self.constraints.max_draw_calls,
                max_memory_mb=self.constraints.max_memory_mb,
                min_frame_time_ms=self.constraints.min_frame_time_ms,
                allow_shadows=self.constraints.allow_shadows,
                allow_transparency=self.constraints.allow_transparency,
            ),
            extensions=dict(self.extensions),
            visual_seed=self.visual_seed,
        )

    def with_render_state(self, state: RenderState) -> "RenderContext":
        """Return a new context referencing a different render state."""
        ctx = self.clone()
        ctx.render_state = state.clone()
        ctx.render_origin = Vector3(state.render_origin.x, state.render_origin.y, state.render_origin.z)
        return ctx

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera": self.camera.to_dict(),
            "viewport": {"x": self.viewport.x, "y": self.viewport.y, "width": self.viewport.width, "height": self.viewport.height},
            "coordinate_frame": self.coordinate_frame,
            "render_origin": self.render_origin.to_tuple(),
            "observation_state": self.observation_state.value,
            "observation_time_s": self.observation_time_s,
            "observer_id": self.observer_id,
            "quality": self.quality.value,
            "visual_seed": self.visual_seed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], render_state: Optional[RenderState] = None) -> "RenderContext":
        from astra.rendering.camera import Camera as Cam
        cam = Cam.from_dict(data.get("camera", {}))
        vp_data = data.get("viewport", {"width": 1920, "height": 1080})
        vp = Viewport(int(vp_data.get("x", 0)), int(vp_data.get("y", 0)), int(vp_data.get("width", 1920)), int(vp_data.get("height", 1080)))
        origin = data.get("render_origin", (0, 0, 0))
        return cls(
            camera=cam,
            viewport=vp,
            render_state=render_state,
            coordinate_frame=data.get("coordinate_frame", "world"),
            render_origin=Vector3(float(origin[0]), float(origin[1]), float(origin[2])),
            observation_state=TemporalRenderMode(data.get("observation_state", "CURRENT")),
            observation_time_s=float(data.get("observation_time_s", 0.0)),
            observer_id=data.get("observer_id", "default_observer"),
            quality=QualityLevel(data.get("quality", "MEDIUM")),
            visual_seed=int(data.get("visual_seed", 0)),
        )
