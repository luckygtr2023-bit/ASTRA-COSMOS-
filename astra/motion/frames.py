"""Frame/rebase helpers for Motion.

Semantics
---------
MotionState.position is defined as the WORLD/PHYSICAL position (absolute).
An origin rebase changes how frames represent that world, but does NOT
change the physical position of a body and MUST NOT inject velocity,
acceleration, or rotation changes.

The helpers below convert to/from a frame-local view for display or
precision management. They do NOT mutate MotionState.
"""
from __future__ import annotations
from typing import Tuple, Union

from astra.mathematics import Vector3
from astra.motion.state import MotionState


def to_frame_local(world_position: Vector3, frame_origin_world: Vector3) -> Vector3:
    """world -> frame-local: p_local = p_world - origin_world."""
    return world_position - frame_origin_world


def from_frame_local(local_position: Vector3, frame_origin_world: Vector3) -> Vector3:
    """frame-local -> world: p_world = p_local + origin_world."""
    return local_position + frame_origin_world


def world_position(state: MotionState,
                   frame_origin_world: Vector3 = None) -> Vector3:
    """Return the physical world position for a MotionState.

    MotionState.position is already world/physical, so if no frame origin
    is provided this simply returns it. If a frame origin is provided the
    caller is asserting that position is frame-local, and the world
    position is origin + local.
    """
    if frame_origin_world is None:
        return state.position
    return state.position + frame_origin_world


def rebase_invariant_state(state: MotionState,
                           offset: Union[Tuple[float, float, float], Vector3, None] = None
                           ) -> MotionState:
    """Return a copy of state that is invariant under origin rebase.

    Because MotionState.position is world/physical, no fields change.
    This function exists to make the invariant explicit and testable.
    """
    return state.copy()
