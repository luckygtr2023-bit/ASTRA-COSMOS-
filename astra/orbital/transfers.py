"""Hohmann and bi-elliptic transfers between circular coplanar orbits.

Conventions
-----------
- r1: initial circular radius (m)
- r2: target circular radius (m)
- mu: gravitational parameter (m^3/s^2)
- All delta-v magnitudes are positive.

Hohmann
-------
Only valid for coplanar circular orbits. Optimal (two-impulse) when
r2 / r1 < ~15.58 for the Hohmann vs bi-elliptic comparison, though
Hohmann is also optimal among two-impulse transfers regardless.

Bi-elliptic
-----------
Three impulses via an intermediate apoapsis radius rb. Advantageous when
r2 / r1 > ~11.94 and rb is chosen far enough out.
"""
from __future__ import annotations
from dataclasses import dataclass
import math

from astra.orbital.errors import InvalidTransferError
from astra.orbital.period import orbital_period
from astra.orbital.velocities import circular_velocity, vis_viva


@dataclass(frozen=True)
class HohmannTransfer:
    r1: float
    r2: float
    mu: float
    semi_major_axis: float
    delta_v_1: float
    delta_v_2: float
    total_delta_v: float
    transfer_time: float


@dataclass(frozen=True)
class BiellipticTransfer:
    r1: float
    r2: float
    rb: float
    mu: float
    delta_v_1: float
    delta_v_2: float
    delta_v_3: float
    total_delta_v: float
    transfer_time: float


def _validate_radii(r1: float, r2: float, mu: float) -> None:
    if not (math.isfinite(r1) and r1 > 0.0):
        raise InvalidTransferError(f"r1 must be positive finite, got {r1!r}")
    if not (math.isfinite(r2) and r2 > 0.0):
        raise InvalidTransferError(f"r2 must be positive finite, got {r2!r}")
    if not (math.isfinite(mu) and mu > 0.0):
        raise InvalidTransferError(f"mu must be positive finite, got {mu!r}")


def hohmann_transfer(r1: float, r2: float, mu: float) -> HohmannTransfer:
    """Classical Hohmann transfer between two coplanar circular orbits."""
    _validate_radii(r1, r2, mu)
    a_t = 0.5 * (r1 + r2)

    v1 = circular_velocity(r1, mu)
    v2 = circular_velocity(r2, mu)
    v_t1 = vis_viva(r1, a_t, mu)
    v_t2 = vis_viva(r2, a_t, mu)

    dv1 = abs(v_t1 - v1)
    dv2 = abs(v2 - v_t2)
    t = 0.5 * orbital_period(a_t, mu)

    return HohmannTransfer(
        r1=r1, r2=r2, mu=mu,
        semi_major_axis=a_t,
        delta_v_1=dv1, delta_v_2=dv2,
        total_delta_v=dv1 + dv2,
        transfer_time=t,
    )


def bielliptic_transfer(r1: float, r2: float, rb: float,
                        mu: float) -> BiellipticTransfer:
    """Three-impulse bi-elliptic transfer via intermediate radius rb."""
    _validate_radii(r1, r2, mu)
    if not (math.isfinite(rb) and rb > 0.0):
        raise InvalidTransferError(f"rb must be positive finite, got {rb!r}")
    if not (rb >= max(r1, r2)):
        raise InvalidTransferError(
            f"rb must be >= max(r1, r2) = {max(r1, r2)!r}, got rb={rb!r}"
        )

    a1 = 0.5 * (r1 + rb)
    a2 = 0.5 * (r2 + rb)

    v1 = circular_velocity(r1, mu)
    v2 = circular_velocity(r2, mu)
    v_at_r1_on_a1 = vis_viva(r1, a1, mu)
    v_at_rb_on_a1 = vis_viva(rb, a1, mu)
    v_at_rb_on_a2 = vis_viva(rb, a2, mu)
    v_at_r2_on_a2 = vis_viva(r2, a2, mu)

    dv1 = abs(v_at_r1_on_a1 - v1)
    dv2 = abs(v_at_rb_on_a2 - v_at_rb_on_a1)
    dv3 = abs(v2 - v_at_r2_on_a2)

    t = 0.5 * orbital_period(a1, mu) + 0.5 * orbital_period(a2, mu)

    return BiellipticTransfer(
        r1=r1, r2=r2, rb=rb, mu=mu,
        delta_v_1=dv1, delta_v_2=dv2, delta_v_3=dv3,
        total_delta_v=dv1 + dv2 + dv3,
        transfer_time=t,
    )
