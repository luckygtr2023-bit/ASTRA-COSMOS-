"""Matrix mathematics for ASTRA.

Conventions
-----------
- Row-major storage: m[r][c] is row r, column c.
- Column-vector convention: v' = M @ v.
- Matrix4 layout: [ R t ; 0 1 ] with translation in last column.

Singularities
-------------
- inverse of singular matrix -> ValueError (no silent NaNs).
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence, Tuple
import math

from astra.mathematics.vectors import Vector3
from astra.mathematics.precision import is_close as _is_close


SINGULAR_TOL = 1e-12


@dataclass(frozen=True)
class Matrix3:
    m00: float = 1.0; m01: float = 0.0; m02: float = 0.0
    m10: float = 0.0; m11: float = 1.0; m12: float = 0.0
    m20: float = 0.0; m21: float = 0.0; m22: float = 1.0

    @classmethod
    def identity(cls) -> "Matrix3":
        return cls()

    @classmethod
    def zeros(cls) -> "Matrix3":
        return cls(0, 0, 0, 0, 0, 0, 0, 0, 0)

    @classmethod
    def diagonal(cls, a: float, b: float, c: float) -> "Matrix3":
        return cls(a, 0, 0, 0, b, 0, 0, 0, c)

    @classmethod
    def from_rows(cls, r0, r1, r2) -> "Matrix3":
        return cls(r0[0], r0[1], r0[2], r1[0], r1[1], r1[2], r2[0], r2[1], r2[2])

    @classmethod
    def from_columns(cls, c0, c1, c2) -> "Matrix3":
        return cls(c0[0], c1[0], c2[0], c0[1], c1[1], c2[1], c0[2], c1[2], c2[2])

    def __add__(self, o: "Matrix3") -> "Matrix3":
        return Matrix3(self.m00 + o.m00, self.m01 + o.m01, self.m02 + o.m02,
                       self.m10 + o.m10, self.m11 + o.m11, self.m12 + o.m12,
                       self.m20 + o.m20, self.m21 + o.m21, self.m22 + o.m22)

    def __sub__(self, o: "Matrix3") -> "Matrix3":
        return Matrix3(self.m00 - o.m00, self.m01 - o.m01, self.m02 - o.m02,
                       self.m10 - o.m10, self.m11 - o.m11, self.m12 - o.m12,
                       self.m20 - o.m20, self.m21 - o.m21, self.m22 - o.m22)

    def __mul__(self, o):
        if isinstance(o, Matrix3):
            return self.matmul(o)
        if isinstance(o, (int, float)):
            s = float(o)
            return Matrix3(self.m00 * s, self.m01 * s, self.m02 * s,
                           self.m10 * s, self.m11 * s, self.m12 * s,
                           self.m20 * s, self.m21 * s, self.m22 * s)
        return NotImplemented

    __rmul__ = __mul__

    def matmul(self, o: "Matrix3") -> "Matrix3":
        a = self; b = o
        return Matrix3(
            a.m00*b.m00 + a.m01*b.m10 + a.m02*b.m20,
            a.m00*b.m01 + a.m01*b.m11 + a.m02*b.m21,
            a.m00*b.m02 + a.m01*b.m12 + a.m02*b.m22,
            a.m10*b.m00 + a.m11*b.m10 + a.m12*b.m20,
            a.m10*b.m01 + a.m11*b.m11 + a.m12*b.m21,
            a.m10*b.m02 + a.m11*b.m12 + a.m12*b.m22,
            a.m20*b.m00 + a.m21*b.m10 + a.m22*b.m20,
            a.m20*b.m01 + a.m21*b.m11 + a.m22*b.m21,
            a.m20*b.m02 + a.m21*b.m12 + a.m22*b.m22,
        )

    def __matmul__(self, o):
        return self.matmul(o)

    def transform(self, v: Vector3) -> Vector3:
        return Vector3(
            self.m00*v.x + self.m01*v.y + self.m02*v.z,
            self.m10*v.x + self.m11*v.y + self.m12*v.z,
            self.m20*v.x + self.m21*v.y + self.m22*v.z,
        )

    def transpose(self) -> "Matrix3":
        return Matrix3(self.m00, self.m10, self.m20,
                       self.m01, self.m11, self.m21,
                       self.m02, self.m12, self.m22)

    def trace(self) -> float:
        return self.m00 + self.m11 + self.m22

    def determinant(self) -> float:
        return (self.m00 * (self.m11 * self.m22 - self.m12 * self.m21)
                - self.m01 * (self.m10 * self.m22 - self.m12 * self.m20)
                + self.m02 * (self.m10 * self.m21 - self.m11 * self.m20))

    def inverse(self) -> "Matrix3":
        det = self.determinant()
        if abs(det) < SINGULAR_TOL:
            raise ValueError(f"Matrix3 is singular (det={det})")
        inv_det = 1.0 / det
        return Matrix3(
            (self.m11*self.m22 - self.m12*self.m21) * inv_det,
            (self.m02*self.m21 - self.m01*self.m22) * inv_det,
            (self.m01*self.m12 - self.m02*self.m11) * inv_det,
            (self.m12*self.m20 - self.m10*self.m22) * inv_det,
            (self.m00*self.m22 - self.m02*self.m20) * inv_det,
            (self.m02*self.m10 - self.m00*self.m12) * inv_det,
            (self.m10*self.m21 - self.m11*self.m20) * inv_det,
            (self.m01*self.m20 - self.m00*self.m21) * inv_det,
            (self.m00*self.m11 - self.m01*self.m10) * inv_det,
        )

    def is_finite(self) -> bool:
        return all(math.isfinite(x) for x in (
            self.m00, self.m01, self.m02,
            self.m10, self.m11, self.m12,
            self.m20, self.m21, self.m22))

    @classmethod
    def rotation_x(cls, angle_rad: float) -> "Matrix3":
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return cls(1, 0, 0, 0, c, -s, 0, s, c)

    @classmethod
    def rotation_y(cls, angle_rad: float) -> "Matrix3":
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return cls(c, 0, s, 0, 1, 0, -s, 0, c)

    @classmethod
    def rotation_z(cls, angle_rad: float) -> "Matrix3":
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        return cls(c, -s, 0, s, c, 0, 0, 0, 1)

    @classmethod
    def rotation_axis_angle(cls, axis: Vector3, angle_rad: float) -> "Matrix3":
        n = axis.normalized()
        c, s = math.cos(angle_rad), math.sin(angle_rad)
        t = 1.0 - c
        x, y, z = n.x, n.y, n.z
        return cls(
            t*x*x + c,   t*x*y - s*z, t*x*z + s*y,
            t*x*y + s*z, t*y*y + c,   t*y*z - s*x,
            t*x*z - s*y, t*y*z + s*x, t*z*z + c,
        )

    @classmethod
    def scale(cls, sx: float, sy: float, sz: float) -> "Matrix3":
        return cls(sx, 0, 0, 0, sy, 0, 0, 0, sz)

    def to_tuple(self) -> Tuple[float, ...]:
        return (self.m00, self.m01, self.m02,
                self.m10, self.m11, self.m12,
                self.m20, self.m21, self.m22)

    def __eq__(self, other):
        if not isinstance(other, Matrix3):
            return NotImplemented
        # Use tolerance-based comparison to handle floating-point associativity
        # differences (e.g., (A*B)*C vs A*(B*C) differ at ~1e-15 level)
        return all(_is_close(a, b, atol=1e-9, rtol=1e-9) for a, b in zip(self.to_tuple(), other.to_tuple()))

    def __hash__(self):
        # Hash must be consistent with tolerant equality.
        # Round to 9 decimal places (atol) to ensure values within tolerance hash same.
        # This is a best-effort quantization; exact hash/equality contract cannot be
        # perfectly satisfied with tolerance, but rounding reduces violations.
        return hash(tuple(round(x, 9) for x in self.to_tuple()))


@dataclass(frozen=True)
class Matrix4:
    m00: float = 1.0; m01: float = 0.0; m02: float = 0.0; m03: float = 0.0
    m10: float = 0.0; m11: float = 1.0; m12: float = 0.0; m13: float = 0.0
    m20: float = 0.0; m21: float = 0.0; m22: float = 1.0; m23: float = 0.0
    m30: float = 0.0; m31: float = 0.0; m32: float = 0.0; m33: float = 1.0

    @classmethod
    def identity(cls) -> "Matrix4":
        return cls()

    @classmethod
    def translation(cls, t: Vector3) -> "Matrix4":
        return cls(1, 0, 0, t.x, 0, 1, 0, t.y, 0, 0, 1, t.z, 0, 0, 0, 1)

    @classmethod
    def scale(cls, sx: float, sy: float, sz: float) -> "Matrix4":
        return cls(sx, 0, 0, 0, 0, sy, 0, 0, 0, 0, sz, 0, 0, 0, 0, 1)

    @classmethod
    def from_matrix3(cls, r: Matrix3) -> "Matrix4":
        return cls(r.m00, r.m01, r.m02, 0.0,
                   r.m10, r.m11, r.m12, 0.0,
                   r.m20, r.m21, r.m22, 0.0,
                   0.0, 0.0, 0.0, 1.0)

    @classmethod
    def from_rotation_translation(cls, r: Matrix3, t: Vector3) -> "Matrix4":
        return cls(r.m00, r.m01, r.m02, t.x,
                   r.m10, r.m11, r.m12, t.y,
                   r.m20, r.m21, r.m22, t.z,
                   0.0, 0.0, 0.0, 1.0)

    def _get(self, r: int, c: int) -> float:
        return (self.m00, self.m01, self.m02, self.m03,
                self.m10, self.m11, self.m12, self.m13,
                self.m20, self.m21, self.m22, self.m23,
                self.m30, self.m31, self.m32, self.m33)[r * 4 + c]

    def matmul(self, o: "Matrix4") -> "Matrix4":
        a, b = self, o
        return Matrix4(
            a.m00*b.m00 + a.m01*b.m10 + a.m02*b.m20 + a.m03*b.m30,
            a.m00*b.m01 + a.m01*b.m11 + a.m02*b.m21 + a.m03*b.m31,
            a.m00*b.m02 + a.m01*b.m12 + a.m02*b.m22 + a.m03*b.m32,
            a.m00*b.m03 + a.m01*b.m13 + a.m02*b.m23 + a.m03*b.m33,
            a.m10*b.m00 + a.m11*b.m10 + a.m12*b.m20 + a.m13*b.m30,
            a.m10*b.m01 + a.m11*b.m11 + a.m12*b.m21 + a.m13*b.m31,
            a.m10*b.m02 + a.m11*b.m12 + a.m12*b.m22 + a.m13*b.m32,
            a.m10*b.m03 + a.m11*b.m13 + a.m12*b.m23 + a.m13*b.m33,
            a.m20*b.m00 + a.m21*b.m10 + a.m22*b.m20 + a.m23*b.m30,
            a.m20*b.m01 + a.m21*b.m11 + a.m22*b.m21 + a.m23*b.m31,
            a.m20*b.m02 + a.m21*b.m12 + a.m22*b.m22 + a.m23*b.m32,
            a.m20*b.m03 + a.m21*b.m13 + a.m22*b.m23 + a.m23*b.m33,
            a.m30*b.m00 + a.m31*b.m10 + a.m32*b.m20 + a.m33*b.m30,
            a.m30*b.m01 + a.m31*b.m11 + a.m32*b.m21 + a.m33*b.m31,
            a.m30*b.m02 + a.m31*b.m12 + a.m32*b.m22 + a.m33*b.m32,
            a.m30*b.m03 + a.m31*b.m13 + a.m32*b.m23 + a.m33*b.m33,
        )

    def __matmul__(self, o):
        return self.matmul(o)

    def transform_point(self, v: Vector3) -> Vector3:
        return Vector3(
            self.m00*v.x + self.m01*v.y + self.m02*v.z + self.m03,
            self.m10*v.x + self.m11*v.y + self.m12*v.z + self.m13,
            self.m20*v.x + self.m21*v.y + self.m22*v.z + self.m23,
        )

    def transform_direction(self, v: Vector3) -> Vector3:
        return Vector3(
            self.m00*v.x + self.m01*v.y + self.m02*v.z,
            self.m10*v.x + self.m11*v.y + self.m12*v.z,
            self.m20*v.x + self.m21*v.y + self.m22*v.z,
        )

    def linear_part(self) -> Matrix3:
        return Matrix3(self.m00, self.m01, self.m02,
                       self.m10, self.m11, self.m12,
                       self.m20, self.m21, self.m22)

    def translation_part(self) -> Vector3:
        return Vector3(self.m03, self.m13, self.m23)

    def transpose(self) -> "Matrix4":
        return Matrix4(
            self.m00, self.m10, self.m20, self.m30,
            self.m01, self.m11, self.m21, self.m31,
            self.m02, self.m12, self.m22, self.m32,
            self.m03, self.m13, self.m23, self.m33,
        )

    def determinant(self) -> float:
        def minor3(rows, cols):
            vals = []
            for r in rows:
                for c in cols:
                    vals.append(self._get(r, c))
            return Matrix3(*vals).determinant()
        return (self.m00 * minor3((1,2,3), (1,2,3))
              - self.m01 * minor3((1,2,3), (0,2,3))
              + self.m02 * minor3((1,2,3), (0,1,3))
              - self.m03 * minor3((1,2,3), (0,1,2)))

    def inverse(self) -> "Matrix4":
        m = [[self._get(r, c) for c in range(4)] for r in range(4)]
        cof = [[0.0]*4 for _ in range(4)]
        for r in range(4):
            for c in range(4):
                minor = [[m[i][j] for j in range(4) if j != c]
                         for i in range(4) if i != r]
                det3 = (minor[0][0]*(minor[1][1]*minor[2][2] - minor[1][2]*minor[2][1])
                      - minor[0][1]*(minor[1][0]*minor[2][2] - minor[1][2]*minor[2][0])
                      + minor[0][2]*(minor[1][0]*minor[2][1] - minor[1][1]*minor[2][0]))
                cof[r][c] = ((-1) ** (r + c)) * det3
        det = sum(m[0][c] * cof[0][c] for c in range(4))
        if abs(det) < SINGULAR_TOL:
            raise ValueError(f"Matrix4 is singular (det={det})")
        inv_det = 1.0 / det
        adj = [[cof[c][r] for c in range(4)] for r in range(4)]
        return Matrix4(
            adj[0][0]*inv_det, adj[0][1]*inv_det, adj[0][2]*inv_det, adj[0][3]*inv_det,
            adj[1][0]*inv_det, adj[1][1]*inv_det, adj[1][2]*inv_det, adj[1][3]*inv_det,
            adj[2][0]*inv_det, adj[2][1]*inv_det, adj[2][2]*inv_det, adj[2][3]*inv_det,
            adj[3][0]*inv_det, adj[3][1]*inv_det, adj[3][2]*inv_det, adj[3][3]*inv_det,
        )

    def is_finite(self) -> bool:
        return all(math.isfinite(x) for x in (
            self.m00, self.m01, self.m02, self.m03,
            self.m10, self.m11, self.m12, self.m13,
            self.m20, self.m21, self.m22, self.m23,
            self.m30, self.m31, self.m32, self.m33))

    def to_tuple(self) -> Tuple[float, ...]:
        return (self.m00, self.m01, self.m02, self.m03,
                self.m10, self.m11, self.m12, self.m13,
                self.m20, self.m21, self.m22, self.m23,
                self.m30, self.m31, self.m32, self.m33)

    def __eq__(self, other):
        if not isinstance(other, Matrix4):
            return NotImplemented
        return all(_is_close(a, b, atol=1e-9, rtol=1e-9) for a, b in zip(self.to_tuple(), other.to_tuple()))

    def __hash__(self):
        return hash(tuple(round(x, 9) for x in self.to_tuple()))
