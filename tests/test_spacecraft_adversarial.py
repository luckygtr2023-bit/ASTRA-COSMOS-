"""Adversarial Spacecraft Physics tests."""
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
    InvalidBurnError, InvalidEngineError, SpacecraftInvalidMassError,
    rocket_delta_v, InvalidRocketEquationError,
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


class TestNumericalEdges:
    def test_very_small_isp_engine(self):
        e = Engine(id="x", thrust_magnitude=1.0, specific_impulse=1.0,
                   thrust_direction_local=Vector3(1, 0, 0))
        assert e.mass_flow_rate > 0.0

    def test_huge_isp_engine(self):
        e = Engine(id="x", thrust_magnitude=1.0, specific_impulse=1e6,
                   thrust_direction_local=Vector3(1, 0, 0))
        assert math.isfinite(e.mass_flow_rate)

    def test_zero_thrust_engine(self):
        e = Engine(id="x", thrust_magnitude=0.0, specific_impulse=300.0,
                   thrust_direction_local=Vector3(1, 0, 0))
        assert e.mass_flow_rate == 0.0

    def test_nan_thrust_rejected(self):
        with pytest.raises(InvalidEngineError):
            Engine(id="x", thrust_magnitude=float("nan"),
                   specific_impulse=300.0,
                   thrust_direction_local=Vector3(1, 0, 0))

    def test_inf_isp_rejected(self):
        with pytest.raises(InvalidEngineError):
            Engine(id="x", thrust_magnitude=1.0,
                   specific_impulse=float("inf"),
                   thrust_direction_local=Vector3(1, 0, 0))


class TestPropellantExhaustion:
    def test_multi_engine_shared_tank(self):
        em = _make_em()
        engine1 = Engine(id="a", thrust_magnitude=5000.0,
                         specific_impulse=300.0,
                         thrust_direction_local=Vector3(1, 0, 0))
        engine2 = Engine(id="b", thrust_magnitude=5000.0,
                         specific_impulse=300.0,
                         thrust_direction_local=Vector3(1, 0, 0))
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.from_scalar_inertia(200.0, 1.0)))
        sc = SpacecraftComponent()
        sc.state.mass = SpacecraftMass(dry_mass=100.0, propellant_mass=0.1)
        sc.state.add_engine(EngineSpec(engine=engine1, burning=True))
        sc.state.add_engine(EngineSpec(engine=engine2, burning=True))
        e.add_component(sc)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with AuthorityContext("test"):
            sys.step(1.0)
        sc_after = e.get_component(SpacecraftComponent)
        assert sc_after.state.mass.is_empty

    def test_never_negative_propellant(self):
        em = _make_em()
        engine = Engine(id="a", thrust_magnitude=1e6,
                        specific_impulse=300.0,
                        thrust_direction_local=Vector3(1, 0, 0))
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.from_scalar_inertia(200.0, 1.0)))
        sc = SpacecraftComponent()
        sc.state.mass = SpacecraftMass(dry_mass=100.0, propellant_mass=1e-10)
        sc.state.add_engine(EngineSpec(engine=engine, burning=True))
        e.add_component(sc)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with AuthorityContext("test"):
            for _ in range(100):
                sys.step(0.1)
        sc_after = e.get_component(SpacecraftComponent)
        assert sc_after.state.mass.propellant_mass >= 0.0


