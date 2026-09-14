"""Coordinate transforms for ASTRA.

Conventions
-----------
- Transform: v' = R * S * v + t.
- compose(self, other) returns self after other (apply other first).
- Compatible with astra.core.coords via Transform.from_core_origin.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple
import math

from astra.mathematics.vectors import Vector3
from astra.mathematics.matrices import Matrix3, Matrix4
from astra.mathematics.quaternions import Quaternion


@dataclass(frozen=True)
class Transform:
    rotation: Matrix3
    translation: Vector3
    scale: Vector3

    @classmethod
    def identity(cls) -> "Transform":
        return cls(Matrix3.identity(), Vector3(0.0, 0.0, 0.0), Vector3(1.0, 1.0, 1.0))

    @classmethod
    def from_translation(cls, t: Vector3) -> "Transform":
        return cls(Matrix3.identity(), t, Vector3(1.0, 1.0, 1.0))

    @classmethod
    def from_rotation(cls, r: Matrix3) -> "Transform":
        return cls(r, Vector3(0.0, 0.0, 0.0), Vector3(1.0, 1.0, 1.0))

    @classmethod
    def from_quaternion(cls, q: Quaternion, t=None) -> "Transform":
        return cls(q.to_matrix3(), t or Vector3(0.0, 0.0, 0.0), Vector3(1.0, 1.0, 1.0))

    @classmethod
    def from_core_origin(cls, origin: Tuple[float, float, float]) -> "Transform":
        return cls.from_translation(Vector3.from_tuple(origin))

    def apply(self, v: Vector3) -> Vector3:
        scaled = Vector3(v.x * self.scale.x, v.y * self.scale.y, v.z * self.scale.z)
        return self.rotation.transform(scaled) + self.translation

    def apply_direction(self, v: Vector3) -> Vector3:
        scaled = Vector3(v.x * self.scale.x, v.y * self.scale.y, v.z * self.scale.z)
        return self.rotation.transform(scaled)

    def compose(self, other: "Transform") -> "Transform":
        r = self.rotation.matmul(other.rotation)
        s = Vector3(self.scale.x * other.scale.x,
                    self.scale.y * other.scale.y,
                    self.scale.z * other.scale.z)
        t_local = Vector3(other.translation.x * self.scale.x,
                          other.translation.y * self.scale.y,
                          other.translation.z * self.scale.z)
        t = self.rotation.transform(t_local) + self.translation
        return Transform(r, t, s)

    def inverse(self) -> "Transform":
        inv_r = self.rotation.inverse()
        if self.scale.x == 0.0 or self.scale.y == 0.0 or self.scale.z == 0.0:
            raise ValueError("Transform with zero scale is not invertible")
        inv_s = Vector3(1.0 / self.scale.x, 1.0 / self.scale.y, 1.0 / self.scale.z)
        rt = inv_r.transform(self.translation)
        new_t = Vector3(-rt.x * inv_s.x, -rt.y * inv_s.y, -rt.z * inv_s.z)
        return Transform(inv_r, new_t, inv_s)

    def to_matrix4(self) -> Matrix4:
        s = Matrix3.diagonal(self.scale.x, self.scale.y, self.scale.z)
        rs = self.rotation.matmul(s)
        return Matrix4.from_rotation_translation(rs, self.translation)

    def is_finite(self) -> bool:
        return (self.rotation.is_finite() and self.translation.is_finite()
                and math.isfinite(self.scale.x) and math.isfinite(self.scale.y)
                and math.isfinite(self.scale.z))
