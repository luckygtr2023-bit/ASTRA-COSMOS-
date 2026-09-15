"""ASTRA Rendering - simulation → render-state boundary (pipeline).

This is the authoritative boundary:

    AUTHORITATIVE SIMULATION STATE
                ↓
            RENDER STATE
                ↓
           RENDER CONTEXT
                ↓
             RENDERER
                ↓
           VISUAL OUTPUT

Never mutates authoritative state; produces derived snapshots.
Deterministic when inputs are deterministic (no wall clock, no hidden RNG;
visual seed is explicit).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from astra.mathematics import Vector3, Quaternion

from astra.rendering.camera import Camera
from astra.rendering.coordinates import FloatingOriginRenderer, world_to_render
from astra.rendering.render_state import RenderObject, RenderState, MaterialRef
from astra.rendering.render_context import RenderContext, RenderingConstraints
from astra.rendering.types import QualityLevel, TemporalRenderMode, RenderObjectKind, LODLevel
from astra.rendering.lod import LODConfig, LODSelector
from astra.rendering.culling import VisibilitySystem, CullingConfig, Frustum
from astra.rendering.performance import PerformanceBudget, PerformanceManager
from astra.rendering.lighting import LightingState
from astra.rendering.exceptions import RenderStateError


# ---------------------------------------------------------------------------
# Pipeline configuration
# ---------------------------------------------------------------------------

@dataclass
class PipelineConfig:
    lod_config: LODConfig = field(default_factory=LODConfig)
    culling_config: CullingConfig = field(default_factory=CullingConfig)
    performance_budget: PerformanceBudget = field(default_factory=PerformanceBudget)
    default_quality: QualityLevel = QualityLevel.MEDIUM

    # How to handle very large coordinates (floating origin)
    enable_floating_origin: bool = True
    render_origin: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))

    # Whether to derive camera-relative fields automatically
    populate_camera_relative: bool = True

    def clone(self) -> "PipelineConfig":
        return PipelineConfig(
            lod_config=self.lod_config.clone(),
            culling_config=CullingConfig(
                enable_frustum=self.culling_config.enable_frustum,
                enable_distance=self.culling_config.enable_distance,
                enable_category_filter=self.culling_config.enable_category_filter,
                max_distance_m=self.culling_config.max_distance_m,
                culled_categories=set(self.culling_config.culled_categories),
                visible_categories=set(self.culling_config.visible_categories) if self.culling_config.visible_categories is not None else None,
                min_importance=self.culling_config.min_importance,
                respect_enabled_flag=self.culling_config.respect_enabled_flag,
                respect_visible_flag=self.culling_config.respect_visible_flag,
            ),
            performance_budget=self.performance_budget.clone(),
            default_quality=self.default_quality,
            enable_floating_origin=self.enable_floating_origin,
            render_origin=Vector3(self.render_origin.x, self.render_origin.y, self.render_origin.z),
            populate_camera_relative=self.populate_camera_relative,
        )


@dataclass
class RenderFrame:
    """Output of the pipeline for one tick: render state + context + lighting + batch info."""

    render_state: RenderState
    context: RenderContext
    lighting: Optional[LightingState] = None
    batches: Optional[List[Any]] = None
    visibility_culled: int = 0
    performance_report: Optional[Dict[str, Any]] = None
    temporal_mode: TemporalRenderMode = TemporalRenderMode.CURRENT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "render_state": self.render_state.to_dict(),
            "context": self.context.to_dict(),
            "visibility_culled": self.visibility_culled,
            "temporal_mode": self.temporal_mode.value,
            "performance": self.performance_report,
        }


# ---------------------------------------------------------------------------
# Pipeline core
# ---------------------------------------------------------------------------

class RenderPipeline:
    """Converts authoritative simulation sources to a RenderFrame.

    Sources are supplied as callables / iterables to keep pipeline decoupled
    from concrete World/SceneGraph/EntityManager/Celestial registry types.
    Callers may provide world objects, celestial objects, motion states, etc.
    No simulation state is mutated.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self._lod_selector = LODSelector(self.config.lod_config)
        self._visibility = VisibilitySystem(self.config.culling_config)
        self._performance = PerformanceManager(self.config.performance_budget)
        self._floating = FloatingOriginRenderer(initial_origin=self.config.render_origin)
        self._frame_index = 0

    @property
    def floating_origin(self) -> FloatingOriginRenderer:
        return self._floating

    @property
    def lod_selector(self) -> LODSelector:
        return self._lod_selector

    # -----------------------------------------------------------------------
    # Helpers to build RenderObjects from generic inputs
    # -----------------------------------------------------------------------

    def _validate_world_pos(self, pos: Vector3) -> Vector3:
        if not isinstance(pos, Vector3):
            raise RenderStateError(f"world position must be Vector3, got {type(pos).__name__}")
        if not pos.is_finite():
            raise RenderStateError(f"world position must be finite, got {pos!r}")
        return pos

    def object_from_world_entry(
        self,
        object_id: str,
        world_position: Vector3,
        kind: RenderObjectKind = RenderObjectKind.UNKNOWN,
        category: str = "unknown",
        orientation: Optional[Quaternion] = None,
        scale: Optional[Vector3] = None,
        bounding_radius_m: float = 1.0,
        importance: float = 0.5,
        material: Optional[MaterialRef] = None,
        visible: bool = True,
        enabled: bool = True,
        tags: Tuple[str, ...] = (),
        source_ref: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RenderObject:
        """Create a RenderObject from a generic world entry (helper for callers).

        Caller is responsible for deriving world_position without mutating
        authoritative state (e.g., reading from MotionState or SceneGraph).
        """
        if not isinstance(object_id, str) or not object_id:
            raise RenderStateError("object_id must be non-empty string")
        world_position = self._validate_world_pos(world_position)
        if orientation is None:
            orientation = Quaternion.identity()
        if scale is None:
            scale = Vector3(1.0, 1.0, 1.0)
        if material is None:
            material = MaterialRef(id=f"mat_{kind.value.lower()}")

        # Convert to render space via current floating origin
        render_pos = world_to_render(world_position, self._floating.origin)

        return RenderObject(
            id=object_id,
            name=object_id,
            kind=kind,
            category=category,
            position=render_pos,
            orientation=orientation,
            scale=scale,
            bounding_radius_m=float(bounding_radius_m),
            enabled=enabled,
            visible=visible,
            importance=float(importance),
            material=material,
            tags=tags,
            source_ref=source_ref,
            metadata=dict(metadata or {}),
        )

    # -----------------------------------------------------------------------
    # Main pipeline entry
    # -----------------------------------------------------------------------

    def build_render_state(
        self,
        tick: int,
        simulation_time_s: float,
        world_objects: List[Dict[str, Any]],
        render_origin: Optional[Vector3] = None,
    ) -> RenderState:
        """Build a RenderState from a list of world object dicts (pure, deterministic).

        world_objects entries should have keys:
            id, world_position (Vector3), kind, category, etc.
        This method does not mutate world_objects.
        """
        if render_origin is not None:
            if not isinstance(render_origin, Vector3) or not render_origin.is_finite():
                raise RenderStateError("render_origin must be finite Vector3")
            self._floating.rebase_to(render_origin)
        origin = self._floating.origin
        state = RenderState(tick=tick, simulation_time_s=float(simulation_time_s), render_origin=Vector3(origin.x, origin.y, origin.z))
        # Deterministic insertion: sort by id unless caller preserved order? Use sorted for determinism if not already sorted.
        # We preserve caller order but document that deterministic inputs produce deterministic state.
        for entry in world_objects:
            if not isinstance(entry, dict):
                raise RenderStateError(f"world_objects entry must be dict, got {type(entry).__name__}")
            oid = entry.get("id") or entry.get("object_id")
            if not isinstance(oid, str) or not oid:
                raise RenderStateError(f"entry must have id string, got {oid!r}")
            wpos = entry.get("world_position") or entry.get("position")
            if not isinstance(wpos, Vector3):
                # allow tuple
                if isinstance(wpos, (tuple, list)) and len(wpos) == 3:
                    wpos = Vector3(float(wpos[0]), float(wpos[1]), float(wpos[2]))
                else:
                    raise RenderStateError(f"entry {oid} world_position must be Vector3 or 3-tuple, got {type(wpos).__name__}")
            kind_val = entry.get("kind", RenderObjectKind.UNKNOWN)
            if isinstance(kind_val, str):
                try:
                    kind = RenderObjectKind(kind_val)
                except ValueError:
                    kind = RenderObjectKind.UNKNOWN
            else:
                kind = kind_val if isinstance(kind_val, RenderObjectKind) else RenderObjectKind.UNKNOWN
            category = str(entry.get("category", "unknown"))
            orientation = entry.get("orientation")
            if orientation is not None and not isinstance(orientation, Quaternion):
                orientation = Quaternion.identity()
            scale = entry.get("scale")
            if scale is not None and not isinstance(scale, Vector3):
                scale = Vector3(1.0, 1.0, 1.0)
            radius = float(entry.get("bounding_radius_m", entry.get("radius_m", 1.0)))
            importance = float(entry.get("importance", 0.5))
            material = entry.get("material")
            if material is not None and not isinstance(material, MaterialRef):
                material = MaterialRef(id=str(material))
            visible = bool(entry.get("visible", True))
            enabled = bool(entry.get("enabled", True))
            tags = tuple(entry.get("tags", ()))
            source_ref = entry.get("source_ref")
            metadata = entry.get("metadata")
            obj = self.object_from_world_entry(
                object_id=oid,
                world_position=wpos,
                kind=kind,
                category=category,
                orientation=orientation,
                scale=scale,
                bounding_radius_m=radius,
                importance=importance,
                material=material,
                visible=visible,
                enabled=enabled,
                tags=tags,
                source_ref=source_ref,
                metadata=metadata if isinstance(metadata, dict) else None,
            )
            # copy over damage / temporal hints if present
            if "damage_state" in entry:
                try:
                    from astra.rendering.types import DamageVisualState as DVS
                    obj.damage_state = DVS(entry["damage_state"]) if isinstance(entry["damage_state"], str) else entry["damage_state"]
                except Exception:
                    pass
            if "lod" in entry:
                try:
                    from astra.rendering.types import LODLevel as LL
                    obj.lod = LL(entry["lod"]) if isinstance(entry["lod"], str) else entry["lod"]
                except Exception:
                    pass
            state.add(obj)
        return state

    def apply_camera_and_lod(
        self,
        state: RenderState,
        camera: Camera,
        quality: QualityLevel | None = None,
    ) -> RenderState:
        """Enrich state with camera-relative fields and LOD selection (clone)."""
        if not isinstance(state, RenderState):
            raise RenderStateError("state must be RenderState")
        if not isinstance(camera, Camera):
            raise RenderStateError("camera must be Camera")
        q = quality or self.config.default_quality
        enriched = state.clone()
        # Compute camera-relative via floating origin helper
        # Reconstruct world positions: render_pos + origin
        origin = enriched.render_origin
        # For precise camera-relative we use world_to_camera directly with world positions
        # But enriched positions are already render-space; we compute relative as render - camera_render
        cam_render = camera.position - origin if self.config.enable_floating_origin else camera.position
        # Actually camera.position is world; convert to render
        cam_render = world_to_render(camera.position, origin)
        for oid in enriched.order:
            obj = enriched.objects[oid]
            # camera-relative position
            rel = obj.position - cam_render
            obj.camera_relative_position = rel
            dist = rel.magnitude()
            obj.distance_to_camera_m = dist
            # apparent size
            if dist > 1e-9 and obj.bounding_radius_m > 0:
                ratio = min(1.0, obj.bounding_radius_m / max(dist, obj.bounding_radius_m))
                obj.apparent_size_rad = 2.0 * math.asin(ratio)
            else:
                obj.apparent_size_rad = math.pi if dist <= 1e-9 else 0.0
            # LOD selection (deterministic)
            # Respect explicit LOD if caller set? Overwrite deterministically unless already culled? We select anew each frame for correctness.
            chosen = self._lod_selector.select(
                distance_m=dist,
                bounding_radius_m=obj.bounding_radius_m,
                apparent_size_rad=obj.apparent_size_rad,
                kind=obj.kind,
                quality=q,
                importance=obj.importance,
            )
            obj.lod = chosen
        return enriched

    def apply_visibility(
        self,
        state: RenderState,
        camera: Camera,
        frustum: Optional[Frustum] = None,
    ) -> Tuple[RenderState, int]:
        """Apply frustum/distance/category culling (mutates clone)."""
        if frustum is None and self.config.culling_config.enable_frustum:
            frustum = Frustum.from_camera(camera)
        # Need world-space frustum vs render-space object positions coherence:
        # If floating origin enabled, camera.position is world, frustum planes derived from world camera.
        # Objects in state are in render space (world - origin). For frustum test we need world space.
        # So we either convert object pos back to world for test, or build frustum in render space.
        # Simpler: convert objects to world for frustum test by adding origin back, or create render-space frustum by shifting planes.
        # We'll create a world-space view: pass world object positions to visibility system.
        # To avoid duplicating, we temporarily shift state positions to world for culling, then restore?
        # Easier: For visibility, reconstruct world positions and test against world frustum, then set visibility flag on render-space objects.
        origin = state.render_origin
        world_frustum = frustum
        culled = 0
        for oid in state.order:
            obj = state.objects[oid]
            # For frustum test, compute world position
            world_pos = obj.position + origin if self.config.enable_floating_origin else Vector3(obj.position.x, obj.position.y, obj.position.z)
            # Create a temporary render object copy with world position for classification
            temp = obj.clone()
            temp.position = world_pos
            vs = self._visibility.classify(temp, camera, world_frustum)
            obj.visibility = vs
            if vs != obj.visibility.__class__.VISIBLE if isinstance(vs, str) else vs != __import__("astra.rendering.types", fromlist=["VisibilityState"]).VisibilityState.VISIBLE:
                # actually use enum comparison
                from astra.rendering.types import VisibilityState
                if vs != VisibilityState.VISIBLE:
                    culled += 1
        # The above counting double-counts? Let's recount correctly
        from astra.rendering.types import VisibilityState
        culled = sum(1 for oid in state.order if state.objects[oid].visibility != VisibilityState.VISIBLE)
        # Note is_renderable also checks lod != CULLED and visibility==VISIBLE
        return state, culled

    def apply_performance_budget(self, state: RenderState) -> Tuple[RenderState, Dict[str, Any]]:
        return self._performance.apply_budget(state)

    def build_frame(
        self,
        tick: int,
        simulation_time_s: float,
        world_objects: List[Dict[str, Any]],
        camera: Camera,
        quality: QualityLevel | None = None,
        lighting: Optional[LightingState] = None,
        render_origin: Optional[Vector3] = None,
        temporal_mode: TemporalRenderMode = TemporalRenderMode.CURRENT,
        observed_records: Optional[Dict[str, Any]] = None,
    ) -> RenderFrame:
        """Full pipeline: world -> render state -> camera/lod -> visibility -> budget -> context.

        Does not mutate any simulation inputs.
        """
        self._frame_index += 1
        # 1. Build base render state
        state = self.build_render_state(tick, simulation_time_s, world_objects, render_origin=render_origin)

        # 2. Temporal handling (applied before camera-relative so distances reflect observed positions)
        if temporal_mode != TemporalRenderMode.CURRENT:
            from astra.rendering.temporal import apply_temporal_mode_to_render_state
            try:
                state = apply_temporal_mode_to_render_state(state, temporal_mode, observer_position=camera.position, observed_records=observed_records)
            except Exception:
                # fallback: just mark mode
                state.temporal_mode = temporal_mode

        # 3. Camera & LOD
        state = self.apply_camera_and_lod(state, camera, quality=quality)

        # 4. Visibility
        state, culled = self.apply_visibility(state, camera)

        # 5. Performance budget
        state, perf_report = self.apply_performance_budget(state)

        # 6. Batching
        batches = self._performance.build_batches(state)

        # 7. Context
        q = quality or self.config.default_quality
        viewport = camera.viewport
        context = RenderContext(
            camera=camera.clone(),
            viewport=viewport,
            render_state=state.clone(),
            coordinate_frame="world",
            render_origin=Vector3(state.render_origin.x, state.render_origin.y, state.render_origin.z),
            observation_state=temporal_mode,
            observation_time_s=float(simulation_time_s),
            quality=q,
            lod_config=self.config.lod_config.clone(),
            constraints=RenderingConstraints(
                max_visible_objects=self.config.performance_budget.max_visible_objects,
                max_draw_calls=self.config.performance_budget.max_draw_calls,
                max_memory_mb=self.config.performance_budget.max_memory_mb,
            ),
            visual_seed=int(tick) & 0xFFFFFFFF,
        )

        return RenderFrame(
            render_state=state,
            context=context,
            lighting=lighting.clone() if lighting is not None else None,
            batches=batches,
            visibility_culled=culled,
            performance_report=perf_report,
            temporal_mode=temporal_mode,
        )

    # -----------------------------------------------------------------------
    # Convenience integration helpers for existing ASTRA subsystems
    # -----------------------------------------------------------------------

    def build_frame_from_adapters(
        self,
        tick: int,
        simulation_time_s: float,
        camera: Camera,
        adapters: List[Callable[[], List[Dict[str, Any]]]],
        quality: QualityLevel | None = None,
        lighting: Optional[LightingState] = None,
        render_origin: Optional[Vector3] = None,
        temporal_mode: TemporalRenderMode = TemporalRenderMode.CURRENT,
    ) -> RenderFrame:
        """Build from multiple adapter callables that each return world object dicts.

        Useful for integrating World/SceneGraph/Motion/Celestial adapters without
        coupling pipeline to their concrete types.
        """
        world_objects: List[Dict[str, Any]] = []
        for adapter in adapters:
            if not callable(adapter):
                raise RenderStateError(f"adapter must be callable, got {type(adapter).__name__}")
            chunk = adapter()
            if not isinstance(chunk, list):
                raise RenderStateError(f"adapter must return list, got {type(chunk).__name__}")
            world_objects.extend(chunk)
        return self.build_frame(tick, simulation_time_s, world_objects, camera, quality=quality, lighting=lighting, render_origin=render_origin, temporal_mode=temporal_mode)


# ---------------------------------------------------------------------------
# Adapters for common ASTRA sources (optional, not required)
# ---------------------------------------------------------------------------

def scene_graph_adapter(scene_graph, include_disabled: bool = False) -> Callable[[], List[Dict[str, Any]]]:
    """Return an adapter that reads a SceneGraph (astra.world.scene_graph) into world object dicts."""
    def _adapter() -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            nodes = scene_graph._nodes if hasattr(scene_graph, "_nodes") else {}
            for node_id, node in list(nodes.items()):
                # respect enabled/visible flags if not include_disabled
                if not include_disabled:
                    if not getattr(node, "enabled", True) or not getattr(node, "visible", True):
                        continue
                # world position: via get_world_position if available else local_position
                try:
                    pos = scene_graph.get_world_position(node_id) if hasattr(scene_graph, "get_world_position") else getattr(node, "local_position", (0, 0, 0))
                except Exception:
                    pos = getattr(node, "local_position", (0, 0, 0))
                if isinstance(pos, (tuple, list)):
                    pos = Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
                elif not isinstance(pos, Vector3):
                    pos = Vector3(0, 0, 0)
                out.append({
                    "id": f"scene_{node_id}",
                    "world_position": pos,
                    "kind": RenderObjectKind.UNKNOWN,
                    "category": "scene_node",
                    "visible": bool(getattr(node, "visible", True)),
                    "enabled": bool(getattr(node, "enabled", True)),
                    "source_ref": getattr(node, "object_ref", None) or getattr(node, "entity_ref", None) or node_id,
                    "tags": tuple(getattr(node, "tags", ())),
                    "bounding_radius_m": 1.0,
                    "importance": 0.5,
                })
        except Exception:
            pass
        return out
    return _adapter


def celestial_adapter(celestial_objects: List[Any], world_positions: Dict[str, Vector3]) -> Callable[[], List[Dict[str, Any]]]:
    """Adapter that converts CelestialObjects with world positions to dicts."""
    def _adapter() -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        try:
            from astra.rendering.celestial import celestial_to_render_object
            for obj in celestial_objects:
                oid = getattr(getattr(obj, "identity", None), "canonical_name", str(id(obj)))
                wpos = world_positions.get(oid)
                if wpos is None:
                    continue
                # Use the celestial conversion to get render-friendly defaults, but return dict form for pipeline
                # We could directly produce RenderObject dict via the helper's outputs, but keep pipeline generic
                ro = celestial_to_render_object(obj, wpos)  # uses render_origin 0 internally; pipeline will re-derive
                # ro.position is already render from 0 origin => world pos; we need to pass world pos instead
                out.append({
                    "id": ro.id,
                    "world_position": wpos,
                    "kind": ro.kind,
                    "category": ro.category,
                    "bounding_radius_m": ro.bounding_radius_m,
                    "material": ro.material,
                    "visible": ro.visible,
                    "enabled": ro.enabled,
                    "source_ref": ro.source_ref,
                    "tags": ro.tags,
                    "metadata": ro.metadata,
                })
        except Exception:
            pass
        return out
    return _adapter
