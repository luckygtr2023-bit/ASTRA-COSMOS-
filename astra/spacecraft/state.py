"""SpacecraftState — pairs MotionState with mass + engine specs.

SpacecraftState wraps a MotionState (owns it) plus a SpacecraftMass and
an ordered list of EngineSpec. It does not duplicate Motion; it composes
Motion.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from astra.motion import MotionState
from astra.spacecraft.mass import SpacecraftMass
from astra.spacecraft.engines import EngineSpec
from astra.spacecraft.errors import InvalidEngineError


@dataclass
class SpacecraftState:
    motion: MotionState = field(default_factory=MotionState)
    mass: SpacecraftMass = field(default_factory=lambda: SpacecraftMass(1.0, 0.0))
    engine_specs: List[EngineSpec] = field(default_factory=list)
    active_burn_id: Optional[str] = None

    def add_engine(self, spec: EngineSpec) -> None:
        if any(s.engine.id == spec.engine.id for s in self.engine_specs):
            raise InvalidEngineError(f"duplicate engine id: {spec.engine.id!r}")
        self.engine_specs.append(spec)

    def get_engine(self, engine_id: str) -> Optional[EngineSpec]:
        for s in self.engine_specs:
            if s.engine.id == engine_id:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "motion": self.motion.to_dict(),
            "mass": self.mass.to_dict(),
            "engine_specs": [
                {"engine": s.engine.to_dict(),
                 "enabled": bool(s.enabled),
                 "burning": bool(s.burning)}
                for s in self.engine_specs
            ],
            "active_burn_id": self.active_burn_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SpacecraftState":
        st = cls(
            motion=MotionState.from_dict(d["motion"]),
            mass=SpacecraftMass.from_dict(d["mass"]),
            active_burn_id=d.get("active_burn_id"),
        )
        for sd in d.get("engine_specs", []):
            from astra.spacecraft.engines import Engine
            st.engine_specs.append(EngineSpec(
                engine=Engine.from_dict(sd["engine"]),
                enabled=bool(sd.get("enabled", True)),
                burning=bool(sd.get("burning", False)),
            ))
        return st
