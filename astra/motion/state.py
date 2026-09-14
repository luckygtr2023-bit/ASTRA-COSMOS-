"""MotionState and domain validation."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict
import math

from astra.core.exceptions import AstraError
from astra.mathematics import Vector3, Quaternion


class MotionError(AstraError):
    """Base Motion-layer error."""


class InvalidMotionStateError(MotionError):
    """Raised when a MotionState holds non-finite values."""


class InvalidTimestepError(MotionError):
    """Raised when a timestep is non-finite or non-positive."""


def validate_timestep(dt: float) -> None:
    """dt must be a finite, strictly positive float."""
    if not isinstance(dt, (int, float)):
        raise InvalidTimestepError(f"timestep must be numeric, got {type(dt).__name__}")
    dt = float(dt)
    if not math.isfinite(dt):
        raise InvalidTimestepError(f"timestep must be finite, got {dt!r}")
    if dt <= 0.0:
        raise InvalidTimestepError(f"timestep must be positive, got {dt!r}")


@dataclass
class MotionState:
    """Kinematic state of a moving object (world frame, SI-like units).

    Fields
    ------
    position              : Vector3, world-frame absolute position
    velocity              : Vector3, world-frame linear velocity
    acceleration          : Vector3, world-frame linear acceleration
    orientation           : Quaternion (unit), body -> world
    angular_velocity      : Vector3, world-frame angular velocity (rad/s)
    angular_acceleration  : Vector3, world-frame angular acceleration (rad/s^2)
    time                  : float, simulation time at which this state is valid
    """
    position: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    velocity: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    acceleration: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    orientation: Quaternion = field(default_factory=Quaternion.identity)
    angular_velocity: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    angular_acceleration: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    time: float = 0.0

    @classmethod
    def at_rest(cls, position: Vector3 = None) -> "MotionState":
        s = cls()
        if position is not None:
            s.position = position
        return s

    @classmethod
    def with_velocity(cls, position: Vector3, velocity: Vector3) -> "MotionState":
        return cls(position=position, velocity=velocity)

    def copy(self) -> "MotionState":
        return MotionState(
            position=self.position,
            velocity=self.velocity,
            acceleration=self.acceleration,
            orientation=self.orientation,
            angular_velocity=self.angular_velocity,
            angular_acceleration=self.angular_acceleration,
            time=self.time,
        )

    def is_finite(self) -> bool:
        return (
            self.position.is_finite()
            and self.velocity.is_finite()
            and self.acceleration.is_finite()
            and self.orientation.is_finite()
            and self.angular_velocity.is_finite()
            and self.angular_acceleration.is_finite()
            and math.isfinite(self.time)
        )

    def validate(self) -> None:
        if not self.is_finite():
            raise InvalidMotionStateError("MotionState contains non-finite values")
        n = self.orientation.norm()
        if n == 0.0:
            raise InvalidMotionStateError("MotionState orientation has zero norm")

    def normalize_orientation(self) -> None:
        """Renormalize orientation in place. Raises on zero quaternion."""
        self.orientation = self.orientation.normalized()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position": list(self.position.to_tuple()),
            "velocity": list(self.velocity.to_tuple()),
            "acceleration": list(self.acceleration.to_tuple()),
            "orientation": list(self.orientation.to_tuple()),
            "angular_velocity": list(self.angular_velocity.to_tuple()),
            "angular_acceleration": list(self.angular_acceleration.to_tuple()),
            "time": float(self.time),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MotionState":
        s = cls(
            position=Vector3.from_tuple(d["position"]),
            velocity=Vector3.from_tuple(d["velocity"]),
            acceleration=Vector3.from_tuple(d["acceleration"]),
            orientation=Quaternion(*d["orientation"]).normalized(),
            angular_velocity=Vector3.from_tuple(d["angular_velocity"]),
            angular_acceleration=Vector3.from_tuple(d["angular_acceleration"]),
            time=float(d.get("time", 0.0)),
        )
        return s
