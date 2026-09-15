import math
import pytest
from astra.mathematics import Vector3, Quaternion
from astra.motion import (
    MotionState, InvalidMotionStateError, InvalidTimestepError,
    validate_timestep,
)


class TestValidation:
    def test_valid_dt(self):
        validate_timestep(0.01)
        validate_timestep(1e-9)
        validate_timestep(1.0)

    def test_zero_negative_non_finite(self):
        for bad in (0.0, -0.1, float("nan"), float("inf"), float("-inf")):
            with pytest.raises(InvalidTimestepError):
                validate_timestep(bad)

    def test_non_numeric(self):
        with pytest.raises(InvalidTimestepError):
            validate_timestep("0.1")


class TestMotionState:
    def test_default(self):
        s = MotionState()
        assert s.position == Vector3(0, 0, 0)
        assert s.velocity == Vector3(0, 0, 0)
        assert s.orientation == Quaternion.identity()
        assert s.time == 0.0

    def test_copy_independent(self):
        s = MotionState()
        s.position = Vector3(1, 2, 3)
        c = s.copy()
        s.position = Vector3(9, 9, 9)
        assert c.position == Vector3(1, 2, 3)

    def test_is_finite(self):
        assert MotionState().is_finite()
        s = MotionState()
        s.position = Vector3(float("nan"), 0, 0)
        assert not s.is_finite()
        with pytest.raises(InvalidMotionStateError):
            s.validate()

    def test_zero_orientation_norm(self):
        s = MotionState()
        s.orientation = Quaternion(0.0, 0.0, 0.0, 0.0)
        with pytest.raises(InvalidMotionStateError):
            s.validate()

    def test_normalize_orientation(self):
        s = MotionState()
        s.orientation = Quaternion(2.0, 0.0, 0.0, 0.0)
        s.normalize_orientation()
        assert math.isclose(s.orientation.norm(), 1.0, abs_tol=1e-12)


class TestSerialization:
    def test_round_trip(self):
        s = MotionState()
        s.position = Vector3(1, 2, 3)
        s.velocity = Vector3(0.1, 0.2, 0.3)
        s.acceleration = Vector3(0.01, 0.0, -0.01)
        s.orientation = Quaternion.from_axis_angle(Vector3(0, 0, 1), 0.5)
        s.angular_velocity = Vector3(0.0, 0.0, 1.0)
        s.angular_acceleration = Vector3(0.0, 0.0, 0.1)
        s.time = 3.5
        d = s.to_dict()
        r = MotionState.from_dict(d)
        for a, b in zip(r.position.to_tuple(), s.position.to_tuple()):
            assert math.isclose(a, b, abs_tol=1e-12)
        for a, b in zip(r.orientation.to_tuple(), s.orientation.to_tuple()):
            assert math.isclose(a, b, abs_tol=1e-12)
        assert math.isclose(r.time, s.time, abs_tol=1e-12)
