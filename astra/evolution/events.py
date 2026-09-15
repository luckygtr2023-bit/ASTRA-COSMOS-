"""ASTRA COSMOS — Phase 21: evolutionary events.

``EvolutionEvent`` is the immutable record of one evolutionary event
(stellar transition, stellar death, merger, star-formation transition,
population/AGN/morphology transition, cosmic-structure transition, epoch
transition). Every event carries:

    event_id             deterministic engine-assigned id (sequential)
    kind                 machine-readable EvolutionEventKind
    cosmic_time_gyr      when the event occurs in cosmic time
    source_object_ids    progenitor objects
    resulting_object_ids objects created/replaced by the event
    physical_cause       stated physical cause (from the model or caller)
    model_id             which registered model produced it
    provenance           DataProvenance (SIMULATED_DATA / THEORETICAL_MODEL
                         / SPECULATIVE_MODEL for projections; never REAL_DATA)
    causal_parent_event_id  the event this one follows causally — chains are
                         validated by the ledger (non-decreasing cosmic time
                         along a causal chain; known parents only)

Events integrate with the existing ASTRA event architecture through
``astra.evolution.adapters.CoreEventPublisherAdapter`` (core EventBus);
the ledger itself never publishes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from astra.celestial.provenance import DataProvenance

from .errors import EvolutionValidationError
from .quantity import require_finite_number


class EvolutionEventKind(str, Enum):
    STELLAR_TRANSITION = "STELLAR_TRANSITION"
    STELLAR_DEATH = "STELLAR_DEATH"
    GALAXY_MERGER = "GALAXY_MERGER"
    BLACK_HOLE_MERGER = "BLACK_HOLE_MERGER"
    CLUSTER_MERGER = "CLUSTER_MERGER"
    STAR_FORMATION_TRANSITION = "STAR_FORMATION_TRANSITION"
    POPULATION_TRANSITION = "POPULATION_TRANSITION"
    AGN_TRANSITION = "AGN_TRANSITION"
    MORPHOLOGY_TRANSITION = "MORPHOLOGY_TRANSITION"
    COSMIC_STRUCTURE_TRANSITION = "COSMIC_STRUCTURE_TRANSITION"
    EPOCH_TRANSITION = "EPOCH_TRANSITION"
    CALLER_SCHEDULED = "CALLER_SCHEDULED"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class EvolutionEvent:
    """Immutable record of a single evolutionary event."""

    event_id: str
    kind: EvolutionEventKind
    cosmic_time_gyr: float
    source_object_ids: Tuple[str, ...]
    resulting_object_ids: Tuple[str, ...]
    physical_cause: str
    model_id: str
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA
    causal_parent_event_id: Optional[str] = None
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.event_id, str) or not self.event_id:
            raise EvolutionValidationError("event_id must be a non-empty string")
        if not isinstance(self.kind, EvolutionEventKind):
            raise EvolutionValidationError("kind must be an EvolutionEventKind member")
        object.__setattr__(
            self, "cosmic_time_gyr", require_finite_number(self.cosmic_time_gyr, "event cosmic_time_gyr")
        )
        object.__setattr__(self, "source_object_ids", tuple(self.source_object_ids))
        object.__setattr__(self, "resulting_object_ids", tuple(self.resulting_object_ids))
        if not isinstance(self.physical_cause, str) or not self.physical_cause:
            raise EvolutionValidationError("physical_cause must be a non-empty string")
        if not isinstance(self.model_id, str) or not self.model_id:
            raise EvolutionValidationError("model_id must be a non-empty string")
        if not isinstance(self.provenance, DataProvenance):
            raise EvolutionValidationError("provenance must be a DataProvenance member")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> Dict[str, object]:
        from .persistence import event_to_dict

        return event_to_dict(self)

    @classmethod
    def from_dict(cls, d) -> "EvolutionEvent":
        from .persistence import event_from_dict

        return event_from_dict(d)


__all__ = ["EvolutionEvent", "EvolutionEventKind"]
