"""Torque helpers. All quantities are world-frame."""
from __future__ import annotations
from astra.mathematics import Vector3
from astra.physics.forces import ForceAccumulator, ForceApplication
from astra.physics.validation import validate_force_vector, validate_torque_vector


def torque_from_force(force: Vector3, application_point: Vector3,
                      com_world: Vector3) -> Vector3:
    """tau = (r_applied - r_com) x F. World frame."""
    validate_force_vector(force)
    r = application_point - com_world
    return r.cross(force)


def torque_accumulator_apply(acc: ForceAccumulator,
                             application: ForceApplication) -> None:
    """Add a ForceApplication to an accumulator (delegates to ForceAccumulator.add)."""
    acc.add(application)


def angular_acceleration_from_torque(
    torque_world: Vector3,
    inverse_inertia_world,
) -> Vector3:
    """alpha = I_world^-1 * tau (world frame).

    inverse_inertia_world is a Matrix3 (world frame). Gyroscopic terms are
    added separately by PhysicsSystem using the full Euler equation.
    """
    validate_torque_vector(torque_world)
    return inverse_inertia_world.transform(torque_world)
