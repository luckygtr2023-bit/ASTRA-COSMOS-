"""Phase-angle and synodic-period foundations.

These are foundations only. Full interplanetary mission planning
(Hohmann phasing with departure/arrival dates, porkchop plots, Lambert
solvers, etc.) belongs to a future dedicated mission-planning phase.
"""
from __future__ import annotations
import math

from astra.orbital.errors import InvalidOrbitError


def synodic_period(t1: float, t2: float) -> float:
    """1/T_syn = |1/T_1 - 1/T_2|."""
    if t1 <= 0.0 or t2 <= 0.0:
        raise InvalidOrbitError(
            f"orbital periods must be positive, got T1={t1!r}, T2={t2!r}"
        )
    inv = abs(1.0 / t1 - 1.0 / t2)
    if inv == 0.0:
        raise InvalidOrbitError("synodic period is infinite (identical periods)")
    return 1.0 / inv


def phase_angle_for_rendezvous(t_target: float,
                               t_transfer: float,
                               departure_phase_angle: float = 0.0) -> float:
    """Compute the phase angle required at departure for a Hohmann-like
    transfer arriving at the target after t_transfer seconds.

    Returns the target's angular position at arrival minus its position
    at departure, in radians, adjusted so that the chaser (moving on the
    transfer ellipse) meets it.

    Inputs
    ------
    t_target: orbital period of the target body (s)
    t_transfer: transfer duration (s). For a Hohmann transfer this is half
        the transfer-ellipse period.
    departure_phase_angle: initial angular separation of target relative to
        chaser at departure (radians). Default 0 for convenience.

    Result
    ------
    The required angular separation (radians) of the target AHEAD of the
    chaser at departure, such that the chaser arrives when the target is
    at the same point.
    """
    if t_target <= 0.0:
        raise InvalidOrbitError(f"t_target must be positive, got {t_target!r}")
    if t_transfer < 0.0:
        raise InvalidOrbitError(f"t_transfer must be non-negative, got {t_transfer!r}")
    n_target = 2.0 * math.pi / t_target
    target_rotation = n_target * t_transfer
    # Required phase angle = pi - target_rotation (mod 2pi), plus initial.
    return (math.pi - target_rotation + departure_phase_angle) % (2.0 * math.pi)
