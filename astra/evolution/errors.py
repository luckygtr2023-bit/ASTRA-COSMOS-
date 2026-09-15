"""ASTRA COSMOS — Phase 21: exceptions for the Long-Term Cosmic Evolution
Engine.

Hierarchy integrates with astra.core.exceptions so that authority and
persistence failures raised by this package are also caught by callers
filtering on the core exception types (the repository convention established
by ``astra.destruction.errors``):

    EvolutionError                 (base, subclass of astra.core AstraError)
    ├── EvolutionValidationError   (bad inputs / config / model / scenario)
    ├── EvolutionNumericalError    (NaN / Inf / invalid numeric input)
    ├── EvolutionAuthorityError    (also subclasses core AuthorityError)
    ├── EvolutionDependencyError   (required ASTRA dependency missing or misused)
    └── EvolutionPersistenceError  (also subclasses core PersistenceError)

Failure states that represent declared scientific limitations are not
exceptions but explicit ``LimitationState`` values carried by
``EvolutionLimitationError`` (see ``astra.evolution.limitations``).
No generic ``Exception`` is ever raised by this package.
"""
from __future__ import annotations

from astra.core.exceptions import AstraError
from astra.core.exceptions import AuthorityError as CoreAuthorityError
from astra.core.exceptions import PersistenceError as CorePersistenceError


class EvolutionError(AstraError):
    """Base class for all long-term cosmic evolution errors."""


class EvolutionValidationError(EvolutionError, ValueError):
    """Invalid input, configuration, model, or scenario."""


class EvolutionNumericalError(EvolutionError, ValueError):
    """NaN, Inf, overflow, or other invalid numeric input."""


class EvolutionAuthorityError(EvolutionError, CoreAuthorityError):
    """Mutation attempted without authority.

    Subclasses both EvolutionError and the core AuthorityError so that
    either ``except`` clause catches it. Constructor signature matches the
    core exception: (message, operation="", context=None).
    """


class EvolutionDependencyError(EvolutionError):
    """A required ASTRA dependency is absent or was misused.

    Raised by the ``Missing*`` adapters in ``astra.evolution.adapters`` when
    a caller invokes a capability whose owning system is not present in this
    repository, and by the engine when a Protocol-based dependency is
    required but not injected. Never silently substituted.
    """


class EvolutionLimitationError(EvolutionError):
    """A declared limitation was hit (approximation outside its valid
    range, unsupported timescale, insufficient resolution, ...).

    ``state`` carries the machine-readable ``LimitationState``; ``detail``
    carries a human-readable, honest explanation.
    """

    def __init__(self, state, detail: str = "") -> None:
        self.state = state
        self.detail = detail
        message = f"{getattr(state, 'value', state)}: {detail}" if detail else str(state)
        super().__init__(message)


class EvolutionPersistenceError(EvolutionError, CorePersistenceError):
    """Serialization/deserialization failure.

    Subclasses both EvolutionError and the core PersistenceError.
    Constructor signature matches the core exception:
    (message, path="", reason="").
    """
