"""Adversarial tests for the ASTRA mathematics layer."""

import math
import pytest
from astra.mathematics import (
    Vector2, Vector3, VectorN,
    Matrix3, Matrix4, Quaternion,
    Ray, Plane, Sphere, AABB,
    Transform,
    is_close,
)
from astra.mathematics.geometry import ray_sphere_intersection
from astra.core.rng import RNGStream
from astra.mathematics.statistics import uniform, normal


class TestZeroVectors:
    def test_normalize_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Vector3(0, 0, 0).normalized()
    def test_angle_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Vector3(0, 0, 0).angle_to(Vector3(1, 0, 0))
    def test_project_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Vector3(1, 1, 1).project_onto(Vector3(0, 0, 0))


class TestHugeValues:
    def test_magnitude_does_not_overflow(self):
        v = Vector3(1e200, 1e200, 1e200)
        assert math.isfinite(v.magnitude())
    def test_normalized_of_huge(self):
        v = Vector3(1e300, 0, 0)
        assert math.isclose(v.normalized().magnitude(), 1.0, abs_tol=1e-12)
    def test_tiny_magnitude(self):
        v = Vector3(1e-300, 0, 0)
        assert math.isclose(v.normalized().magnitude(), 1.0, abs_tol=1e-12)


class TestMatrixNumerics:
    def test_near_singular_inverse(self):
        A = Matrix3(1e-10, 0, 0, 0, 1e-10, 0, 0, 0, 1e-10)
        with pytest.raises(ValueError):
            A.inverse()
    def test_inverse_round_trip_random(self):
        import random
        rng = random.Random(0)
        for _ in range(50):
            A = Matrix3(*(rng.uniform(-2, 2) for _ in range(9)))
            det = A.determinant()
            if abs(det) < 1e-3:
                continue
            inv = A.inverse()
            prod = A.matmul(inv)
            ident = Matrix3.identity().to_tuple()
            for a, b in zip(prod.to_tuple(), ident):
                assert abs(a - b) < 1e-6


class TestQuaternionInvariants:
    def test_rotate_preserves_magnitude_many(self):
        import random
        rng = random.Random(0)
        for _ in range(200):
            axis = Vector3(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            if axis.is_zero():
                continue
            q = Quaternion.from_axis_angle(axis, rng.uniform(-math.pi, math.pi))
            v = Vector3(rng.uniform(-10, 10), rng.uniform(-10, 10), rng.uniform(-10, 10))
            r = q.rotate(v)
            assert math.isclose(r.magnitude(), v.magnitude(), rel_tol=1e-9, abs_tol=1e-9)
    def test_inverse_right(self):
        import random
        rng = random.Random(1)
        for _ in range(50):
            q = Quaternion(rng.uniform(-1, 1), rng.uniform(-1, 1),
                           rng.uniform(-1, 1), rng.uniform(-1, 1))
            if q.norm() == 0.0:
                continue
            prod = q.multiply(q.inverse())
            assert math.isclose(prod.w, 1.0, abs_tol=1e-9)


class TestGeometryDegenerate:
    def test_ray_origin_on_sphere_surface(self):
        s = Sphere(Vector3(0, 0, 0), 1.0)
        r = Ray(Vector3(1, 0, 0), Vector3(1, 0, 0))
        t = ray_sphere_intersection(r, s)
        assert t is not None
    def test_plane_from_collinear_rejected(self):
        with pytest.raises(ValueError):
            Plane.from_three_points(Vector3(0, 0, 0), Vector3(1, 0, 0), Vector3(2, 0, 0))
    def test_plane_zero_normal_rejected(self):
        with pytest.raises(ValueError):
            Plane(Vector3(0, 0, 0), 0.0)


class TestTransformInverse:
    def test_full_inverse_roundtrip(self):
        import random
        rng = random.Random(2)
        for _ in range(50):
            axis = Vector3(rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            if axis.is_zero():
                continue
            q = Quaternion.from_axis_angle(axis, rng.uniform(-math.pi, math.pi))
            T = Transform.from_quaternion(q, Vector3(rng.uniform(-5, 5),
                                                     rng.uniform(-5, 5),
                                                     rng.uniform(-5, 5)))
            v = Vector3(rng.uniform(-10, 10), rng.uniform(-10, 10), rng.uniform(-10, 10))
            back = T.inverse().apply(T.apply(v))
            assert back.distance_to(v) < 1e-9


class TestDeterminism:
    def test_sampling_is_reproducible(self):
        s1 = RNGStream("a", 7); s2 = RNGStream("b", 7)
        for _ in range(100):
            assert uniform(s1, 0, 1) == uniform(s2, 0, 1)
    def test_normal_reproducible(self):
        s1 = RNGStream("a", 7); s2 = RNGStream("b", 7)
        for _ in range(100):
            assert normal(s1, 0, 1) == normal(s2, 0, 1)


class TestNumericBounds:
    def test_infinite_vectors_are_flagged(self):
        v = Vector3(float("inf"), 0, 0)
        assert not v.is_finite()
    def test_nan_matrix_is_flagged(self):
        m = Matrix3(float("nan"), 0, 0, 0, 1, 0, 0, 0, 1)
        assert not m.is_finite()
    def test_is_close_not_reflexive_for_nan(self):
        assert not is_close(float("nan"), float("nan"))
