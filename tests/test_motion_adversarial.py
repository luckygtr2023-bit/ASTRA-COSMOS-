"""Adversarial motion tests."""
import math
import threading
import pytest

from astra.core.entities import EntityManager
from astra.core.threading import (
    AuthorityContext, get_simulation_thread_registry,
    reset_simulation_thread_registry,
)
from astra.core.exceptions import AuthorityError
from astra.mathematics import Vector3, Quaternion
from astra.motion import (
    MotionState, MotionComponent, MotionSystem,
    ExplicitEulerIntegrator, SemiImplicitEulerIntegrator,
    RK4Integrator, rebase_invariant_state,
    InvalidMotionStateError, InvalidTimestepError,
)


@pytest.fixture(autouse=True)
def sim_thread():
    reset_simulation_thread_registry()
    reg = get_simulation_thread_registry()
    reg.register_simulation_thread(threading.current_thread().ident)
    yield
    reset_simulation_thread_registry()


class TestDeterminism:
    def test_repeat_run_identical(self):
        def run(integ):
            s = MotionState()
            s.velocity = Vector3(1e-3, 2e-3, -3e-3)
            s.acceleration = Vector3(1e-4, -2e-4, 3e-4)
            s.angular_velocity = Vector3(0.01, 0.02, -0.005)
            states = []
            for _ in range(500):
                s = integ.step(s, 0.01)
                states.append(s.position.to_tuple())
            return states
        for integ in (ExplicitEulerIntegrator(),
                      SemiImplicitEulerIntegrator(),
                      RK4Integrator()):
            assert run(integ) == run(integ)


class TestNumericalEdges:
    def test_long_integration_does_not_break_unit_norm(self):
        s = MotionState()
        s.angular_velocity = Vector3(0.5, 0.5, 0.5)
        integ = RK4Integrator()
        for _ in range(10_000):
            s = integ.step(s, 0.001)
        assert math.isclose(s.orientation.norm(), 1.0, abs_tol=1e-9)

    def test_large_position_drift_bounded_constant_velocity(self):
        s = MotionState()
        s.velocity = Vector3(1.0, 0.0, 0.0)
        for _ in range(1000):
            s = RK4Integrator().step(s, 1.0)
        assert s.position.x == pytest.approx(1000.0, abs=1e-9)

    def test_tiny_acceleration(self):
        s = MotionState()
        s.acceleration = Vector3(1e-30, 0.0, 0.0)
        s = RK4Integrator().step(s, 1.0)
        assert s.position.x == pytest.approx(0.5e-30, abs=1e-40)

    def test_nan_rejected(self):
        s = MotionState()
        s.velocity = Vector3(float("nan"), 0, 0)
        assert not s.is_finite()
        with pytest.raises(InvalidMotionStateError):
            s.validate()

    def test_inf_rejected(self):
        s = MotionState()
        s.position = Vector3(float("inf"), 0, 0)
        with pytest.raises(InvalidMotionStateError):
            s.validate()

    def test_invalid_timestep(self):
        for bad in (0.0, -1.0, float("nan"), float("inf")):
            with pytest.raises(InvalidTimestepError):
                RK4Integrator().step(MotionState(), bad)


class TestQuaternionStability:
    def test_5000_rotations_under_normalization(self):
        for integ in (SemiImplicitEulerIntegrator(), RK4Integrator()):
            s = MotionState()
            s.angular_velocity = Vector3(0.3, -0.4, 0.5)
            for _ in range(5000):
                s = integ.step(s, 0.001)
            assert math.isclose(s.orientation.norm(), 1.0, abs_tol=1e-9)

    def test_zero_angular_velocity_no_change(self):
        s = MotionState()
        q0 = s.orientation
        for _ in range(100):
            s = RK4Integrator().step(s, 0.01)
        for a, b in zip(s.orientation.to_tuple(), q0.to_tuple()):
            assert math.isclose(a, b, abs_tol=1e-12)


class TestAuthority:
    def test_unauthorized_step_rejected(self):
        em = EntityManager(); em.set_current_tick(0)
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        sys = MotionSystem(em)
        with pytest.raises(AuthorityError):
            sys.step(0.01)

    def test_after_unregister_rejected(self):
        reg = get_simulation_thread_registry()
        reg.unregister_simulation_thread(threading.current_thread().ident)
        em = EntityManager(); em.set_current_tick(0)
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        sys = MotionSystem(em)
        with pytest.raises(AuthorityError):
            sys.step(0.01)


class TestRebaseInvariance:
    def test_rebase_does_not_change_motion(self):
        s = MotionState()
        s.position = Vector3(1e9, -2e9, 3e9)
        s.velocity = Vector3(1, 2, 3)
        s.acceleration = Vector3(0.1, 0.2, 0.3)
        s.angular_velocity = Vector3(0.01, 0.02, 0.03)
        r = rebase_invariant_state(s, (1e9, 0, 0))
        assert r.position == s.position
        assert r.velocity == s.velocity
        assert r.acceleration == s.acceleration
        assert r.angular_velocity == s.angular_velocity

    def test_multiple_rebases_preserve_state(self):
        s = MotionState()
        s.position = Vector3(7, 8, 9)
        s.velocity = Vector3(1, 0, 0)
        for _ in range(20):
            r = rebase_invariant_state(s, (1, 1, 1))
            assert r.position == s.position
            assert r.velocity == s.velocity
