"""ASTRA Interaction — explicit structured actions/events (no scattered UI callbacks)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple, Any
import math

from .errors import InvalidInteractionError
from astra.scientific.classification import Classification


class InteractionType(str, Enum):
    INSPECT = "INSPECT"
    OBSERVE = "OBSERVE"
    MEASURE = "MEASURE"
    APPROACH = "APPROACH"
    DEPART = "DEPART"
    ENTER = "ENTER"
    LEAVE = "LEAVE"
    SELECT = "SELECT"
    TRACK = "TRACK"
    FOLLOW = "FOLLOW_TRAJECTORY"
    INITIATE_TRAVEL = "INITIATE_TRAVEL"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    CHANGE_PERSPECTIVE = "CHANGE_PERSPECTIVE"
    CHANGE_FRAME = "CHANGE_FRAME"
    SPACECRAFT_COMMAND = "SPACECRAFT_COMMAND"
    WORLD_INTERACT = "WORLD_INTERACT"
    EXPERIMENT = "EXPERIMENT"
    RECORD_DISCOVERY = "RECORD_DISCOVERY"
    NAVIGATE = "NAVIGATE"
    SET_SCALE = "SET_SCALE"


@dataclass(frozen=True)
class InteractionAction:
    """Explicit, serializable player/operator action."""

    action_id: str
    type: InteractionType
    tick: int
    target_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    frame_id: Optional[str] = None
    classification: Classification = Classification.SIMULATED_DATA
    provenance_note: str = ""

    def __post_init__(self):
        if not isinstance(self.action_id, str) or not self.action_id:
            raise InvalidInteractionError("action_id must be non-empty string")
        if not isinstance(self.type, InteractionType):
            raise InvalidInteractionError("type must be InteractionType")
        if not isinstance(self.tick, int) or self.tick < 0:
            raise InvalidInteractionError("tick must be int >=0")
        if self.target_id is not None and not isinstance(self.target_id, str):
            raise InvalidInteractionError("target_id must be str or None")
        if not isinstance(self.parameters, dict):
            raise InvalidInteractionError("parameters must be dict")
        if not isinstance(self.classification, Classification):
            raise InvalidInteractionError("classification must be Classification")
        object.__setattr__(self, "parameters", dict(self.parameters))

    def to_dict(self) -> Dict:
        return {
            "action_id": self.action_id,
            "type": self.type.value,
            "tick": self.tick,
            "target_id": self.target_id,
            "parameters": dict(self.parameters),
            "frame_id": self.frame_id,
            "classification": self.classification.value,
            "provenance_note": self.provenance_note,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "InteractionAction":
        return cls(
            action_id=d["action_id"],
            type=InteractionType(d["type"]),
            tick=int(d["tick"]),
            target_id=d.get("target_id"),
            parameters=dict(d.get("parameters", {})),
            frame_id=d.get("frame_id"),
            classification=Classification(d.get("classification", "SIMULATED_DATA")),
            provenance_note=d.get("provenance_note", ""),
        )


@dataclass(frozen=True)
class InteractionResult:
    """Structured result — never silent success/failure."""

    action_id: str
    success: bool
    tick: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    classification: Classification = Classification.SIMULATED_DATA
    warnings: Tuple[Dict, ...] = ()

    def __post_init__(self):
        if not isinstance(self.action_id, str) or not self.action_id:
            raise InvalidInteractionError("action_id must be non-empty string")
        if not isinstance(self.success, bool):
            raise InvalidInteractionError("success must be bool")
        if not isinstance(self.tick, int) or self.tick < 0:
            raise InvalidInteractionError("tick must be int >=0")
        object.__setattr__(self, "data", dict(self.data))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        if not self.success and not self.error_code:
            raise InvalidInteractionError("failing result must carry error_code")

    def to_dict(self) -> Dict:
        return {
            "action_id": self.action_id,
            "success": self.success,
            "tick": self.tick,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "data": dict(self.data),
            "classification": self.classification.value,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "InteractionResult":
        return cls(
            action_id=d["action_id"],
            success=bool(d["success"]),
            tick=int(d["tick"]),
            error_code=d.get("error_code"),
            error_message=d.get("error_message"),
            data=dict(d.get("data", {})),
            classification=Classification(d.get("classification", "SIMULATED_DATA")),
            warnings=tuple(d.get("warnings", [])),
        )


# Helper factory that enforces deterministic IDs without RNG leakage
def make_action_id(prefix: str, seq: int) -> str:
    return f"{prefix}-{seq:06d}"
