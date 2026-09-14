import math
import pytest
from astra.mathematics import Vector3, Matrix3, Quaternion
from astra.physics import (
    linear_momentum, angular_momentum, Impulse,
    velocity_change_from_impulse, angular_velocity_change_from_impulse,
    apply_impulse,
    kinetic_energy, gravitational_potential_energy, work, power,
    EnergyLedger,
    MassProperties,
    PhysicsError,
)


class TestMomentum:
    def test_linear(self):
        p = linear_momentum(2.0, Vector3(3, 0, 0))
        assert p == Vector3(6, 0, 0)

    def test_angular(self):
        I = Matrix3.diagonal(1.0, 2.0, 3.0)
        L = angular_momentum(I, Vector3(1, 1, 1))
        assert L == Vector3(1, 2, 3)


class TestImpulse:
    def test_velocity_change(self):
        dv = velocity_change_from_impulse(Vector3(4, 0, 0), 0.5)
        assert dv == Vector3(2, 0, 0)

    def test_angular_change_off_center(self):
        I_inv_world = Matrix3.identity()
        imp = Impulse(Vector3(1, 0, 0),
                      application_point=Vector3(0, 2, 0))
        dw = angular_velocity_change_from_impulse(
            imp, com_world=Vector3(0, 0, 0),
            inverse_inertia_world=I_inv_world)
        # d omega = I^-1 (r x J) = (0,2,0) x (1,0,0) = (0,0,-2) (right-handed)
        assert dw == Vector3(0, 0, -2)

    def test_apply_impulse(self):
        mp = MassProperties.from_scalar_inertia(2.0, 4.0)
        q = Quaternion.identity()
        v = Vector3(1, 0, 0)
        w = Vector3(0, 0, 0)
        imp = Impulse(Vector3(2, 0, 0))
        nv, nw = apply_impulse(imp, Vector3(0, 0, 0), mp, q, v, w)
        assert nv == Vector3(2, 0, 0)
        assert nw == Vector3(0, 0, 0)


class TestEnergy:
    def test_kinetic(self):
        assert kinetic_energy(2.0, Vector3(3, 4, 0)) == pytest.approx(25.0)

    def test_gravitational_pe(self):
        U = gravitational_potential_energy(2.0, 3.0, 1.0)
        assert U < 0.0

    def test_gravitational_pe_zero_distance(self):
        with pytest.raises(PhysicsError):
            gravitational_potential_energy(1.0, 1.0, 0.0)

    def test_work(self):
        assert work(Vector3(1, 0, 0), Vector3(5, 0, 0)) == 5.0

    def test_power(self):
        assert power(Vector3(1, 0, 0), Vector3(3, 0, 0)) == 3.0


class TestLedger:
    def test_zero_drift_no_work(self):
        led = EnergyLedger(initial_kinetic=10.0, initial_potential=0.0)
        assert led.drift(10.0, 0.0) == 0.0

    def test_positive_drift(self):
        led = EnergyLedger(initial_kinetic=10.0)
        assert led.drift(11.0, 0.0) == pytest.approx(1.0)

    def test_work_offset(self):
        led = EnergyLedger(initial_kinetic=10.0)
        led.record_work(5.0)
        assert led.drift(15.0, 0.0) == 0.0
