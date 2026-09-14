import math
import pytest
from astra.mathematics.vectors import Vector3
from astra.mathematics.geometry import (
    Ray, Plane, Sphere, AABB,
    ray_sphere_intersection, ray_plane_intersection, ray_aabb_intersection,
    point_plane_distance, point_line_distance, segment_segment_distance,
)

class TestRaySphere:
    def test_direct_hit(self):
        ray = Ray(Vector3(0, 0, 0), Vector3(1, 0, 0))
        s = Sphere(Vector3(5, 0, 0), 1.0)
        t = ray_sphere_intersection(ray, s)
        assert t is not None
        assert t[0] == pytest.approx(4.0)
        assert t[1] == pytest.approx(6.0)
    def test_miss(self):
        ray = Ray(Vector3(0, 10, 0), Vector3(1, 0, 0))
        s = Sphere(Vector3(5, 0, 0), 1.0)
        assert ray_sphere_intersection(ray, s) is None
    def test_behind(self):
        ray = Ray(Vector3(10, 0, 0), Vector3(1, 0, 0))
        s = Sphere(Vector3(5, 0, 0), 1.0)
        assert ray_sphere_intersection(ray, s) is None
    def test_inside(self):
        ray = Ray(Vector3(5, 0, 0), Vector3(1, 0, 0))
        s = Sphere(Vector3(5, 0, 0), 1.0)
        t = ray_sphere_intersection(ray, s)
        assert t is not None and t[0] >= 0.0
    def test_zero_radius_rejected(self):
        with pytest.raises(ValueError):
            Sphere(Vector3(0, 0, 0), 0.0)

class TestRayPlane:
    def test_hit(self):
        plane = Plane.from_point_normal(Vector3(0, 0, 0), Vector3(0, 1, 0))
        ray = Ray(Vector3(0, 5, 0), Vector3(0, -1, 0))
        t = ray_plane_intersection(ray, plane)
        assert t == pytest.approx(5.0)
    def test_parallel(self):
        plane = Plane.from_point_normal(Vector3(0, 0, 0), Vector3(0, 1, 0))
        ray = Ray(Vector3(0, 5, 0), Vector3(1, 0, 0))
        assert ray_plane_intersection(ray, plane) is None
    def test_behind(self):
        plane = Plane.from_point_normal(Vector3(0, 0, 0), Vector3(0, 1, 0))
        ray = Ray(Vector3(0, -5, 0), Vector3(0, -1, 0))
        assert ray_plane_intersection(ray, plane) is None

class TestRayAABB:
    def test_direct_hit(self):
        box = AABB(Vector3(-1, -1, -1), Vector3(1, 1, 1))
        ray = Ray(Vector3(-5, 0, 0), Vector3(1, 0, 0))
        t = ray_aabb_intersection(ray, box)
        assert t is not None
        assert t[0] == pytest.approx(4.0)
        assert t[1] == pytest.approx(6.0)
    def test_miss(self):
        box = AABB(Vector3(-1, -1, -1), Vector3(1, 1, 1))
        ray = Ray(Vector3(-5, 5, 0), Vector3(1, 0, 0))
        assert ray_aabb_intersection(ray, box) is None
    def test_inside(self):
        box = AABB(Vector3(-1, -1, -1), Vector3(1, 1, 1))
        ray = Ray(Vector3(0, 0, 0), Vector3(1, 0, 0))
        t = ray_aabb_intersection(ray, box)
        assert t is not None
    def test_invalid_aabb(self):
        with pytest.raises(ValueError):
            AABB(Vector3(1, 0, 0), Vector3(-1, 0, 0))

class TestDistances:
    def test_point_plane(self):
        plane = Plane.from_point_normal(Vector3(0, 0, 0), Vector3(0, 1, 0))
        assert point_plane_distance(plane, Vector3(0, 5, 0)) == pytest.approx(5.0)
    def test_point_line(self):
        d = point_line_distance(Vector3(0, 1, 0), Vector3(-1, 0, 0), Vector3(1, 0, 0))
        assert d == pytest.approx(1.0)
    def test_segment_segment_parallel(self):
        d = segment_segment_distance(
            Vector3(0, 0, 0), Vector3(1, 0, 0),
            Vector3(0, 1, 0), Vector3(1, 1, 0))
        assert d == pytest.approx(1.0)
    def test_segment_segment_crossing(self):
        d = segment_segment_distance(
            Vector3(-1, 0, 0), Vector3(1, 0, 0),
            Vector3(0, -1, 0), Vector3(0, 1, 0))
        assert d == pytest.approx(0.0, abs=1e-12)
    def test_segment_degenerate(self):
        d = segment_segment_distance(
            Vector3(0, 0, 0), Vector3(0, 0, 0),
            Vector3(1, 0, 0), Vector3(1, 0, 0))
        assert d == pytest.approx(1.0)
