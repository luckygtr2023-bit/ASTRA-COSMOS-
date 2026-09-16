"""ASTRA Evolution — exception hierarchy.

Each failure mode maps to a specific exception class; no generic
Exception is raised by the evolution engine.  This allows callers
to distinguish validation, authority, numerical, dependency and
limitation failures without string parsing.
"""

from __future__ import annotations


class EvolutionError(Exception):
    """Base class for all long-term cosmic evolution errors."""


class EvolutionValidationError(EvolutionError):
    """Invalid input, config, model, or scenario."""


class EvolutionAuthorityError(EvolutionError):
    """Mutation attempted without simulation-thread authority."""


class EvolutionNumericalError(EvolutionError):
    """NaN, Inf, overflow, timestep, precision, or instability issue."""


class EvolutionDependencyError(EvolutionError):
    """Required ASTRA dependency is missing or misused."""


class EvolutionLimitationError(EvolutionError):
    """A declared limitation was violated (approximation outside valid range, etc.).

    Carries a ``limitation`` attribute identifying the
    :class:`~astra.evolution.limitations.LimitationState`.
    """

    def __init__(self, message: str, limitation=None):
        super().__init__(message)
        self.limitation = limitation
