"""ASTRA Black-Hole - exceptions.

Contract: every Black-Hole-layer error derives from
``astra.core.exceptions.AstraError``. Validation errors additionally derive
from ``ValueError`` (caller programming bugs), while spacetime-boundary
violations raise the dedicated :class:`CoordinateSingularityError`.

NOTE (Agent LM): the handoff referenced a ``PermissionClient`` and a
``Serializable`` base class; neither exists in this repository. Authority in
ASTRA is enforced by ``astra.core.threading`` (``AuthorityContext`` /
``AuthorityError``) and persistence by ``PersistenceManager``/``Snapshot``.
The Black-Hole layer is a pure calculation layer: it holds no mutable
simulation state and therefore needs no mutation authority; serializable
state is provided via ``BlackHoleState.to_dict`` / ``from_dict``.
"""

from astra.core.exceptions import AstraError


class BlackHoleError(AstraError):
    """Base Black-Hole-layer error."""


class InvalidBlackHoleMassError(BlackHoleError, ValueError):
    """Raised when a black-hole mass is not a finite positive number."""


class InvalidSpinParameterError(BlackHoleError, ValueError):
    """Raised when the dimensionless spin violates |a*| <= 1.

    |a*| > 1 would describe a naked singularity (no event horizon), which
    ASTRA rejects explicitly instead of computing unphysical metrics.
    Non-finite spin values raise this error as well.
    """


class InvalidGeometryInputError(BlackHoleError, ValueError):
    """Raised when a geometric input (radius, angle) is non-finite."""


class CoordinateSingularityError(BlackHoleError):
    """Raised when a quantity is evaluated at or inside a horizon.

    Boyer-Lindquist / Schwarzschild coordinates are singular at the event
    horizon (division by zero, negative square roots). Evaluations within
    ``NUMERICAL_HORIZON_EPSILON`` of a horizon raise this error instead of
    silently propagating NaN/Inf into Orbital/Spacecraft subsystems. The
    physical singularity (r = 0) is also reported through this error.
    """
