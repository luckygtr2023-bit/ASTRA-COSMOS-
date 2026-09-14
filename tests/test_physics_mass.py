import math
import pytest
from astra.mathematics import Matrix3, Vector3, Quaternion
from astra.physics import (
    MassProperties, InvalidMassError,
)


class TestFactories:
    def test_static(self):
        mp = MassProperties.static()
        assert mp.is_static
        assert mp.inverse_mass == 0.0
        assert mp.mass == math.inf

    def test_point_mass(self):
        mp = MassProperties.point_mass(2.0)
        assert not mp.is_static
        assert mp.inverse_mass == 0.5
        assert mp.is_point_mass

    def test_scalar_inertia(self):
        mp = MassProperties.from_scalar_inertia(2.0, 4.0)
        assert mp.inverse_mass == 0.5
        assert mp.inertia_body == Matrix3.diagonal(4, 4, 4)
        assert mp.inverse_inertia_body == Matrix3.diagonal(0.25, 0.25, 0.25)

    def test_tensor_inertia(self):
        I = Matrix3.diagonal(1.0, 2.0, 3.0)
        mp = MassProperties.from_tensor(1.0, I)
        assert mp.inertia_body == I

    def test_sphere(self):
        mp = MassProperties.sphere(2.0, 1.0)
        expected_I = (2.0 / 5.0) * 2.0 * 1.0
        assert mp.inertia_body == Matrix3.diagonal(expected_I,
                                                    expected_I,
                                                    expected_I)

    def test_solid_box(self):
        mp = MassProperties.solid_box(12.0, 1.0, 2.0, 3.0)
        assert mp.mass == 12.0
        # I_x = (1/12) * m * (sy^2 + sz^2) = (1/12)*12*(4+9) = 13
        assert mp.inertia_body.m00 == pytest.approx(13.0)
        assert mp.inertia_body.m11 == pytest.approx(10.0)
        assert mp.inertia_body.m22 == pytest.approx(5.0)


class TestInvalid:
    def test_zero_mass(self):
        with pytest.raises(InvalidMassError):
            MassProperties.point_mass(0.0)

    def test_negative_mass(self):
        with pytest.raises(InvalidMassError):
            MassProperties.point_mass(-1.0)

    def test_nan_mass(self):
        with pytest.raises(InvalidMassError):
            MassProperties.point_mass(float("nan"))

    def test_zero_inertia(self):
        with pytest.raises(InvalidMassError):
            MassProperties.from_scalar_inertia(1.0, 0.0)

    def test_negative_definite_tensor(self):
        with pytest.raises(InvalidMassError):
            MassProperties.from_tensor(1.0, Matrix3.diagonal(-1.0, 1.0, 1.0))


class TestWorldInertia:
    def test_scalar_invariance(self):
        mp = MassProperties.from_scalar_inertia(1.0, 2.0)
        q = Quaternion.from_axis_angle(Vector3(1, 1, 1), 0.7)
        I_world = mp.world_inertia(q)
        assert I_world.m00 == pytest.approx(2.0)
        assert I_world.m11 == pytest.approx(2.0)
        assert I_world.m22 == pytest.approx(2.0)

    def test_tensor_rotates(self):
        I = Matrix3.diagonal(1.0, 2.0, 3.0)
        mp = MassProperties.from_tensor(1.0, I)
        q = Quaternion.from_axis_angle(Vector3(0, 0, 1), math.pi / 2)
        I_world = mp.world_inertia(q)
        # After 90deg rotation about z, x and y swap in world frame.
        assert I_world.m00 == pytest.approx(2.0, abs=1e-9)
        assert I_world.m11 == pytest.approx(1.0, abs=1e-9)


class TestSerialization:
    def test_round_trip(self):
        mp = MassProperties.solid_box(12.0, 1.0, 2.0, 3.0)
        d = mp.to_dict()
        mp2 = MassProperties.from_dict(d)
        assert mp2.mass == mp.mass
        assert mp2.inertia_body == mp.inertia_body
        assert mp2.inverse_inertia_body == mp.inverse_inertia_body
