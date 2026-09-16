"""SpacecraftMass — dry + propellant accounting.

Invariants maintained at all times:
    dry_mass >= 0
    propellant_mass >= 0
    total_mass = dry_mass + propellant_mass > 0

Consumption is deterministic: `consume(amount)` removes at most
`amount` from propellant_mass, returning the amount actually removed.
If less propellant is available, the tank is simply emptied and the
returned value equals the remaining propellant. It never goes negative
and never uses floating-point trickery.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict
import math

from astra.spacecraft.errors import InvalidMassError
from astra.spacecraft.constants import PROP_TOL


@dataclass
class SpacecraftMass:
    """Mutable dry/propellant accounting for a single spacecraft."""
    dry_mass: float
    propellant_mass: float

    def __post_init__(self):
        if not (math.isfinite(self.dry_mass) and self.dry_mass >= 0.0):
            raise InvalidMassError(
                f"dry_mass must be non-negative finite, got {self.dry_mass!r}"
            )
        if not (math.isfinite(self.propellant_mass) and self.propellant_mass >= 0.0):
            raise InvalidMassError(
                f"propellant_mass must be non-negative finite, "
                f"got {self.propellant_mass!r}"
            )
        if self.dry_mass + self.propellant_mass <= 0.0:
            raise InvalidMassError(
                "total mass must be strictly positive "
                f"(dry={self.dry_mass}, prop={self.propellant_mass})"
            )

    @property
    def total_mass(self) -> float:
        return self.dry_mass + self.propellant_mass

    @property
    def inverse_mass(self) -> float:
        return 1.0 / self.total_mass

    @property
    def is_empty(self) -> bool:
        return self.propellant_mass <= PROP_TOL

    def consume(self, amount: float) -> float:
        """Remove up to `amount` propellant. Returns amount actually removed.

        `amount` must be non-negative finite. Never produces negative
        propellant; never consumes more than is available.
        """
        if not (math.isfinite(amount) and amount >= 0.0):
            raise InvalidMassError(
                f"consume amount must be non-negative finite, got {amount!r}"
            )
        removed = min(amount, self.propellant_mass)
        if removed < 0.0:
            removed = 0.0
        self.propellant_mass -= removed
        if self.propellant_mass < 0.0:
            self.propellant_mass = 0.0
        return removed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dry_mass": float(self.dry_mass),
            "propellant_mass": float(self.propellant_mass),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SpacecraftMass":
        try:
            return cls(dry_mass=float(d["dry_mass"]),
                       propellant_mass=float(d["propellant_mass"]))
        except KeyError as e:
            raise InvalidMassError(f"missing required field: {e.args[0]}")
