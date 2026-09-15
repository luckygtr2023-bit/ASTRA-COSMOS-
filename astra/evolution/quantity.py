"""ASTRA COSMOS — Phase 21: tracked physical quantities.

A ``Quantity`` is an immutable value + unit + provenance (+ optional
uncertainty and owning model id). Every physical number that enters or
leaves the evolution engine travels inside a Quantity, so provenance can
never be detached from data.

Validation: values must be finite floats (NaN/Inf rejected explicitly —
no silent clamping of physically meaningful values); uncertainties must be
finite and >= 0. Units are documented strings ("Msun", "Msun/yr", "Lsun",
"Gyr", "dimensionless", ...); the evolution layer performs no implicit unit
conversion.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from astra.celestial.provenance import DataProvenance
from astra.mathematics.validation import require_finite, require_non_negative

from .errors import EvolutionNumericalError


def require_finite_number(value, name: str) -> float:
    """Reject bools and non-numeric types with the evolution-layer error."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvolutionNumericalError(f"{name} must be a real number, got {type(value).__name__}")
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        raise EvolutionNumericalError(f"{name} must be finite, got {value!r}")
    return v


@dataclass(frozen=True)
class Quantity:
    """A tracked physical quantity: value + unit + provenance."""

    value: float
    unit: str
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA
    uncertainty: Optional[float] = None
    model_id: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "value", require_finite_number(self.value, "Quantity.value"))
        if not isinstance(self.unit, str) or not self.unit:
            raise EvolutionNumericalError("Quantity.unit must be a non-empty string")
        if not isinstance(self.provenance, DataProvenance):
            raise EvolutionNumericalError("Quantity.provenance must be a DataProvenance member")
        if self.uncertainty is not None:
            u = require_finite_number(self.uncertainty, "Quantity.uncertainty")
            require_non_negative(u, "Quantity.uncertainty")
        if self.model_id is not None and not isinstance(self.model_id, str):
            raise EvolutionNumericalError("Quantity.model_id must be a string or None")
        if self.note is not None and not isinstance(self.note, str):
            raise EvolutionNumericalError("Quantity.note must be a string or None")

    def with_value(self, value: float) -> "Quantity":
        """Same unit/provenance/uncertainty, new value (engine bookkeeping)."""
        return Quantity(
            value=value,
            unit=self.unit,
            provenance=self.provenance,
            uncertainty=self.uncertainty,
            model_id=self.model_id,
            note=self.note,
        )

    def to_dict(self):
        return {
            "value": float(self.value),
            "unit": self.unit,
            "provenance": self.provenance.value,
            "uncertainty": None if self.uncertainty is None else float(self.uncertainty),
            "model_id": self.model_id,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d) -> "Quantity":
        return cls(
            value=d["value"],
            unit=d["unit"],
            provenance=DataProvenance(d["provenance"]),
            uncertainty=d.get("uncertainty"),
            model_id=d.get("model_id"),
            note=d.get("note"),
        )


__all__ = ["Quantity", "require_finite_number"]
