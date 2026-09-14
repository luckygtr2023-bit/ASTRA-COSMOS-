"""Scalar/vector interpolation utilities for ASTRA.

Conventions
-----------
- lerp is linear in t and NOT clamped.
- smoothstep(edge0, edge1, x): 0 for x <= edge0, 1 for x >= edge1.
- catmull_rom takes 4 control points, interpolates p1..p2 for t in [0, 1].
"""

from __future__ import annotations
from astra.mathematics.vectors import Vector3
from astra.mathematics.precision import clamp01


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def inverse_lerp(a: float, b: float, x: float) -> float:
    if a == b:
        raise ValueError("inverse_lerp undefined when a == b")
    return (x - a) / (b - a)


def remap(x: float, in_a: float, in_b: float, out_a: float, out_b: float) -> float:
    return lerp(out_a, out_b, inverse_lerp(in_a, in_b, x))


def smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        raise ValueError("smoothstep edges must differ")
    t = clamp01((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def smootherstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        raise ValueError("smootherstep edges must differ")
    t = clamp01((x - edge0) / (edge1 - edge0))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def bilinear(x00: float, x10: float, x01: float, x11: float,
             tx: float, ty: float) -> float:
    top = lerp(x00, x10, tx)
    bot = lerp(x01, x11, tx)
    return lerp(top, bot, ty)


def catmull_rom(p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3,
                t: float) -> Vector3:
    t2 = t * t
    t3 = t2 * t
    return (p1 * 2.0
            + (p2 - p0) * t
            + (p0 * 2.0 - p1 * 5.0 + p2 * 4.0 - p3) * t2
            + (-p0 + p1 * 3.0 - p2 * 3.0 + p3) * t3) * 0.5


def hermite(p0: Vector3, m0: Vector3, p1: Vector3, m1: Vector3,
            t: float) -> Vector3:
    t2 = t * t
    t3 = t2 * t
    h00 = 2 * t3 - 3 * t2 + 1
    h10 = t3 - 2 * t2 + t
    h01 = -2 * t3 + 3 * t2
    h11 = t3 - t2
    return p0 * h00 + m0 * h10 + p1 * h01 + m1 * h11
