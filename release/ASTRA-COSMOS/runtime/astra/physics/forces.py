"""Force representation, force applications, force accumulation, sources.

Design
------
- Force            : a raw (vector) force with an optional world-frame
                     application point. If application_point is None the
                     force acts at the centre of mass (no torque).
- ForceApplication : a structured contribution from a source. Contains
                     a force vector (may be zero), a pure torque (may be
                     zero), and an optional application point offset from
                     the centre of mass.
- ForceAccumulator : mutable per-body accumulator that nets force and
                     torque. Also stores the pure torque separately so
                     sources can add couples.
- ForceSource      : Protocol. `evaluate(mass, position, orientation,
                     velocity, angular_velocity, dt)` returns a list of
                     ForceApplication instances.

Ordering: sources are evaluated in the order they were added. This is
deterministic and documented.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Sequence
from astra.mathematics import Vector3, Quaternion
from astra.physics.validation import validate_force_vector, validate_torque_vector


@dataclass(frozen=True)
class Force:
    """A raw force vector with optional world-frame application point."""
    vector: Vector3
    application_point: Optional[Vector3] = None
    label: str = ""

    def __post_init__(self):
        validate_force_vector(self.vector)

    def to_torque(self, com_world: Vector3) -> Vector3:
        if self.application_point is None:
            return Vector3(0.0, 0.0, 0.0)
        r = self.application_point - com_world
        return r.cross(self.vector)


@dataclass(frozen=True)
class ForceApplication:
    """A structured force+torque contribution from a source."""
    force: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    torque: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    application_point_offset: Optional[Vector3] = None
    label: str = ""

    def __post_init__(self):
        validate_force_vector(self.force)
        validate_torque_vector(self.torque)


@dataclass
class ForceAccumulator:
    """Accumulates net force and net torque for a single body."""
    net_force: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))
    net_torque: Vector3 = field(default_factory=lambda: Vector3(0.0, 0.0, 0.0))

    def clear(self) -> None:
        self.net_force = Vector3(0.0, 0.0, 0.0)
        self.net_torque = Vector3(0.0, 0.0, 0.0)

    def add(self, application: ForceApplication) -> None:
        validate_force_vector(application.force)
        validate_torque_vector(application.torque)
        self.net_force = self.net_force + application.force
        self.net_torque = self.net_torque + application.torque
        if application.application_point_offset is not None:
            self.net_torque = self.net_torque + \
                application.application_point_offset.cross(application.force)

    def add_force(self, f: Force, com_world: Vector3) -> None:
        validate_force_vector(f.vector)
        self.net_force = self.net_force + f.vector
        self.net_torque = self.net_torque + f.to_torque(com_world)

    def add_raw_force(self, f: Vector3) -> None:
        validate_force_vector(f)
        self.net_force = self.net_force + f

    def add_raw_torque(self, t: Vector3) -> None:
        validate_torque_vector(t)
        self.net_torque = self.net_torque + t


class ForceSource(Protocol):
    """Protocol for a deterministic force source."""
    name: str

    def evaluate(
        self,
        mass: float,
        position: Vector3,
        orientation: Quaternion,
        velocity: Vector3,
        angular_velocity: Vector3,
        dt: float,
    ) -> Sequence[ForceApplication]:
        """Return force applications this source contributes to a body."""


@dataclass
class ConstantForce:
    """A constant force applied at the centre of mass. Test-friendly."""
    force_vector: Vector3
    name: str = "constant_force"

    def __post_init__(self):
        validate_force_vector(self.force_vector)

    def evaluate(self, mass, position, orientation, velocity,
                 angular_velocity, dt):
        return (ForceApplication(force=self.force_vector,
                                 label=self.name),)
