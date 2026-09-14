"""Adversarial N-body tests."""
import math
import threading
import pytest

from astra.core.threading import (
    AuthorityContext, get_simulation_thread_registry,
    reset_simulation_thread_registry,
)
from astra.core.exceptions import AuthorityError
from astra.mathematics import Vector3
from astra.physics import GRAVITATIONAL_CONSTANT
from astra.nbody import (
    NBodySystem, NBodyBody,
    compute_accelerations, pairwise_acceleration,
    DuplicateBodyError, InvalidBodyError, NBodyInvalidMassError,
    NBodySingularityError, InvalidTimestepError,
)


@pytest.fixture(autouse=True)
def sim_thread():
    reset_simulation_thread_registry()
    reg = get_simulation_thread_registry()
    reg.register_simulation_thread(threading.current_thread().ident)
    yield
    reset_simulation_thread_registry()


def _b(id_, m, p, v):
    return NBodyBody(id=id_, mass=m, position=Vector3(*p), velocity=Vector3(*v))


class TestSingularity:
    def test_zero_separation_zero_softening(self):
        with pytest.raises(NBodySingularityError):
            pairwise_acceleration(Vector3(0, 0, 0), Vector3(0, 0, 0),
                                   1.0, 1.0, softening=0.0)

    def test_zero_separation_with_softening_finite(self):
        a_i, a_j = pairwise_acceleration(Vector3(0, 0, 0), Vector3(0, 0, 0),
                                          1.0, 1.0, softening=1e-3)
        assert math.isfinite(a_i.magnitude())


class TestInvalidInput:
    def test_nan_mass(self):
        with pytest.raises(NBodyInvalidMassError):
            _b("x", float("nan"), (0, 0, 0), (0, 0, 0))

    def test_duplicate_ids(self):
        with pytest.raises(DuplicateBodyError):
            NBodySystem([_b("a", 1.0, (0, 0, 0), (0, 0, 0)),
                          _b("a", 1.0, (1, 0, 0), (0, 0, 0))])

    def test_invalid_dt(self):
        s = NBodySystem([_b("a", 1.0, (0, 0, 0), (0, 0, 0)),
                          _b("b", 1.0, (1, 0, 0), (0, 0, 0))])
        with AuthorityContext("test"):
            with pytest.raises(InvalidTimestepError):
                s.step(0.0)
            with pytest.raises(InvalidTimestepError):
                s.step(-1.0)
            with pytest.raises(InvalidTimestepError):
                s.step(float("nan"))
            with pytest.raises(InvalidTimestepError):
                s.step(float("inf"))


class TestExtremeScales:
    def test_huge_distances(self):
        a, _ = pairwise_acceleration(Vector3(0, 0, 0), Vector3(1e15, 0, 0),
                                      1e30, 1e30, softening=1.0)
        assert math.isfinite(a.magnitude())

    def test_tiny_distances_softened(self):
        a, _ = pairwise_acceleration(Vector3(0, 0, 0), Vector3(1e-10, 0, 0),
                                      1e30, 1e30, softening=1.0)
        assert math.isfinite(a.magnitude())

    def test_mass_ratio_1e9(self):
        bodies = [
            _b("big", 1e30, (0, 0, 0), (0, 0, 0)),
            _b("small", 1e21, (1e9, 0, 0), (0, 0, 0)),
        ]
        s = NBodySystem(bodies, softening=1.0)
        with AuthorityContext("test"):
            for _ in range(100):
                s.step(1.0)
        assert s.is_finite()


class TestDeterminism:
    def test_repeat_run(self):
        def run():
            bodies = [
                _b("a", 1.0, (0.1, 0.2, 0.3), (0.01, 0.02, 0.03)),
                _b("b", 2.0, (1.0, -0.5, 0.4), (-0.01, 0.01, 0.0)),
                _b("c", 3.0, (-0.7, 1.2, -0.2), (0.0, -0.01, 0.02)),
            ]
            s = NBodySystem(bodies, softening=0.01)
            with AuthorityContext("test"):
                for _ in range(500):
                    s.step(0.001)
            return [b.position.to_tuple() for b in s.bodies]
        assert run() == run()

    def test_repeat_from_snapshot(self):
        bodies = [
            _b("a", 1.0, (0.1, 0.2, 0.3), (0.01, 0.02, 0.03)),
            _b("b", 2.0, (1.0, -0.5, 0.4), (-0.01, 0.01, 0.0)),
        ]
        s = NBodySystem(bodies, softening=0.01)
        with AuthorityContext("test"):
            for _ in range(100):
                s.step(0.001)
        snap = s.to_dict()
        s2 = NBodySystem.from_dict(snap)
        with AuthorityContext("test"):
            for _ in range(100):
                s.step(0.001)
                s2.step(0.001)
        for a, b in zip(s.bodies, s2.bodies):
            assert a.position == b.position
            assert a.velocity == b.velocity


class TestConservation:
    def test_momentum_long_run(self):
        bodies = [
            _b("a", 1.0, (0.0, 0.0, 0.0), (0.1, 0.0, 0.0)),
            _b("b", 1.0, (2.0, 0.0, 0.0), (-0.1, 0.0, 0.0)),
            _b("c", 1.0, (0.0, 2.0, 0.0), (0.0, -0.1, 0.0)),
        ]
        s = NBodySystem(bodies, softening=0.05)
        P0 = s.total_linear_momentum()
        with AuthorityContext("test"):
            for _ in range(5000):
                s.step(0.001)
        P1 = s.total_linear_momentum()
        assert (P1 - P0).magnitude() < 1e-12

    def test_energy_bounded_drift(self):
        bodies = [
            _b("a", 1.0, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)),
            _b("b", 1.0, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        ]
        s = NBodySystem(bodies, softening=0.1)
        E0 = s.total_energy()
        with AuthorityContext("test"):
            for _ in range(5000):
                s.step(0.001)
        E1 = s.total_energy()
        # Symplectic integrator: bounded energy oscillation, no secular drift.
        assert abs(E1 - E0) / abs(E0) < 1e-3


class TestAuthority:
    def test_step_unauthorized(self):
        s = NBodySystem([_b("a", 1.0, (0, 0, 0), (0, 0, 0)),
                          _b("b", 1.0, (1, 0, 0), (0, 0, 0))])
        with pytest.raises(AuthorityError):
            s.step(0.01)

    def test_write_to_entities_requires_authority(self):
        # Standalone test: verify that write_to_motion_physics_entities
        # enforces authority even without a real entity manager.
        s = NBodySystem([_b("a", 1.0, (0, 0, 0), (0, 0, 0))])
        class _DummyEM:
            def get_entity(self, _eid):
                return None
        with pytest.raises(AuthorityError):
            s.write_to_motion_physics_entities(_DummyEM())


class TestEmptyAndSingle:
    def test_empty_system_energy_zero(self):
        s = NBodySystem()
        assert s.kinetic_energy() == 0.0
        assert s.total_energy() == 0.0

    def test_single_body_no_gravity(self):
        s = NBodySystem([_b("a", 1.0, (0, 0, 0), (1, 0, 0))])
        with AuthorityContext("test"):
            for _ in range(100):
                s.step(0.1)
        # No other body -> no acceleration -> straight-line motion
        b = s.bodies[0]
        assert b.position.x == pytest.approx(10.0, abs=1e-9)
        assert b.velocity.x == 1.0
