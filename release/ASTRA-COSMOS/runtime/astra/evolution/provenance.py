"""ASTRA Evolution — provenance and quantitative typing (Phase 22 migrated).

This module now re-exports the CANONICAL :class:`astra.scientific.classification.Classification`
as ``Provenance`` for backward compatibility.  The single source of truth is
``astra.scientific``; this file exists only as a thin shim so that existing
``from astra.evolution.provenance import Provenance`` imports continue to work
without creating a third parallel enum.

Canonical taxonomy (six categories, ordered by epistemic strength):
    REAL_DATA < DERIVED_DATA < SIMULATED_DATA < THEORETICAL < HYPOTHETICAL < SPECULATIVE
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from .errors import EvolutionNumericalError

# Canonical import — single source of truth
from astra.scientific.classification import Classification as Provenance
from astra.scientific.classification import Classification

# Re-export for callers that expect `astra.evolution.provenance.Classification`
__all__ = ["Provenance", "Classification", "Quantity"]


def _finite(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EvolutionNumericalError(f"{name} must be numeric, got {v!r}")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise EvolutionNumericalError(f"{name} must be finite, got {fv!r}")
    return fv


def _map_to_data_provenance(p: Provenance):  # type: ignore[valid-type]
    """Best-effort mapping to :class:`astra.celestial.provenance.DataProvenance`."""
    try:
        from astra.celestial.provenance import DataProvenance
    except ImportError:
        return None
    mapping = {
        Provenance.REAL_DATA: DataProvenance.REAL_DATA,
        Provenance.DERIVED_DATA: DataProvenance.DERIVED_DATA,
        Provenance.SIMULATED_DATA: DataProvenance.SIMULATED_DATA,
        Provenance.THEORETICAL: DataProvenance.THEORETICAL_MODEL,
        Provenance.HYPOTHETICAL: DataProvenance.SPECULATIVE_MODEL,
        Provenance.SPECULATIVE: DataProvenance.SPECULATIVE_MODEL,
    }
    return mapping.get(p)


@dataclass(frozen=True)
class Quantity:
    """A tracked physical quantity: value + unit + provenance + optional uncertainty."""

    value: float
    unit: str
    provenance: Provenance  # type: ignore[valid-type]
    uncertainty: Optional[float] = None
    model_id: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self):
        _finite("value", self.value)
        if not isinstance(self.unit, str) or not self.unit:
            raise EvolutionNumericalError("unit must be a non-empty string")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance/Classification member")
        if self.uncertainty is not None:
            _finite("uncertainty", self.uncertainty)
            if self.uncertainty < 0.0:
                raise EvolutionNumericalError("uncertainty must be >= 0")
        if self.model_id is not None and not isinstance(self.model_id, str):
            raise TypeError("model_id must be a string or None")
        if self.note is not None and not isinstance(self.note, str):
            raise TypeError("note must be a string or None")

    def to_data_provenance(self):
        """Map to the celestial :class:`DataProvenance` where possible."""
        return _map_to_data_provenance(self.provenance)
