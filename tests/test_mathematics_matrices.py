import math
import pytest
from astra.mathematics.matrices import Matrix3, Matrix4
from astra.mathematics.vectors import Vector3

class TestMatrix3:
    def test_identity(self):
        I = Matrix3.identity()
        v = Vector3(1, 2, 3)
        assert I.transform(v) == v
    def test_matmul_identity(self):
        A = Matrix3(1, 2, 3, 4, 5, 6, 7, 8, 9)
        assert A.matmul(Matrix3.identity()) == A
        assert Matrix3.identity().matmul(A) == A
    def test_matmul_associative(self):
        A = Matrix3(1, 2, 3, 4, 5, 6, 7, 8, 9)
        B = Matrix3(9, 8, 7, 6, 5, 4, 3, 2, 1)
        C = Matrix3.rotation_x(0.3)
        assert A.matmul(B).matmul(C) == A.matmul(B.matmul(C))
    def test_transpose(self):
        A = Matrix3(1, 2, 3, 4, 5, 6, 7, 8, 9)
        assert A.transpose().transpose() == A
    def test_determinant_identity(self):
        assert Matrix3.identity().determinant() == 1.0
    def test_determinant_known(self):
        assert Matrix3.diagonal(2, 3, 4).determinant() == 24.0
    def test_inverse_identity(self):
        A = Matrix3(1, 2, 3, 0, 1, 4, 5, 6, 0)
        inv = A.inverse()
        prod = A.matmul(inv)
        for a, b in zip(prod.to_tuple(), Matrix3.identity().to_tuple()):
            assert math.isclose(a, b, abs_tol=1e-9)
    def test_inverse_singular(self):
        with pytest.raises(ValueError):
            Matrix3.zeros().inverse()
    def test_rotation_preserves_length(self):
        R = Matrix3.rotation_z(math.pi / 3)
        v = Vector3(1, 0, 0)
        r = R.transform(v)
        assert math.isclose(r.magnitude(), 1.0, abs_tol=1e-12)
    def test_rotation_compose(self):
        Rx = Matrix3.rotation_x(0.3)
        Ry = Matrix3.rotation_y(0.4)
        assert math.isclose(Rx.matmul(Ry).determinant(), 1.0, abs_tol=1e-12)

class TestMatrix4:
    def test_translation(self):
        T = Matrix4.translation(Vector3(1, 2, 3))
        assert T.transform_point(Vector3(0, 0, 0)) == Vector3(1, 2, 3)
        assert T.transform_direction(Vector3(1, 0, 0)) == Vector3(1, 0, 0)
    def test_compose(self):
        T1 = Matrix4.translation(Vector3(1, 0, 0))
        T2 = Matrix4.translation(Vector3(0, 1, 0))
        combined = T1.matmul(T2)
        assert combined.transform_point(Vector3(0, 0, 0)) == Vector3(1, 1, 0)
    def test_inverse(self):
        T = Matrix4.translation(Vector3(5, -2, 3))
        inv = T.inverse()
        prod = T.matmul(inv)
        for a, b in zip(prod.to_tuple(), Matrix4.identity().to_tuple()):
            assert math.isclose(a, b, abs_tol=1e-9)
    def test_inverse_singular(self):
        M = Matrix4(0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0)
        with pytest.raises(ValueError):
            M.inverse()
    def test_linear_translation_parts(self):
        T = Matrix4.translation(Vector3(1, 2, 3))
        assert T.translation_part() == Vector3(1, 2, 3)
        assert T.linear_part() == Matrix3.identity()
