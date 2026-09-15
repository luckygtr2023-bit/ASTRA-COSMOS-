"""PhysicsComponent — attaches MassProperties to an ASTRA entity.

MotionComponent owns the kinematic state (position, velocity, orientation,
etc.). PhysicsComponent owns the mass and inertia. PhysicsSystem reads and
writes MotionState fields (acceleration, angular_acceleration) and never
bypasses Motion.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict

from astra.core.entities import Component
from astra.physics.mass import MassProperties


@dataclass
class PhysicsComponent(Component):
    mass_properties: MassProperties = field(default_factory=MassProperties.static)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "enabled": bool(self.enabled),
            "mass_properties": self.mass_properties.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PhysicsComponent":
        return cls(
            id=d.get("id", ""),
            mass_properties=MassProperties.from_dict(d["mass_properties"]),
            enabled=bool(d.get("enabled", True)),
        )
