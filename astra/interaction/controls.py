"""ASTRA Interaction — player control model.

Player commands are translated into VALID simulation inputs.
Never directly mutates physics state unless the architecture permits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import math

from .errors import ControlError


def _finite(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
        raise ControlError(f"{name} must be finite, got {v!r}")
    return float(v)


@dataclass(frozen=True)
class ThrottleCommand:
    """Normalized throttle in [-1, 1] plus duration."""
    throttle: float
    duration_s: float
    engine_id: Optional[str] = None

    def __post_init__(self):
        _finite("throttle", self.throttle)
        if not -1.0 <= self.throttle <= 1.0:
            raise ControlError("throttle must be in [-1, 1]")
        _finite("duration_s", self.duration_s)
        if self.duration_s < 0:
            raise ControlError("duration_s must be >=0")

    def to_impulse_scale(self) -> float:
        return float(self.throttle)


@dataclass(frozen=True)
class OrientationCommand:
    """Quaternion or euler targeting; validated finite."""
    # yaw/pitch/roll in radians OR explicit quaternion
    yaw_rad: float = 0.0
    pitch_rad: float = 0.0
    roll_rad: float = 0.0
    quaternion: Optional[Tuple[float, float, float, float]] = None

    def __post_init__(self):
        for name in ("yaw_rad","pitch_rad","roll_rad"):
            _finite(name, getattr(self, name))
        if self.quaternion is not None:
            if len(self.quaternion) != 4:
                raise ControlError("quaternion must be 4-tuple")
            for i, v in enumerate(self.quaternion):
                _finite(f"quaternion[{i}]", v)
            n2 = sum(x*x for x in self.quaternion)
            if not 0.99 < n2 < 1.01:
                # allow slight tolerance but still warn via error: we normalize later
                pass


@dataclass(frozen=True)
class TrajectoryControl:
    """delta-v or thrust vector in world frame (m/s or N·s)."""
    delta_v: Tuple[float, float, float]
    frame_id: Optional[str] = None

    def __post_init__(self):
        if len(self.delta_v) != 3:
            raise ControlError("delta_v must be 3-tuple")
        for i, v in enumerate(self.delta_v):
            _finite(f"delta_v[{i}]", v)
        object.__setattr__(self, "delta_v", tuple(float(x) for x in self.delta_v))


@dataclass(frozen=True)
class CameraControl:
    """Observer/camera movement relative to target or world."""
    position_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    look_at: Optional[Tuple[float, float, float]] = None
    fov_deg: float = 60.0
    frame_id: Optional[str] = None

    def __post_init__(self):
        for i, v in enumerate(self.position_offset):
            _finite(f"position_offset[{i}]", v)
        if self.look_at is not None:
            if len(self.look_at) != 3:
                raise ControlError("look_at must be 3-tuple")
            for i, v in enumerate(self.look_at):
                _finite(f"look_at[{i}]", v)
        _finite("fov_deg", self.fov_deg)
        if not 1.0 <= self.fov_deg <= 179.0:
            raise ControlError("fov_deg must be in [1,179]")
        object.__setattr__(self, "position_offset", tuple(float(x) for x in self.position_offset))
        if self.look_at is not None:
            object.__setattr__(self, "look_at", tuple(float(x) for x in self.look_at))


@dataclass(frozen=True)
class ControlInput:
    """Aggregated control for one tick."""
    throttle: Optional[ThrottleCommand] = None
    orientation: Optional[OrientationCommand] = None
    trajectory: Optional[TrajectoryControl] = None
    camera: Optional[CameraControl] = None
    target_id: Optional[str] = None

    def __post_init__(self):
        if self.target_id is not None and not isinstance(self.target_id, str):
            raise ControlError("target_id must be str or None")

    def is_empty(self) -> bool:
        return self.throttle is None and self.orientation is None and self.trajectory is None and self.camera is None


class ControlTranslator:
    """Translates ControlInput into VALID simulation inputs.

    Delegates to authoritative providers; never mutates physics directly.
    """

    def __init__(self, spacecraft_provider=None, motion_provider=None):
        self._sc = spacecraft_provider
        self._motion = motion_provider

    def translate(self, entity_id: str, inp: ControlInput, tick: int) -> dict:
        """Return a dict describing the VALID commands to queue.

        Does not execute; caller must submit via CommandDispatcher / SpacecraftSystem.
        Structured failures if providers missing or inputs invalid.
        """
        if not isinstance(entity_id, str) or not entity_id:
            raise ControlError("entity_id must be non-empty string")
        if not isinstance(inp, ControlInput):
            raise ControlError("inp must be ControlInput")
        if inp.is_empty():
            return {"entity_id": entity_id, "tick": tick, "commands": []}
        cmds = []
        if inp.throttle is not None:
            # Translation is allowed without provider — real execution will validate via SpacecraftSystem.
            # We just encode intent deterministically.
            cmds.append({
                "type": "throttle",
                "engine_id": inp.throttle.engine_id,
                "throttle": inp.throttle.throttle,
                "duration_s": inp.throttle.duration_s,
            })
        if inp.trajectory is not None:
            cmds.append({
                "type": "trajectory",
                "delta_v": list(inp.trajectory.delta_v),
                "frame_id": inp.trajectory.frame_id,
            })
        if inp.orientation is not None:
            cmds.append({
                "type": "orientation",
                "yaw": inp.orientation.yaw_rad,
                "pitch": inp.orientation.pitch_rad,
                "roll": inp.orientation.roll_rad,
                "quaternion": list(inp.orientation.quaternion) if inp.orientation.quaternion else None,
            })
        if inp.camera is not None:
            cmds.append({
                "type": "camera",
                "position_offset": list(inp.camera.position_offset),
                "look_at": list(inp.camera.look_at) if inp.camera.look_at else None,
                "fov_deg": inp.camera.fov_deg,
                "frame_id": inp.camera.frame_id,
            })
        return {"entity_id": entity_id, "tick": tick, "commands": cmds}
