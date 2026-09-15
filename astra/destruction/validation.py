"""Numeric validation shared across destruction modules."""
from __future__ import annotations

import math

from .errors import ImpactValidationError, NumericalError


def require_finite(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise NumericalError(f"{name} must be numeric")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise NumericalError(f"{name} must be finite, got {fv}")
    return fv


def require_positive(name: str, v: float, *, allow_zero: bool = False) -> float:
    fv = require_finite(name, v)
    if allow_zero:
        if fv < 0.0:
            raise NumericalError(f"{name} must be >= 0, got {fv}")
    else:
        if fv <= 0.0:
            raise NumericalError(f"{name} must be > 0, got {fv}")
    return fv


def require_non_negative(name: str, v: float) -> float:
    fv = require_finite(name, v)
    if fv < 0.0:
        raise NumericalError(f"{name} must be >= 0, got {fv}")
    return fv


def require_timestep(dt: float) -> float:
    fv = require_finite("timestep", dt)
    if fv <= 0.0:
        raise ImpactValidationError(f"timestep must be > 0, got {fv}")
    return fv
