"""ASTRA Interaction — explicit exploration state machine."""

from __future__ import annotations

from enum import Enum
from typing import Dict, Set, Tuple

from .errors import StateTransitionError


class ExplorationStateType(str, Enum):
    IDLE = "IDLE"
    NAVIGATING = "NAVIGATING"
    APPROACHING = "APPROACHING"
    OBSERVING = "OBSERVING"
    MEASURING = "MEASURING"
    TRAVELLING = "TRAVELLING"
    IN_TRANSIT = "IN_TRANSIT"
    ARRIVING = "ARRIVING"
    EXPLORING = "EXPLORING"
    INTERACTING = "INTERACTING"
    TRACKING = "TRACKING"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


# Explicit valid transitions — never silent repair
_VALID: Dict[ExplorationStateType, Set[ExplorationStateType]] = {
    ExplorationStateType.IDLE: {
        ExplorationStateType.NAVIGATING, ExplorationStateType.APPROACHING,
        ExplorationStateType.OBSERVING, ExplorationStateType.MEASURING,
        ExplorationStateType.TRAVELLING, ExplorationStateType.EXPLORING,
        ExplorationStateType.INTERACTING, ExplorationStateType.TRACKING,
        ExplorationStateType.PAUSED, ExplorationStateType.COMPLETED,
    },
    ExplorationStateType.NAVIGATING: {
        ExplorationStateType.APPROACHING, ExplorationStateType.ARRIVING,
        ExplorationStateType.IDLE, ExplorationStateType.PAUSED, ExplorationStateType.FAILED,
        ExplorationStateType.OBSERVING, ExplorationStateType.INTERACTING, ExplorationStateType.EXPLORING,
        ExplorationStateType.TRACKING, ExplorationStateType.MEASURING,
    },
    ExplorationStateType.APPROACHING: {
        ExplorationStateType.ARRIVING, ExplorationStateType.OBSERVING,
        ExplorationStateType.NAVIGATING, ExplorationStateType.IDLE, ExplorationStateType.FAILED,
    },
    ExplorationStateType.OBSERVING: {
        ExplorationStateType.MEASURING, ExplorationStateType.TRACKING,
        ExplorationStateType.IDLE, ExplorationStateType.EXPLORING, ExplorationStateType.PAUSED,
        ExplorationStateType.FAILED, ExplorationStateType.NAVIGATING, ExplorationStateType.APPROACHING,
        ExplorationStateType.INTERACTING, ExplorationStateType.TRAVELLING,
    },
    ExplorationStateType.MEASURING: {
        ExplorationStateType.OBSERVING, ExplorationStateType.IDLE,
        ExplorationStateType.EXPLORING, ExplorationStateType.PAUSED, ExplorationStateType.FAILED,
    },
    ExplorationStateType.TRAVELLING: {
        ExplorationStateType.IN_TRANSIT, ExplorationStateType.FAILED, ExplorationStateType.PAUSED,
    },
    ExplorationStateType.IN_TRANSIT: {
        ExplorationStateType.ARRIVING, ExplorationStateType.FAILED, ExplorationStateType.PAUSED,
    },
    ExplorationStateType.ARRIVING: {
        ExplorationStateType.EXPLORING, ExplorationStateType.IDLE, ExplorationStateType.OBSERVING,
        ExplorationStateType.FAILED, ExplorationStateType.COMPLETED,
    },
    ExplorationStateType.EXPLORING: {
        ExplorationStateType.INTERACTING, ExplorationStateType.OBSERVING,
        ExplorationStateType.NAVIGATING, ExplorationStateType.TRAVELLING,
        ExplorationStateType.IDLE, ExplorationStateType.PAUSED, ExplorationStateType.COMPLETED,
        ExplorationStateType.APPROACHING, ExplorationStateType.MEASURING, ExplorationStateType.TRACKING,
    },
    ExplorationStateType.INTERACTING: {
        ExplorationStateType.EXPLORING, ExplorationStateType.IDLE, ExplorationStateType.FAILED, ExplorationStateType.COMPLETED,
        ExplorationStateType.NAVIGATING, ExplorationStateType.APPROACHING, ExplorationStateType.OBSERVING,
        ExplorationStateType.MEASURING, ExplorationStateType.TRACKING, ExplorationStateType.TRAVELLING,
        ExplorationStateType.PAUSED,
    },
    ExplorationStateType.TRACKING: {
        ExplorationStateType.OBSERVING, ExplorationStateType.APPROACHING,
        ExplorationStateType.IDLE, ExplorationStateType.FAILED,
        ExplorationStateType.NAVIGATING, ExplorationStateType.INTERACTING, ExplorationStateType.EXPLORING,
        ExplorationStateType.PAUSED,
    },
    ExplorationStateType.PAUSED: {
        ExplorationStateType.IDLE, ExplorationStateType.NAVIGATING,
        ExplorationStateType.OBSERVING, ExplorationStateType.TRAVELLING,
        ExplorationStateType.IN_TRANSIT, ExplorationStateType.EXPLORING,
        ExplorationStateType.TRACKING, ExplorationStateType.FAILED,
    },
    ExplorationStateType.FAILED: {
        ExplorationStateType.IDLE, ExplorationStateType.PAUSED,
    },
    ExplorationStateType.COMPLETED: {
        ExplorationStateType.IDLE,
    },
}


class ExplorationStateMachine:
    """Deterministic FSM — invalid transitions fail explicitly."""

    def __init__(self, initial: ExplorationStateType = ExplorationStateType.IDLE):
        if not isinstance(initial, ExplorationStateType):
            raise StateTransitionError("initial must be ExplorationStateType")
        self._state = initial
        self._history: list[Tuple[ExplorationStateType, ExplorationStateType]] = []

    @property
    def state(self) -> ExplorationStateType:
        return self._state

    def can_transition(self, to: ExplorationStateType) -> bool:
        return to in _VALID.get(self._state, set())

    def transition(self, to: ExplorationStateType) -> ExplorationStateType:
        if not isinstance(to, ExplorationStateType):
            raise StateTransitionError("to must be ExplorationStateType")
        if to == self._state:
            return self._state
        allowed = _VALID.get(self._state, set())
        if to not in allowed:
            raise StateTransitionError(f"invalid transition {self._state.value} -> {to.value}; allowed: {sorted(x.value for x in allowed)}")
        prev = self._state
        self._state = to
        self._history.append((prev, to))
        return self._state

    def force(self, to: ExplorationStateType) -> ExplorationStateType:
        """Force without validation — for recovery only; logs history."""
        prev = self._state
        self._state = to
        self._history.append((prev, to))
        return self._state

    def history(self) -> Tuple[Tuple[ExplorationStateType, ExplorationStateType], ...]:
        return tuple(self._history)

    def to_dict(self) -> Dict:
        return {
            "state": self._state.value,
            "history": [(a.value, b.value) for a, b in self._history],
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ExplorationStateMachine":
        m = cls(ExplorationStateType(d["state"]))
        m._history = [(ExplorationStateType(a), ExplorationStateType(b)) for a, b in d.get("history", [])]
        return m
