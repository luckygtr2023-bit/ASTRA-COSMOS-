"""Engine — physical description of a spacecraft thruster.

An engine is an immutable value object: id, thrust magnitude, specific
impulse, local thrust direction, and local mount offset from centre of
mass. Its on/off state lives in EngineSpec (see below) so that the
Engine value can be shared across copies of spacecraft.

Multiple engines per spacecraft are supported; the caller provides them
in a deterministic order (the order is preserved by the system).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict
import math

from astra.mathematics import Vector3
from astra.spacecraft.errors import InvalidEngineError
from astra.spacecraft.constants import MIN_ISP, MAX_ISP, MIN_THRUST


@dataclass(frozen=True)
class Engine:
    """Engine specification (immutable).

    Fields
    ------
    id                    : str, unique within a spacecraft
    thrust_magnitude      : N, >= 0 (0 is an idle engine)
    specific_impulse      : s, > 0
    thrust_direction_local: Vector3, body-frame thrust direction (normalized)
    mount_offset_local    : Vector3, engine application point relative to
                            spacecraft centre of mass, in body frame
    """
    id: str
    thrust_magnitude: float
    specific_impulse: float
    thrust_direction_local: Vector3
    mount_offset_local: Vector3 = field(default_factory=lambda: Vector3(0, 0, 0))

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise InvalidEngineError("engine id must be a non-empty string")
        if not math.isfinite(self.thrust_magnitude) or self.thrust_magnitude < MIN_THRUST:
            raise InvalidEngineError(
                f"thrust_magnitude must be finite and >= {MIN_THRUST}, "
                f"got {self.thrust_magnitude!r}"
            )
        if not math.isfinite(self.specific_impulse):
            raise InvalidEngineError("specific_impulse must be finite")
        if not (MIN_ISP <= self.specific_impulse <= MAX_ISP):
            raise InvalidEngineError(
                f"specific_impulse must be in [{MIN_ISP}, {MAX_ISP}], "
                f"got {self.specific_impulse!r}"
            )
        if self.thrust_direction_local.is_zero():
            raise InvalidEngineError("thrust_direction_local must be non-zero")
        if not self.mount_offset_local.is_finite():
            raise InvalidEngineError("mount_offset_local must be finite")

    @property
    def thrust_direction_body(self) -> Vector3:
        return self.thrust_direction_local.normalized()

    @property
    def mass_flow_rate(self) -> float:
        """Full-throttle propellant consumption (kg/s)."""
        from astra.spacecraft.constants import G0
        return self.thrust_magnitude / (self.specific_impulse * G0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "thrust_magnitude": float(self.thrust_magnitude),
            "specific_impulse": float(self.specific_impulse),
            "thrust_direction_local": list(self.thrust_direction_local.to_tuple()),
            "mount_offset_local": list(self.mount_offset_local.to_tuple()),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Engine":
        try:
            return cls(
                id=str(d["id"]),
                thrust_magnitude=float(d["thrust_magnitude"]),
                specific_impulse=float(d["specific_impulse"]),
                thrust_direction_local=Vector3.from_tuple(d["thrust_direction_local"]),
                mount_offset_local=Vector3.from_tuple(
                    d.get("mount_offset_local", (0.0, 0.0, 0.0))
                ),
            )
        except KeyError as e:
            raise InvalidEngineError(f"missing required field: {e.args[0]}")


@dataclass
class EngineSpec:
    """A mutable engine operational state: on/off, and whether it is currently
    executing a burn. The Engine value itself is immutable and shared."""
    engine: Engine
    enabled: bool = True
    burning: bool = False

    def __post_init__(self):
        if not isinstance(self.engine, Engine):
            raise InvalidEngineError("engine must be an Engine instance")
