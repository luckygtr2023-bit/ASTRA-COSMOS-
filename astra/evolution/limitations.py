"""ASTRA COSMOS — Phase 21: explicit limitation states.

Every failure mode of the evolution engine maps either to an
``EvolutionError`` subclass (see ``astra.evolution.errors``) or to one of
these machine-readable limitation states carried by
``EvolutionLimitationError``. The engine never substitutes a fallback
result when a limitation is hit: it fails explicitly and says why.
"""
from enum import Enum


class LimitationState(str, Enum):
    """Machine-readable declaration of why an operation cannot proceed."""

    UNSUPPORTED_TIMESCALE = "UNSUPPORTED_TIMESCALE"
    UNSUPPORTED_PROCESS = "UNSUPPORTED_PROCESS"
    NUMERICAL_INSTABILITY = "NUMERICAL_INSTABILITY"
    INVALID_TIMESTEP = "INVALID_TIMESTEP"
    INVALID_COSMOLOGY = "INVALID_COSMOLOGY"
    INCOMPATIBLE_MODEL = "INCOMPATIBLE_MODEL"
    MISSING_REQUIRED_DATA = "MISSING_REQUIRED_DATA"
    INSUFFICIENT_RESOLUTION = "INSUFFICIENT_RESOLUTION"
    OUTSIDE_VALID_RANGE = "OUTSIDE_VALID_RANGE"
    CAUSAL_INCONSISTENCY = "CAUSAL_INCONSISTENCY"
    COORDINATE_INCONSISTENCY = "COORDINATE_INCONSISTENCY"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"


__all__ = ["LimitationState"]
