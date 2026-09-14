import math
import pytest
from astra.mathematics.quaternions import Quaternion
from astra.mathematics.vectors import Vector3
from astra.mathematics.constants import PI

class TestQuaternionBasics:
    def test_identity(self):
        q = Quaternion.identity()
        assert q == Quaternion(1, 0, 0, 0)
        assert q.norm() == 1.0
    def test_from_axis_angle(self):
        q = Quaternion.from_axis_angle(Vector3(0, 0, 1), PI / 2)
        v = q.rotate(Vector3(1, 0, 0))
        assert v.x == pytest.approx(0.0, abs=1e-12)
        assert v.y == pytest.approx(1.0, abs=1e-12)
        assert v.z == pytest.approx(0.0, abs=1e-12)
    def test_conjugate(self):
        q = Quaternion(1, 2, 3, 4)
        assert q.conjugate() == Quaternion(1, -2, -3, -4)
    def test_inverse(self):
        q = Quaternion.from_axis_angle(Vector3(1, 2, 3), 0.7)
        prod = q.multiply(q.inverse())
        assert prod.w == pytest.approx(1.0, abs=1e-12)
        assert prod.x == pytest.approx(0.0, abs=1e-12)
    def test_zero_inverse(self):
        with pytest.raises(ZeroDivisionError):
            Quaternion(0, 0, 0, 0).inverse()
    def test_normalize(self):
        q = Quaternion(2, 0, 0, 0).normalized()
        assert q.norm() == pytest.approx(1.0)
    def test_normalize_zero(self):
        with pytest.raises(ZeroDivisionError):
            Quaternion(0, 0, 0, 0).normalized()

class TestQuaternionRotation:
    def test_preserves_magnitude(self):
        q = Quaternion.from_axis_angle(Vector3(1, 1, 1), 1.1)
        v = Vector3(2, -3, 4)
        r = q.rotate(v)
        assert math.isclose(r.magnitude(), v.magnitude(), abs_tol=1e-12)
    def test_identity_rotation(self):
        q = Quaternion.identity()
        v = Vector3(1, 2, 3)
        assert q.rotate(v) == v
    def test_composition_matches_matrix(self):
        q1 = Quaternion.from_axis_angle(Vector3(0, 0, 1), 0.3)
        q2 = Quaternion.from_axis_angle(Vector3(1, 0, 0), 0.5)
        q = q1.multiply(q2)
        v = Vector3(1, 2, 3)
        r1 = q.rotate(v)
        r2 = q1.rotate(q2.rotate(v))
        assert r1.x == pytest.approx(r2.x, abs=1e-12)
        assert r1.y == pytest.approx(r2.y, abs=1e-12)
        assert r1.z == pytest.approx(r2.z, abs=1e-12)

class TestQuaternionInterp:
    def test_slerp_endpoints(self):
        a = Quaternion.identity()
        b = Quaternion.from_axis_angle(Vector3(0, 0, 1), PI)
        assert a.slerp(b, 0.0).w == pytest.approx(a.w)
        r = a.slerp(b, 1.0)
        assert min((r - b).norm(), (r + b).norm()) < 1e-9
    def test_slerp_half(self):
        a = Quaternion.identity()
        b = Quaternion.from_axis_angle(Vector3(0, 0, 1), PI / 2)
        m = a.slerp(b, 0.5)
        v = m.rotate(Vector3(1, 0, 0))
        assert v.x == pytest.approx(math.cos(PI / 4), abs=1e-9)
        assert v.y == pytest.approx(math.sin(PI / 4), abs=1e-9)
    def test_slerp_nearly_parallel(self):
        a = Quaternion.identity()
        b = Quaternion.from_axis_angle(Vector3(0, 0, 1), 1e-8)
        r = a.slerp(b, 0.5)
        assert math.isfinite(r.norm())
