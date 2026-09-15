"""ASTRA Black-Hole - immutable state and parameter validation.

Contract: strictly positive masses, dimensionless spin |a*| <= 1 (naked
singularities rejected), SI units, and an immutable state object whose only
serialized payload is the canonical parameter pair (mass, spin). Every
derived boundary (r_s, r_+, ISCO, ...) is recomputed on demand or on
deserialization, preventing schema drift and corrupted saves.

Integration:
    - G is imported from ``astra.physics.constants`` (single source of truth).
    - c (SPEED_OF_LIGHT) is imported from ``astra.relativity.core``.

NOTE (Agent LM): the handoff claimed inheritance from a non-existent
``astra.core.persistence.Serializable``; the serializable surface here is
``to_dict`` / ``from_dict`` over plain Python primitives, matching the
``astra.core.persistence`` snapshot philosophy. Immutability is enforced by
a frozen dataclass (the repository has no PermissionClient; this layer is a
stateless calculator and mutates nothing).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

from astra.physics.constants import GRAVITATIONAL_CONSTANT
from astra.relativity.core import SPEED_OF_LIGHT
from astra.blackhole.exceptions import (
    InvalidBlackHoleMassError,
    InvalidSpinParameterError,
)
from astra.blackhole.models import BlackHoleModel

# Dimensionless spin is rejected beyond 1 + this slack... strictly: any
# |a*| > 1.0 raises; the tolerance exists only to keep exact-unity floats
# stable, never to admit over-spin.
MAX_SPIN: float = 1.0


def validate_mass_kg(mass_kg) -> float:
    """Validate a black-hole mass: real, finite, strictly positive (kg)."""
    if isinstance(mass_kg, bool) or not isinstance(mass_kg, (int, float)):
        raise InvalidBlackHoleMassError(f"Mass must be a real number, got {type(mass_kg).__name__}")
    m = float(mass_kg)
    if math.isnan(m) or math.isinf(m) or m <= 0.0:
        raise InvalidBlackHoleMassError(f"Mass must be finite and > 0, got {mass_kg!r}")
    return m


def validate_spin_param(spin_param) -> float:
    """Validate the dimensionless Kerr spin: real and |a*| <= 1.

    |a*| = 1 (extremal Kerr) is admitted; |a*| > 1 (naked singularity) is
    rejected with :class:`InvalidSpinParameterError`.
    """
    if isinstance(spin_param, bool) or not isinstance(spin_param, (int, float)):
        raise InvalidSpinParameterError(
            f"Spin must be a real number, got {type(spin_param).__name__}"
        )
    a = float(spin_param)
    if math.isnan(a) or math.isinf(a):
        raise InvalidSpinParameterError(f"Spin cannot be NaN or Infinite, got {spin_param!r}")
    if abs(a) > MAX_SPIN:
        raise InvalidSpinParameterError(
            f"Naked singularity rejected: |a*| = {abs(a)!r} > 1."
        )
    return a


@dataclass(frozen=True)
class BlackHoleState:
    """Immutable central-object specification.

    Attributes:
        mass_kg: mass of the compact object (kg), strictly positive.
        spin_param: dimensionless Kerr spin a* = cJ/(GM^2) in [-1, 1].
    """

    mass_kg: float
    spin_param: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "mass_kg", validate_mass_kg(self.mass_kg))
        object.__setattr__(self, "spin_param", validate_spin_param(self.spin_param))

    @property
    def model(self) -> BlackHoleModel:
        """SCHWARZSCHILD for a* = 0, KERR otherwise."""
        if self.spin_param == 0.0:
            return BlackHoleModel.SCHWARZSCHILD
        return BlackHoleModel.KERR

    @property
    def gravitational_radius(self) -> float:
        """Length unit r_g = G M / c^2 (m); half the Schwarzschild radius."""
        return (GRAVITATIONAL_CONSTANT * self.mass_kg) / (SPEED_OF_LIGHT * SPEED_OF_LIGHT)

    @property
    def spin_length(self) -> float:
        """Kerr spin in length units a = a* * r_g (m)."""
        return self.spin_param * self.gravitational_radius

    def to_dict(self) -> Dict[str, float]:
        """Canonical serialization: ONLY the (mass, spin) pair."""
        return {"mass_kg": self.mass_kg, "spin_param": self.spin_param}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "BlackHoleState":
        """Reconstruct from canonical primitives, re-validating everything.

        No derived quantities are ever deserialized; they are recomputed
        from the validated canonical pair.
        """
        return cls(mass_kg=data["mass_kg"], spin_param=data.get("spin_param", 0.0))
