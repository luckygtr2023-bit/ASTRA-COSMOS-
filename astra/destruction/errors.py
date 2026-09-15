"""Exceptions for the ASTRA Destruction & Impact system.

Hierarchy integrates with astra.core.exceptions so that authority and
persistence failures raised by this package are also caught by callers
filtering on the core exception types:

    DestructionError                (base, subclass of astra.core AstraError)
    ├── ImpactValidationError       (bad impact inputs / state-machine misuse)
    ├── NumericalError              (NaN / Inf / non-positive quantities)
    ├── LimitExceededError          (configured simulation limits breached)
    ├── UnsupportedBodyError        (object not compatible with impact model)
    ├── AuthorityError              (also subclasses core AuthorityError)
    └── PersistenceError            (also subclasses core PersistenceError)
"""
from __future__ import annotations

from astra.core.exceptions import AstraError
from astra.core.exceptions import AuthorityError as CoreAuthorityError
from astra.core.exceptions import PersistenceError as CorePersistenceError


class DestructionError(AstraError):
    """Base class for all destruction/impact errors."""


class ImpactValidationError(DestructionError):
    """Impact event or inputs failed validation."""


class NumericalError(DestructionError):
    """NaN, Inf, zero-length vector, or other invalid numeric input."""


class LimitExceededError(DestructionError):
    """Configured limit exceeded (fragments, recursion, energy floor, ...)."""


class UnsupportedBodyError(DestructionError):
    """Object type not compatible with the impact model."""


class AuthorityError(DestructionError, CoreAuthorityError):
    """Mutation attempted without authority.

    Subclasses both DestructionError and the core AuthorityError so that
    either ``except`` clause catches it. Constructor signature matches the
    core exception: (message, operation="", context=None).
    """


class PersistenceError(DestructionError, CorePersistenceError):
    """Serialization/deserialization failure.

    Subclasses both DestructionError and the core PersistenceError.
    Constructor signature matches the core exception:
    (message, path="", reason="").
    """
