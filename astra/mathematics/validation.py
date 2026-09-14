"""Mathematical validation helpers for ASTRA."""

from __future__ import annotations
import math

from astra.mathematics.vectors import Vector3
from astra.mathematics.precision import is_close


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_finite(x: float, name: str = "value") -> None:
    if not math.isfinite(x):
        raise ValueError(f"{name} must be finite, got {x!r}")


def require_positive(x: float, name: str = "value") -> None:
    if not (math.isfinite(x) and x > 0.0):
        raise ValueError(f"{name} must be a positive finite float, got {x!r}")


def require_non_negative(x: float, name: str = "value") -> None:
    if not (math.isfinite(x) and x >= 0.0):
        raise ValueError(f"{name} must be a non-negative finite float, got {x!r}")


def require_in_range(x: float, lo: float, hi: float, name: str = "value") -> None:
    if not (lo <= x <= hi):
        raise ValueError(f"{name} must be in [{lo}, {hi}], got {x!r}")


def require_finite_vector3(v: Vector3, name: str = "value") -> None:
    if not v.is_finite():
        raise ValueError(f"{name} must have finite components, got {v!r}")


def require_unit_vector3(v: Vector3, atol: float = 1e-9, name: str = "value") -> None:
    if not is_close(v.magnitude(), 1.0, atol=atol):
        raise ValueError(f"{name} must be a unit vector, |v|={v.magnitude()}")


def check_invariant(condition: bool, message: str = "invariant violated") -> None:
    if not condition:
        raise AssertionError(message)


def normalize_preserves_direction(v: Vector3, atol: float = 1e-12) -> None:
    n = v.normalized()
    check_invariant(n.cross(v).magnitude() <= atol * max(1.0, v.magnitude()),
                    "normalize changed direction")


def quaternion_rotation_preserves_length(v: Vector3, q, atol: float = 1e-9) -> None:
    rotated = q.rotate(v)
    if not is_close(rotated.magnitude(), v.magnitude(), atol=atol):
        raise AssertionError(
            f"quaternion rotation changed magnitude: "
            f"{v.magnitude()} -> {rotated.magnitude()}")


def matrix_inverse_identity(m, atol: float = 1e-9) -> None:
    from astra.mathematics.matrices import Matrix3, Matrix4
    inv = m.inverse()
    prod = m.matmul(inv)
    if isinstance(m, Matrix3):
        ident = Matrix3.identity()
        for a, b in zip(prod.to_tuple(), ident.to_tuple()):
            if not is_close(a, b, atol=atol):
                raise AssertionError("M * M^-1 != I")
    elif isinstance(m, Matrix4):
        ident = Matrix4.identity()
        for a, b in zip(prod.to_tuple(), ident.to_tuple()):
            if not is_close(a, b, atol=atol):
                raise AssertionError("M * M^-1 != I")
