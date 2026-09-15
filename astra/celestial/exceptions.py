"""ASTRA Celestial - exceptions.

Contract: every Celestial-layer error derives from
``astra.core.exceptions.AstraError``. Data-validation errors additionally
derive from ``ValueError``.

Design note (per phase audit): ``IncompletePhysicalDataError`` is distinct
from ``InvalidPropertyError``. UNKNOWN data (``None``) is a legitimate,
honored state - requesting it for a physics pipeline fails with the
explicit "incomplete" error; PRESENT but impossible data (negative radius,
NaN mass) fails with the "invalid" error. Zero is never a placeholder.
"""

from astra.core.exceptions import AstraError


class CelestialError(AstraError):
    """Base Celestial-layer error."""


class InvalidPropertyError(CelestialError, ValueError):
    """Raised when a physical property is present but impossible
    (negative mass/radius/temperature, NaN/Inf values)."""


class IncompletePhysicalDataError(CelestialError):
    """Raised when a physics pipeline requests a property that is
    explicitly UNKNOWN (None). ASTRA never substitutes 0.0 for unknown
    data and never fabricates a value on request."""


class CyclicHierarchyError(CelestialError):
    """Raised when a hierarchy edge would create a cycle (e.g. A orbiting
    B while B orbits A). Parent-child structure must remain a DAG."""


class DuplicateNodeError(CelestialError, ValueError):
    """Raised when the same celestial identity is attached twice to a
    hierarchy."""
