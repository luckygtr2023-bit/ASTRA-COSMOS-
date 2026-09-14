"""Quaternion mathematics for ASTRA.

Convention
----------
- q = w + xi + yj + zk stored as (w, x, y, z).
- Rotation: q = (cos(angle/2), axis * sin(angle/2)) with unit axis.
- Hamilton product; (q1*q2).rotate(v) == q1.rotate(q2.rotate(v)).
- slerp uses shortest path (negates on negative dot).
"""

from __future__ import annotations
from dataclasses import dataclass
import math

from astra.mathematics.vectors import Vector3
from astra.mathematics.matrices import Matrix3
from astra.mathematics.precision import clamp


@dataclass(frozen=True)
class Quaternion:
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @classmethod
    def identity(cls) -> "Quaternion":
        return cls(1.0, 0.0, 0.0, 0.0)

    @classmethod
    def from_axis_angle(cls, axis: Vector3, angle_rad: float) -> "Quaternion":
        n = axis.normalized()
        h = 0.5 * angle_rad
        s = math.sin(h)
        return cls(math.cos(h), n.x * s, n.y * s, n.z * s)

    @classmethod
    def from_euler_xyz(cls, rx: float, ry: float, rz: float) -> "Quaternion":
        cx, sx = math.cos(rx*0.5), math.sin(rx*0.5)
        cy, sy = math.cos(ry*0.5), math.sin(ry*0.5)
        cz, sz = math.cos(rz*0.5), math.sin(rz*0.5)
        return cls(
            cx*cy*cz + sx*sy*sz,
            sx*cy*cz - cx*sy*sz,
            cx*sy*cz + sx*cy*sz,
            cx*cy*sz - sx*sy*cz,
        )

    def __add__(self, o: "Quaternion") -> "Quaternion":
        return Quaternion(self.w+o.w, self.x+o.x, self.y+o.y, self.z+o.z)

    def __sub__(self, o: "Quaternion") -> "Quaternion":
        return Quaternion(self.w-o.w, self.x-o.x, self.y-o.y, self.z-o.z)

    def __neg__(self) -> "Quaternion":
        return Quaternion(-self.w, -self.x, -self.y, -self.z)

    def __mul__(self, o):
        if isinstance(o, Quaternion):
            return self.multiply(o)
        if isinstance(o, (int, float)):
            s = float(o)
            return Quaternion(self.w*s, self.x*s, self.y*s, self.z*s)
        return NotImplemented

    __rmul__ = __mul__

    def multiply(self, o: "Quaternion") -> "Quaternion":
        a, b = self, o
        return Quaternion(
            a.w*b.w - a.x*b.x - a.y*b.y - a.z*b.z,
            a.w*b.x + a.x*b.w + a.y*b.z - a.z*b.y,
            a.w*b.y - a.x*b.z + a.y*b.w + a.z*b.x,
            a.w*b.z + a.x*b.y - a.y*b.x + a.z*b.w,
        )

    def dot(self, o: "Quaternion") -> float:
        return self.w*o.w + self.x*o.x + self.y*o.y + self.z*o.z

    def conjugate(self) -> "Quaternion":
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def norm_sq(self) -> float:
        return self.w*self.w + self.x*self.x + self.y*self.y + self.z*self.z

    def norm(self) -> float:
        return math.sqrt(self.norm_sq())

    def normalized(self) -> "Quaternion":
        n = self.norm()
        if n == 0.0:
            raise ZeroDivisionError("Cannot normalize zero quaternion")
        inv = 1.0 / n
        return Quaternion(self.w*inv, self.x*inv, self.y*inv, self.z*inv)

    def inverse(self) -> "Quaternion":
        nsq = self.norm_sq()
        if nsq == 0.0:
            raise ZeroDivisionError("Cannot invert zero quaternion")
        inv = 1.0 / nsq
        return Quaternion(self.w*inv, -self.x*inv, -self.y*inv, -self.z*inv)

    def rotate(self, v: Vector3) -> Vector3:
        qv = Vector3(self.x, self.y, self.z)
        t = qv.cross(v) * 2.0
        return v + t * self.w + qv.cross(t)

    def to_matrix3(self) -> Matrix3:
        q = self.normalized()
        w, x, y, z = q.w, q.x, q.y, q.z
        xx, yy, zz = x*x, y*y, z*z
        xy, xz, yz = x*y, x*z, y*z
        wx, wy, wz = w*x, w*y, w*z
        return Matrix3(
            1 - 2*(yy+zz), 2*(xy-wz),     2*(xz+wy),
            2*(xy+wz),     1 - 2*(xx+zz), 2*(yz-wx),
            2*(xz-wy),     2*(yz+wx),     1 - 2*(xx+yy),
        )

    def slerp(self, o: "Quaternion", t: float) -> "Quaternion":
        a = self.normalized()
        b = o.normalized()
        dot = a.dot(b)
        if dot < 0.0:
            b = -b
            dot = -dot
        if dot > 1.0:
            dot = 1.0
        if dot > 0.9995:
            result = a + (b - a) * t
            return result.normalized()
        theta_0 = math.acos(dot)
        sin_theta_0 = math.sin(theta_0)
        theta = theta_0 * t
        s0 = math.sin(theta_0 - theta) / sin_theta_0
        s1 = math.sin(theta) / sin_theta_0
        return Quaternion(
            s0*a.w + s1*b.w,
            s0*a.x + s1*b.x,
            s0*a.y + s1*b.y,
            s0*a.z + s1*b.z,
        ).normalized()

    def is_finite(self) -> bool:
        return all(math.isfinite(v) for v in (self.w, self.x, self.y, self.z))

    def to_tuple(self):
        return (self.w, self.x, self.y, self.z)
