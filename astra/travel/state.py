"""Travel state machine. Reconciled — reuses ASTRA conventions where applicable."""
from __future__ import annotations

from enum import Enum

from .errors import TravelValidationError


class TravelState(str, Enum):
    UNCONFIGURED = "UNCONFIGURED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    STABLE = "STABLE"
    UNSTABLE = "UNSTABLE"
    ABORTED = "ABORTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CAUSALLY_INVALID = "CAUSALLY_INVALID"
    PHYSICALLY_UNSUPPORTED = "PHYSICALLY_UNSUPPORTED"


_TRANSITIONS = {
    TravelState.UNCONFIGURED: frozenset({TravelState.READY, TravelState.FAILED}),
    TravelState.READY: frozenset(
        {
            TravelState.ACTIVE,
            TravelState.ABORTED,
            TravelState.FAILED,
            TravelState.PHYSICALLY_UNSUPPORTED,
            TravelState.CAUSALLY_INVALID,
        }
    ),
    TravelState.ACTIVE: frozenset(
        {
            TravelState.STABLE,
            TravelState.UNSTABLE,
            TravelState.ABORTED,
            TravelState.COMPLETED,
            TravelState.FAILED,
            TravelState.CAUSALLY_INVALID,
            TravelState.PHYSICALLY_UNSUPPORTED,
        }
    ),
    TravelState.STABLE: frozenset({TravelState.COMPLETED, TravelState.ABORTED, TravelState.FAILED}),
    TravelState.UNSTABLE: frozenset({TravelState.ABORTED, TravelState.FAILED}),
    TravelState.ABORTED: frozenset(),
    TravelState.COMPLETED: frozenset(),
    TravelState.FAILED: frozenset(),
    TravelState.CAUSALLY_INVALID: frozenset(),
    TravelState.PHYSICALLY_UNSUPPORTED: frozenset(),
}


class Transition:
    @staticmethod
    def is_valid(src: TravelState, dst: TravelState) -> bool:
        if src == dst:
            return True
        return dst in _TRANSITIONS[src]

    @staticmethod
    def apply(src: TravelState, dst: TravelState) -> TravelState:
        if not Transition.is_valid(src, dst):
            raise TravelValidationError(f"illegal travel transition {src.value} -> {dst.value}")
        return dst


def is_valid_transition(src: TravelState, dst: TravelState) -> bool:
    return Transition.is_valid(src, dst)
