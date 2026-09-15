"""Validation helpers for Physics. Reuse Mathematics where appropriate."""
from __future__ import annotations
import math

from astra.mathematics import Matrix3, Vector3
from astra.physics.errors import (
    InvalidMassError, InvalidForceError, InvalidTorqueError,
    InvalidGravityError, InvalidContactError,
)


def validate_mass(mass: float, *, allow_inf: bool = True) -> None:
    """mass must be positive and finite; +inf allowed iff allow_inf."""
    if not isinstance(mass, (int, float)):
        raise InvalidMassError(f"mass must be numeric, got {type(mass).__name__}")
    if math.isnan(mass):
        raise InvalidMassError("mass must not be NaN")
    if mass == math.inf and allow_inf:
        return
    if not math.isfinite(mass):
        raise InvalidMassError(f"mass must be finite, got {mass!r}")
    if mass <= 0.0:
        raise InvalidMassError(f"mass must be positive, got {mass!r}")


def validate_inertia(inertia: float) -> None:
    if not (math.isfinite(inertia) and inertia > 0.0):
        raise InvalidMassError(f"inertia must be positive finite, got {inertia!r}")


def validate_softening(eps: float) -> None:
    if not math.isfinite(eps):
        raise InvalidGravityError(f"softening must be finite, got {eps!r}")
    if eps < 0.0:
        raise InvalidGravityError(f"softening must be >= 0, got {eps!r}")


def validate_restitution(e: float) -> None:
    if not (math.isfinite(e) and 0.0 <= e <= 1.0):
        raise InvalidContactError(f"restitution must be in [0, 1], got {e!r}")


def validate_friction(mu: float) -> None:
    if not (math.isfinite(mu) and mu >= 0.0):
        raise InvalidContactError(f"friction must be >= 0, got {mu!r}")


def validate_force_vector(f: Vector3) -> None:
    if not f.is_finite():
        raise InvalidForceError(f"force must be finite, got {f!r}")


def validate_torque_vector(t: Vector3) -> None:
    if not t.is_finite():
        raise InvalidTorqueError(f"torque must be finite, got {t!r}")
