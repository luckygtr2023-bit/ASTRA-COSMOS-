"""ASTRA COSMOS - Four-Vector mathematics.

Contract: Minkowski vectors on the eta = diag(-1, 1, 1, 1) signature.

Conventions
-----------
- Components are (t, x, y, z) where the time component t carries the same
  units as the spatial ones (i.e. t is normally ct, metres of light travel).
- Invariant square: A^2 = -(t^2) + x^2 + y^2 + z^2  (signature (-,+,+,+)).
- Deterministic pure value type: immutable by convention, ``__slots__``,
  no RNG, no wall-clock.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Tuple

from astra.relativity.core import SPEED_OF_LIGHT
from astra.relativity.exceptions import SpacelikeIntervalError


class SpacetimeIntervalType(Enum):
    """Classification of a 4-vector (or interval) by its invariant square."""

    TIMELIKE = "TIMELIKE"
    SPACELIKE = "SPACELIKE"
    NULL = "NULL"


class FourVector:
    """A generalized 4-vector [A^0, A^1, A^2, A^3] in flat spacetime.

    Signature used throughout ASTRA: (-1, 1, 1, 1).
    """

    __slots__ = ["t", "x", "y", "z"]

    def __init__(self, t: float, x: float, y: float, z: float):
        self.t = float(t)  # Time component (often ct, metres of light travel)
        self.x = float(x)  # Spatial X
        self.y = float(y)  # Spatial Y
        self.z = float(z)  # Spatial Z

    def invariant_sq(self) -> float:
        """Return the invariant square -(t)^2 + x^2 + y^2 + z^2."""
        return -(self.t ** 2) + (self.x ** 2) + (self.y ** 2) + (self.z ** 2)

    def interval_type(self, tolerance: float = 1e-9) -> SpacetimeIntervalType:
        """Classify the interval as TIMELIKE, SPACELIKE or NULL.

        ``tolerance`` is in the same units as the components (m^2 for the
        invariant square).
        """
        ds2 = self.invariant_sq()
        if ds2 < -tolerance:
            return SpacetimeIntervalType.TIMELIKE
        elif ds2 > tolerance:
            return SpacetimeIntervalType.SPACELIKE
        return SpacetimeIntervalType.NULL

    def components(self) -> Tuple[float, float, float, float]:
        """Return (t, x, y, z) as a plain tuple (persistence-friendly)."""
        return (self.t, self.x, self.y, self.z)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FourVector):
            return NotImplemented
        return (
            self.t == other.t
            and self.x == other.x
            and self.y == other.y
            and self.z == other.z
        )

    def __hash__(self) -> int:
        return hash((self.t, self.x, self.y, self.z))

    def __repr__(self) -> str:
        return f"FourVector(t={self.t!r}, x={self.x!r}, y={self.y!r}, z={self.z!r})"


class SpacetimeEvent(FourVector):
    """An event in spacetime; ``t`` is the coordinate time multiplied by c.

    Build one from SI quantities with :meth:`from_coordinates`.
    """

    __slots__ = []

    @classmethod
    def from_coordinates(cls, time_sec: float, x: float, y: float, z: float) -> "SpacetimeEvent":
        """Create an event from SI coordinates: time in s, position in m."""
        return cls(time_sec * SPEED_OF_LIGHT, x, y, z)

    def proper_time_to(self, other: FourVector) -> float:
        """Proper time dtau (s) along the straight worldline between events.

        For timelike separation, ds^2 = -c^2 dtau^2, hence
        dtau = sqrt(-ds^2) / c. Returns 0.0 for null separation and raises
        :class:`SpacelikeIntervalError` for spacelike separation (no
        inertial frame orders such events in time).
        """
        delta = FourVector(
            other.t - self.t, other.x - self.x, other.y - self.y, other.z - self.z
        )
        ds2 = delta.invariant_sq()
        if delta.interval_type() == SpacetimeIntervalType.SPACELIKE:
            raise SpacelikeIntervalError(
                "Cannot calculate proper time for spacelike separated events "
                f"(ds^2 = {ds2!r} m^2 > 0)."
            )
        # ds^2 = -c^2 dtau^2  =>  dtau = sqrt(-ds^2) / c  (0 for null).
        return math.sqrt(-ds2) / SPEED_OF_LIGHT

    def __repr__(self) -> str:
        return f"SpacetimeEvent(t={self.t!r}, x={self.x!r}, y={self.y!r}, z={self.z!r})"
