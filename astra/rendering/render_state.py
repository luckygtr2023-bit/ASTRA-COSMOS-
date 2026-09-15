"""ASTRA Rendering - render state (derived, non-authoritative).

Design:
- RenderState is a SNAPSHOT derived from authoritative simulation state.
- It copies data into rendering-friendly structures; mutations do NOT
  propagate back to simulation.
- Deterministic construction when inputs are deterministic.
- Validates finiteness, bounded scales, and isolation.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from astra.mathematics import Vector3, Quaternion
from astra.rendering.exceptions import RenderStateError
from astra.rendering.types import (
    DamageVisualState,
    LODLevel,
    RenderObjectKind,
    TemporalRenderMode,
    VisibilityState,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_finite_vector(v: Vector3, name: str) -> Vector3:
    if not isinstance(v, Vector3):
        raise RenderStateError(f"{name} must be a Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise RenderStateError(f"{name} must be finite, got {v!r}")
    return v


def _require_finite_float(value: float, name: str, low: Optional[float] = None, high: Optional[float] = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RenderStateError(f"{name} must be numeric, got {type(value).__name__}")
    f = float(value)
    if math.isnan(f) or math.isinf(f):
        raise RenderStateError(f"{name} must be finite, got {value!r}")
    if low is not None and f < low:
        raise RenderStateError(f"{name} must be >= {low}, got {f}")
    if high is not None and f > high:
        raise RenderStateError(f"{name} must be <= {high}, got {f}")
    return f


def _require_quaternion(q: Quaternion, name: str) -> Quaternion:
    if not isinstance(q, Quaternion):
        raise RenderStateError(f"{name} must be a Quaternion, got {type(q).__name__}")
    if not q.is_finite():
        raise RenderStateError(f"{name} must be finite, got {q!r}")
    n = q.norm()
    if n == 0.0 or math.isnan(n) or math.isinf(n):
        raise RenderStateError(f"{name} has zero/invalid norm")
    # Normalize to unit if not already (tolerance 1e-6)
    if abs(n - 1.0) > 1e-6:
        return q.normalized()
    return q


# ---------------------------------------------------------------------------
# Material placeholder (renderer-independent)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MaterialRef:
    """Placeholder reference to a material; resolved by future Graphics/VFX."""

    id: str = "default"
    kind: str = "pbr_placeholder"  # allows future mapping without shader logic
    params: Tuple[Tuple[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise RenderStateError("MaterialRef.id must be non-empty string")

    def get(self, key: str, default=None):
        for k, v in self.params:
            if k == key:
                return v
        return default


# ---------------------------------------------------------------------------
# RenderObject
# ---------------------------------------------------------------------------

@dataclass
class RenderObject:
    """Single visual object in render space.

    This is a DERIVED view: position/orientation are already in rendering
    coordinates (camera-relative or floating-origin). Visual-only.
    """

    id: str
    name: str = ""
    kind: RenderObjectKind = RenderObjectKind.UNKNOWN
    category: str = "unknown"  # mirrors celestial ObjectCategory string for filtering

    # -- spatial --
    position: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    orientation: Quaternion = field(default_factory=Quaternion.identity)
    scale: Vector3 = field(default_factory=lambda: Vector3(1.0, 1.0, 1.0))
    bounding_radius_m: float = 1.0

    # -- visibility / state --
    enabled: bool = True
    visible: bool = True
    visibility: VisibilityState = VisibilityState.VISIBLE
    lod: LODLevel = LODLevel.HIGH

    # -- camera-relative (filled by pipeline, optional) --
    camera_relative_position: Optional[Vector3] = None
    distance_to_camera_m: Optional[float] = None
    apparent_size_rad: Optional[float] = None

    # -- visual classification --
    material: MaterialRef = field(default_factory=MaterialRef)

    # -- LOD / importance --
    importance: float = 1.0  # 0..1, higher = more important for culling/budget

    # -- planetary / surface hints --
    atmosphere_params: Optional[Dict[str, Any]] = None
    terrain_params: Optional[Dict[str, Any]] = None
    ocean_params: Optional[Dict[str, Any]] = None

    # -- lighting hints --
    receives_light: bool = True
    casts_shadow: bool = False
    emissive: bool = False

    # -- destruction visual --
    damage_state: DamageVisualState = DamageVisualState.INTACT
    fragment_ids: Tuple[str, ...] = field(default_factory=tuple)
    ejecta_ids: Tuple[str, ...] = field(default_factory=tuple)

    # -- temporal / provenance --
    temporal_mode: TemporalRenderMode = TemporalRenderMode.CURRENT
    observation_time_s: Optional[float] = None
    emission_time_s: Optional[float] = None
    provenance: str = "simulated"
    source_ref: Optional[str] = None  # celestial object id / entity id reference

    # -- generic metadata (renderer-independent) --
    tags: Tuple[str, ...] = field(default_factory=tuple)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise RenderStateError("RenderObject.id must be non-empty string")
        if not isinstance(self.kind, RenderObjectKind):
            raise RenderStateError(f"RenderObject.kind must be RenderObjectKind, got {self.kind!r}")
        if not isinstance(self.category, str):
            raise RenderStateError("RenderObject.category must be string")
        self.position = _require_finite_vector(self.position, "position")
        self.orientation = _require_quaternion(self.orientation, "orientation")
        self.scale = _require_finite_vector(self.scale, "scale")
        if self.scale.x <= 0 or self.scale.y <= 0 or self.scale.z <= 0:
            raise RenderStateError(f"scale must be positive, got {self.scale!r}")
        self.bounding_radius_m = _require_finite_float(self.bounding_radius_m, "bounding_radius_m", low=0.0)
        if self.bounding_radius_m < 0:
            raise RenderStateError("bounding_radius_m must be >= 0")
        if not isinstance(self.lod, LODLevel):
            raise RenderStateError(f"lod must be LODLevel, got {self.lod!r}")
        if not isinstance(self.visibility, VisibilityState):
            raise RenderStateError(f"visibility must be VisibilityState, got {self.visibility!r}")
        if not isinstance(self.damage_state, DamageVisualState):
            raise RenderStateError(f"damage_state must be DamageVisualState, got {self.damage_state!r}")
        if not isinstance(self.temporal_mode, TemporalRenderMode):
            raise RenderStateError(f"temporal_mode must be TemporalRenderMode, got {self.temporal_mode!r}")
        self.importance = _require_finite_float(self.importance, "importance", low=0.0, high=1.0)
        if self.camera_relative_position is not None:
            self.camera_relative_position = _require_finite_vector(self.camera_relative_position, "camera_relative_position")
        if self.distance_to_camera_m is not None:
            self.distance_to_camera_m = _require_finite_float(self.distance_to_camera_m, "distance_to_camera_m", low=0.0)
        if self.apparent_size_rad is not None:
            self.apparent_size_rad = _require_finite_float(self.apparent_size_rad, "apparent_size_rad", low=0.0)

    def clone(self) -> "RenderObject":
        """Deep copy for isolation (rendering never mutates simulation)."""
        return copy.deepcopy(self)

    def is_renderable(self) -> bool:
        return self.enabled and self.visible and self.visibility == VisibilityState.VISIBLE and self.lod != LODLevel.CULLED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind.value,
            "category": self.category,
            "position": self.position.to_tuple(),
            "orientation": (self.orientation.w, self.orientation.x, self.orientation.y, self.orientation.z),
            "scale": self.scale.to_tuple(),
            "bounding_radius_m": self.bounding_radius_m,
            "enabled": self.enabled,
            "visible": self.visible,
            "visibility": self.visibility.value,
            "lod": self.lod.value,
            "importance": self.importance,
            "material": {"id": self.material.id, "kind": self.material.kind},
            "damage_state": self.damage_state.value,
            "temporal_mode": self.temporal_mode.value,
            "provenance": self.provenance,
            "source_ref": self.source_ref,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RenderObject":
        pos = data.get("position", (0, 0, 0))
        ori = data.get("orientation", (1, 0, 0, 0))
        scl = data.get("scale", (1, 1, 1))
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            kind=RenderObjectKind(data.get("kind", "UNKNOWN")),
            category=data.get("category", "unknown"),
            position=Vector3(float(pos[0]), float(pos[1]), float(pos[2])),
            orientation=Quaternion(float(ori[0]), float(ori[1]), float(ori[2]), float(ori[3])),
            scale=Vector3(float(scl[0]), float(scl[1]), float(scl[2])),
            bounding_radius_m=float(data.get("bounding_radius_m", 1.0)),
            enabled=bool(data.get("enabled", True)),
            visible=bool(data.get("visible", True)),
            visibility=VisibilityState(data.get("visibility", "VISIBLE")),
            lod=LODLevel(data.get("lod", "HIGH")),
            importance=float(data.get("importance", 1.0)),
            provenance=data.get("provenance", "simulated"),
            source_ref=data.get("source_ref"),
            tags=tuple(data.get("tags", [])),
        )


# ---------------------------------------------------------------------------
# RenderState
# ---------------------------------------------------------------------------

@dataclass
class RenderState:
    """Snapshot of all renderable objects at a simulation tick/time.

    - Ordered dict semantics via list + dict index for determinism.
    - Bounded: refuses unbounded growth.
    - Isolation: get() returns copies; internal dict never exposed directly.
    """

    tick: int = 0
    simulation_time_s: float = 0.0
    render_origin: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    objects: Dict[str, RenderObject] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)  # deterministic iteration order
    temporal_mode: TemporalRenderMode = TemporalRenderMode.CURRENT
    provenance: str = "simulated"
    max_objects: int = 200_000  # hard cap for performance isolation

    def __post_init__(self) -> None:
        if not isinstance(self.tick, int) or self.tick < 0:
            raise RenderStateError(f"tick must be int >=0, got {self.tick!r}")
        self.simulation_time_s = _require_finite_float(self.simulation_time_s, "simulation_time_s", low=0.0)
        self.render_origin = _require_finite_vector(self.render_origin, "render_origin")
        if not isinstance(self.temporal_mode, TemporalRenderMode):
            raise RenderStateError(f"temporal_mode must be TemporalRenderMode, got {self.temporal_mode!r}")
        if len(self.objects) != len(self.order):
            raise RenderStateError("objects and order length mismatch")
        if len(self.objects) > self.max_objects:
            raise RenderStateError(f"RenderState exceeds max_objects {self.max_objects}")

    # -- mutation (builder only, not simulation) --

    def add(self, obj: RenderObject) -> None:
        if obj.id in self.objects:
            raise RenderStateError(f"RenderObject already exists: {obj.id}")
        if len(self.objects) >= self.max_objects:
            raise RenderStateError(f"RenderState at capacity {self.max_objects}, refusing {obj.id}")
        # clone for isolation
        cloned = obj.clone()
        self.objects[cloned.id] = cloned
        self.order.append(cloned.id)

    def update(self, obj: RenderObject) -> None:
        if obj.id not in self.objects:
            raise RenderStateError(f"RenderObject not found for update: {obj.id}")
        self.objects[obj.id] = obj.clone()

    def remove(self, object_id: str) -> None:
        if object_id not in self.objects:
            raise RenderStateError(f"RenderObject not found: {object_id}")
        del self.objects[object_id]
        self.order.remove(object_id)

    def get(self, object_id: str) -> Optional[RenderObject]:
        obj = self.objects.get(object_id)
        return obj.clone() if obj is not None else None

    def get_or_raise(self, object_id: str) -> RenderObject:
        obj = self.objects.get(object_id)
        if obj is None:
            raise RenderStateError(f"RenderObject not found: {object_id}")
        return obj.clone()

    def contains(self, object_id: str) -> bool:
        return object_id in self.objects

    def count(self) -> int:
        return len(self.objects)

    def iterate(self):
        """Deterministic iteration in insertion order (clones)."""
        for oid in self.order:
            obj = self.objects.get(oid)
            if obj is not None:
                yield obj.clone()

    def iterate_renderable(self):
        for oid in self.order:
            obj = self.objects.get(oid)
            if obj is not None and obj.is_renderable():
                yield obj.clone()

    def clear(self) -> None:
        self.objects.clear()
        self.order.clear()

    def clone(self) -> "RenderState":
        """Deep isolated copy."""
        cloned = RenderState(
            tick=self.tick,
            simulation_time_s=self.simulation_time_s,
            render_origin=Vector3(self.render_origin.x, self.render_origin.y, self.render_origin.z),
            temporal_mode=self.temporal_mode,
            provenance=self.provenance,
            max_objects=self.max_objects,
        )
        for oid in self.order:
            cloned.add(self.objects[oid])  # add clones internally
        return cloned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "simulation_time_s": self.simulation_time_s,
            "render_origin": self.render_origin.to_tuple(),
            "temporal_mode": self.temporal_mode.value,
            "provenance": self.provenance,
            "objects": [self.objects[oid].to_dict() for oid in self.order],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RenderState":
        origin = data.get("render_origin", (0, 0, 0))
        rs = cls(
            tick=int(data.get("tick", 0)),
            simulation_time_s=float(data.get("simulation_time_s", 0.0)),
            render_origin=Vector3(float(origin[0]), float(origin[1]), float(origin[2])),
            temporal_mode=TemporalRenderMode(data.get("temporal_mode", "CURRENT")),
            provenance=data.get("provenance", "simulated"),
        )
        for od in data.get("objects", []):
            rs.add(RenderObject.from_dict(od))
        return rs

    # -- stats --
    def stats(self) -> Dict[str, Any]:
        renderable = sum(1 for o in self.objects.values() if o.is_renderable())
        by_kind: Dict[str, int] = {}
        for o in self.objects.values():
            by_kind[o.kind.value] = by_kind.get(o.kind.value, 0) + 1
        return {
            "total": len(self.objects),
            "renderable": renderable,
            "by_kind": by_kind,
            "tick": self.tick,
            "time": self.simulation_time_s,
        }
