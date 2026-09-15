import math
import pytest
from astra.mathematics import Vector3, Quaternion
from astra.spacecraft import (
    Engine, EngineSpec,
    engine_mass_flow, engine_thrust_world, engine_torque_world,
    evaluate_engines,
    InvalidEngineError,
)


def _engine(id="main", T=1000.0, Isp=300.0, d=(1, 0, 0), off=(0, 0, 0)):
    return Engine(id=id, thrust_magnitude=T, specific_impulse=Isp,
                  thrust_direction_local=Vector3(*d),
                  mount_offset_local=Vector3(*off))


class TestEngine:
    def test_valid(self):
        e = _engine()
        assert e.id == "main"

    def test_zero_thrust_ok(self):
        e = _engine(T=0.0)
        assert e.thrust_magnitude == 0.0

    def test_empty_id(self):
        with pytest.raises(InvalidEngineError):
            _engine(id="")

    def test_bad_isp(self):
        with pytest.raises(InvalidEngineError):
            _engine(Isp=0.0)
        with pytest.raises(InvalidEngineError):
            _engine(Isp=-1.0)

    def test_zero_direction(self):
        with pytest.raises(InvalidEngineError):
            _engine(d=(0, 0, 0))

    def test_mass_flow(self):
        e = _engine(T=1000.0, Isp=300.0)
        # mdot = 1000 / (300 * 9.80665)
        assert engine_mass_flow(e) == pytest.approx(1000.0 / (300.0 * 9.80665))


class TestThrustVector:
    def test_identity_orientation(self):
        e = _engine(d=(1, 0, 0), T=500.0)
        f = engine_thrust_world(e, Quaternion.identity())
        assert f.x == pytest.approx(500.0)
        assert f.y == 0.0
        assert f.z == 0.0

    def test_rotated(self):
        e = _engine(d=(1, 0, 0), T=500.0)
        q = Quaternion.from_axis_angle(Vector3(0, 0, 1), math.pi / 2)
        f = engine_thrust_world(e, q)
        assert f.x == pytest.approx(0.0, abs=1e-9)
        assert f.y == pytest.approx(500.0, abs=1e-9)

    def test_direction_normalized(self):
        e = Engine(id="e", thrust_magnitude=100.0, specific_impulse=300.0,
                   thrust_direction_local=Vector3(2.0, 0.0, 0.0))
        f = engine_thrust_world(e, Quaternion.identity())
        assert f.magnitude() == pytest.approx(100.0)


class TestTorque:
    def test_offset_creates_torque(self):
        e = _engine(d=(1, 0, 0), T=100.0, off=(0, 1, 0))
        t = engine_torque_world(e, Quaternion.identity())
        # r = (0,1,0), F = (100,0,0), r x F = (0,0,-100)
        assert t.z == pytest.approx(-100.0)

    def test_zero_offset_no_torque(self):
        e = _engine(d=(1, 0, 0), T=100.0, off=(0, 0, 0))
        assert engine_torque_world(e, Quaternion.identity()).magnitude() == 0.0


class TestEvaluateEngines:
    def test_no_burning(self):
        spec = EngineSpec(engine=_engine(), enabled=True, burning=False)
        evals, used = evaluate_engines([spec], Quaternion.identity(), 100.0, 1.0)
        assert evals == []
        assert used == 0.0

    def test_burning_consumes(self):
        spec = EngineSpec(engine=_engine(T=1000.0, Isp=300.0),
                          enabled=True, burning=True)
        evals, used = evaluate_engines([spec], Quaternion.identity(), 100.0, 1.0)
        assert len(evals) == 1
        assert evals[0].thrust_force_world.x == pytest.approx(1000.0)
        # mdot = 1000/(300*9.80665) ≈ 0.3399 kg/s
        assert used == pytest.approx(1000.0 / (300.0 * 9.80665))

    def test_truncated_when_propellant_short(self):
        spec = EngineSpec(engine=_engine(T=1000.0, Isp=300.0),
                          enabled=True, burning=True)
        # only 0.1 kg available, mdot ~0.34 kg/s
        evals, used = evaluate_engines([spec], Quaternion.identity(), 0.1, 1.0)
        assert len(evals) == 1
        assert used == pytest.approx(0.1)
        assert evals[0].terminated is True

    def test_two_engines_deterministic_order(self):
        a = EngineSpec(engine=_engine(id="a", T=100.0, Isp=300.0),
                       enabled=True, burning=True)
        b = EngineSpec(engine=_engine(id="b", T=200.0, Isp=300.0),
                       enabled=True, burning=True)
        evals1, _ = evaluate_engines([a, b], Quaternion.identity(), 100.0, 0.1)
        evals2, _ = evaluate_engines([a, b], Quaternion.identity(), 100.0, 0.1)
        assert [e.engine_id for e in evals1] == ["a", "b"]
        assert [e.engine_id for e in evals2] == ["a", "b"]
        # Reverse order gives different iteration
        evals3, _ = evaluate_engines([b, a], Quaternion.identity(), 100.0, 0.1)
        assert [e.engine_id for e in evals3] == ["b", "a"]
