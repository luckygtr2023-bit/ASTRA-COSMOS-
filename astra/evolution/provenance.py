"""ASTRA COSMOS — Phase 21: provenance for the Long-Term Cosmic Evolution
Engine.

This is a thin re-export of the repository's canonical provenance taxonomy
defined in ``astra.celestial.provenance``. It defines NO new provenance
enum: there is exactly one provenance type in ASTRA and this package uses
it (the same convention as ``astra.destruction.provenance``).

Provenance policy for Phase 21
------------------------------
- Every ``Quantity``, ``EvolutionState``, ``EvolutionEvent``, scenario, and
  model carries a ``DataProvenance`` tag.
- Phase 21 NEVER assigns REAL_DATA or DERIVED_DATA to its own outputs: all
  engine-produced quantities are SIMULATED_DATA or THEORETICAL_MODEL /
  SPECULATIVE_MODEL depending on the registered model's classification.
  REAL_DATA can only enter by a caller supplying it in an initial state.
- Future / far-future states are SIMULATED projections, never observations.

Projection depth
----------------
``DataProvenance`` says where a value came from. It does not express HOW FAR
beyond the validated present a projected state sits. That role belongs to
``ProjectionClass`` below (spec 2.26 / 2.39): every scenario declares its
projection class and the engine stamps it onto the states produced under
that scenario. ``THEORETICAL``, ``HYPOTHETICAL`` and ``SPECULATIVE`` far-future
states are therefore always machine-readably distinguishable from
present-epoch states, and a speculative scenario can never silently pass as
a confirmed prediction.
"""
from astra.celestial.provenance import (  # noqa: F401
    DEFAULT_CONFIDENCE,
    DataProvenance,
    ProvenanceTag,
    ScientificConfidence,
)
from enum import Enum

__all__ = [
    "DataProvenance",
    "ProvenanceTag",
    "ScientificConfidence",
    "DEFAULT_CONFIDENCE",
    "ProjectionClass",
]


class ProjectionClass(str, Enum):
    """Epistemic depth of a projected (future) cosmic state.

    NONE              : present-epoch state (no future projection claimed).
    MODEL_PROJECTED   : projection of established/derived models inside
                        their declared validity range ("THEORETICAL").
    HYPOTHETICAL      : projection that depends on an assumed scenario
                        parameterization not fixed by validated physics.
    SPECULATIVE       : projection beyond every registered model's validity;
                        illustrative only, never a prediction.

    The engine refuses to run a MODEL_PROJECTED scenario past a model's
    declared validity horizon (EvolutionLimitationError OUTSIDE_VALID_RANGE)
    and instructs the caller to re-classify the scenario as HYPOTHETICAL or
    SPECULATIVE and register a correspondingly classified model.
    """

    NONE = "NONE"
    MODEL_PROJECTED = "MODEL_PROJECTED"
    HYPOTHETICAL = "HYPOTHETICAL"
    SPECULATIVE = "SPECULATIVE"


def projection_class_for(provenance: DataProvenance) -> ProjectionClass:
    """Deterministic mapping from data provenance to projection depth.

    SIMULATED_DATA      -> MODEL_PROJECTED (engine-generated projection)
    THEORETICAL_MODEL   -> MODEL_PROJECTED
    SPECULATIVE_MODEL   -> SPECULATIVE
    REAL/DERIVED        -> NONE (present-epoch, observationally grounded)
    """
    if provenance is DataProvenance.SPECULATIVE_MODEL:
        return ProjectionClass.SPECULATIVE
    if provenance in (DataProvenance.SIMULATED_DATA, DataProvenance.THEORETICAL_MODEL):
        return ProjectionClass.MODEL_PROJECTED
    return ProjectionClass.NONE
