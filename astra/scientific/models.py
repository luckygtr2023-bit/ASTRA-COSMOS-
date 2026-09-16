"""ASTRA Scientific — model descriptors + canonical registry (§2.7).

If Phase 20 or 21 already declared a ModelRegistry, this module generalizes it.
Callers that previously used ``astra.evolution.models.ModelRegistry`` can now
use this canonical registry (or the evolution registry can be made an alias
to this one).  For backward compatibility, ``astra.evolution.models`` remains
importable but its models are convertible via ``astra.scientific.migration``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .assumptions import Assumption
from .classification import Classification
from .errors import ScientificValidationError


@dataclass(frozen=True)
class ValidityDomain:
    """Multi-dimensional validity domain (§2.8).

    Each dimension maps to a closed interval [lo, hi].  Example:
        {"v_kms": (0.0, 300000.0), "M_msun": (0.1, 100.0)}
    """

    dimensions: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self):
        if not isinstance(self.notes, str):
            raise TypeError("notes must be a string")
        norm = {}
        for dim, bounds in self.dimensions.items():
            if not isinstance(dim, str) or not dim:
                raise ScientificValidationError("dimension keys must be non-empty strings")
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
                raise ScientificValidationError(f"dimension {dim!r} bounds must be (lo, hi)")
            lo, hi = bounds
            if isinstance(lo, bool) or isinstance(hi, bool) or not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
                raise ScientificValidationError(f"dimension {dim!r} bounds must be numeric")
            import math
            lo_f = float(lo); hi_f = float(hi)
            if math.isnan(lo_f) or math.isinf(lo_f) or math.isnan(hi_f) or math.isinf(hi_f):
                raise ScientificValidationError(f"dimension {dim!r} bounds must be finite")
            if lo_f > hi_f:
                raise ScientificValidationError(f"dimension {dim!r} lo must be <= hi")
            norm[dim] = (lo_f, hi_f)
        object.__setattr__(self, "dimensions", norm)


@dataclass(frozen=True)
class ModelDescriptor:
    """Canonical model descriptor (§2.7)."""

    model_id: str
    name: str
    version: str
    classification: Classification
    description: str
    reference: str = ""  # equations / algorithm citation
    parameters: Dict[str, object] = field(default_factory=dict)
    units: Dict[str, str] = field(default_factory=dict)
    assumptions: Tuple[Assumption, ...] = ()
    validity: Optional[ValidityDomain] = None
    limitations: Tuple[str, ...] = ()
    uncertainty_notes: str = ""
    compatibility: Tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.model_id, str) or not self.model_id:
            raise ScientificValidationError("model_id required: non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise ScientificValidationError("name must be a non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise ScientificValidationError("version must be a non-empty string")
        if not isinstance(self.classification, Classification):
            raise TypeError("classification must be a Classification")
        if not isinstance(self.description, str):
            raise TypeError("description must be a string")
        if not isinstance(self.reference, str):
            raise TypeError("reference must be a string")
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "units", dict(self.units))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "limitations", tuple(self.limitations))
        object.__setattr__(self, "compatibility", tuple(self.compatibility))
        for a in self.assumptions:
            if not isinstance(a, Assumption):
                raise TypeError("assumptions must be Assumption instances")
        if self.validity is not None and not isinstance(self.validity, ValidityDomain):
            raise TypeError("validity must be a ValidityDomain or None")
        for lim in self.limitations:
            if not isinstance(lim, str) or not lim:
                raise ScientificValidationError("limitations must be non-empty strings")
        for comp in self.compatibility:
            if not isinstance(comp, str) or not comp:
                raise ScientificValidationError("compatibility entries must be non-empty strings")


class ModelRegistry:
    """Canonical registry of model descriptors (deterministic ordering)."""

    def __init__(self) -> None:
        self._models: Dict[str, ModelDescriptor] = {}

    def register(self, d: ModelDescriptor) -> None:
        if not isinstance(d, ModelDescriptor):
            raise TypeError("d must be a ModelDescriptor")
        if d.model_id in self._models:
            raise ScientificValidationError(f"duplicate model_id {d.model_id!r}")
        self._models[d.model_id] = d

    def get(self, model_id: str) -> ModelDescriptor:
        try:
            return self._models[model_id]
        except KeyError:
            raise ScientificValidationError(f"unknown model_id {model_id!r}")

    def contains(self, model_id: str) -> bool:
        return model_id in self._models

    def query_by_classification(self, c: Classification) -> Tuple[ModelDescriptor, ...]:
        if not isinstance(c, Classification):
            raise TypeError("c must be a Classification")
        return tuple(m for mid, m in sorted(self._models.items()) if m.classification == c)

    def query(self, *, classification: Classification | None = None) -> Tuple[ModelDescriptor, ...]:
        if classification is None:
            return tuple(m for _, m in sorted(self._models.items()))
        return self.query_by_classification(classification)

    def list_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._models.keys()))

    def __len__(self) -> int:
        return len(self._models)

    def to_dict(self) -> Dict:
        return {mid: {"model_id": m.model_id, "name": m.name, "version": m.version,
                       "classification": m.classification.value, "description": m.description}
                for mid, m in self._models.items()}
