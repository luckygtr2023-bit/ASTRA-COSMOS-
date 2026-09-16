"""Vector mathematics for ASTRA.

Conventions
-----------
- Right-handed Cartesian.
- Vector3 = (x, y, z), Vector2 = (x, y). All values float64.
- Immutable, hashable, frozen dataclasses. Arithmetic returns new vectors.
- Vector3.cross uses the right-hand rule: x cross y = z.
- lerp parameter t is NOT clamped; callers who want [0, 1] must clamp.
- normalized() raises ZeroDivisionError on the zero vector.

Singularities / undefined domains
---------------------------------
- normalized(0)          -> ZeroDivisionError
- project_onto(0)        -> ZeroDivisionError
- angle_to(0-vector)     -> ZeroDivisionError
- reflect on zero normal -> ZeroDivisionError
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Sequence, Tuple
import math

from astra.mathematics.constants import DEFAULT_ATOL, PI
from astra.mathematics.precision import is_close_zero, clamp


@dataclass(frozen=True)
class Vector2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, o: "Vector2") -> "Vector2":
        return Vector2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: "Vector2") -> "Vector2":
        return Vector2(self.x - o.x, self.y - o.y)

    def __neg__(self) -> "Vector2":
        return Vector2(-self.x, -self.y)

    def __mul__(self, s: float) -> "Vector2":
        return Vector2(self.x * s, self.y * s)

    __rmul__ = __mul__

    def __truediv__(self, s: float) -> "Vector2":
        if s == 0.0:
            raise ZeroDivisionError("Vector2 division by zero")
        return Vector2(self.x / s, self.y / s)

    def dot(self, o: "Vector2") -> float:
        return self.x * o.x + self.y * o.y

    def cross(self, o: "Vector2") -> float:
        return self.x * o.y - self.y * o.x

    def magnitude_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def magnitude(self) -> float:
        return math.sqrt(self.magnitude_sq())

    def normalized(self) -> "Vector2":
        m = self.magnitude()
        if m == 0.0:
            raise ZeroDivisionError("Cannot normalize zero Vector2")
        return Vector2(self.x / m, self.y / m)

    def distance_to(self, o: "Vector2") -> float:
        return (self - o).magnitude()

    def project_onto(self, o: "Vector2") -> "Vector2":
        d = o.magnitude_sq()
        if d == 0.0:
            raise ZeroDivisionError("Cannot project onto zero Vector2")
        return o * (self.dot(o) / d)

    def reflect(self, normal: "Vector2") -> "Vector2":
        n = normal.normalized()
        return self - n * (2.0 * self.dot(n))

    def lerp(self, o: "Vector2", t: float) -> "Vector2":
        return Vector2(self.x + (o.x - self.x) * t,
                       self.y + (o.y - self.y) * t)

    def angle(self) -> float:
        return math.atan2(self.y, self.x)

    def angle_to(self, o: "Vector2") -> float:
        denom = self.magnitude() * o.magnitude()
        if denom == 0.0:
            raise ZeroDivisionError("Cannot compute angle with zero Vector2")
        c = self.dot(o) / denom
        c = clamp(c, -1.0, 1.0)
        return math.acos(c)

    def perpendicular(self) -> "Vector2":
        return Vector2(-self.y, self.x)

    def rotated(self, angle_rad: float) -> "Vector2":
        c = math.cos(angle_rad)
        s = math.sin(angle_rad)
        return Vector2(c * self.x - s * self.y,
                       s * self.x + c * self.y)

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    @classmethod
    def from_tuple(cls, t: Sequence[float]) -> "Vector2":
        if len(t) != 2:
            raise ValueError(f"Vector2.from_tuple expects 2 values, got {len(t)}")
        return cls(float(t[0]), float(t[1]))

    def is_finite(self) -> bool:
        return math.isfinite(self.x) and math.isfinite(self.y)

    def is_zero(self, atol: float = DEFAULT_ATOL) -> bool:
        return is_close_zero(self.magnitude_sq(), atol * atol)

    def __iter__(self):
        yield self.x
        yield self.y


@dataclass(frozen=True)
class Vector3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self, o: "Vector3") -> "Vector3":
        return Vector3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vector3") -> "Vector3":
        return Vector3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __neg__(self) -> "Vector3":
        return Vector3(-self.x, -self.y, -self.z)

    def __mul__(self, s: float) -> "Vector3":
        return Vector3(self.x * s, self.y * s, self.z * s)

    __rmul__ = __mul__

    def __truediv__(self, s: float) -> "Vector3":
        if s == 0.0:
            raise ZeroDivisionError("Vector3 division by zero")
        return Vector3(self.x / s, self.y / s, self.z / s)

    def dot(self, o: "Vector3") -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o: "Vector3") -> "Vector3":
        return Vector3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x,
        )

    def outer(self, o: "Vector3"):
        from astra.mathematics.matrices import Matrix3
        return Matrix3(
            self.x * o.x, self.x * o.y, self.x * o.z,
            self.y * o.x, self.y * o.y, self.y * o.z,
            self.z * o.x, self.z * o.y, self.z * o.z,
        )

    def magnitude_sq(self) -> float:
        return self.x * self.x + self.y * self.y + self.z * self.z

    def magnitude(self) -> float:
        return math.hypot(math.hypot(self.x, self.y), self.z)

    def normalized(self) -> "Vector3":
        m = self.magnitude()
        if m == 0.0:
            raise ZeroDivisionError("Cannot normalize zero Vector3")
        return Vector3(self.x / m, self.y / m, self.z / m)

    def with_magnitude(self, m: float) -> "Vector3":
        return self.normalized() * m

    def distance_to(self, o: "Vector3") -> float:
        return (self - o).magnitude()

    def distance_sq_to(self, o: "Vector3") -> float:
        return (self - o).magnitude_sq()

    def project_onto(self, o: "Vector3") -> "Vector3":
        d = o.magnitude_sq()
        if d == 0.0:
            raise ZeroDivisionError("Cannot project onto zero Vector3")
        return o * (self.dot(o) / d)

    def reject_from(self, o: "Vector3") -> "Vector3":
        return self - self.project_onto(o)

    def reflect(self, normal: "Vector3") -> "Vector3":
        n = normal.normalized()
        return self - n * (2.0 * self.dot(n))

    def lerp(self, o: "Vector3", t: float) -> "Vector3":
        return Vector3(
            self.x + (o.x - self.x) * t,
            self.y + (o.y - self.y) * t,
            self.z + (o.z - self.z) * t,
        )

    def angle_to(self, o: "Vector3") -> float:
        denom = self.magnitude() * o.magnitude()
        if denom == 0.0:
            raise ZeroDivisionError("Cannot compute angle with zero Vector3")
        c = self.dot(o) / denom
        c = clamp(c, -1.0, 1.0)
        return math.acos(c)

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @classmethod
    def from_tuple(cls, t: Sequence[float]) -> "Vector3":
        if len(t) != 3:
            raise ValueError(f"Vector3.from_tuple expects 3 values, got {len(t)}")
        return cls(float(t[0]), float(t[1]), float(t[2]))

    def is_finite(self) -> bool:
        return math.isfinite(self.x) and math.isfinite(self.y) and math.isfinite(self.z)

    def is_zero(self, atol: float = DEFAULT_ATOL) -> bool:
        return is_close_zero(self.magnitude_sq(), atol * atol)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __len__(self) -> int:
        return 3


class VectorN:
    """Immutable N-dimensional float vector backed by a tuple."""

    __slots__ = ("_data",)

    def __init__(self, data: Iterable[float]):
        self._data = tuple(float(x) for x in data)

    @property
    def dim(self) -> int:
        return len(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, i: int) -> float:
        return self._data[i]

    def __eq__(self, other):
        return isinstance(other, VectorN) and self._data == other._data

    def __hash__(self):
        return hash(self._data)

    def __add__(self, o: "VectorN") -> "VectorN":
        if len(self) != len(o):
            raise ValueError("VectorN dimension mismatch")
        return VectorN(a + b for a, b in zip(self._data, o._data))

    def __sub__(self, o: "VectorN") -> "VectorN":
        if len(self) != len(o):
            raise ValueError("VectorN dimension mismatch")
        return VectorN(a - b for a, b in zip(self._data, o._data))

    def __neg__(self) -> "VectorN":
        return VectorN(-a for a in self._data)

    def __mul__(self, s: float) -> "VectorN":
        return VectorN(a * s for a in self._data)

    __rmul__ = __mul__

    def __truediv__(self, s: float) -> "VectorN":
        if s == 0.0:
            raise ZeroDivisionError("VectorN division by zero")
        return VectorN(a / s for a in self._data)

    def dot(self, o: "VectorN") -> float:
        if len(self) != len(o):
            raise ValueError("VectorN dimension mismatch")
        return sum(a * b for a, b in zip(self._data, o._data))

    def magnitude_sq(self) -> float:
        return sum(a * a for a in self._data)

    def magnitude(self) -> float:
        return math.sqrt(self.magnitude_sq())

    def normalized(self) -> "VectorN":
        m = self.magnitude()
        if m == 0.0:
            raise ZeroDivisionError("Cannot normalize zero VectorN")
        return self / m

    def lerp(self, o: "VectorN", t: float) -> "VectorN":
        if len(self) != len(o):
            raise ValueError("VectorN dimension mismatch")
        return VectorN(a + (b - a) * t for a, b in zip(self._data, o._data))

    def to_tuple(self) -> Tuple[float, ...]:
        return self._data

    @classmethod
    def zeros(cls, n: int) -> "VectorN":
        return cls((0.0,) * n)

    def is_finite(self) -> bool:
        return all(math.isfinite(x) for x in self._data)

    def __repr__(self) -> str:
        return f"VectorN{self._data!r}"
