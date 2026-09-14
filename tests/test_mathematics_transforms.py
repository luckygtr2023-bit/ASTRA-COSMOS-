import math
import pytest
from astra.mathematics.transforms import Transform
from astra.mathematics.vectors import Vector3
from astra.mathematics.matrices import Matrix3
from astra.mathematics.quaternions import Quaternion
from astra.mathematics.constants import PI

class TestTransform:
    def test_identity(self):
        T = Transform.identity()
        v = Vector3(1, 2, 3)
        assert T.apply(v) == v
    def test_translation(self):
        T = Transform.from_translation(Vector3(1, 2, 3))
        assert T.apply(Vector3(0, 0, 0)) == Vector3(1, 2, 3)
    def test_rotation(self):
        R = Matrix3.rotation_z(PI / 2)
        T = Transform.from_rotation(R)
        v = T.apply(Vector3(1, 0, 0))
        assert v.x == pytest.approx(0.0, abs=1e-12)
        assert v.y == pytest.approx(1.0, abs=1e-12)
    def test_compose(self):
        T1 = Transform.from_translation(Vector3(1, 0, 0))
        T2 = Transform.from_translation(Vector3(0, 1, 0))
        T = T1.compose(T2)
        assert T.apply(Vector3(0, 0, 0)) == Vector3(1, 1, 0)
    def test_inverse(self):
        T = Transform.from_translation(Vector3(5, -3, 2))
        Ti = T.inverse()
        v = Vector3(1, 1, 1)
        assert Ti.apply(T.apply(v)).distance_to(v) < 1e-12
    def test_inverse_zero_scale(self):
        T = Transform(Matrix3.identity(), Vector3(0, 0, 0), Vector3(0, 1, 1))
        with pytest.raises(ValueError):
            T.inverse()
    def test_from_core_origin(self):
        T = Transform.from_core_origin((1.0, 2.0, 3.0))
        assert T.apply(Vector3(0, 0, 0)) == Vector3(1, 2, 3)
    def test_from_quaternion(self):
        q = Quaternion.from_axis_angle(Vector3(0, 0, 1), PI / 2)
        T = Transform.from_quaternion(q)
        v = T.apply(Vector3(1, 0, 0))
        assert v.y == pytest.approx(1.0, abs=1e-12)
