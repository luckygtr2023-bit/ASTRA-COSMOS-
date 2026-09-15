"""Collision-response interfaces.

Physics provides impulse-based response primitives. It does NOT perform
collision detection, contact generation, or geometry queries. A future
Collision phase will supply contacts; this module computes response
impulses from a contact normal and material parameters.

Reference
---------
Restitution e in [0, 1]: e=0 perfectly inelastic, e=1 perfectly elastic.
Friction mu >= 0: Coulomb-style tangential limit derived in future phases.
"""
from __future__ import annotations
from dataclasses import dataclass

from astra.mathematics import Vector3
from astra.physics.errors import InvalidContactError
from astra.physics.validation import validate_restitution, validate_friction
from astra.physics.momentum import Impulse


@dataclass(frozen=True)
class ContactResponse:
    """Material and geometric parameters for a single contact."""
    normal: Vector3                 # unit normal pointing from body A to body B
    restitution: float = 0.0        # in [0, 1]
    friction: float = 0.0           # >= 0
    contact_point: Vector3 = None   # world-frame contact point

    def __post_init__(self):
        validate_restitution(self.restitution)
        validate_friction(self.friction)
        if self.normal.is_zero():
            raise InvalidContactError("contact normal must be non-zero")
        if self.contact_point is not None and not self.contact_point.is_finite():
            raise InvalidContactError("contact point must be finite")


@dataclass(frozen=True)
class ImpulseResponse:
    """Result of resolving an impulse-based contact response."""
    impulse_a: Impulse
    impulse_b: Impulse


def resolve_impulse_response(
    contact: ContactResponse,
    relative_velocity: Vector3,
    inv_mass_a: float, inv_mass_b: float,
    normal_mass_a: float, normal_mass_b: float,
) -> ImpulseResponse:
    """Return impulse pair (on A, on B) for a 1-D contact along the normal.

    Uses the reduced mass formulation:
        j = -(1 + e) * v_rel_normal / (1/mA + 1/mB + n . I^-1_A (rA x n) x rA
                                                     + n . I^-1_B (rB x n) x rB)
    Simplified here to the linear part (no rotational coupling). Rotational
    coupling is left to the future Collision phase.

    normal_mass_a/b are the effective normal-direction inertias of each body
    (usually equal to the inverse mass for a point contact; provided as
    parameters to allow coupling to future rigid-body response).
    """
    n = contact.normal.normalized()
    v_rel_n = relative_velocity.dot(n)
    denom = normal_mass_a + normal_mass_b
    if denom <= 0.0:
        return ImpulseResponse(
            impulse_a=Impulse(Vector3(0, 0, 0)),
            impulse_b=Impulse(Vector3(0, 0, 0)),
        )
    j_mag = -(1.0 + contact.restitution) * v_rel_n / denom
    j_vec = n * j_mag
    return ImpulseResponse(
        impulse_a=Impulse(vector=j_vec, application_point=contact.contact_point),
        impulse_b=Impulse(vector=-j_vec, application_point=contact.contact_point),
    )
