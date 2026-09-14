"""Center of mass, total mass, barycentric transforms."""
from __future__ import annotations
from typing import List, Sequence

from astra.mathematics import Vector3
from astra.nbody.bodies import NBodyBody


def total_mass(bodies: Sequence[NBodyBody]) -> float:
    return sum(b.mass for b in bodies)


def center_of_mass(bodies: Sequence[NBodyBody]) -> Vector3:
    """R_cm = sum(m_i r_i) / sum(m_i). Raises if empty."""
    if not bodies:
        raise ValueError("center_of_mass: empty body list")
    m_tot = total_mass(bodies)
    if m_tot == 0.0:
        raise ValueError("center_of_mass: total mass is zero")
    acc = Vector3(0.0, 0.0, 0.0)
    for b in bodies:
        acc = acc + b.position * b.mass
    return acc * (1.0 / m_tot)


def center_of_mass_velocity(bodies: Sequence[NBodyBody]) -> Vector3:
    """V_cm = sum(m_i v_i) / sum(m_i). Raises if empty."""
    if not bodies:
        raise ValueError("center_of_mass_velocity: empty body list")
    m_tot = total_mass(bodies)
    if m_tot == 0.0:
        raise ValueError("center_of_mass_velocity: total mass is zero")
    acc = Vector3(0.0, 0.0, 0.0)
    for b in bodies:
        acc = acc + b.velocity * b.mass
    return acc * (1.0 / m_tot)


def to_barycentric(bodies: Sequence[NBodyBody]) -> List[NBodyBody]:
    """Return copies whose positions/velocities are relative to the COM."""
    R = center_of_mass(bodies)
    V = center_of_mass_velocity(bodies)
    return [b.copy(position=b.position - R, velocity=b.velocity - V) for b in bodies]


def from_barycentric(bodies: Sequence[NBodyBody],
                     R: Vector3, V: Vector3) -> List[NBodyBody]:
    """Inverse of to_barycentric: shift a barycentric system back to world."""
    return [b.copy(position=b.position + R, velocity=b.velocity + V) for b in bodies]
