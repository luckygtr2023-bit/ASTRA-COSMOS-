import pytest
from astra.mathematics import Vector3
from astra.motion import (
    MotionState, to_frame_local, from_frame_local,
    world_position, rebase_invariant_state,
)


class TestFrameHelpers:
    def test_to_from_local(self):
        world = Vector3(5, -3, 2)
        origin = Vector3(10, 0, 0)
        local = to_frame_local(world, origin)
        assert local == Vector3(-5, -3, 2)
        assert from_frame_local(local, origin) == world


class TestRebaseInvariance:
    def test_state_unchanged(self):
        s = MotionState()
        s.position = Vector3(1e10, -1e10, 5e9)
        s.velocity = Vector3(1, 2, 3)
        s.angular_velocity = Vector3(0, 0, 0.1)
        r = rebase_invariant_state(s, (1e10, 0, 0))
        assert r.position == s.position
        assert r.velocity == s.velocity
        assert r.angular_velocity == s.angular_velocity

    def test_world_position_via_frame_origin(self):
        s = MotionState()
        s.position = Vector3(2, 3, 4)
        assert world_position(s) == Vector3(2, 3, 4)
        assert world_position(s, Vector3(10, 0, 0)) == Vector3(12, 3, 4)

    def test_multiple_rebases_idempotent_for_world(self):
        s = MotionState()
        s.position = Vector3(7, 8, 9)
        for _ in range(5):
            s2 = rebase_invariant_state(s, (1, 2, 3))
            assert s2.position == s.position
