"""Provenance for the Destruction & Impact package.

This is a thin re-export of the repository's canonical provenance taxonomy
defined in ``astra.celestial.provenance``. It defines NO new enum: there is
exactly one provenance type in ASTRA and this package uses it. Impact

outputs are always tagged ``DataProvenance.SIMULATED_DATA``.
"""
from astra.celestial.provenance import (  # noqa: F401
    DEFAULT_CONFIDENCE,
    DataProvenance,
    ProvenanceTag,
    ScientificConfidence,
)

__all__ = [
    "DataProvenance",
    "ProvenanceTag",
    "ScientificConfidence",
    "DEFAULT_CONFIDENCE",
]
