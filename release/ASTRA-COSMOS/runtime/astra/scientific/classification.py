"""ASTRA Scientific — canonical classification primitives.

This is the SINGLE source of truth for epistemic classification in ASTRA.
All other packages (including ``astra.evolution`` and any future
``astra.galactic``) must import ``Classification`` from here, not declare
their own Provenance/Classification enums.

Ordering by epistemic strength (0 = strongest, 5 = weakest):

    REAL_DATA (0) < DERIVED_DATA (1) < SIMULATED_DATA (2)
    < THEORETICAL (3) < HYPOTHETICAL (4) < SPECULATIVE (5)

A transformation may never silently produce a stronger classification than
its inputs except where an explicit real-data ingestion boundary is crossed.
``classify_combination`` enforces this by returning the *weakest* input.

Backward compatibility: ``astra.evolution.provenance.Provenance`` is now an
alias to this enum (see ``astra/evolution/provenance.py``).  The legacy
``DataProvenance`` in ``astra.celestial.provenance`` maps to this taxonomy
via ``astra.scientific.migration``.
"""

from __future__ import annotations

from enum import Enum
from typing import Tuple

from .errors import ScientificValidationError


class Classification(str, Enum):
    """Canonical scientific classification (six categories, §2.3)."""

    REAL_DATA = "REAL_DATA"
    DERIVED_DATA = "DERIVED_DATA"
    SIMULATED_DATA = "SIMULATED_DATA"
    THEORETICAL = "THEORETICAL"
    HYPOTHETICAL = "HYPOTHETICAL"
    SPECULATIVE = "SPECULATIVE"


_ORDER = {
    Classification.REAL_DATA: 0,
    Classification.DERIVED_DATA: 1,
    Classification.SIMULATED_DATA: 2,
    Classification.THEORETICAL: 3,
    Classification.HYPOTHETICAL: 4,
    Classification.SPECULATIVE: 5,
}


class ClassificationOrder:
    """Epistemic ordering helpers (static, no state)."""

    @staticmethod
    def strength(c: Classification) -> int:
        """Lower value = stronger epistemic status."""
        try:
            return _ORDER[c]
        except KeyError:
            raise ScientificValidationError(f"unknown classification {c!r}")

    @staticmethod
    def weakest(a: Classification, b: Classification) -> Classification:
        """Return the weaker (larger _ORDER) of two."""
        return a if _ORDER[a] >= _ORDER[b] else b

    @staticmethod
    def strongest(a: Classification, b: Classification) -> Classification:
        """Return the stronger (smaller _ORDER) of two."""
        return a if _ORDER[a] <= _ORDER[b] else b

    @staticmethod
    def is_stronger(a: Classification, b: Classification) -> bool:
        """True if ``a`` is stronger than ``b``."""
        return _ORDER[a] < _ORDER[b]

    @staticmethod
    def is_weaker(a: Classification, b: Classification) -> bool:
        return _ORDER[a] > _ORDER[b]


def classify_combination(inputs: Tuple[Classification, ...]) -> Classification:
    """Return the weakest classification across all inputs.

    A derivation may not silently strengthen epistemic status.
    Example: ``{REAL_DATA, SIMULATED_DATA} → SIMULATED_DATA``;
             ``{THEORETICAL, REAL_DATA} → THEORETICAL``.

    Raises:
        ScientificValidationError: on empty inputs or non-Classification members.
    """
    if not inputs:
        raise ScientificValidationError("classify_combination requires at least one input")
    # Validate all members
    for c in inputs:
        if not isinstance(c, Classification):
            raise ScientificValidationError(f"classify_combination expects Classification members, got {c!r}")
    weakest = inputs[0]
    for c in inputs[1:]:
        weakest = ClassificationOrder.weakest(weakest, c)
    return weakest


# Backwards-compat alias used by older code that imported Provenance from evolution.
# We keep it here so `from astra.scientific.classification import Provenance` also works.
Provenance = Classification
