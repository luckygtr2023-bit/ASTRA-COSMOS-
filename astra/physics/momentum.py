"""Linear and angular momentum, impulse, impulse application."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from astra.mathematics import Vector3, Matrix3
from astra.physics.errors import PhysicsError
from astra.physics.validation import validate_force_vector


def linear_momentum(mass: float, velocity: Vector3) -> Vector3:
    """p = m v."""
    return velocity * mass


def angular_momentum(inertia_world: Matrix3, angular_velocity: Vector3) -> Vector3:
    """L = I_world * omega (world frame)."""
    return inertia_world.transform(angular_velocity)


@dataclass(frozen=True)
class Impulse:
    """An impulse J applied at an optional world-frame point."""
    vector: Vector3
    application_point: Optional[Vector3] = None
    label: str = ""

    def __post_init__(self):
        validate_force_vector(self.vector)

    def torque_impulse(self, com_world: Vector3) -> Vector3:
        if self.application_point is None:
            return Vector3(0.0, 0.0, 0.0)
        r = self.application_point - com_world
        return r.cross(self.vector)


def velocity_change_from_impulse(impulse: Vector3, inverse_mass: float) -> Vector3:
    """dv = J * inv_m."""
    return impulse * inverse_mass


def angular_velocity_change_from_impulse(
    impulse: Impulse,
    com_world: Vector3,
    inverse_inertia_world: Matrix3,
) -> Vector3:
    """d omega = I_world^-1 * (r x J)."""
    r = impulse.torque_impulse(com_world)
    return inverse_inertia_world.transform(r)


def apply_impulse(impulse: Impulse, com_world: Vector3,
                  mass_properties, orientation,
                  velocity: Vector3,
                  angular_velocity: Vector3):
    """Return (new_velocity, new_angular_velocity) after applying impulse.

    Does not mutate the inputs. Caller assigns them to a MotionState.
    """
    inv_m = mass_properties.inverse_mass
    inv_I_world = mass_properties.world_inverse_inertia(orientation)
    new_v = velocity + velocity_change_from_impulse(impulse.vector, inv_m)
    new_w = angular_velocity + angular_velocity_change_from_impulse(
        impulse, com_world, inv_I_world
    )
    return new_v, new_w


def mutual_impulse(j: Vector3) -> tuple:
    """Return (J, -J) for equal-and-opposite impulse application."""
    return j, -j
