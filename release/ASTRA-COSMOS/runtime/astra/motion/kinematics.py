"""Linear and angular kinematic primitives.

- Linear: exact analytic step for constant acceleration.
- Angular: quaternion derivative for world-frame angular velocity.
"""
from __future__ import annotations
import math
from typing import Tuple

from astra.mathematics import Vector3, Quaternion


def linear_step_constant_acceleration(
    position: Vector3, velocity: Vector3, acceleration: Vector3, dt: float
) -> Tuple[Vector3, Vector3]:
    """Exact solution of  dx/dt = v,  dv/dt = a  for constant a over dt.

    Returns (new_position, new_velocity).
    """
    new_velocity = velocity + acceleration * dt
    new_position = position + velocity * dt + acceleration * (0.5 * dt * dt)
    return new_position, new_velocity


def linear_derivative(
    velocity: Vector3, acceleration: Vector3
) -> Tuple[Vector3, Vector3]:
    """Return (dx/dt, dv/dt) = (velocity, acceleration)."""
    return velocity, acceleration


def quaternion_derivative(q: Quaternion, omega_world: Vector3) -> Quaternion:
    """Return dq/dt for world-frame angular velocity omega.

    Convention: dq/dt = 0.5 * omega_quat * q
    where omega_quat = (0, omega.x, omega.y, omega.z).
    """
    omega_quat = Quaternion(0.0, omega_world.x, omega_world.y, omega_world.z)
    return omega_quat.multiply(q) * 0.5


def angular_step_constant_omega(
    q: Quaternion, omega_world: Vector3, dt: float
) -> Quaternion:
    """Exact integration of dq/dt = 0.5 * omega_quat * q for constant omega.

    Rotates q by exp(omega * dt) on the left (world frame).
    """
    speed = omega_world.magnitude()
    if speed == 0.0:
        return q
    axis = omega_world / speed
    angle = speed * dt
    dq = Quaternion.from_axis_angle(axis, angle)
    return dq.multiply(q).normalized()


def angular_step_constant_alpha(
    q: Quaternion, omega: Vector3, alpha: Vector3, dt: float
) -> Tuple[Quaternion, Vector3]:
    """Second-order update for constant angular acceleration.

    omega_new = omega + alpha * dt
    Uses a midpoint angular speed for the orientation update.
    """
    omega_new = omega + alpha * dt
    omega_mid = (omega + omega_new) * 0.5
    q_new = angular_step_constant_omega(q, omega_mid, dt)
    return q_new, omega_new


def quaternion_rotation_angle(q: Quaternion) -> float:
    """Magnitude of rotation represented by q in [0, 2*pi]."""
    w = abs(q.w)
    if w > 1.0:
        w = 1.0
    return 2.0 * math.acos(w)
