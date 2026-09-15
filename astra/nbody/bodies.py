"""NBodyBody — an immutable, hashable physical body in an N-body system."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict
import math

from astra.mathematics import Vector3
from astra.nbody.errors import InvalidMassError, InvalidBodyError


@dataclass(frozen=True)
class NBodyBody:
    """A gravitational body.

    Fields
    ------
    id       : str, unique within a system (used for deterministic ordering)
    mass     : float, kg. Must be positive finite. (+inf is rejected here;
               use the Physics layer's MassProperties.static() for infinite
               mass concepts — N-body uses finite masses only.)
    position : Vector3, world-frame position (m)
    velocity : Vector3, world-frame velocity (m/s)
    """
    id: str
    mass: float
    position: Vector3
    velocity: Vector3

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise InvalidBodyError("id must be a non-empty string")
        if not math.isfinite(self.mass) or self.mass <= 0.0:
            raise InvalidMassError(f"mass must be positive finite, got {self.mass!r}")
        if not self.position.is_finite():
            raise InvalidBodyError("position must be finite")
        if not self.velocity.is_finite():
            raise InvalidBodyError("velocity must be finite")

    def copy(self, **changes) -> "NBodyBody":
        return NBodyBody(
            id=changes.get("id", self.id),
            mass=changes.get("mass", self.mass),
            position=changes.get("position", self.position),
            velocity=changes.get("velocity", self.velocity),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mass": float(self.mass),
            "position": list(self.position.to_tuple()),
            "velocity": list(self.velocity.to_tuple()),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NBodyBody":
        try:
            return cls(
                id=str(d["id"]),
                mass=float(d["mass"]),
                position=Vector3.from_tuple(d["position"]),
                velocity=Vector3.from_tuple(d["velocity"]),
            )
        except KeyError as e:
            raise InvalidBodyError(f"missing required field: {e.args[0]}")
