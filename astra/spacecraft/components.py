"""SpacecraftComponent — attaches SpacecraftState to an ASTRA entity.

The entity will typically also carry a MotionComponent (for kinematic
state) and a PhysicsComponent (for mass properties). SpacecraftComponent
adds the propulsion model: engines, propellant, active burn.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict

from astra.core.entities import Component
from astra.spacecraft.state import SpacecraftState


@dataclass
class SpacecraftComponent(Component):
    state: SpacecraftState = field(default_factory=SpacecraftState)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "enabled": bool(self.enabled),
            "state": self.state.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SpacecraftComponent":
        return cls(
            id=d.get("id", ""),
            state=SpacecraftState.from_dict(d["state"]),
            enabled=bool(d.get("enabled", True)),
        )
