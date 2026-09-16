"""ASTRA Evolution — explicit limitation states.

Every approximation or unsupported regime surfaces a ``LimitationState``
value rather than a silent substitution.  Callers that receive an
``EvolutionLimitationError`` can inspect the embedded state to decide
whether to widen validity, choose a different model, or abort.
"""

from __future__ import annotations

from enum import Enum


class LimitationState(str, Enum):
    """Machine-readable limitation taxonomy."""

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
    # Domain-specific extension used when a chemical/dark-matter model
    # is not available in the current repository.
    UNSUPPORTED_STRUCTURE = "UNSUPPORTED_STRUCTURE"
