"""ASTRA Rendering - coordinate conversion and floating-origin support.

Boundary:
    AUTHORITATIVE SIMULATION COORDINATES  (world, double precision, absolute)
                ↓
          RENDER COORDINATES              (floating-origin, camera-friendly)
                ↓
       CAMERA-RELATIVE COORDINATES        (for precision at the eye)

Rendering must NEVER mutate authoritative simulation coordinates.
Only derived copies are transformed.

Floating-origin for rendering is INDEPENDENT of simulation OriginRebaser;
it tracks a render_origin offset and applies it to render snapshots only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Tuple

from astra.mathematics import Vector3, Quaternion
from astra.rendering.exceptions import CoordinateConversionError
from astra.rendering.render_state import RenderObject, RenderState


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _require_finite_vector(v: Vector3, name: str) -> None:
    if not isinstance(v, Vector3):
        raise CoordinateConversionError(f"{name} must be Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise CoordinateConversionError(f"{name} must be finite, got {v!r}")


def _require_finite_tuple(t: Tuple[float, float, float], name: str) -> Tuple[float, float, float]:
    if len(t) != 3:
        raise CoordinateConversionError(f"{name} must be 3-tuple")
    out = []
    for i, val in enumerate(t):
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise CoordinateConversionError(f"{name}[{i}] must be numeric, got {type(val).__name__}")
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            raise CoordinateConversionError(f"{name}[{i}] must be finite, got {val!r}")
        out.append(f)
    return (out[0], out[1], out[2])


# ---------------------------------------------------------------------------
# Pure conversion functions (deterministic, stateless)
# ---------------------------------------------------------------------------

def world_to_render(world_pos: Vector3, render_origin: Vector3) -> Vector3:
    """Convert absolute world position to floating-origin render position.

    render_pos = world_pos - render_origin
    Does not mutate inputs; returns new Vector3.
    """
    _require_finite_vector(world_pos, "world_pos")
    _require_finite_vector(render_origin, "render_origin")
    return world_pos - render_origin


def render_to_world(render_pos: Vector3, render_origin: Vector3) -> Vector3:
    """Inverse of world_to_render."""
    _require_finite_vector(render_pos, "render_pos")
    _require_finite_vector(render_origin, "render_origin")
    return render_pos + render_origin


def world_to_camera_relative(world_pos: Vector3, camera_world_pos: Vector3) -> Vector3:
    """Direct camera-relative coordinate (highest precision near camera)."""
    _require_finite_vector(world_pos, "world_pos")
    _require_finite_vector(camera_world_pos, "camera_world_pos")
    return world_pos - camera_world_pos


def render_to_camera_relative(render_pos: Vector3, camera_render_pos: Vector3) -> Vector3:
    """Render-space camera-relative (for already-rebased data)."""
    _require_finite_vector(render_pos, "render_pos")
    _require_finite_vector(camera_render_pos, "camera_render_pos")
    return render_pos - camera_render_pos


def batch_world_to_render(positions: Tuple[Vector3, ...], render_origin: Vector3) -> Tuple[Vector3, ...]:
    """Deterministic batch conversion."""
    _require_finite_vector(render_origin, "render_origin")
    out = []
    for i, p in enumerate(positions):
        _require_finite_vector(p, f"positions[{i}]")
        out.append(p - render_origin)
    return tuple(out)


def apply_render_origin_to_state(state: RenderState, new_origin: Vector3) -> RenderState:
    """Return a new RenderState rebased to new_origin.

    Original state is NOT mutated. Positions are transformed as:
        new_render_pos = old_render_pos + (old_origin - new_origin)
    which is equivalent to world_pos - new_origin.
    Preserves physical relative positions.
    """
    _require_finite_vector(new_origin, "new_origin")
    old_origin = state.render_origin
    delta = old_origin - new_origin  # shift to apply
    cloned = state.clone()
    # update origin
    cloned.render_origin = Vector3(new_origin.x, new_origin.y, new_origin.z)
    # shift each object
    for oid in cloned.order:
        obj = cloned.objects[oid]
        obj.position = obj.position + delta
        # also shift camera-relative if present (will be recomputed later, but keep consistent)
        if obj.camera_relative_position is not None:
            # camera relative is invariant to render origin if both shifted? Actually
            # camera_relative = world - camera = (render + origin) - (cam_render + origin) = render - cam_render
            # So camera-relative does not depend on origin; preserve as-is.
            pass
    return cloned


# ---------------------------------------------------------------------------
# Floating-origin manager for rendering
# ---------------------------------------------------------------------------

@dataclass
class FloatingOriginConfig:
    """Configuration for rendering floating origin."""

    # When camera displacement from current origin exceeds this, rebase.
    rebase_threshold_m: float = 1e6  # 1000 km default, may be tuned per scale
    # Hysteresis to avoid thrashing
    hysteresis_m: float = 100.0
    # Maximum render coordinate magnitude before forcing rebase (precision guard)
    max_render_distance_m: float = 5e6

    def __post_init__(self) -> None:
        for name in ("rebase_threshold_m", "hysteresis_m", "max_render_distance_m"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise CoordinateConversionError(f"{name} must be numeric")
            f = float(v)
            if math.isnan(f) or math.isinf(f) or f <= 0:
                raise CoordinateConversionError(f"{name} must be finite >0, got {v!r}")
            setattr(self, name, f)
        if self.hysteresis_m >= self.rebase_threshold_m:
            raise CoordinateConversionError("hysteresis must be < rebase_threshold")


class FloatingOriginRenderer:
    """Renderer-side floating origin (does NOT touch simulation truth).

    Tracks render_origin as a Vector3 offset subtracted from world positions.
    Rebase is a pure render operation: authoritative world positions unchanged.
    """

    def __init__(self, initial_origin: Vector3 | None = None, config: FloatingOriginConfig | None = None):
        self._origin = initial_origin if initial_origin is not None else Vector3(0.0, 0.0, 0.0)
        _require_finite_vector(self._origin, "initial_origin")
        self._config = config or FloatingOriginConfig()
        self._rebase_count = 0
        self._history: list[Tuple[Vector3, Vector3]] = []  # (old, new)

    @property
    def origin(self) -> Vector3:
        return Vector3(self._origin.x, self._origin.y, self._origin.z)

    @property
    def config(self) -> FloatingOriginConfig:
        return self._config

    @property
    def rebase_count(self) -> int:
        return self._rebase_count

    def needs_rebase(self, camera_world_pos: Vector3) -> bool:
        """Deterministic check: does camera require a new render origin?"""
        _require_finite_vector(camera_world_pos, "camera_world_pos")
        # distance from current origin
        render_pos = camera_world_pos - self._origin
        dist = render_pos.magnitude()
        # rebase if beyond threshold or if max render distance exceeded
        if dist > self._config.rebase_threshold_m:
            return True
        if dist > self._config.max_render_distance_m:
            return True
        return False

    def rebase_to(self, new_origin: Vector3) -> Tuple[Vector3, Vector3]:
        """Set new render origin; returns (old, new). Does not mutate simulation."""
        _require_finite_vector(new_origin, "new_origin")
        old = Vector3(self._origin.x, self._origin.y, self._origin.z)
        if old.x == new_origin.x and old.y == new_origin.y and old.z == new_origin.z:
            return (old, old)
        self._history.append((old, Vector3(new_origin.x, new_origin.y, new_origin.z)))
        self._origin = Vector3(new_origin.x, new_origin.y, new_origin.z)
        self._rebase_count += 1
        return (old, self._origin)

    def rebase_to_camera(self, camera_world_pos: Vector3) -> Tuple[Vector3, Vector3]:
        """Convenience: rebase origin to camera's world position."""
        _require_finite_vector(camera_world_pos, "camera_world_pos")
        return self.rebase_to(camera_world_pos)

    def world_to_render(self, world_pos: Vector3) -> Vector3:
        return world_to_render(world_pos, self._origin)

    def render_to_world(self, render_pos: Vector3) -> Vector3:
        return render_to_world(render_pos, self._origin)

    def apply_to_render_state(self, state: RenderState) -> RenderState:
        """Rebase an existing RenderState to this manager's current origin."""
        if state.render_origin.x == self._origin.x and state.render_origin.y == self._origin.y and state.render_origin.z == self._origin.z:
            return state.clone()
        return apply_render_origin_to_state(state, self._origin)

    def transform_render_state_camera_relative(
        self, state: RenderState, camera_world_pos: Vector3
    ) -> RenderState:
        """Fill camera_relative_position/distance/apparent_size for each object.

        Uses world positions (render + origin) to compute camera-relative vectors
        with maximal precision, then stores them as render-state derived fields.
        Does not mutate input.
        """
        _require_finite_vector(camera_world_pos, "camera_world_pos")
        cloned = state.clone()
        cam_render = camera_world_pos - cloned.render_origin
        for oid in cloned.order:
            obj = cloned.objects[oid]
            # world_pos = render_pos + origin, but render_pos already is world - origin
            # So camera_relative robustly: (render_pos - cam_render)
            rel = obj.position - cam_render
            obj.camera_relative_position = rel
            dist = rel.magnitude()
            obj.distance_to_camera_m = dist
            # apparent angular radius approx = radius / distance (for small angles)
            if dist > 1e-9 and obj.bounding_radius_m > 0:
                # clamp to avoid > pi/2 artifacts at zero distance
                obj.apparent_size_rad = min(math.pi, 2.0 * math.asin(min(1.0, obj.bounding_radius_m / max(dist, obj.bounding_radius_m))))
            else:
                obj.apparent_size_rad = 0.0 if dist > 0 else math.pi
        return cloned

    def history(self) -> Tuple[Tuple[Vector3, Vector3], ...]:
        return tuple(self._history)

    def reset(self) -> None:
        self._origin = Vector3(0.0, 0.0, 0.0)
        self._rebase_count = 0
        self._history.clear()
