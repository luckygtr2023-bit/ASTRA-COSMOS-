"""Provenance + uncertainty tracking.

Every physical quantity in the galactic engine carries:
    - a value
    - a provenance tag
    - an uncertainty (may be unknown)
    - a source reference (may be a catalog, a model name, or a simulation run)

This module is deliberately independent of astra.celestial.provenance (which
has 5 enum members) — here we expose the 6-value provenance required by
Phase 20, including HYPOTHETICAL as distinct from THEORETICAL/SPECULATIVE.
Bridging to celestial provenance is via to_celestial_provenance().
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .errors import GalacticNumericalError, GalacticValidationError


class Provenance(str, Enum):
    REAL_DATA = "REAL_DATA"
    DERIVED_DATA = "DERIVED_DATA"
    SIMULATED_DATA = "SIMULATED_DATA"
    THEORETICAL = "THEORETICAL"
    HYPOTHETICAL = "HYPOTHETICAL"
    SPECULATIVE = "SPECULATIVE"


def _finite(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise GalacticNumericalError(f"{name} must be numeric")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise GalacticNumericalError(f"{name} must be finite, got {fv}")
    return fv


def to_celestial_provenance(p: Provenance):
    """Bridge to astra.celestial.provenance.DataProvenance where possible."""
    try:
        from astra.celestial.provenance import DataProvenance
        mapping = {
            Provenance.REAL_DATA: DataProvenance.REAL_DATA,
            Provenance.DERIVED_DATA: DataProvenance.DERIVED_DATA,
            Provenance.SIMULATED_DATA: DataProvenance.SIMULATED_DATA,
            Provenance.THEORETICAL: DataProvenance.THEORETICAL_MODEL,
            Provenance.HYPOTHETICAL: DataProvenance.SPECULATIVE_MODEL,
            Provenance.SPECULATIVE: DataProvenance.SPECULATIVE_MODEL,
        }
        return mapping.get(p, DataProvenance.SIMULATED_DATA)
    except Exception:
        return p


@dataclass(frozen=True)
class ObservedValue:
    """A value observed in real data. Uncertainty is mandatory (may be 0 for exact ints)."""
    value: float
    uncertainty: float
    unit: str
    source: str
    provenance: Provenance = Provenance.REAL_DATA
    note: Optional[str] = None

    def __post_init__(self):
        _finite("ObservedValue.value", self.value)
        _finite("ObservedValue.uncertainty", self.uncertainty)
        if self.uncertainty < 0.0:
            raise GalacticNumericalError("uncertainty must be >= 0")
        if not isinstance(self.unit, str) or not self.unit:
            raise GalacticNumericalError("unit must be non-empty string")
        if not isinstance(self.source, str) or not self.source:
            raise GalacticNumericalError("source must be non-empty string")
        if self.provenance != Provenance.REAL_DATA:
            # allow but warn via note — observed must be REAL_DATA
            # enforce strictly:
            raise GalacticValidationError(f"ObservedValue provenance must be REAL_DATA, got {self.provenance}")  # type: ignore

    # for import compatibility
    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "uncertainty": self.uncertainty,
            "unit": self.unit,
            "source": self.source,
            "provenance": self.provenance.value,
            "note": self.note,
        }





@dataclass(frozen=True)
class DerivedValue:
    """A value computed from other ASTRA state. Inputs must be traceable."""
    value: float
    unit: str
    method: str
    inputs: tuple = ()  # tuple of (name, value_or_provenance) tuples
    provenance: Provenance = Provenance.DERIVED_DATA

    def __post_init__(self):
        _finite("DerivedValue.value", self.value)
        if not isinstance(self.unit, str) or not self.unit:
            raise GalacticNumericalError("unit must be non-empty string")
        if not isinstance(self.method, str) or not self.method:
            raise GalacticNumericalError("method must be non-empty string")
        if self.provenance != Provenance.DERIVED_DATA:
            raise GalacticValidationError(f"DerivedValue provenance must be DERIVED_DATA, got {self.provenance}")


@dataclass(frozen=True)
class SimulatedValue:
    """A value produced by ASTRA's own simulation."""
    value: float
    unit: str
    model: str
    seed: Optional[int] = None
    provenance: Provenance = Provenance.SIMULATED_DATA

    def __post_init__(self):
        _finite("SimulatedValue.value", self.value)
        if not isinstance(self.unit, str) or not self.unit:
            raise GalacticNumericalError("unit must be non-empty string")
        if not isinstance(self.model, str) or not self.model:
            raise GalacticNumericalError("model must be non-empty string")
        if self.provenance != Provenance.SIMULATED_DATA:
            raise GalacticValidationError(f"SimulatedValue provenance must be SIMULATED_DATA, got {self.provenance}")


@dataclass(frozen=True)
class UnknownValue:
    """Explicit unknown. Never a fabricated zero."""
    unit: str
    reason: str
    provenance: Provenance = Provenance.SIMULATED_DATA  # the *absence* is simulated bookkeeping

    def __post_init__(self):
        if not isinstance(self.unit, str) or not self.unit:
            raise GalacticNumericalError("unit must be non-empty string")
        if not isinstance(self.reason, str) or not self.reason:
            raise GalacticNumericalError("reason must be non-empty string")
        # provenance for unknown is bookkeeping — allow SIMULATED_DATA only
        if self.provenance not in (Provenance.SIMULATED_DATA, Provenance.THEORETICAL):
            raise GalacticValidationError(f"UnknownValue provenance must be SIMULATED_DATA/ THEORETICAL, got {self.provenance}")
