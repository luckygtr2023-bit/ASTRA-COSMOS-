"""Conic-section classification using eccentricity and energy."""
from __future__ import annotations
from enum import Enum

from astra.orbital.constants import PARABOLIC_TOL
from astra.orbital.state import OrbitalState
from astra.orbital.energy import specific_orbital_energy


class ConicType(Enum):
    ELLIPTIC = "elliptic"
    PARABOLIC = "parabolic"
    HYPERBOLIC = "hyperbolic"


def classify_conic(eccentricity: float) -> ConicType:
    if not (eccentricity >= 0.0):
        raise ValueError(f"eccentricity must be non-negative, got {eccentricity!r}")
    if abs(eccentricity - 1.0) < PARABOLIC_TOL:
        return ConicType.PARABOLIC
    if eccentricity < 1.0:
        return ConicType.ELLIPTIC
    return ConicType.HYPERBOLIC


def is_elliptic(eccentricity: float) -> bool:
    return classify_conic(eccentricity) is ConicType.ELLIPTIC


def is_parabolic(eccentricity: float) -> bool:
    return classify_conic(eccentricity) is ConicType.PARABOLIC


def is_hyperbolic(eccentricity: float) -> bool:
    return classify_conic(eccentricity) is ConicType.HYPERBOLIC
