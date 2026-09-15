"""Newtonian point-mass gravity with Plummer softening.

Model
-----
For a source at world position p_s with mass M and a body at p_b with mass m:

    r_vec = p_s - p_b                (points from body toward source)
    r2    = |r_vec|^2
    F     = G * M * m * r_vec / (r2 + eps^2)^(3/2)

With eps > 0 the force is finite and smooth everywhere, including r = 0.
With eps = 0 the classical 1/r^2 law is recovered; the r = 0 case is then
a genuine singularity and force_on(...) raises InvalidGravityError.

Determinism
-----------
Evaluation is a pure function of the source list, the body mass and the
body position. Sources are visited in insertion order.

Newton's third law
------------------
`mutual_gravity_force(m1, p1, m2, p2, G, eps)` returns the force on body 1.
Body 2 receives exactly -F (bit-identical up to floating point symmetry of
the arithmetic, tested).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple
import math

from astra.mathematics import Vector3, Quaternion
from astra.physics.constants import GRAVITATIONAL_CONSTANT, DEFAULT_SOFTENING
from astra.physics.errors import InvalidGravityError
from astra.physics.forces import ForceApplication
from astra.physics.validation import validate_mass, validate_softening


@dataclass(frozen=True)
class GravitationalBody:
    mass: float
    position: Vector3

    def __post_init__(self):
        validate_mass(self.mass, allow_inf=False)
        if not self.position.is_finite():
            raise InvalidGravityError("gravitational body position must be finite")


def _gravity_force(m_source: float, p_source: Vector3,
                   m_body: float, p_body: Vector3,
                   G: float, eps: float) -> Vector3:
    r_vec = p_source - p_body
    r2 = r_vec.magnitude_sq()
    soft2 = eps * eps
    denom = (r2 + soft2)
    if denom <= 0.0:
        raise InvalidGravityError(
            "gravitational force is singular at r = 0 with no softening"
        )
    # F = G * m_source * m_body * r_vec / (r^2 + eps^2)^(3/2)
    k = G * m_source * m_body / (denom ** 1.5)
    return r_vec * k


def mutual_gravity_force(m1: float, p1: Vector3,
                         m2: float, p2: Vector3,
                         G: float = GRAVITATIONAL_CONSTANT,
                         eps: float = DEFAULT_SOFTENING) -> Vector3:
    """Force on body 1 due to body 2. Body 2 receives the exact negative."""
    validate_mass(m1, allow_inf=False)
    validate_mass(m2, allow_inf=False)
    validate_softening(eps)
    if not (p1.is_finite() and p2.is_finite()):
        raise InvalidGravityError("positions must be finite")
    return _gravity_force(m2, p2, m1, p1, G, eps)


@dataclass
class GravitySource:
    """A collection of fixed gravitational bodies acting on dynamic bodies.

    Fixed reference bodies: their positions are queried at evaluation time,
    so external code may update them (e.g. from a Keplerian propagator
    elsewhere). GravitySource does not integrate or move them.
    """
    bodies: List[GravitationalBody] = field(default_factory=list)
    G: float = GRAVITATIONAL_CONSTANT
    softening: float = DEFAULT_SOFTENING
    name: str = "gravity"

    def __post_init__(self):
        validate_softening(self.softening)
        if not math.isfinite(self.G) or self.G < 0.0:
            raise InvalidGravityError(f"G must be finite and non-negative, got {self.G!r}")

    def add_body(self, mass: float, position: Vector3) -> None:
        self.bodies.append(GravitationalBody(mass=mass, position=position))

    def clear(self) -> None:
        self.bodies.clear()

    def force_on(self, mass: float, position: Vector3) -> Vector3:
        """Net gravitational force on a body of the given mass and position."""
        validate_mass(mass, allow_inf=False)
        if not position.is_finite():
            raise InvalidGravityError("body position must be finite")
        total = Vector3(0.0, 0.0, 0.0)
        for gb in self.bodies:
            total = total + _gravity_force(
                gb.mass, gb.position, mass, position, self.G, self.softening
            )
        return total

    def evaluate(self, mass, position, orientation, velocity,
                 angular_velocity, dt):
        """ForceSource protocol."""
        f = self.force_on(mass, position)
        return (ForceApplication(force=f, label=self.name),)
