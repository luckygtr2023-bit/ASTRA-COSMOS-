"""ASTRA Physics layer.

Dependency direction:
    CORE -> MATHEMATICS -> MOTION -> PHYSICS -> (future domains)

Physics computes physical causes (forces, torques, impulses, mass, inertia,
momentum, energy). Motion integrates the resulting state. Physics does NOT
integrate kinematics itself and does NOT duplicate Mathematics primitives.

Units: SI-coherent. See astra.physics.constants for the full unit table.

Determinism: no wall-clock, no global RNG, deterministic iteration order.
Authority: mutating operations require CORE simulation-thread authority.
"""
from astra.physics.constants import (
    GRAVITATIONAL_CONSTANT, DEFAULT_SOFTENING, DEFAULT_MASS_TOL,
)
from astra.physics.errors import (
    PhysicsError, InvalidMassError, InvalidForceError,
    InvalidTorqueError, InvalidGravityError, InvalidContactError,
)
from astra.physics.validation import (
    validate_mass, validate_inertia, validate_softening, validate_restitution,
    validate_friction, validate_force_vector, validate_torque_vector,
)
from astra.physics.mass import MassProperties
from astra.physics.forces import (
    Force, ForceApplication, ForceAccumulator, ForceSource, ConstantForce,
)
from astra.physics.gravity import (
    GravitationalBody, GravitySource, mutual_gravity_force,
)
from astra.physics.torque import torque_from_force, torque_accumulator_apply
from astra.physics.momentum import (
    linear_momentum, angular_momentum, Impulse,
    velocity_change_from_impulse, angular_velocity_change_from_impulse,
    apply_impulse, mutual_impulse,
)
from astra.physics.energy import (
    kinetic_energy, gravitational_potential_energy, work, power,
    EnergyLedger,
)
from astra.physics.contact import (
    ContactResponse, ImpulseResponse, resolve_impulse_response,
)
from astra.physics.components import PhysicsComponent
from astra.physics.system import PhysicsSystem

__all__ = [
    # constants
    "GRAVITATIONAL_CONSTANT", "DEFAULT_SOFTENING", "DEFAULT_MASS_TOL",
    # errors
    "PhysicsError", "InvalidMassError", "InvalidForceError",
    "InvalidTorqueError", "InvalidGravityError", "InvalidContactError",
    # validation
    "validate_mass", "validate_inertia", "validate_softening",
    "validate_restitution", "validate_friction",
    "validate_force_vector", "validate_torque_vector",
    # mass
    "MassProperties",
    # forces
    "Force", "ForceApplication", "ForceAccumulator",
    "ForceSource", "ConstantForce",
    # gravity
    "GravitationalBody", "GravitySource", "mutual_gravity_force",
    # torque
    "torque_from_force", "torque_accumulator_apply",
    # momentum
    "linear_momentum", "angular_momentum", "Impulse",
    "velocity_change_from_impulse", "angular_velocity_change_from_impulse",
    "apply_impulse", "mutual_impulse",
    # energy
    "kinetic_energy", "gravitational_potential_energy", "work", "power",
    "EnergyLedger",
    # contact
    "ContactResponse", "ImpulseResponse", "resolve_impulse_response",
    # components
    "PhysicsComponent",
    # system
    "PhysicsSystem",
]
