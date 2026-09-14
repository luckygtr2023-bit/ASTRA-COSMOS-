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
from astra.motion import MotionComponent, MotionSystem, MotionState
from astra.physics import (
    PhysicsSystem, PhysicsComponent, MassProperties,
    ConstantForce, GravitySource,
)


@pytest.fixture(autouse=True)
def sim_thread():
    reset_simulation_thread_registry()
    reg = get_simulation_thread_registry()
    reg.register_simulation_thread(threading.current_thread().ident)
    yield
    reset_simulation_thread_registry()


def _make_em():
    em = EntityManager()
    em.set_current_tick(0)
    return em


class TestForceToMotion:
    def test_constant_force_produces_acceleration(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent(state=MotionState()))
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(2.0)))
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [ConstantForce(Vector3(4.0, 0.0, 0.0))])

        with AuthorityContext("test.physics"):
            phys.compute_forces(0.01)
        mc = e.get_component(MotionComponent)
        assert mc.state.acceleration.x == pytest.approx(2.0, abs=1e-12)

    def test_constant_force_updates_velocity_via_motion(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent(state=MotionState()))
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(2.0)))
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [ConstantForce(Vector3(4.0, 0.0, 0.0))])

        with AuthorityContext("test.physics"):
            phys.step(1.0)
        mc = e.get_component(MotionComponent)
        # a = 2 m/s^2, dt = 1 s -> v = 2 m/s, x = 1 m (semi-implicit)
        assert mc.state.velocity.x == pytest.approx(2.0, abs=1e-12)
        assert mc.state.position.x == pytest.approx(2.0, abs=1e-12)

    def test_zero_force_constant_velocity(self):
        em = _make_em()
        e = em.create_entity("ship")
        st = MotionState()
        st.velocity = Vector3(3.0, 0.0, 0.0)
        e.add_component(MotionComponent(state=st))
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(1.0)))
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [ConstantForce(Vector3(0, 0, 0))])

        with AuthorityContext("test.physics"):
            for _ in range(10):
                phys.step(1.0)
        mc = e.get_component(MotionComponent)
        assert mc.state.position.x == pytest.approx(30.0, abs=1e-12)
        assert mc.state.velocity.x == pytest.approx(3.0, abs=1e-12)


class TestGravityIntegration:
    def test_free_fall_two_body(self):
        em = _make_em()
        e = em.create_entity("ship")
        st = MotionState()
        # Ship starts at rest at Earth's surface radius above the origin,
        # so r > 0 and the unsingularized force is well-defined.
        st.position = Vector3(0.0, 6.371e6, 0.0)
        e.add_component(MotionComponent(state=st))
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(1.0)))
        motion = MotionSystem(em)
        gravity = GravitySource(softening=0.0)
        gravity.add_body(5.972e24, Vector3(0, 0, 0))  # Earth-like
        phys = PhysicsSystem(em, motion, [gravity])

        with AuthorityContext("test.physics"):
            for _ in range(100):
                phys.step(0.1)
        mc = e.get_component(MotionComponent)
        # Ship started at rest at Earth's surface approximation; should
        # have non-zero velocity toward origin.
        assert mc.state.velocity.y != 0.0


class TestAuthority:
    def test_step_without_authority_rejected(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(1.0)))
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [ConstantForce(Vector3(1, 0, 0))])
        with pytest.raises(AuthorityError):
            phys.step(0.01)

    def test_compute_forces_without_authority_rejected(self):
        em = _make_em()
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [])
        with pytest.raises(AuthorityError):
            phys.compute_forces(0.01)


class TestDeterminism:
    def test_two_runs_identical(self):
        def run():
            em = _make_em()
            e = em.create_entity("ship")
            e.add_component(MotionComponent(state=MotionState()))
            e.add_component(PhysicsComponent(
                mass_properties=MassProperties.from_scalar_inertia(1.0, 1.0)))
            motion = MotionSystem(em)
            gravity = GravitySource(softening=0.0)
            gravity.add_body(100.0, Vector3(5.0, 0.0, 0.0))
            phys = PhysicsSystem(em, motion, [gravity])
            with AuthorityContext("test.determinism"):
                for _ in range(200):
                    phys.step(0.01)
            mc = e.get_component(MotionComponent)
            return (mc.state.position.to_tuple(), mc.state.velocity.to_tuple())
        a = run(); b = run()
        assert a == b


class TestSnapshot:
    def test_round_trip(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.solid_box(12.0, 1.0, 2.0, 3.0)))
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [])
        snap = phys.snapshot()
        assert e.id.value in snap
        e.get_component(PhysicsComponent).mass_properties = MassProperties.static()
        phys.restore_from_snapshot(snap)
        restored = e.get_component(PhysicsComponent).mass_properties
        assert restored.mass == 12.0
