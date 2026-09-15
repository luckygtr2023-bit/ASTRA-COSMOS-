"""ASTRA Evolution — provenance and quantitative typing.

This module defines the provenance taxonomy required by Phase 21 and a
``Quantity`` value-object that carries value, unit, provenance, uncertainty
and model identity together.  It is intentionally independent of
``astra.celestial.provenance`` — that module models catalog observations
(``REAL_DATA`` / ``DERIVED_DATA`` / ``SIMULATED_DATA`` /
``THEORETICAL_MODEL`` / ``SPECULATIVE_MODEL``) while evolution distinguishes
``THEORETICAL`` / ``HYPOTHETICAL`` / ``SPECULATIVE`` as separate far-future
regimes per §2.39.  A conversion helper is provided for interop.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .errors import EvolutionNumericalError


class Provenance(str, Enum):
    """Scientific-provenance classification for every evolutionary output.

    - REAL_DATA: direct observation / catalog value.
    - DERIVED_DATA: deterministic derivation from REAL_DATA.
    - SIMULATED_DATA: output of a simulation with real input boundaries.
    - THEORETICAL: prediction of a well-established theoretical model.
    - HYPOTHETICAL: prediction of a plausible but unconfirmed model.
    - SPECULATIVE: far-future extrapolation beyond validated regimes.
    """

    REAL_DATA = "REAL_DATA"
    DERIVED_DATA = "DERIVED_DATA"
    SIMULATED_DATA = "SIMULATED_DATA"
    THEORETICAL = "THEORETICAL"
    HYPOTHETICAL = "HYPOTHETICAL"
    SPECULATIVE = "SPECULATIVE"


def _finite(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EvolutionNumericalError(f"{name} must be numeric, got {v!r}")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise EvolutionNumericalError(f"{name} must be finite, got {fv!r}")
    return fv


def _map_to_data_provenance(p: Provenance):
    """Best-effort mapping to :class:`astra.celestial.provenance.DataProvenance`.

    Used only for interop with celestial property blocks; the mapping is
    documented and lossy (HYPOTHETICAL → SPECULATIVE_MODEL).
    """
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
    """A tracked physical quantity: value + unit + provenance + optional uncertainty.

    Attributes:
        value: numeric value in the declared unit.
        unit: free-form unit label (e.g. ``"Msun"``, ``"Mpc"``, ``"km/s"``).
        provenance: classification per :class:`Provenance`.
        uncertainty: 1-sigma uncertainty in the same unit, if known.
        model_id: identifier of the model that produced this quantity.
        note: optional human-readable note (e.g. assumption reference).
    """

    value: float
    unit: str
    provenance: Provenance
    uncertainty: Optional[float] = None
    model_id: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self):
        _finite("value", self.value)
        if not isinstance(self.unit, str) or not self.unit:
            raise EvolutionNumericalError("unit must be a non-empty string")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance member")
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
