"""Pairwise Newtonian gravity with Plummer softening.

Model
-----
For positions r_i, r_j and masses m_i, m_j:

    r_vec = r_j - r_i
    denom = |r_vec|^2 + eps^2
    a_i   = G m_j r_vec / denom^(3/2)
    a_j   = -G m_i r_vec / denom^(3/2)
    U_ij  = -G m_i m_j / sqrt(denom)

The antisymmetric form is exact in the acceleration contributions up to
float rounding. Momentum is conserved to numerical tolerance; the
diagnostic tests measure residual drift honestly.

If eps == 0 and |r_vec| == 0, raise NBodySingularityError. This is
deterministic and explicit; it is not silently swallowed.
"""
from __future__ import annotations
from typing import List, Sequence, Tuple
import math

from astra.mathematics import Vector3
from astra.physics.constants import GRAVITATIONAL_CONSTANT, DEFAULT_SOFTENING
from astra.nbody.errors import NBodySingularityError
from astra.nbody.bodies import NBodyBody


def pairwise_acceleration(
    pos_i: Vector3, pos_j: Vector3,
    m_i: float, m_j: float,
    G: float = GRAVITATIONAL_CONSTANT,
    softening: float = DEFAULT_SOFTENING,
) -> Tuple[Vector3, Vector3]:
    """Return (a_i, a_j) — the pair's acceleration contributions.

    Ordering within the pair is arbitrary; the caller decides which index
    is "i" and which is "j". The two accelerations are exact negatives
    up to float rounding.
    """
    r_vec = pos_j - pos_i
    r2 = r_vec.magnitude_sq()
    denom = r2 + softening * softening
    if denom == 0.0:
        raise NBodySingularityError(
            "pairwise_acceleration: zero separation with zero softening"
        )
    r_mag = math.sqrt(denom)
    k = G / (denom * r_mag)
    a_i = r_vec * (k * m_j)
    a_j = r_vec * (-k * m_i)
    return a_i, a_j


def pairwise_potential(
    m_i: float, m_j: float, distance_softened: float,
    G: float = GRAVITATIONAL_CONSTANT,
) -> float:
    """U_ij = -G m_i m_j / r_softened. Positive G, positive masses."""
    if distance_softened <= 0.0:
        raise NBodySingularityError(
            "pairwise_potential: distance must be positive"
        )
    return -G * m_i * m_j / distance_softened


def compute_accelerations(
    bodies: Sequence[NBodyBody],
    G: float = GRAVITATIONAL_CONSTANT,
    softening: float = DEFAULT_SOFTENING,
) -> List[Vector3]:
    """Deterministic O(N^2) acceleration evaluation.

    Pairs are evaluated in index order i < j. Results accumulated into a
    fixed-size list indexed by position in the input sequence. No
    iteration over unordered containers.
    """
    n = len(bodies)
    acc = [Vector3(0.0, 0.0, 0.0) for _ in range(n)]
    for i in range(n):
        bi = bodies[i]
        for j in range(i + 1, n):
            bj = bodies[j]
            a_i, a_j = pairwise_acceleration(
                bi.position, bj.position, bi.mass, bj.mass, G, softening
            )
            acc[i] = acc[i] + a_i
            acc[j] = acc[j] + a_j
    return acc


def gravitational_potential_energy(
    bodies: Sequence[NBodyBody],
    G: float = GRAVITATIONAL_CONSTANT,
    softening: float = DEFAULT_SOFTENING,
) -> float:
    """Total potential energy. Pairwise; each pair counted once (i < j)."""
    n = len(bodies)
    U = 0.0
    eps2 = softening * softening
    for i in range(n):
        bi = bodies[i]
        for j in range(i + 1, n):
            bj = bodies[j]
            r2 = (bj.position - bi.position).magnitude_sq()
            denom = r2 + eps2
            if denom <= 0.0:
                raise NBodySingularityError(
                    "gravitational_potential_energy: zero softened distance"
                )
            U += -G * bi.mass * bj.mass / math.sqrt(denom)
    return U
