"""Impulsive maneuver calculations.

These are IDEALIZED impulsive maneuvers: a velocity change applied
instantaneously at a single point on the orbit. Continuous-thrust
spacecraft physics belongs to the future Spacecraft Physics phase.
"""
from __future__ import annotations
import math

from astra.mathematics import Vector3
from astra.orbital.errors import InvalidOrbitError


def plane_change_delta_v(v: float, delta_inclination: float) -> float:
    """dv = 2 v sin(di/2). Pure plane change at the same speed."""
    if v < 0.0:
        raise InvalidOrbitError(f"v must be non-negative, got {v!r}")
    if not math.isfinite(delta_inclination):
        raise InvalidOrbitError("delta_inclination must be finite")
    return 2.0 * v * abs(math.sin(0.5 * delta_inclination))


def circularize_delta_v(v_at_point: float, target_circular_velocity: float) -> float:
    """|v_target - v_current| at a given point."""
    return abs(target_circular_velocity - v_at_point)


def impulsive_delta_v(v_before: Vector3, v_after: Vector3) -> float:
    """Magnitude of velocity change between two velocity vectors."""
    return (v_after - v_before).magnitude()
