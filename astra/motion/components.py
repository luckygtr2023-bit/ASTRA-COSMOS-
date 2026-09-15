"""MotionComponent — attaches MotionState to an ASTRA entity.

Inherits from the CORE Component so that EntityManager queries,
iteration, and clone() semantics apply unchanged.

Serialization note
------------------
CORE's EntityManager.get_state_snapshot() records a component's Python
class name but restore_from_snapshot() rebuilds base Component objects.
Motion therefore provides its own snapshot/restore on MotionSystem
(see system.py) rather than depending on CORE component rehydration.
"""
from __future__ import annotations
from dataclasses import dataclass, field

from astra.core.entities import Component
from astra.motion.state import MotionState


@dataclass
class MotionComponent(Component):
    """Carries a MotionState on an entity.

    enabled:
        If False, MotionSystem.step() will skip this component.
    state:
        The current MotionState (mutable container).
    """
    state: MotionState = field(default_factory=MotionState)
    enabled: bool = True

    def to_dict(self):
        return {
            "id": self.id,
            "enabled": bool(self.enabled),
            "state": self.state.to_dict(),
        }

    @classmethod
    def from_dict(cls, d) -> "MotionComponent":
        c = cls(id=d.get("id", ""),
                state=MotionState.from_dict(d["state"]),
                enabled=bool(d.get("enabled", True)))
        return c
