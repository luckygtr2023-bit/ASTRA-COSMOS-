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
    DuplicateBodyError, InvalidBodyError,
)


@pytest.fixture(autouse=True)
def sim_thread():
    reset_simulation_thread_registry()
    reg = get_simulation_thread_registry()
    reg.register_simulation_thread(threading.current_thread().ident)
    yield
    reset_simulation_thread_registry()


def _two_body():
    b1 = NBodyBody(id="sun", mass=1.0,
                   position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
    b2 = NBodyBody(id="planet", mass=1.0,
                   position=Vector3(1, 0, 0), velocity=Vector3(0, 1, 0))
    return [b1, b2]


class TestConstruction:
    def test_empty(self):
        s = NBodySystem()
        assert len(s) == 0

    def test_duplicate_id(self):
        b1 = NBodyBody(id="x", mass=1.0,
                       position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        b2 = NBodyBody(id="x", mass=1.0,
                       position=Vector3(1, 0, 0), velocity=Vector3(0, 0, 0))
        with pytest.raises(DuplicateBodyError):
            NBodySystem([b1, b2])


class TestStep:
    def test_step_requires_authority(self):
        s = NBodySystem(_two_body())
        with pytest.raises(AuthorityError):
            s.step(0.01)

    def test_step_with_authority(self):
        s = NBodySystem(_two_body())
        with AuthorityContext("test.nbody"):
            s.step(0.01)
        assert s.is_finite()

    def test_two_body_conserves_momentum(self):
        s = NBodySystem(_two_body(), softening=1e-6)
        P0 = s.total_linear_momentum()
        with AuthorityContext("test"):
            for _ in range(100):
                s.step(0.001)
        P1 = s.total_linear_momentum()
        assert (P1 - P0).magnitude() < 1e-15

    def test_two_body_conserves_energy_short(self):
        s = NBodySystem(_two_body(), softening=1e-6)
        E0 = s.total_energy()
        with AuthorityContext("test"):
            for _ in range(1000):
                s.step(0.0001)
        E1 = s.total_energy()
        assert abs(E1 - E0) / abs(E0) < 1e-4

    def test_deterministic(self):
        def run():
            s = NBodySystem(_two_body(), softening=1e-6)
            with AuthorityContext("test"):
                for _ in range(50):
                    s.step(0.001)
            return [b.position.to_tuple() for b in s.bodies]
        assert run() == run()


class TestMutation:
    def test_add_body_requires_authority(self):
        s = NBodySystem()
        b = NBodyBody(id="x", mass=1.0,
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        with pytest.raises(AuthorityError):
            s.add_body(b)

    def test_add_body_with_authority(self):
        s = NBodySystem()
        b = NBodyBody(id="x", mass=1.0,
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        with AuthorityContext("test"):
            s.add_body(b)
        assert len(s) == 1

    def test_add_duplicate_id_raises(self):
        s = NBodySystem()
        b = NBodyBody(id="x", mass=1.0,
                      position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        with AuthorityContext("test"):
            s.add_body(b)
            with pytest.raises(DuplicateBodyError):
                s.add_body(b)

    def test_remove_missing_raises(self):
        s = NBodySystem()
        with AuthorityContext("test"):
            with pytest.raises(InvalidBodyError):
                s.remove_body("missing")


class TestPersistence:
    def test_round_trip(self):
        s = NBodySystem(_two_body(), softening=1e-6)
        with AuthorityContext("test"):
            for _ in range(20):
                s.step(0.001)
        d = s.to_dict()
        s2 = NBodySystem.from_dict(d)
        assert len(s2) == len(s)
        for a, b in zip(s.bodies, s2.bodies):
            assert a.position == b.position
            assert a.velocity == b.velocity

    def test_corrupted_missing_bodies(self):
        with pytest.raises(InvalidBodyError):
            NBodySystem.from_dict({"schema_version": "1.0.0"})

    def test_incompatible_schema(self):
        with pytest.raises(InvalidBodyError):
            NBodySystem.from_dict({
                "schema_version": "2.0.0",
                "bodies": [],
            })


class TestDiagnostics:
    def test_center_of_mass(self):
        b1 = NBodyBody(id="a", mass=1.0,
                       position=Vector3(0, 0, 0), velocity=Vector3(0, 0, 0))
        b2 = NBodyBody(id="b", mass=3.0,
                       position=Vector3(4, 0, 0), velocity=Vector3(0, 0, 0))
        s = NBodySystem([b1, b2])
        R = s.center_of_mass()
        assert R.x == pytest.approx(3.0)

    def test_energy_sign(self):
        # G = 1.0 makes this a genuinely bound two-body: at r = 1,
        # |U| = G*m1*m2/r = 1.0 > K = 0.5, so E = K + U < 0.
        # (With the physical G = 6.67e-11 the same fixture is unbound:
        #  E = 0.5 - 6.67e-11 > 0, so the assertion would be wrong.)
        s = NBodySystem(_two_body(), G=1.0, softening=1e-6)
        # Bound two-body: E < 0
        E = s.total_energy()
        assert E < 0.0
