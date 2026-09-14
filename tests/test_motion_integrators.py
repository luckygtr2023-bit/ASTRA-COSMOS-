import math
import pytest
from astra.mathematics import Vector3, Quaternion
from astra.motion import (
    MotionState, ExplicitEulerIntegrator,
    SemiImplicitEulerIntegrator, RK4Integrator,
    InvalidTimestepError,
)


class TestConstantVelocity:
    def test_exact_under_all_integrators(self):
        for integ in (ExplicitEulerIntegrator(),
                      SemiImplicitEulerIntegrator(),
                      RK4Integrator()):
            s = MotionState()
            s.velocity = Vector3(2.0, -1.0, 0.5)
            out = integ.step(s, 3.0)
            exp = Vector3(6.0, -3.0, 1.5)
            assert out.position.distance_to(exp) < 1e-12


class TestConstantAcceleration:
    def test_exact_under_all(self):
        a = Vector3(0.5, -0.25, 1.0)
        t = 2.0
        for integ in (ExplicitEulerIntegrator(),
                      SemiImplicitEulerIntegrator(),
                      RK4Integrator()):
            s = MotionState()
            s.acceleration = a
            out = integ.step(s, t)
            expected_v = a * t
            assert out.velocity.distance_to(expected_v) < 1e-12


class TestInvalidTimestep:
    def test_rejected_by_all(self):
        for integ in (ExplicitEulerIntegrator(),
                      SemiImplicitEulerIntegrator(),
                      RK4Integrator()):
            with pytest.raises(InvalidTimestepError):
                integ.step(MotionState(), 0.0)
            with pytest.raises(InvalidTimestepError):
                integ.step(MotionState(), -1.0)
            with pytest.raises(InvalidTimestepError):
                integ.step(MotionState(), float("nan"))


class TestAngular:
    def test_constant_omega_half_turn(self):
        s = MotionState()
        s.angular_velocity = Vector3(0.0, 0.0, math.pi)
        out = SemiImplicitEulerIntegrator().step(s, 1.0)
        v = out.orientation.rotate(Vector3(1, 0, 0))
        assert v.x == pytest.approx(-1.0, abs=1e-6)
        assert v.y == pytest.approx(0.0, abs=1e-6)

    def test_constant_alpha(self):
        s = MotionState()
        s.angular_acceleration = Vector3(0.0, 0.0, 1.0)
        out = RK4Integrator().step(s, 1.0)
        assert out.angular_velocity.z == pytest.approx(1.0, abs=1e-12)

    def test_orientation_stays_unit(self):
        for integ in (ExplicitEulerIntegrator(),
                      SemiImplicitEulerIntegrator(),
                      RK4Integrator()):
            s = MotionState()
            s.angular_velocity = Vector3(0.1, 0.2, 0.3)
            for _ in range(50):
                s = integ.step(s, 0.01)
            assert math.isclose(s.orientation.norm(), 1.0, abs_tol=1e-9)


class TestRK4Order:
    def test_harmonic_error_shrinks(self):
        def step_with(dt):
            s = MotionState()
            s.position = Vector3(1.0, 0.0, 0.0)
            steps = int(round(math.tau / dt))
            actual_dt = math.tau / steps
            for _ in range(steps):
                s.acceleration = -s.position
                s = RK4Integrator().step(s, actual_dt)
            return s.position.x

        err_small = abs(step_with(1e-3) - 1.0)
        err_large = abs(step_with(1e-2) - 1.0)
        assert err_small < err_large
