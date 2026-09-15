"""Kinetic energy, gravitational potential energy, work, power, ledgers.

Conservation diagnostics are honest: with numerical integration, energy
is NOT exactly conserved and drift is measurable. EnergyLedger tracks
starting energy, current energy, and cumulative work to expose drift.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import math

from astra.mathematics import Vector3
from astra.physics.constants import GRAVITATIONAL_CONSTANT
from astra.physics.errors import PhysicsError


def kinetic_energy(mass: float, velocity: Vector3) -> float:
    """K = 1/2 m |v|^2."""
    return 0.5 * mass * velocity.magnitude_sq()


def gravitational_potential_energy(m1: float, m2: float, r: float,
                                   G: float = GRAVITATIONAL_CONSTANT) -> float:
    """U = -G m1 m2 / r. r must be > 0."""
    if not math.isfinite(r):
        raise PhysicsError(f"distance must be finite, got {r!r}")
    if r <= 0.0:
        raise PhysicsError(f"gravitational potential undefined at r <= 0, got {r!r}")
    return -G * m1 * m2 / r


def work(force: Vector3, displacement: Vector3) -> float:
    """W = F . d."""
    return force.dot(displacement)


def power(force: Vector3, velocity: Vector3) -> float:
    """P = F . v."""
    return force.dot(velocity)


@dataclass
class EnergyLedger:
    """Tracks a body's (or system's) energy bookkeeping deterministically."""
    initial_kinetic: float = 0.0
    initial_potential: float = 0.0
    cumulative_work: float = 0.0

    def total_initial(self) -> float:
        return self.initial_kinetic + self.initial_potential

    def drift(self, current_kinetic: float, current_potential: float) -> float:
        """current_total - (initial_total + cumulative_work)."""
        current_total = current_kinetic + current_potential
        return current_total - (self.total_initial() + self.cumulative_work)

    def record_work(self, w: float) -> None:
        self.cumulative_work += w
