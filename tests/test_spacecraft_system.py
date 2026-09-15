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
from astra.physics import PhysicsComponent, MassProperties
from astra.spacecraft import (
    SpacecraftSystem, SpacecraftComponent, SpacecraftState,
    SpacecraftMass, Engine, EngineSpec, FiniteBurn, ImpulsiveBurn,
    InvalidBurnError,
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


def _make_ship(em, engine=None, dry=100.0, prop=900.0):
    e = em.create_entity("ship")
    e.add_component(MotionComponent(state=MotionState()))
    e.add_component(PhysicsComponent(
        mass_properties=MassProperties.from_scalar_inertia(dry + prop, 1.0)))
    sc = SpacecraftComponent()
    sc.state.mass = SpacecraftMass(dry_mass=dry, propellant_mass=prop)
    if engine is not None:
        sc.state.add_engine(EngineSpec(engine=engine))
    e.add_component(sc)
    return e


class TestFiniteBurn:
    def test_basic_thrust(self):
        em = _make_em()
        engine = Engine(id="main", thrust_magnitude=1000.0,
                        specific_impulse=300.0,
                        thrust_direction_local=Vector3(1, 0, 0))
        e = _make_ship(em, engine=engine, dry=100.0, prop=900.0)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)

        with AuthorityContext("test"):
            sys.start_finite_burn(e.id.value,
                                  FiniteBurn(id="b1", engine_id="main",
                                             duration=10.0))
            sys.step(1.0)

        sc = e.get_component(SpacecraftComponent)
        mc = e.get_component(MotionComponent)
        # Force = 1000 N, m_total ~ 1000 kg -> a ~ 1 m/s^2
        assert mc.state.acceleration.x == pytest.approx(1.0, rel=1e-3)
        # Propellant consumed: mdot = 1000 / (300 * 9.80665) kg/s
        assert sc.state.mass.propellant_mass < 900.0
        assert sc.state.mass.propellant_mass > 899.0

    def test_burn_terminates_when_tank_empty(self):
        em = _make_em()
        engine = Engine(id="main", thrust_magnitude=10000.0,
                        specific_impulse=300.0,
                        thrust_direction_local=Vector3(1, 0, 0))
        e = _make_ship(em, engine=engine, dry=100.0, prop=0.5)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)

        with AuthorityContext("test"):
            sys.start_finite_burn(e.id.value,
                                  FiniteBurn(id="b1", engine_id="main",
                                             duration=100.0))
            sys.step(1.0)

        sc = e.get_component(SpacecraftComponent)
        assert sc.state.mass.is_empty
        assert sc.state.active_burn_id is None
        # All engines stopped
        for spec in sc.state.engine_specs:
            assert not spec.burning


class TestImpulsive:
    def test_impulsive_delta_v(self):
        em = _make_em()
        e = _make_ship(em, engine=None)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)

        with AuthorityContext("test"):
            sys.apply_impulsive(e.id.value,
                                 ImpulsiveBurn(id="i1",
                                                delta_v=Vector3(100.0, 0.0, 0.0)))
        mc = e.get_component(MotionComponent)
        assert mc.state.velocity.x == pytest.approx(100.0)


class TestAuthority:
    def test_step_requires_authority(self):
        em = _make_em()
        e = _make_ship(em)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with pytest.raises(AuthorityError):
            sys.step(0.01)

    def test_start_burn_requires_authority(self):
        em = _make_em()
        engine = Engine(id="m", thrust_magnitude=1.0, specific_impulse=300.0,
                        thrust_direction_local=Vector3(1, 0, 0))
        e = _make_ship(em, engine=engine)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with pytest.raises(AuthorityError):
            sys.start_finite_burn(e.id.value,
                                  FiniteBurn(id="b", engine_id="m", duration=1.0))


class TestGravity:
    def test_gravity_provider_used(self):
        class ConstantGravity:
            def acceleration_at(self, position, mass, t):
                return Vector3(0.0, -9.81, 0.0)

        em = _make_em()
        e = _make_ship(em, engine=None)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion, gravity_provider=ConstantGravity())

        with AuthorityContext("test"):
            sys.step(0.1)

        mc = e.get_component(MotionComponent)
        assert mc.state.acceleration.y == pytest.approx(-9.81)
        assert mc.state.velocity.y == pytest.approx(-0.981)

    def test_no_gravity_provider_zero_acc(self):
        em = _make_em()
        e = _make_ship(em, engine=None)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion, gravity_provider=None)
        with AuthorityContext("test"):
            sys.step(0.1)
        mc = e.get_component(MotionComponent)
        assert mc.state.acceleration.magnitude() == 0.0


class TestDeterminism:
    def test_repeat_run(self):
        def run():
            em = _make_em()
            engine = Engine(id="main", thrust_magnitude=1000.0,
                            specific_impulse=300.0,
                            thrust_direction_local=Vector3(1, 0, 0))
            e = _make_ship(em, engine=engine, dry=100.0, prop=900.0)
            motion = MotionSystem(em)
            sys = SpacecraftSystem(em, motion)
            with AuthorityContext("test"):
                sys.start_finite_burn(e.id.value,
                                      FiniteBurn(id="b1", engine_id="main",
                                                 duration=10.0))
                for _ in range(20):
                    sys.step(0.1)
            mc = e.get_component(MotionComponent)
            return (mc.state.position.to_tuple(),
                    mc.state.velocity.to_tuple(),
                    mc.state.acceleration.to_tuple())
        assert run() == run()


class TestPersistence:
    def test_round_trip(self):
        em = _make_em()
        engine = Engine(id="main", thrust_magnitude=1000.0,
                        specific_impulse=300.0,
                        thrust_direction_local=Vector3(1, 0, 0),
                        mount_offset_local=Vector3(0.5, 0.0, 0.0))
        e = _make_ship(em, engine=engine)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with AuthorityContext("test"):
            sys.step(0.1)
        snap = sys.snapshot()
        assert e.id.value in snap
        sc = e.get_component(SpacecraftComponent)
        sc.state.mass.propellant_mass = 0.0
        sys.restore_from_snapshot(snap)
        restored = e.get_component(SpacecraftComponent)
        assert restored.state.mass.propellant_mass == 900.0