class TestBurnLifecycle:
    def test_no_double_burn(self):
        em = _make_em()
        engine = Engine(id="a", thrust_magnitude=1000.0,
                        specific_impulse=300.0,
                        thrust_direction_local=Vector3(1, 0, 0))
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.from_scalar_inertia(1000.0, 1.0)))
        sc = SpacecraftComponent()
        sc.state.mass = SpacecraftMass(dry_mass=100.0, propellant_mass=900.0)
        sc.state.add_engine(EngineSpec(engine=engine))
        e.add_component(sc)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with AuthorityContext("test"):
            sys.start_finite_burn(e.id.value,
                                  FiniteBurn(id="b1", engine_id="a", duration=1.0))
            with pytest.raises(InvalidBurnError):
                sys.start_finite_burn(e.id.value,
                                      FiniteBurn(id="b2", engine_id="a", duration=1.0))

    def test_cancel_burn_stops_thrust(self):
        em = _make_em()
        engine = Engine(id="a", thrust_magnitude=1000.0,
                        specific_impulse=300.0,
                        thrust_direction_local=Vector3(1, 0, 0))
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(PhysicsComponent(
            mass_properties=MassProperties.from_scalar_inertia(1000.0, 1.0)))
        sc = SpacecraftComponent()
        sc.state.mass = SpacecraftMass(dry_mass=100.0, propellant_mass=900.0)
        sc.state.add_engine(EngineSpec(engine=engine))
        e.add_component(sc)
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with AuthorityContext("test"):
            sys.start_finite_burn(e.id.value,
                                  FiniteBurn(id="b1", engine_id="a", duration=100.0))
            sys.cancel_burn(e.id.value)
            sys.step(0.1)
        mc = e.get_component(MotionComponent)
        assert mc.state.acceleration.magnitude() == 0.0


class TestDeterminism:
    def test_repeat_identical_burn(self):
        def run():
            em = _make_em()
            engine = Engine(id="main", thrust_magnitude=1000.0,
                            specific_impulse=300.0,
                            thrust_direction_local=Vector3(1, 0, 0),
                            mount_offset_local=Vector3(0.1, 0.0, 0.0))
            e = em.create_entity("ship")
            e.add_component(MotionComponent())
            e.add_component(PhysicsComponent(
                mass_properties=MassProperties.from_scalar_inertia(1000.0, 1.0)))
            sc = SpacecraftComponent()
            sc.state.mass = SpacecraftMass(dry_mass=100.0, propellant_mass=900.0)
            sc.state.add_engine(EngineSpec(engine=engine))
            e.add_component(sc)
            motion = MotionSystem(em)
            sys = SpacecraftSystem(em, motion)
            with AuthorityContext("test"):
                sys.start_finite_burn(
                    e.id.value,
                    FiniteBurn(id="b", engine_id="main", duration=5.0))
                for _ in range(50):
                    sys.step(0.05)
            sc2 = e.get_component(SpacecraftComponent)
            mc = e.get_component(MotionComponent)
            return (mc.state.position.to_tuple(),
                    mc.state.velocity.to_tuple(),
                    mc.state.orientation.to_tuple(),
                    sc2.state.mass.propellant_mass)
        r1 = run()
        r2 = run()
        assert r1 == r2


class TestAuthorityBypass:
    def test_cancel_requires_authority(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(SpacecraftComponent())
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with pytest.raises(AuthorityError):
            sys.cancel_burn(e.id.value, require_authority=True)

    def test_impulsive_requires_authority(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(SpacecraftComponent())
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with pytest.raises(AuthorityError):
            sys.apply_impulsive(
                e.id.value,
                ImpulsiveBurn(id="i", delta_v=Vector3(1, 0, 0)))


class TestNonFiniteInputs:
    def test_nan_dt(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(SpacecraftComponent())
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with AuthorityContext("test"):
            with pytest.raises(Exception):
                sys.step(float("nan"))

    def test_zero_dt(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(SpacecraftComponent())
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with AuthorityContext("test"):
            with pytest.raises(Exception):
                sys.step(0.0)

    def test_negative_dt(self):
        em = _make_em()
        e = em.create_entity("ship")
        e.add_component(MotionComponent())
        e.add_component(SpacecraftComponent())
        motion = MotionSystem(em)
        sys = SpacecraftSystem(em, motion)
        with AuthorityContext("test"):
            with pytest.raises(Exception):
                sys.step(-1.0)


class TestMassFlowEdge:
    def test_consumption_accounting_exact(self):
        # Burn exactly long enough to consume a known amount
        m = SpacecraftMass(dry_mass=100.0, propellant_mass=1.0)
        removed = m.consume(0.3)
        assert removed == 0.3
        assert m.propellant_mass == 0.7

    def test_depletes_exactly_at_boundary(self):
        m = SpacecraftMass(dry_mass=100.0, propellant_mass=0.5)
        removed = m.consume(0.5)
        assert removed == 0.5
        assert m.propellant_mass == 0.0
