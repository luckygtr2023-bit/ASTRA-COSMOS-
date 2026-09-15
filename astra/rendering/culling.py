"""ASTRA Rendering - visibility and culling (frustum, distance, category).

A simulation object is NEVER removed from simulation because it is culled;
culling only affects the derived RenderState visibility flags.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from astra.mathematics import Vector3
from astra.rendering.camera import Camera
from astra.rendering.render_state import RenderObject
from astra.rendering.types import VisibilityState, RenderObjectKind, LODLevel
from astra.rendering.exceptions import VisibilityError


def _require_finite_vector(v: Vector3, name: str) -> None:
    if not isinstance(v, Vector3):
        raise VisibilityError(f"{name} must be Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise VisibilityError(f"{name} must be finite, got {v!r}")


@dataclass(frozen=True)
class Plane:
    """Plane equation: n·p + d = 0, n unit."""

    normal: Vector3
    d: float

    def distance_to(self, point: Vector3) -> float:
        return self.normal.dot(point) + self.d

    def contains_sphere(self, center: Vector3, radius: float) -> bool:
        # True if sphere is at least partially in front of plane (distance > -radius)
        return self.distance_to(center) >= -radius


@dataclass
class Frustum:
    """Six-plane frustum extracted from camera (deterministic).

    Planes are inward-facing; a point is inside if all distances >=0.
    """

    planes: Tuple[Plane, Plane, Plane, Plane, Plane, Plane]  # near, far, left, right, top, bottom

    @classmethod
    def from_camera(cls, camera: Camera) -> "Frustum":
        if not isinstance(camera, Camera):
            raise VisibilityError(f"camera must be Camera")
        # Extract camera basis
        pos = camera.position
        fwd = camera.get_forward()
        up = camera.get_up()
        right = camera.get_right()

        # For perspective: compute frustum corners then planes
        # Simpler: construct planes analytically (more deterministic than matrix inversion)
        if camera.projection.value == "PERSPECTIVE":
            near = camera.near
            far = camera.far
            fov_y = math.radians(camera.fov_y_deg)
            aspect = camera.viewport.aspect
            tan_half_y = math.tan(fov_y * 0.5)
            tan_half_x = tan_half_y * aspect

            near_center = pos + fwd * near
            far_center = pos + fwd * far

            # near/far planes
            near_plane = Plane(normal=fwd, d=-fwd.dot(near_center))
            far_plane = Plane(normal=Vector3(-fwd.x, -fwd.y, -fwd.z), d=Vector3(-fwd.x, -fwd.y, -fwd.z).dot(far_center) * -1 if False else -Vector3(-fwd.x, -fwd.y, -fwd.z).dot(far_center))
            # Actually far plane normal is -fwd, distance to far_center
            far_normal = Vector3(-fwd.x, -fwd.y, -fwd.z)
            far_plane = Plane(normal=far_normal, d=-far_normal.dot(far_center))

            # side planes: need to go through camera position
            # left plane: contains camera pos and top/bottom of near rect left edge
            # Vector to left edge center: -right * near * tan_half_x + fwd*near
            # Plane normal: cross(edge vectors). For robust, compute normals as normalized cross products
            # Left plane: normal points inside frustum (to the right)
            # Left edge direction: fwd - right*tan_half_x
            left_dir = (fwd - right * tan_half_x).normalized() if (fwd - right * tan_half_x).magnitude() > 1e-12 else fwd
            # left plane normal = up cross left_dir  ??? Let's derive.
            # Alternative simpler: left plane contains camera pos and is perpendicular to plane that includes left_dir and up?
            # Better to compute plane that includes camera pos and the two vertical edges of left side.
            # Normal = ( (fwd*near + up*near*tan_half_y - right*near*tan_half_x) normalized? ) This gets messy.
            # Simpler method: compute plane normals for perspective using angle method.
            # Left plane normal = (fwd * tan_half_x + right).normalized ??? Need correct orientation.
            # Known formula for perspective frustum side normals (in camera space):
            # left:  ( 1, 0, tanHalfX ) -> after transform: right *? Actually camera space: +X right, +Y up, -Z forward.
            # So left plane in camera space: passes through origin, normal = ( -tanHalfY? ) Let's use standard extraction via matrix but analytic for determinism.
            # Easier: compute 4 corner directions and then cross product for each plane.
            near_h = near * tan_half_y
            near_w = near * tan_half_x
            # Near rectangle corners in world space
            near_top = up * near_h
            near_right = right * near_w
            # Directions to corners from camera
            to_tl = (fwd * near - near_right + near_top)  # top-left
            to_tr = (fwd * near + near_right + near_top)
            to_bl = (fwd * near - near_right - near_top)
            to_br = (fwd * near + near_right - near_top)
            # Normalize for plane creation
            # Planes through origin (camera pos): each plane contains camera pos and one edge of far rectangle? Actually side planes contain camera pos and two adjacent frustum edge rays.
            # So left plane contains camera, to_tl and to_bl
            # Right plane contains to_tr and to_br
            # Top plane contains to_tl and to_tr
            # Bottom plane contains to_bl and to_br
            # Compute normals as cross products pointing inward.
            def _norm(cross: Vector3) -> Vector3:
                m = cross.magnitude()
                if m < 1e-12:
                    return cross
                return cross * (1.0 / m)

            # left: to_bl cross to_tl  should point right+forward inside
            left_normal = _norm(to_bl.cross(to_tl))
            # Ensure it points inside (test point slightly forward should be positive)
            if left_normal.dot(fwd) < 0:
                left_normal = left_normal * -1.0
            right_normal = _norm(to_tr.cross(to_br))
            if right_normal.dot(fwd) < 0:
                right_normal = right_normal * -1.0
            bottom_normal = _norm(to_br.cross(to_bl))
            if bottom_normal.dot(fwd) < 0:
                bottom_normal = bottom_normal * -1.0
            top_normal = _norm(to_tl.cross(to_tr))
            if top_normal.dot(fwd) < 0:
                top_normal = top_normal * -1.0

            # Planes through camera position: d = -n·pos
            left_plane = Plane(normal=left_normal, d=-left_normal.dot(pos))
            right_plane = Plane(normal=right_normal, d=-right_normal.dot(pos))
            top_plane = Plane(normal=top_normal, d=-top_normal.dot(pos))
            bottom_plane = Plane(normal=bottom_normal, d=-bottom_normal.dot(pos))

            return cls(planes=(near_plane, far_plane, left_plane, right_plane, top_plane, bottom_plane))
        else:
            # Orthographic: axis-aligned box in camera space
            # Need width = height * aspect
            half_h = camera.ortho_height_m * 0.5
            half_w = half_h * camera.viewport.aspect
            # Near/far centers
            near_center = pos + fwd * camera.near
            far_center = pos + fwd * camera.far
            near_plane = Plane(normal=fwd, d=-fwd.dot(near_center))
            far_normal = Vector3(-fwd.x, -fwd.y, -fwd.z)
            far_plane = Plane(normal=far_normal, d=-far_normal.dot(far_center))
            # Side planes: offset from camera origin by half extents
            left_center = pos - right * half_w
            right_center = pos + right * half_w
            top_center = pos + up * half_h
            bottom_center = pos - up * half_h
            left_plane = Plane(normal=right, d=-right.dot(left_center))
            right_plane = Plane(normal=Vector3(-right.x, -right.y, -right.z), d=-Vector3(-right.x, -right.y, -right.z).dot(right_center))
            top_plane = Plane(normal=Vector3(-up.x, -up.y, -up.z), d=-Vector3(-up.x, -up.y, -up.z).dot(top_center))
            bottom_plane = Plane(normal=up, d=-up.dot(bottom_center))
            return cls(planes=(near_plane, far_plane, left_plane, right_plane, top_plane, bottom_plane))

    def contains_point(self, point: Vector3) -> bool:
        _require_finite_vector(point, "point")
        for plane in self.planes:
            if plane.distance_to(point) < -1e-9:
                return False
        return True

    def contains_sphere(self, center: Vector3, radius: float) -> bool:
        _require_finite_vector(center, "center")
        if math.isnan(radius) or math.isinf(radius) or radius < 0:
            raise VisibilityError(f"radius must be finite >=0, got {radius!r}")
        for plane in self.planes:
            if plane.distance_to(center) < -radius - 1e-9:
                return False
        return True

    def intersects_sphere(self, center: Vector3, radius: float) -> bool:
        return self.contains_sphere(center, radius)


@dataclass
class CullingConfig:
    """Policy for visibility filtering."""

    enable_frustum: bool = True
    enable_distance: bool = True
    enable_category_filter: bool = False
    max_distance_m: float = 1.0e13  # 10 trillion m (~70 AU) default uncapped
    culled_categories: Set[str] = field(default_factory=set)
    visible_categories: Optional[Set[str]] = None  # if set, only these pass
    min_importance: float = 0.0  # 0..1, cull below
    respect_enabled_flag: bool = True
    respect_visible_flag: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.max_distance_m, (int, float)) or math.isnan(float(self.max_distance_m)) or math.isinf(float(self.max_distance_m)) or float(self.max_distance_m) <= 0:
            raise VisibilityError(f"max_distance_m must be finite >0, got {self.max_distance_m!r}")
        if not 0.0 <= self.min_importance <= 1.0:
            raise VisibilityError(f"min_importance must be 0..1, got {self.min_importance!r}")


class VisibilitySystem:
    """Determines per-object visibility; never deletes from simulation."""

    def __init__(self, config: Optional[CullingConfig] = None):
        self.config = config or CullingConfig()

    def classify(self, obj: RenderObject, camera: Camera, frustum: Optional[Frustum] = None) -> VisibilityState:
        """Return VisibilityState for a single object (deterministic)."""
        if not isinstance(obj, RenderObject):
            raise VisibilityError(f"obj must be RenderObject")
        if not isinstance(camera, Camera):
            raise VisibilityError(f"camera must be Camera")

        # Explicit disabled/enabled
        if self.config.respect_enabled_flag and not obj.enabled:
            return VisibilityState.DISABLED
        if self.config.respect_visible_flag and not obj.visible:
            return VisibilityState.HIDDEN

        # Category filtering
        if self.config.enable_category_filter:
            cat = obj.category
            if self.config.visible_categories is not None and cat not in self.config.visible_categories:
                return VisibilityState.CULLED_CATEGORY
            if cat in self.config.culled_categories:
                return VisibilityState.CULLED_CATEGORY

        # Importance
        if obj.importance < self.config.min_importance:
            return VisibilityState.CULLED_CATEGORY

        # Distance cull (using camera-relative distance if available, else world distance to camera)
        dist: Optional[float] = obj.distance_to_camera_m
        if dist is None:
            # fallback: compute from camera and object position (assuming both in same space: render space)
            # If render origin differs, this is approximate; pipeline fills distance_to_camera_m for accuracy.
            dist = (obj.position - camera.position).magnitude()  # type: ignore
        if self.config.enable_distance and dist is not None and dist > self.config.max_distance_m:
            return VisibilityState.CULLED_DISTANCE

        # LOD culled takes precedence (object decided by LODSelector)
        if obj.lod == LODLevel.CULLED:
            return VisibilityState.CULLED_DISTANCE

        # Frustum cull (sphere test)
        if self.config.enable_frustum and frustum is not None:
            # Need camera-relative or render position in same space as camera.
            # Assume frustum was built from camera.position; test obj.position (render) only if render_origin == 0?
            # Our pipeline transforms render_state with camera_relative_position and uses frustum that is world-anchored?
            # For conceptual independence, test camera-relative position against frustum shifted by camera pos?
            # Simplify: use frustum built from same camera; object position expected in world space.
            # If pipeline uses floating-origin, we need to use render_to_world for test? VisibilitySystem callers should pass world-space frustum and world-space object pos.
            # Here we test obj.position directly (callers must ensure coherence).
            # Use sphere cull with bounding radius
            if not frustum.contains_sphere(obj.position, obj.bounding_radius_m):
                return VisibilityState.CULLED_FRUSTUM

        return VisibilityState.VISIBLE

    def update_object_visibility(self, obj: RenderObject, camera: Camera, frustum: Optional[Frustum] = None) -> VisibilityState:
        state = self.classify(obj, camera, frustum)
        obj.visibility = state
        # Also mirror to visible flag for renderable check? Keep original visible flag intact but visibility enum drives is_renderable()
        # is_renderable checks visibility == VISIBLE, so hidden/culled won't render.
        return state

    def filter_visible(self, objects: List[RenderObject], camera: Camera, frustum: Optional[Frustum] = None) -> List[RenderObject]:
        """Return new list of objects classified as VISIBLE (deterministic order preserved)."""
        out: List[RenderObject] = []
        # Build frustum if not supplied and needed
        if frustum is None and self.config.enable_frustum:
            frustum = Frustum.from_camera(camera)
        for obj in objects:
            state = self.classify(obj, camera, frustum)
            if state == VisibilityState.VISIBLE:
                out.append(obj)
        return out

    def apply_to_render_state(self, state, camera: Camera, frustum: Optional[Frustum] = None) -> int:
        """Mutate visibility flags in a RenderState clone (counts culled). Caller should clone if preservation needed."""
        from astra.rendering.render_state import RenderState as RS
        if not isinstance(state, RS):
            raise VisibilityError("state must be RenderState")
        if frustum is None and self.config.enable_frustum:
            frustum = Frustum.from_camera(camera)
        culled = 0
        for oid in state.order:
            obj = state.objects[oid]
            vs = self.classify(obj, camera, frustum)
            obj.visibility = vs
            if vs != VisibilityState.VISIBLE:
                culled += 1
        return culled
