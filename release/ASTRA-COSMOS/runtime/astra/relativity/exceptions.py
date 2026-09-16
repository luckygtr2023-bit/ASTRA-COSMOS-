"""ASTRA Relativity - exceptions.

Contract: every Relativity-layer error derives from
``astra.core.exceptions.AstraError`` so callers can catch the whole ASTRA
error family with a single ``except AstraError``.

``InvalidVelocityError`` and ``InvalidRestMassError`` additionally derive
from ``ValueError``: non-finite / negative *scalar* inputs are caller bugs
(in the same spirit as ``math.sqrt(-1)``), while physics violations such as
``v >= c`` raise the dedicated :class:`LightSpeedViolation`.
"""

from astra.core.exceptions import AstraError


class RelativityError(AstraError):
    """Base Relativity-layer error."""


class LightSpeedViolation(RelativityError):
    """Raised when a massive object's speed reaches or exceeds c.

    Special relativity assigns infinite energy to v = c for m0 > 0, so this
    is a hard validation boundary, never a silent clamp.
    """


class DegenerateMetricError(RelativityError):
    """Raised when a spacetime metric is singular or invalid.

    Typical cases: determinant <= 0 (e.g. Schwarzschild coordinates at or
    inside r = r_s) or physically meaningless inputs (negative mass).
    """


class InvalidVelocityError(RelativityError, ValueError):
    """Raised when a velocity input is NaN or infinite.

    Derives from both ``RelativityError`` and ``ValueError``: NaN/Inf speed
    is a caller programming error, so plain ``except ValueError`` also works.
    """


class InvalidRestMassError(RelativityError, ValueError):
    """Raised when a rest mass is negative or non-finite.

    Derives from both ``RelativityError`` and ``ValueError`` for the same
    reason as :class:`InvalidVelocityError`.
    """


class SpacelikeIntervalError(RelativityError):
    """Raised when proper time is requested for spacelike-separated events.

    No inertial frame orders spacelike-separated events in time, so a proper
    time does not exist; dtau would be imaginary.
    """
