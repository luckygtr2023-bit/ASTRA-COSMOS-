"""ASTRA Scientific — result envelope (§2.28).

The envelope is opt-in.  Performance-critical kernels use EnvelopeRef
(a lightweight reference) instead of the full ResultEnvelope.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

from .classification import Classification
from .provenance import ProvenanceRef
from .uncertainty import Uncertainty
from .warnings import ScientificWarning


@dataclass(frozen=True)
class EnvelopeRef:
    """Lightweight reference to a result envelope (for hot loops).

    Hot kernels can produce an ID and defer full metadata construction.
    """

    envelope_id: str

    def __post_init__(self):
        if not isinstance(self.envelope_id, str) or not self.envelope_id:
            raise ValueError("envelope_id must be a non-empty string")


@dataclass(frozen=True)
class ResultEnvelope:
    """Full scientific result envelope (§2.28).

    Value/state + classification + provenance + uncertainty + assumptions
    + validity + model + warnings + reproducibility metadata.
    """

    envelope_id: str
    value: Any
    classification: Classification
    provenance: Optional[ProvenanceRef] = None
    uncertainty: Optional[Uncertainty] = None
    assumption_ids: Tuple[str, ...] = ()
    model_id: Optional[str] = None
    valid: Optional[bool] = None
    warnings: Tuple[ScientificWarning, ...] = ()
    reproducibility: Dict[str, object] = field(default_factory=dict)
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.envelope_id, str) or not self.envelope_id:
            raise ValueError("envelope_id must be a non-empty string")
        if not isinstance(self.classification, Classification):
            raise TypeError("classification must be a Classification")
        if self.provenance is not None and not isinstance(self.provenance, ProvenanceRef):
            raise TypeError("provenance must be a ProvenanceRef or None")
        if self.uncertainty is not None:
            from .uncertainty import Uncertainty as U
            if not isinstance(self.uncertainty, U):
                raise TypeError("uncertainty must be an Uncertainty or None")
        object.__setattr__(self, "assumption_ids", tuple(self.assumption_ids))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "reproducibility", dict(self.reproducibility))
        object.__setattr__(self, "metadata", dict(self.metadata))
        for aid in self.assumption_ids:
            if not isinstance(aid, str) or not aid:
                raise ValueError("assumption_ids must be non-empty strings")
        for w in self.warnings:
            if not isinstance(w, ScientificWarning):
                raise TypeError("warnings must be ScientificWarning instances")
        if self.model_id is not None and not isinstance(self.model_id, str):
            raise TypeError("model_id must be string or None")
        if self.valid is not None and not isinstance(self.valid, bool):
            raise TypeError("valid must be bool or None")

    def to_ref(self) -> EnvelopeRef:
        return EnvelopeRef(self.envelope_id)

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def is_speculative(self) -> bool:
        return self.classification in (Classification.HYPOTHETICAL, Classification.SPECULATIVE)

    def to_dict(self) -> Dict[str, object]:
        return {
            "envelope_id": self.envelope_id,
            "classification": self.classification.value,
            "provenance": self.provenance.node_id if self.provenance else None,
            "model_id": self.model_id,
            "valid": self.valid,
            "assumption_ids": list(self.assumption_ids),
            "warnings": [w.to_dict() for w in self.warnings],
            "reproducibility": dict(self.reproducibility),
            "metadata": dict(self.metadata),
        }
