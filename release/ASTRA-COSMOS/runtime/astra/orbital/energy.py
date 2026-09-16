"""Specific orbital energy and specific angular momentum."""
from __future__ import annotations
import math

from astra.mathematics import Vector3
from astra.orbital.state import OrbitalState


def specific_orbital_energy(state: OrbitalState) -> float:
    """epsilon = v^2/2 - mu/r.

    Elliptic: epsilon < 0;  Parabolic: epsilon = 0;  Hyperbolic: epsilon > 0.
    """
    r = state.r
    if r == 0.0:
        raise ValueError("specific_orbital_energy undefined at r = 0")
    return 0.5 * state.v * state.v - state.mu / r


def specific_angular_momentum(state: OrbitalState) -> Vector3:
    """h_vec = r x v."""
    return state.position.cross(state.velocity)
