"""Adversarial physics tests."""
import math
import threading
import pytest

from astra.core.entities import EntityManager
from astra.core.threading import (
    AuthorityContext, get_simulation_thread_registry,
    reset_simulation_thread_registry,
)
from astra.core.exceptions import AuthorityError
from astra.mathematics import Vector3, Matrix3, Quaternion
from astra.motion import MotionComponent, MotionSystem, MotionState
from astra.physics import (
    PhysicsSystem, PhysicsComponent, MassProperties,
    ConstantForce, GravitySource, mutual_gravity_force,
    InvalidMassError, InvalidForceError, InvalidGravityError,
    GRAVITATIONAL_CONSTANT,
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


class TestNaNInf:
    def test_nan_force_rejected(self):
        with pytest.raises(InvalidForceError):
            ConstantForce(Vector3(float("nan"), 0, 0))

    def test_inf_force_rejected(self):
        with pytest.raises(InvalidForceError):
            ConstantForce(Vector3(float("inf"), 0, 0))

    def test_nan_mass_rejected(self):
        with pytest.raises(InvalidMassError):
            MassProperties.point_mass(float("nan"))

    def test_inf_position_in_gravity_rejected(self):
        src = GravitySource()
        with pytest.raises(InvalidGravityError):
            src.force_on(1.0, Vector3(float("inf"), 0, 0))


class TestZeroDistance:
    def test_softening_finite(self):
        f = mutual_gravity_force(1.0, Vector3(0, 0, 0),
                                 1.0, Vector3(0, 0, 0), eps=1e-6)
        assert math.isfinite(f.magnitude())

    def test_no_softening_raises(self):
        with pytest.raises(InvalidGravityError):
            mutual_gravity_force(1.0, Vector3(0, 0, 0),
                                 1.0, Vector3(0, 0, 0), eps=0.0)


class TestExtremeValues:
    def test_huge_distance(self):
        f = mutual_gravity_force(1e30, Vector3(0, 0, 0),
                                 1e30, Vector3(1e12, 0, 0),
                                 eps=0.0)
        assert math.isfinite(f.magnitude())
        # F ~ G m1 m2 / r^2 ~ 6.67e-11 * 1e60 / 1e24 = 6.67e25
        assert f.magnitude() > 1e24

    def test_tiny_mass_product(self):
        f = mutual_gravity_force(1e-20, Vector3(0, 0, 0),
                                 1e-20, Vector3(1, 0, 0),
                                 eps=0.0)
        assert math.isfinite(f.magnitude())

    def test_huge_force_acceleration(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(1e-30)))
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [ConstantForce(Vector3(1e30, 0, 0))])
        with AuthorityContext("test"):
            phys.compute_forces(0.01)
        mc = e.get_component(MotionComponent)
        assert mc.state.acceleration.x == pytest.approx(1e60)
        assert math.isfinite(mc.state.acceleration.x)


class TestStaticBody:
    def test_static_not_affected_by_force(self):
        em = _make_em()
        e = em.create_entity("wall")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(mass_properties=MassProperties.static()))
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [ConstantForce(Vector3(1e30, 0, 0))])
        with AuthorityContext("test"):
            phys.step(1.0)
        mc = e.get_component(MotionComponent)
        assert mc.state.position == Vector3(0, 0, 0)
        assert mc.state.velocity == Vector3(0, 0, 0)


class TestPointMassTorque:
    def test_torque_produces_zero_alpha_on_point_mass(self):
        em = _make_em()
        e = em.create_entity("p")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(1.0)))

        class PureTorque:
            name = "torque"
            def evaluate(self, mass, position, orientation, velocity,
                         angular_velocity, dt):
                from astra.physics import ForceApplication
                return (ForceApplication(torque=Vector3(0, 0, 1.0)),)
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [PureTorque()])
        with AuthorityContext("test"):
            phys.compute_forces(0.01)
        mc = e.get_component(MotionComponent)
        assert mc.state.angular_acceleration == Vector3(0, 0, 0)


class TestRigidBodyRotation:
    def test_torque_produces_angular_acceleration(self):
        em = _make_em()
        e = em.create_entity("dumbbell")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.from_scalar_inertia(1.0, 2.0)))

        class PureTorque:
            name = "torque"
            def evaluate(self, mass, position, orientation, velocity,
                         angular_velocity, dt):
                from astra.physics import ForceApplication
                return (ForceApplication(torque=Vector3(0, 0, 4.0)),)
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [PureTorque()])
        with AuthorityContext("test"):
            phys.compute_forces(0.01)
        mc = e.get_component(MotionComponent)
        # alpha = I^-1 tau = 0.5 * 4 = 2 rad/s^2
        assert mc.state.angular_acceleration.z == pytest.approx(2.0, abs=1e-12)


class TestLongRunStability:
    def test_no_nan_after_long_simulation(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(1.0)))
        motion = MotionSystem(em)
        gravity = GravitySource(softening=0.1)
        gravity.add_body(1e10, Vector3(10, 0, 0))
        phys = PhysicsSystem(em, motion, [gravity])
        with AuthorityContext("test"):
            for _ in range(5000):
                phys.step(0.01)
        mc = e.get_component(MotionComponent)
        assert mc.state.is_finite()


class TestAuthorityBypass:
    def test_no_authority_no_mutation(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.point_mass(1.0)))
        motion = MotionSystem(em)
        phys = PhysicsSystem(em, motion, [ConstantForce(Vector3(1, 0, 0))])
        with pytest.raises(AuthorityError):
            phys.step(0.01)
        # Nothing was mutated.
        mc = e.get_component(MotionComponent)
        assert mc.state.acceleration == Vector3(0, 0, 0)
