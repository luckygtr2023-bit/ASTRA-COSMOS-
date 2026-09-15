"""Relativistic travel. Reconciled — delegates to astra.relativity.core.

If the authoritative Relativity module exposes the same quantities, this
module wraps it and preserves the scaffold API for compatibility.
"""
from __future__ import annotations

import math

from astra.mathematics import Vector3
from astra.relativity.core import SPEED_OF_LIGHT as _C
from astra.relativity.core import lorentz_factor as _astro_gamma

from .errors import TravelNumericalError, TravelUnsupportedError

C_M_S = _C  # exact SI — re-export for scaffold compatibility


def lorentz_factor(speed_m_s: float) -> float:
    """Scaffold-compatible lorentz_factor delegating to authoritative implementation."""
    if isinstance(speed_m_s, Vector3):
        # Vector3 input — delegate directly
        try:
            return _astro_gamma(speed_m_s)
        except Exception as e:
            # map to travel error types for scaffold tests
            from astra.relativity.exceptions import LightSpeedViolation

            if isinstance(e, LightSpeedViolation):
                raise TravelUnsupportedError(str(e)) from e
            raise
    if isinstance(speed_m_s, (int, float)) and not isinstance(speed_m_s, bool):
        if math.isnan(speed_m_s) or math.isinf(speed_m_s):
            raise TravelNumericalError(f"speed must be finite, got {speed_m_s!r}")
        if speed_m_s < 0.0:
            raise TravelNumericalError("speed must be >= 0")
        try:
            return _astro_gamma(float(speed_m_s))
        except Exception as e:
            from astra.relativity.exceptions import LightSpeedViolation

            if isinstance(e, LightSpeedViolation):
                raise TravelUnsupportedError(str(e)) from e
            raise
    # Vec3 or other
    try:
        # try to extract norm
        if hasattr(speed_m_s, "norm"):
            s = float(speed_m_s.norm())
        elif hasattr(speed_m_s, "magnitude"):
            s = float(speed_m_s.magnitude())
        else:
            s = float(speed_m_s)
        return lorentz_factor(s)
    except TravelNumericalError:
        raise
    except TravelUnsupportedError:
        raise
    except Exception as e:
        raise TravelNumericalError(str(e)) from e


def proper_time_for_coordinate(coordinate_dt_s: float, speed_m_s: float) -> float:
    if isinstance(coordinate_dt_s, bool) or not isinstance(coordinate_dt_s, (int, float)):
        raise TravelNumericalError("coordinate_dt_s must be numeric")
    coordinate_dt_s = float(coordinate_dt_s)
    if math.isnan(coordinate_dt_s) or math.isinf(coordinate_dt_s):
        raise TravelNumericalError("coordinate_dt_s must be finite")
    if coordinate_dt_s < 0.0:
        raise TravelNumericalError("coordinate_dt_s must be >= 0")
    gamma = lorentz_factor(speed_m_s)
    return coordinate_dt_s / gamma


def coordinate_time_for_proper(proper_dt_s: float, speed_m_s: float) -> float:
    if isinstance(proper_dt_s, bool) or not isinstance(proper_dt_s, (int, float)):
        raise TravelNumericalError("proper_dt_s must be numeric")
    proper_dt_s = float(proper_dt_s)
    if math.isnan(proper_dt_s) or math.isinf(proper_dt_s):
        raise TravelNumericalError("proper_dt_s must be finite")
    if proper_dt_s < 0.0:
        raise TravelNumericalError("proper_dt_s must be >= 0")
    gamma = lorentz_factor(speed_m_s)
    return proper_dt_s * gamma


def speed_from_vector(v) -> float:
    """Extract speed magnitude from Vec3 / Vector3 / float."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if hasattr(v, "norm"):
        return float(v.norm())
    if hasattr(v, "magnitude"):
        return float(v.magnitude())
    if isinstance(v, (list, tuple)) and len(v) == 3:
        return math.sqrt(float(v[0]) ** 2 + float(v[1]) ** 2 + float(v[2]) ** 2)
    raise TravelNumericalError(f"cannot extract speed from {type(v).__name__}")
