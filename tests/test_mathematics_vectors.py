import math
import pytest
from astra.mathematics.vectors import Vector2, Vector3, VectorN
from astra.mathematics.constants import PI

class TestVector3Basics:
    def test_add_sub(self):
        a = Vector3(1, 2, 3); b = Vector3(4, 5, 6)
        assert a + b == Vector3(5, 7, 9)
        assert b - a == Vector3(3, 3, 3)
        assert -a == Vector3(-1, -2, -3)
    def test_scale(self):
        a = Vector3(1, 2, 3)
        assert a * 2 == Vector3(2, 4, 6)
        assert 2 * a == Vector3(2, 4, 6)
        assert a / 2 == Vector3(0.5, 1.0, 1.5)
    def test_div_zero(self):
        with pytest.raises(ZeroDivisionError):
            Vector3(1, 2, 3) / 0.0
    def test_dot(self):
        assert Vector3(1, 0, 0).dot(Vector3(0, 1, 0)) == 0.0
        assert Vector3(1, 2, 3).dot(Vector3(4, 5, 6)) == 32.0
    def test_cross(self):
        x = Vector3(1, 0, 0); y = Vector3(0, 1, 0); z = Vector3(0, 0, 1)
        assert x.cross(y) == z
        assert y.cross(z) == x
        assert z.cross(x) == y
        assert x.cross(x) == Vector3(0, 0, 0)
    def test_cross_anticommutative(self):
        a = Vector3(1, 2, 3); b = Vector3(4, 5, 6)
        assert a.cross(b) == -(b.cross(a))

class TestVector3Magnitude:
    def test_magnitude(self):
        assert Vector3(3, 4, 0).magnitude() == 5.0
        assert Vector3(0, 0, 0).magnitude() == 0.0
    def test_normalized(self):
        v = Vector3(3, 4, 0).normalized()
        assert math.isclose(v.magnitude(), 1.0, abs_tol=1e-12)
    def test_normalize_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Vector3(0, 0, 0).normalized()
    def test_magnitude_overflow_safe(self):
        big = Vector3(1e200, 1e200, 1e200)
        assert math.isfinite(big.magnitude())

class TestVector3Projection:
    def test_project(self):
        v = Vector3(3, 4, 0)
        proj = v.project_onto(Vector3(1, 0, 0))
        assert proj == Vector3(3, 0, 0)
    def test_project_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Vector3(1, 1, 1).project_onto(Vector3(0, 0, 0))
    def test_reject(self):
        v = Vector3(3, 4, 0)
        r = v.reject_from(Vector3(1, 0, 0))
        assert r == Vector3(0, 4, 0)
    def test_reflect(self):
        v = Vector3(1, -1, 0)
        r = v.reflect(Vector3(0, 1, 0))
        assert r == Vector3(1, 1, 0)

class TestVector3Interp:
    def test_lerp(self):
        a = Vector3(0, 0, 0); b = Vector3(10, 20, 30)
        assert a.lerp(b, 0.5) == Vector3(5, 10, 15)
        assert a.lerp(b, 0.0) == a
        assert a.lerp(b, 1.0) == b
        assert a.lerp(b, 2.0) == Vector3(20, 40, 60)
    def test_angle(self):
        x = Vector3(1, 0, 0); y = Vector3(0, 1, 0)
        assert math.isclose(x.angle_to(y), PI / 2, abs_tol=1e-12)
        assert math.isclose(x.angle_to(x), 0.0, abs_tol=1e-12)

class TestVector3Tuple:
    def test_roundtrip(self):
        v = Vector3(1, 2, 3)
        assert Vector3.from_tuple(v.to_tuple()) == v
    def test_from_bad_tuple(self):
        with pytest.raises(ValueError):
            Vector3.from_tuple((1, 2))

class TestVector2:
    def test_basic(self):
        a = Vector2(3, 4)
        assert a.magnitude() == 5.0
        assert a.normalized().magnitude() == pytest.approx(1.0)
    def test_cross_scalar(self):
        assert Vector2(1, 0).cross(Vector2(0, 1)) == 1.0
    def test_rotation(self):
        v = Vector2(1, 0).rotated(PI / 2)
        assert v.x == pytest.approx(0.0, abs=1e-12)
        assert v.y == pytest.approx(1.0, abs=1e-12)

class TestVectorN:
    def test_ops(self):
        a = VectorN([1, 2, 3]); b = VectorN([4, 5, 6])
        assert (a + b).to_tuple() == (5.0, 7.0, 9.0)
        assert a.dot(b) == 32.0
        assert a.magnitude() == pytest.approx(math.sqrt(14))
    def test_dim_mismatch(self):
        with pytest.raises(ValueError):
            VectorN([1, 2]) + VectorN([1, 2, 3])
    def test_normalize_zero(self):
        with pytest.raises(ZeroDivisionError):
            VectorN([0, 0, 0]).normalized()
