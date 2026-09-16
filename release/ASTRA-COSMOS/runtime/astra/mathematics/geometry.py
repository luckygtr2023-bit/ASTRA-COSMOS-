"""Geometric primitives and intersections for ASTRA.

Conventions
-----------
- Plane: n . p + d == 0. Signed distance from p is n.p + d (n may be non-unit).
- Sphere: radius must be > 0.
- AABB: min corner <= max corner componentwise.
- Ray intersections: only t >= 0 considered; tangencies count.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import math

from astra.mathematics.vectors import Vector3
from astra.mathematics.precision import is_close_zero


@dataclass(frozen=True)
class Ray:
    origin: Vector3
    direction: Vector3

    def point_at(self, t: float) -> Vector3:
        return self.origin + self.direction * t

    def normalized(self) -> "Ray":
        return Ray(self.origin, self.direction.normalized())


@dataclass(frozen=True)
class Plane:
    normal: Vector3
    d: float

    def __post_init__(self):
        if self.normal.is_zero():
            raise ValueError("Plane normal must be non-zero")

    @classmethod
    def from_point_normal(cls, point: Vector3, normal: Vector3) -> "Plane":
        n = normal.normalized()
        return cls(n, -n.dot(point))

    @classmethod
    def from_three_points(cls, a: Vector3, b: Vector3, c: Vector3) -> "Plane":
        n = (b - a).cross(c - a)
        if n.is_zero():
            raise ValueError("Three points are collinear; plane is undefined")
        return cls.from_point_normal(a, n)

    def unit_normal(self) -> Vector3:
        return self.normal.normalized()

    def signed_distance(self, p: Vector3) -> float:
        n = self.normal
        m = n.magnitude()
        return (n.dot(p) + self.d) / m

    def distance(self, p: Vector3) -> float:
        return abs(self.signed_distance(p))

    def project_point(self, p: Vector3) -> Vector3:
        n = self.normal
        m2 = n.magnitude_sq()
        signed = (n.dot(p) + self.d) / m2
        return p - n * signed


@dataclass(frozen=True)
class Sphere:
    center: Vector3
    radius: float

    def __post_init__(self):
        if self.radius <= 0.0:
            raise ValueError(f"Sphere radius must be positive, got {self.radius}")

    def contains(self, p: Vector3) -> bool:
        return self.center.distance_sq_to(p) <= self.radius * self.radius

    def surface_distance(self, p: Vector3) -> float:
        return abs(self.center.distance_to(p) - self.radius)


@dataclass(frozen=True)
class AABB:
    min_corner: Vector3
    max_corner: Vector3

    def __post_init__(self):
        if (self.min_corner.x > self.max_corner.x or
            self.min_corner.y > self.max_corner.y or
            self.min_corner.z > self.max_corner.z):
            raise ValueError("AABB min corner must be <= max corner componentwise")

    @classmethod
    def from_points(cls, pts) -> "AABB":
        xs = [p.x for p in pts]; ys = [p.y for p in pts]; zs = [p.z for p in pts]
        return cls(Vector3(min(xs), min(ys), min(zs)),
                   Vector3(max(xs), max(ys), max(zs)))

    def center(self) -> Vector3:
        return (self.min_corner + self.max_corner) * 0.5

    def extent(self) -> Vector3:
        return self.max_corner - self.min_corner

    def contains(self, p: Vector3) -> bool:
        return (self.min_corner.x <= p.x <= self.max_corner.x and
                self.min_corner.y <= p.y <= self.max_corner.y and
                self.min_corner.z <= p.z <= self.max_corner.z)


def ray_sphere_intersection(ray: Ray, sphere: Sphere) -> Optional[Tuple[float, float]]:
    oc = ray.origin - sphere.center
    a = ray.direction.dot(ray.direction)
    if a == 0.0:
        return None
    b = 2.0 * oc.dot(ray.direction)
    c = oc.dot(oc) - sphere.radius * sphere.radius
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return None
    sqrt_disc = math.sqrt(disc)
    t0 = (-b - sqrt_disc) / (2.0 * a)
    t1 = (-b + sqrt_disc) / (2.0 * a)
    if t1 < 0.0:
        return None
    if t0 < 0.0:
        t0 = t1
    return (t0, t1)


def ray_plane_intersection(ray: Ray, plane: Plane) -> Optional[float]:
    n = plane.normal
    m = n.magnitude()
    nu = n / m
    du = plane.d / m
    denom = nu.dot(ray.direction)
    if is_close_zero(denom):
        return None
    t = -(nu.dot(ray.origin) + du) / denom
    if t < 0.0:
        return None
    return t


def ray_aabb_intersection(ray: Ray, box: AABB) -> Optional[Tuple[float, float]]:
    tmin = -math.inf
    tmax = math.inf
    o = ray.origin
    d = ray.direction
    for oi, di, mini, maxi in (
        (o.x, d.x, box.min_corner.x, box.max_corner.x),
        (o.y, d.y, box.min_corner.y, box.max_corner.y),
        (o.z, d.z, box.min_corner.z, box.max_corner.z),
    ):
        if abs(di) < 1e-30:
            if oi < mini or oi > maxi:
                return None
        else:
            t1 = (mini - oi) / di
            t2 = (maxi - oi) / di
            if t1 > t2:
                t1, t2 = t2, t1
            if t1 > tmin:
                tmin = t1
            if t2 < tmax:
                tmax = t2
            if tmin > tmax:
                return None
    if tmax < 0.0:
        return None
    if tmin < 0.0:
        tmin = tmax
    return (tmin, tmax)


def point_plane_distance(plane: Plane, p: Vector3) -> float:
    return abs(plane.signed_distance(p))


def point_line_distance(p: Vector3, a: Vector3, b: Vector3) -> float:
    ab = b - a
    denom = ab.magnitude_sq()
    if denom == 0.0:
        return p.distance_to(a)
    t = (p - a).dot(ab) / denom
    proj = a + ab * t
    return p.distance_to(proj)


def segment_segment_distance(p1: Vector3, q1: Vector3,
                             p2: Vector3, q2: Vector3) -> float:
    d1 = q1 - p1
    d2 = q2 - p2
    r = p1 - p2
    a = d1.dot(d1)
    e = d2.dot(d2)
    f = d2.dot(r)
    if a <= 1e-30 and e <= 1e-30:
        return p1.distance_to(p2)
    if a <= 1e-30:
        s = 0.0
        t = max(0.0, min(1.0, f / e))
    else:
        c = d1.dot(r)
        if e <= 1e-30:
            t = 0.0
            s = max(0.0, min(1.0, -c / a))
        else:
            b = d1.dot(d2)
            denom = a * e - b * b
            if denom != 0.0:
                s = max(0.0, min(1.0, (b * f - c * e) / denom))
            else:
                s = 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = max(0.0, min(1.0, -c / a))
            elif t > 1.0:
                t = 1.0
                s = max(0.0, min(1.0, (b - c) / a))
    c1 = p1 + d1 * s
    c2 = p2 + d2 * t
    return c1.distance_to(c2)
