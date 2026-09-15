"""ASTRA Rendering - camera architecture.

Single camera model that scales from spacecraft to galaxy structures.
No separate incompatible per-scale cameras; precision is handled via
double-precision world coordinates plus floating-origin support elsewhere.

Features:
- position / orientation / target
- FOV, aspect, near/far
- projection (perspective / orthographic)
- viewport
- tracking / following
- camera-relative coordinate helpers
- frustum extraction for culling (delegates to culling module)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from astra.mathematics import Vector3, Quaternion
from astra.mathematics.vectors import Vector3 as Vec3
from astra.rendering.exceptions import CameraError
from astra.rendering.types import ProjectionType, Viewport
from astra.rendering.coordinates import world_to_camera_relative


def _require_finite_vector(v: Vector3, name: str) -> Vector3:
    if not isinstance(v, Vector3):
        raise CameraError(f"{name} must be Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise CameraError(f"{name} must be finite, got {v!r}")
    return v


def _require_quaternion(q: Quaternion, name: str) -> Quaternion:
    if not isinstance(q, Quaternion):
        raise CameraError(f"{name} must be Quaternion, got {type(q).__name__}")
    if not q.is_finite():
        raise CameraError(f"{name} must be finite, got {q!r}")
    n = q.norm()
    if n == 0.0 or math.isnan(n) or math.isinf(n):
        raise CameraError(f"{name} has invalid norm")
    if abs(n - 1.0) > 1e-6:
        return q.normalized()
    return q


def _require_finite_float(v, name: str, low=None, high=None, allow_inf=False) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise CameraError(f"{name} must be numeric, got {type(v).__name__}")
    f = float(v)
    if math.isnan(f):
        raise CameraError(f"{name} must not be NaN, got {v!r}")
    if not allow_inf and math.isinf(f):
        raise CameraError(f"{name} must be finite, got {v!r}")
    if low is not None and f < low:
        raise CameraError(f"{name} must be >= {low}, got {f}")
    if high is not None and f > high:
        raise CameraError(f"{name} must be <= {high}, got {f}")
    return f


class CameraMode(str, Enum):
    FREE = "FREE"
    ORBIT = "ORBIT"
    TRACKING = "TRACKING"
    FOLLOW = "FOLLOW"
    FIXED = "FIXED"


@dataclass
class Camera:
    """Renderer-independent camera.

    - position: world-space absolute (double) — authoritative eye location
    - orientation: unit quaternion body->world
    - fov_y_deg: vertical field of view in degrees (perspective)
    - near / far: clipping planes >0, far > near
    - projection: perspective or orthographic
    - viewport: pixel rectangle
    - target: optional look-at point for orbit/tracking
    """

    position: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 10.0))
    orientation: Quaternion = field(default_factory=Quaternion.identity)
    fov_y_deg: float = 60.0
    near: float = 0.1
    far: float = 1.0e12  # large to cover star-system scale; vice versa via LOD
    projection: ProjectionType = ProjectionType.PERSPECTIVE
    viewport: Viewport = field(default_factory=Viewport)
    target: Optional[Vector3] = None
    mode: CameraMode = CameraMode.FREE
    follow_target_id: Optional[str] = None  # object id to follow (entity/celestial ref)

    # orthographic size (when projection == ORTHOGRAPHIC)
    ortho_height_m: float = 100.0

    def __post_init__(self) -> None:
        self.position = _require_finite_vector(self.position, "position")
        self.orientation = _require_quaternion(self.orientation, "orientation")
        self.fov_y_deg = _require_finite_float(self.fov_y_deg, "fov_y_deg", low=1.0, high=179.0)
        self.near = _require_finite_float(self.near, "near", low=1e-9)
        self.far = _require_finite_float(self.far, "far", low=self.near * 1.01)
        if not isinstance(self.projection, ProjectionType):
            raise CameraError(f"projection must be ProjectionType, got {self.projection!r}")
        if not isinstance(self.mode, CameraMode):
            raise CameraError(f"mode must be CameraMode, got {self.mode!r}")
        if not isinstance(self.viewport, Viewport):
            raise CameraError(f"viewport must be Viewport")
        if self.target is not None:
            self.target = _require_finite_vector(self.target, "target")
        if self.projection == ProjectionType.ORTHOGRAPHIC:
            self.ortho_height_m = _require_finite_float(self.ortho_height_m, "ortho_height_m", low=1e-9)
        if self.follow_target_id is not None and not isinstance(self.follow_target_id, str):
            raise CameraError("follow_target_id must be string or None")
        # far can be enormous — allow up to 1e18 (cosmic scale) but must be finite
        if math.isinf(self.far) or math.isnan(self.far):
            raise CameraError(f"far must be finite, got {self.far!r}")

    # -- basic operations --

    def set_position(self, pos: Vector3) -> None:
        self.position = _require_finite_vector(pos, "position")

    def set_orientation(self, q: Quaternion) -> None:
        self.orientation = _require_quaternion(q, "orientation")

    def look_at(self, target: Vector3, up: Vector3 = Vector3(0.0, 1.0, 0.0)) -> None:
        """Orient camera to look at target from current position.

        Uses right-handed coordinates: -Z is forward in view space.
        """
        target = _require_finite_vector(target, "target")
        up = _require_finite_vector(up, "up")
        if up.is_zero():
            raise CameraError("up vector must not be zero")
        self.target = Vector3(target.x, target.y, target.z)
        forward = (target - self.position)
        dist = forward.magnitude()
        if dist < 1e-12:
            raise CameraError("look_at: camera and target coincide")
        forward = forward * (1.0 / dist)
        # Compute orthonormal basis
        # forward is -Z in view, up roughly world Y
        # right = forward cross up
        right = forward.cross(up)
        rn = right.magnitude()
        if rn < 1e-12:
            # forward parallel to up, pick alternative up
            alt = Vector3(1.0, 0.0, 0.0) if abs(forward.y) < 0.9 else Vector3(0.0, 0.0, 1.0)
            right = forward.cross(alt)
            rn = right.magnitude()
            if rn < 1e-12:
                raise CameraError("look_at: degenerate basis")
        right = right * (1.0 / rn)
        true_up = right.cross(forward)
        # Build rotation matrix columns: right, true_up, -forward correspond to world?
        # Orientation maps camera local -> world, so we need quaternion from basis.
        # For simplicity, use iterative quaternion construction.
        # Use matrix -> quaternion via trace method (right-handed).
        # Basis in world: [right, true_up, -forward] ? Actually forward is -Z view, so world Z is -forward.
        # So rotation matrix R such that R * (1,0,0)=right, R*(0,1,0)=true_up, R*(0,0,1)=-forward
        # Columns are right, true_up, -forward
        m00, m01, m02 = right.x, true_up.x, -forward.x
        m10, m11, m12 = right.y, true_up.y, -forward.y
        m20, m21, m22 = right.z, true_up.z, -forward.z
        trace = m00 + m11 + m22
        if trace > 0:
            s = 0.5 / math.sqrt(trace + 1.0)
            w = 0.25 / s
            x = (m21 - m12) * s
            y = (m02 - m20) * s
            z = (m10 - m01) * s
        elif m00 > m11 and m00 > m22:
            s = 2.0 * math.sqrt(1.0 + m00 - m11 - m22)
            w = (m21 - m12) / s
            x = 0.25 * s
            y = (m01 + m10) / s
            z = (m02 + m20) / s
        elif m11 > m22:
            s = 2.0 * math.sqrt(1.0 + m11 - m00 - m22)
            w = (m02 - m20) / s
            x = (m01 + m10) / s
            y = 0.25 * s
            z = (m12 + m21) / s
        else:
            s = 2.0 * math.sqrt(1.0 + m22 - m00 - m11)
            w = (m10 - m01) / s
            x = (m02 + m20) / s
            y = (m12 + m21) / s
            z = 0.25 * s
        q = Quaternion(w, x, y, z)
        n = q.norm()
        if n == 0.0 or math.isnan(n) or math.isinf(n):
            raise CameraError("look_at produced degenerate quaternion")
        self.orientation = q.normalized()

    def get_forward(self) -> Vector3:
        """World-space forward direction (-Z in view)."""
        # Rotate local -Z = (0,0,-1) by orientation
        return self.orientation.rotate(Vector3(0.0, 0.0, -1.0))

    def get_up(self) -> Vector3:
        return self.orientation.rotate(Vector3(0.0, 1.0, 0.0))

    def get_right(self) -> Vector3:
        return self.orientation.rotate(Vector3(1.0, 0.0, 0.0))

    def get_view_direction(self) -> Vector3:
        if self.target is not None:
            d = self.target - self.position
            m = d.magnitude()
            if m > 1e-12:
                return d * (1.0 / m)
        return self.get_forward()

    def move(self, delta: Vector3) -> None:
        delta = _require_finite_vector(delta, "delta")
        self.position = self.position + delta
        if self.target is not None:
            self.target = self.target + delta

    def orbit(self, yaw_rad: float, pitch_rad: float, distance: Optional[float] = None) -> None:
        """Orbit around target (if target set) or yaw/pitch in place."""
        yaw_rad = _require_finite_float(yaw_rad, "yaw_rad")
        pitch_rad = _require_finite_float(pitch_rad, "pitch_rad")
        if self.target is None:
            # yaw around world up, pitch around camera right
            q_yaw = Quaternion.from_axis_angle(Vector3(0.0, 1.0, 0.0), yaw_rad)
            q_pitch = Quaternion.from_axis_angle(self.get_right(), pitch_rad)
            self.orientation = (q_yaw * q_pitch * self.orientation).normalized()
            return
        # orbit around target
        if distance is not None:
            distance = _require_finite_float(distance, "distance", low=1e-9)
        else:
            distance = (self.position - self.target).magnitude()
            if distance < 1e-9:
                distance = 10.0
        # apply yaw/pitch to offset vector
        offset = self.position - self.target
        # yaw around world up
        q_yaw = Quaternion.from_axis_angle(Vector3(0.0, 1.0, 0.0), yaw_rad)
        offset = q_yaw.rotate(offset)
        # pitch around current right
        right = offset.cross(Vector3(0.0, 1.0, 0.0))
        if right.magnitude() < 1e-9:
            right = Vector3(1.0, 0.0, 0.0)
        else:
            right = right.normalized()
        q_pitch = Quaternion.from_axis_angle(right, pitch_rad)
        offset = q_pitch.rotate(offset)
        # renormalize to distance
        m = offset.magnitude()
        if m > 1e-12:
            offset = offset * (distance / m)
        self.position = self.target + offset
        self.look_at(self.target)

    def set_perspective(self, fov_y_deg: float, near: float, far: float) -> None:
        fov_y_deg = _require_finite_float(fov_y_deg, "fov_y_deg", low=1.0, high=179.0)
        near = _require_finite_float(near, "near", low=1e-9)
        far = _require_finite_float(far, "far", low=near*1.01)
        self.fov_y_deg = fov_y_deg
        self.near = near
        self.far = far
        self.projection = ProjectionType.PERSPECTIVE

    def set_orthographic(self, height_m: float, near: float, far: float) -> None:
        height_m = _require_finite_float(height_m, "ortho_height_m", low=1e-9)
        near = _require_finite_float(near, "near", low=1e-9)
        far = _require_finite_float(far, "far", low=near*1.01)
        self.ortho_height_m = height_m
        self.near = near
        self.far = far
        self.projection = ProjectionType.ORTHOGRAPHIC

    def world_to_camera(self, world_pos: Vector3) -> Vector3:
        """Transform world position to camera-relative vector."""
        return world_to_camera_relative(world_pos, self.position)

    def distance_to(self, world_pos: Vector3) -> float:
        _require_finite_vector(world_pos, "world_pos")
        return (world_pos - self.position).magnitude()

    def apparent_angular_size(self, world_pos: Vector3, radius_m: float) -> float:
        """Angular radius in radians (approximate) for LOD decisions."""
        radius_m = _require_finite_float(radius_m, "radius_m", low=0.0)
        if radius_m == 0.0:
            return 0.0
        dist = self.distance_to(world_pos)
        if dist <= 1e-9:
            return math.pi
        # clamp to avoid asin domain error
        ratio = min(1.0, radius_m / max(dist, radius_m))
        return 2.0 * math.asin(ratio)

    # -- tracking / following --

    def track(self, target_world_pos: Vector3) -> None:
        """Immediately orient to face target position."""
        target_world_pos = _require_finite_vector(target_world_pos, "target_world_pos")
        self.target = Vector3(target_world_pos.x, target_world_pos.y, target_world_pos.z)
        self.mode = CameraMode.TRACKING
        self.look_at(target_world_pos)

    def follow(self, target_id: str, offset: Vector3 = Vector3(0.0, 5.0, 20.0)) -> None:
        """Set follow mode; actual position updated via controller."""
        if not isinstance(target_id, str) or not target_id:
            raise CameraError("follow target_id must be non-empty string")
        offset = _require_finite_vector(offset, "offset")
        self.follow_target_id = target_id
        self.mode = CameraMode.FOLLOW
        # store offset in metadata? Keep simple
        self._follow_offset = offset  # type: ignore

    def get_follow_offset(self) -> Vector3:
        return getattr(self, "_follow_offset", Vector3(0.0, 5.0, 20.0))

    # -- serialization / copy --

    def clone(self) -> "Camera":
        c = Camera(
            position=Vector3(self.position.x, self.position.y, self.position.z),
            orientation=Quaternion(self.orientation.w, self.orientation.x, self.orientation.y, self.orientation.z),
            fov_y_deg=self.fov_y_deg,
            near=self.near,
            far=self.far,
            projection=self.projection,
            viewport=Viewport(self.viewport.x, self.viewport.y, self.viewport.width, self.viewport.height),
            target=Vector3(self.target.x, self.target.y, self.target.z) if self.target is not None else None,
            mode=self.mode,
            follow_target_id=self.follow_target_id,
            ortho_height_m=self.ortho_height_m,
        )
        if hasattr(self, "_follow_offset"):
            c._follow_offset = self._follow_offset  # type: ignore
        return c

    def to_dict(self) -> dict:
        return {
            "position": self.position.to_tuple(),
            "orientation": (self.orientation.w, self.orientation.x, self.orientation.y, self.orientation.z),
            "fov_y_deg": self.fov_y_deg,
            "near": self.near,
            "far": self.far,
            "projection": self.projection.value,
            "viewport": {"x": self.viewport.x, "y": self.viewport.y, "width": self.viewport.width, "height": self.viewport.height},
            "target": self.target.to_tuple() if self.target is not None else None,
            "mode": self.mode.value,
            "follow_target_id": self.follow_target_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Camera":
        pos = data.get("position", (0, 0, 10))
        ori = data.get("orientation", (1, 0, 0, 0))
        vp = data.get("viewport", {"width": 1920, "height": 1080})
        target = data.get("target")
        return cls(
            position=Vector3(float(pos[0]), float(pos[1]), float(pos[2])),
            orientation=Quaternion(float(ori[0]), float(ori[1]), float(ori[2]), float(ori[3])),
            fov_y_deg=float(data.get("fov_y_deg", 60.0)),
            near=float(data.get("near", 0.1)),
            far=float(data.get("far", 1e12)),
            projection=ProjectionType(data.get("projection", "PERSPECTIVE")),
            viewport=Viewport(int(vp.get("x", 0)), int(vp.get("y", 0)), int(vp.get("width", 1920)), int(vp.get("height", 1080))),
            target=Vector3(float(target[0]), float(target[1]), float(target[2])) if target is not None else None,
            mode=CameraMode(data.get("mode", "FREE")),
            follow_target_id=data.get("follow_target_id"),
        )


class CameraController:
    """High-level camera control respecting authority & determinism.

    No wall-clock; updates are driven by explicit dt / target positions
    supplied by the caller (simulation tick).
    """

    def __init__(self, camera: Camera):
        if not isinstance(camera, Camera):
            raise CameraError(f"camera must be Camera, got {type(camera).__name__}")
        self._camera = camera
        self._tracking_target: Optional[Vector3] = None
        self._follow_positions: dict[str, Vector3] = {}

    @property
    def camera(self) -> Camera:
        return self._camera

    def set_tracking_target(self, world_pos: Vector3) -> None:
        self._tracking_target = _require_finite_vector(world_pos, "world_pos")
        self._camera.track(self._tracking_target)

    def register_follow_position(self, target_id: str, world_pos: Vector3) -> None:
        if not isinstance(target_id, str) or not target_id:
            raise CameraError("target_id must be non-empty string")
        _require_finite_vector(world_pos, "world_pos")
        self._follow_positions[target_id] = Vector3(world_pos.x, world_pos.y, world_pos.z)

    def update_tracking(self) -> None:
        if self._tracking_target is not None:
            self._camera.look_at(self._tracking_target)

    def update_follow(self) -> None:
        fid = self._camera.follow_target_id
        if fid is None or fid not in self._follow_positions:
            return
        target_pos = self._follow_positions[fid]
        offset = self._camera.get_follow_offset()
        # offset is in world-ish but we interpret as following offset relative to target
        # Transform offset by inverse? Keep simple world offset
        self._camera.position = target_pos + offset
        self._camera.target = Vector3(target_pos.x, target_pos.y, target_pos.z)
        self._camera.look_at(target_pos)

    def move_free(self, delta: Vector3) -> None:
        delta = _require_finite_vector(delta, "delta")
        self._camera.move(delta)

    def orbit_around_target(self, yaw_rad: float, pitch_rad: float, distance: Optional[float] = None) -> None:
        self._camera.orbit(yaw_rad, pitch_rad, distance)

    def update(self, dt_s: float | None = None) -> None:
        """Deterministic update dispatch based on mode."""
        if dt_s is not None:
            _require_finite_float(dt_s, "dt_s", low=0.0)
        mode = self._camera.mode
        if mode == CameraMode.TRACKING:
            self.update_tracking()
        elif mode == CameraMode.FOLLOW:
            self.update_follow()
        # FREE / ORBIT / FIXED need no auto-update
