"""Damage state machine.

States are strictly ordered. A transition may advance to ANY later state
(catastrophic impacts legitimately skip intermediate states, e.g.
INTACT -> FRAGMENTED for a specific energy above the fragmentation
threshold) or remain in place (idempotent re-application). Moving
backwards is never permitted; DESTROYED is absorbing.

    INTACT(0) < DAMAGED(1) < FRACTURED(2) < FRAGMENTED(3) < DESTROYED(4)

Any backward transition raises ImpactValidationError.
"""
from __future__ import annotations

from enum import Enum

from .errors import ImpactValidationError


class DamageState(str, Enum):
    INTACT = "INTACT"
    DAMAGED = "DAMAGED"
    FRACTURED = "FRACTURED"
    FRAGMENTED = "FRAGMENTED"
    DESTROYED = "DESTROYED"


_ORDER = {
    DamageState.INTACT: 0,
    DamageState.DAMAGED: 1,
    DamageState.FRACTURED: 2,
    DamageState.FRAGMENTED: 3,
    DamageState.DESTROYED: 4,
}


def order(state: DamageState) -> int:
    return _ORDER[state]


def is_valid_transition(src: DamageState, dst: DamageState) -> bool:
    """True iff dst is not earlier than src (forward or same-state)."""
    if not isinstance(src, DamageState) or not isinstance(dst, DamageState):
        raise ImpactValidationError("damage states must be DamageState members")
    return _ORDER[dst] >= _ORDER[src]


def transition(src: DamageState, dst: DamageState) -> DamageState:
    if not is_valid_transition(src, dst):
        raise ImpactValidationError(
            f"illegal damage transition {src.value} -> {dst.value}",
        )
    return dst
