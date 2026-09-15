"""ASTRA Rendering - performance architecture.

Designed for modest hardware (16 GB RAM, integrated graphics, limited VRAM).

Provides:
- budgeting (max objects, memory)
- batching / instancing grouping
- LOD-aware prioritization
- lazy resource handling (handles, not heavy data)
- caching hints
- graceful quality degradation
- bounded allocations
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from astra.mathematics import Vector3
from astra.rendering.exceptions import PerformanceError
from astra.rendering.render_state import RenderObject, RenderState
from astra.rendering.types import LODLevel, RenderObjectKind


def _finite(name: str, v, low=None, high=None) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise PerformanceError(f"{name} must be numeric, got {type(v).__name__}")
    f = float(v)
    if math.isnan(f) or math.isinf(f):
        raise PerformanceError(f"{name} must be finite, got {v!r}")
    if low is not None and f < low:
        raise PerformanceError(f"{name} must be >= {low}, got {f}")
    if high is not None and f > high:
        raise PerformanceError(f"{name} must be <= {high}, got {f}")
    return f


@dataclass
class PerformanceBudget:
    """Hard limits for a frame."""

    max_visible_objects: int = 5000
    max_total_objects: int = 20000
    max_memory_mb: float = 512.0
    max_draw_calls: int = 8000
    max_vertices_per_frame: int = 5_000_000
    target_frame_time_ms: float = 16.6
    # Per-object memory estimate (KB) for bounding
    estimated_kb_per_object: float = 2.0

    def __post_init__(self) -> None:
        if not isinstance(self.max_visible_objects, int) or self.max_visible_objects <= 0:
            raise PerformanceError("max_visible_objects must be int >0")
        if not isinstance(self.max_total_objects, int) or self.max_total_objects <= 0:
            raise PerformanceError("max_total_objects must be int >0")
        if self.max_visible_objects > self.max_total_objects:
            raise PerformanceError("max_visible_objects cannot exceed max_total_objects")
        self.max_memory_mb = _finite("max_memory_mb", self.max_memory_mb, low=1.0)
        if not isinstance(self.max_draw_calls, int) or self.max_draw_calls <= 0:
            raise PerformanceError("max_draw_calls must be int >0")
        self.target_frame_time_ms = _finite("target_frame_time_ms", self.target_frame_time_ms, low=1.0)
        self.estimated_kb_per_object = _finite("estimated_kb_per_object", self.estimated_kb_per_object, low=0.01)

    def estimated_memory_mb(self, object_count: int) -> float:
        return (object_count * self.estimated_kb_per_object) / 1024.0

    def fits_memory(self, object_count: int) -> bool:
        return self.estimated_memory_mb(object_count) <= self.max_memory_mb

    def clone(self) -> "PerformanceBudget":
        return PerformanceBudget(
            max_visible_objects=self.max_visible_objects,
            max_total_objects=self.max_total_objects,
            max_memory_mb=self.max_memory_mb,
            max_draw_calls=self.max_draw_calls,
            max_vertices_per_frame=self.max_vertices_per_frame,
            target_frame_time_ms=self.target_frame_time_ms,
            estimated_kb_per_object=self.estimated_kb_per_object,
        )


@dataclass
class BatchGroup:
    """Objects that can be drawn together (instancing/batching)."""

    kind: RenderObjectKind
    material_id: str
    lod: LODLevel
    object_ids: List[str] = field(default_factory=list)
    instanced: bool = True
    estimated_draw_calls: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.kind, RenderObjectKind):
            raise PerformanceError(f"kind must be RenderObjectKind, got {self.kind!r}")
        if not isinstance(self.lod, LODLevel):
            raise PerformanceError(f"lod must be LODLevel, got {self.lod!r}")
        if not isinstance(self.material_id, str) or not self.material_id:
            raise PerformanceError("material_id must be non-empty string")

    def count(self) -> int:
        return len(self.object_ids)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "material_id": self.material_id,
            "lod": self.lod.value,
            "count": len(self.object_ids),
            "instanced": self.instanced,
            "draw_calls": self.estimated_draw_calls,
        }


class PerformanceManager:
    """Applies budgets via prioritized culling, LOD relaxation, and batching."""

    def __init__(self, budget: Optional[PerformanceBudget] = None):
        self.budget = budget or PerformanceBudget()

    def prioritize(self, state: RenderState) -> List[RenderObject]:
        """Return objects sorted by importance/distance for budget decisions (deterministic)."""
        from astra.rendering.render_state import RenderState as RS
        if not isinstance(state, RS):
            raise PerformanceError("state must be RenderState")
        objs = list(state.iterate())
        # Sort by: importance descending, then distance ascending (closer more important for detail), then kind
        def sort_key(o: RenderObject):
            dist = o.distance_to_camera_m if o.distance_to_camera_m is not None else 0.0
            # NaN guard
            if dist is None or math.isnan(dist) or math.isinf(dist):
                dist = 1e12
            # Use negative importance to get descending
            return (-o.importance, dist, o.kind.value, o.id)
        return sorted(objs, key=sort_key)

    def apply_budget(
        self,
        state: RenderState,
        degrade_lod: bool = True,
    ) -> Tuple[RenderState, Dict[str, Any]]:
        """Enforce budget on a RenderState clone.

        Strategy:
        1. If over max_total_objects, keep most important.
        2. If over max_visible_objects, degrade LOD of least important to IMPOSTOR/CULLED or hide.
        3. Estimate batching afterwards.

        Returns (new_state, report).
        """
        from astra.rendering.render_state import RenderState as RS
        if not isinstance(state, RS):
            raise PerformanceError("state must be RenderState")
        cloned = state.clone()
        total = cloned.count()
        visible = sum(1 for o in cloned.objects.values() if o.is_renderable())

        report: Dict[str, Any] = {
            "input_total": total,
            "input_visible": visible,
            "budget": {
                "max_total": self.budget.max_total_objects,
                "max_visible": self.budget.max_visible_objects,
                "max_memory_mb": self.budget.max_memory_mb,
            },
            "degraded": 0,
            "culled": 0,
            "kept_total": 0,
            "kept_visible": 0,
        }

        # Phase 1: hard total cap - remove least important entirely (from derived state only!)
        if total > self.budget.max_total_objects:
            prioritized = self.prioritize(cloned)
            keep_ids = set(o.id for o in prioritized[: self.budget.max_total_objects])
            remove_ids = [oid for oid in list(cloned.order) if oid not in keep_ids]
            for oid in remove_ids:
                try:
                    cloned.remove(oid)
                    report["culled"] += 1
                except Exception:
                    pass

        # Phase 2: visible cap - degrade LOD or hide least important visible objects
        # Re-evaluate visible after total cull
        if degrade_lod:
            # Sort visible renderable objects by priority ascending (least important first to degrade)
            prioritized_visible = [o for o in self.prioritize(cloned) if o.is_renderable()]
            visible_now = len(prioritized_visible)
            need_to_reduce = max(0, visible_now - self.budget.max_visible_objects)
            degraded = 0
            # degrade least important first to IMPOSTOR then CULLED
            for idx in range(need_to_reduce):
                # pick from least important end
                victim = prioritized_visible[-(idx + 1)] if (idx + 1) <= len(prioritized_visible) else None
                if victim is None:
                    break
                obj = cloned.objects.get(victim.id)
                if obj is None:
                    continue
                # If already impostor, cull; otherwise degrade to impostor
                if obj.lod == LODLevel.IMPOSTOR:
                    obj.lod = LODLevel.CULLED
                    obj.visibility = obj.visibility  # will be caught by is_renderable false
                    # Keep object but mark culled for performance (not removed)
                else:
                    obj.lod = LODLevel.IMPOSTOR
                degraded += 1
            report["degraded"] = degraded
            # If still over, cull impostors beyond budget
            prioritized_visible_after = [o for o in cloned.objects.values() if o.is_renderable()]
            if len(prioritized_visible_after) > self.budget.max_visible_objects:
                # cull lowest importance beyond budget
                sorted_after = sorted(prioritized_visible_after, key=lambda o: (-o.importance, o.distance_to_camera_m or 0))
                to_keep = set(o.id for o in sorted_after[: self.budget.max_visible_objects])
                for o in prioritized_visible_after:
                    if o.id not in to_keep:
                        # mark as culled via LOD
                        cloned.objects[o.id].lod = LODLevel.CULLED
                        report["culled"] += 1

        # Phase 3: memory budget - cull lowest importance objects until fits (graceful degradation)
        # Estimate memory after previous phases
        est_mem = self.budget.estimated_memory_mb(cloned.count())
        if est_mem > self.budget.max_memory_mb:
            # Number to cull to fit memory
            max_allowed = int(self.budget.max_memory_mb * 1024 / max(0.01, self.budget.estimated_kb_per_object))
            max_allowed = max(1, min(max_allowed, cloned.count()))
            if cloned.count() > max_allowed:
                prioritized_all = self.prioritize(cloned)
                keep_ids = set(o.id for o in prioritized_all[:max_allowed])
                remove_ids = [oid for oid in list(cloned.order) if oid not in keep_ids]
                for oid in remove_ids:
                    try:
                        cloned.remove(oid)
                        report["culled"] += 1
                    except Exception:
                        pass

        report["kept_total"] = cloned.count()
        report["kept_visible"] = sum(1 for o in cloned.objects.values() if o.is_renderable())
        report["estimated_memory_mb"] = self.budget.estimated_memory_mb(report["kept_total"])
        report["within_memory"] = report["estimated_memory_mb"] <= self.budget.max_memory_mb
        return cloned, report

    def build_batches(self, state: RenderState) -> List[BatchGroup]:
        """Group renderable objects for instancing/batching (deterministic)."""
        from astra.rendering.render_state import RenderState as RS
        if not isinstance(state, RS):
            raise PerformanceError("state must be RenderState")
        groups: Dict[Tuple[str, str, str], BatchGroup] = {}
        for obj in state.iterate_renderable():
            key = (obj.kind.value, obj.material.id, obj.lod.value)
            if key not in groups:
                groups[key] = BatchGroup(kind=obj.kind, material_id=obj.material.id, lod=obj.lod, instanced=True)
            groups[key].object_ids.append(obj.id)
            # Deterministic order: sort ids later
        # Sort groups deterministically by kind, material, lod order
        def group_sort(kv):
            key, grp = kv
            # lod order for sorting
            from astra.rendering.types import LOD_ORDER
            return (key[0], key[1], LOD_ORDER.get(grp.lod, 99))
        batches = [grp for _, grp in sorted(groups.items(), key=group_sort)]
        for b in batches:
            b.object_ids.sort()  # deterministic
            # Estimate draw calls: 1 per batch if instanced, else 1 per object
            b.estimated_draw_calls = 1 if b.instanced else len(b.object_ids)
        return batches

    def estimate_draw_calls(self, batches: List[BatchGroup]) -> int:
        return sum(b.estimated_draw_calls for b in batches)

    def is_within_budget(self, state: RenderState) -> bool:
        total = state.count()
        visible = sum(1 for o in state.objects.values() if o.is_renderable())
        return (
            total <= self.budget.max_total_objects
            and visible <= self.budget.max_visible_objects
            and self.budget.fits_memory(total)
        )
