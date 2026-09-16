"""ASTRA Evolution — model registry and classification.

Every evolution model is explicitly registered with provenance,
assumptions, parameters and classification.  The registry is queryable
without trial-and-error (§2.37 enhanced requirement).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional, Protocol, Tuple

from .errors import EvolutionValidationError
from .provenance import Provenance, Quantity


class ModelClassification(str, Enum):
    """Scientific classification of a model (§2.37)."""

    REAL_PHYSICS = "REAL_PHYSICS"
    DERIVED_MODEL = "DERIVED_MODEL"
    SIMULATION = "SIMULATION"
    THEORETICAL = "THEORETICAL"
    HYPOTHETICAL = "HYPOTHETICAL"
    SPECULATIVE = "SPECULATIVE"


@dataclass(frozen=True)
class ModelAssumption:
    """Explicit statement of a model's domain of validity (§2.8 enhanced).

    Attributes:
        statement: human-readable validity claim.
        valid_regime: shorthand regime description (e.g. ``"z < 6"``).
        outside_behaviour: what the model does outside validity.
        source: optional source reference (paper, calibration, etc.).
        uncertainty: optional fractional uncertainty in regime.
    """

    statement: str
    valid_regime: str
    outside_behaviour: str
    source: Optional[str] = None
    uncertainty: Optional[float] = None

    def __post_init__(self):
        for name in ("statement", "valid_regime", "outside_behaviour"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v:
                raise EvolutionValidationError(f"{name} must be a non-empty string")
        if self.uncertainty is not None:
            if isinstance(self.uncertainty, bool) or not isinstance(self.uncertainty, (int, float)):
                raise EvolutionValidationError("uncertainty must be numeric or None")
            if math.isnan(float(self.uncertainty)) or math.isinf(float(self.uncertainty)):
                raise EvolutionValidationError("uncertainty must be finite")
            if float(self.uncertainty) < 0.0:
                raise EvolutionValidationError("uncertainty must be >= 0")


@dataclass(frozen=True)
class EvolutionModel:
    """Metadata for an evolution model.  Actual step logic lives in a callable
    registered alongside the metadata (see :class:`ModelRegistry`).

    Attributes:
        model_id: stable identifier.
        name: human-readable name.
        description: scientific description.
        classification: scientific classification.
        provenance: provenance of the model's predictions.
        parameters: model parameters as Quantities (with units + provenance).
        assumptions: explicit validity assumptions.
        limitations: free-form limitation notes.
        applicable_object_kinds: object kinds this model applies to (e.g. GALAXY).
        applies_to_regimes: epoch regimes (e.g. STELLIFEROUS).
    """

    model_id: str
    name: str
    description: str
    classification: ModelClassification
    provenance: Provenance
    parameters: Dict[str, Quantity] = field(default_factory=dict)
    assumptions: Tuple[ModelAssumption, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    applicable_object_kinds: Tuple[str, ...] = field(default_factory=tuple)
    applies_to_regimes: Tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not isinstance(self.model_id, str) or not self.model_id:
            raise EvolutionValidationError("model_id required: non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise EvolutionValidationError("name required")
        if not isinstance(self.description, str):
            raise EvolutionValidationError("description must be a string")
        if not isinstance(self.classification, ModelClassification):
            raise TypeError("classification must be a ModelClassification")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "limitations", tuple(self.limitations))
        object.__setattr__(self, "applicable_object_kinds", tuple(self.applicable_object_kinds))
        object.__setattr__(self, "applies_to_regimes", tuple(self.applies_to_regimes))
        for k, v in self.parameters.items():
            if not isinstance(k, str):
                raise EvolutionValidationError("parameter keys must be strings")
            if not isinstance(v, Quantity):
                raise EvolutionValidationError(f"parameter {k!r} must be a Quantity")

    def to_dict(self) -> Dict:
        return dict(
            model_id=self.model_id,
            name=self.name,
            description=self.description,
            classification=self.classification.value,
            provenance=self.provenance.value,
            parameters={k: dict(value=v.value, unit=v.unit,
                                provenance=v.provenance.value,
                                uncertainty=v.uncertainty,
                                model_id=v.model_id,
                                note=v.note)
                        for k, v in self.parameters.items()},
            assumptions=[dict(statement=a.statement,
                              valid_regime=a.valid_regime,
                              outside_behaviour=a.outside_behaviour,
                              source=a.source,
                              uncertainty=a.uncertainty)
                         for a in self.assumptions],
            limitations=list(self.limitations),
            applicable_object_kinds=list(self.applicable_object_kinds),
            applies_to_regimes=list(self.applies_to_regimes),
        )

    @classmethod
    def from_dict(cls, d: Dict) -> "EvolutionModel":
        params = {}
        for k, v in d.get("parameters", {}).items():
            params[k] = Quantity(
                value=v["value"], unit=v["unit"],
                provenance=Provenance(v["provenance"]),
                uncertainty=v.get("uncertainty"),
                model_id=v.get("model_id"),
                note=v.get("note"),
            )
        assumptions = tuple(
            ModelAssumption(
                statement=a["statement"],
                valid_regime=a["valid_regime"],
                outside_behaviour=a["outside_behaviour"],
                source=a.get("source"),
                uncertainty=a.get("uncertainty"),
            )
            for a in d.get("assumptions", [])
        )
        return cls(
            model_id=d["model_id"],
            name=d["name"],
            description=d.get("description", ""),
            classification=ModelClassification(d["classification"]),
            provenance=Provenance(d["provenance"]),
            parameters=params,
            assumptions=assumptions,
            limitations=tuple(d.get("limitations", [])),
            applicable_object_kinds=tuple(d.get("applicable_object_kinds", [])),
            applies_to_regimes=tuple(d.get("applies_to_regimes", [])),
        )


class EvolutionStep(Protocol):
    """Callable signature for a model's step function.

    ``state`` is the current :class:`~astra.evolution.state.EvolutionState`,
    ``dt_gyr`` is the timestep in Gyr, ``model`` is the metadata object.
    Returns the advanced state at ``state.cosmic_time_gyr + dt_gyr``.
    """

    def __call__(self, state, dt_gyr: float, model: EvolutionModel): ...  # type: ignore[valid-type]


class ModelRegistry:
    """Registry of evolution models with deterministic query (§2.37)."""

    def __init__(self) -> None:
        self._models: Dict[str, EvolutionModel] = {}
        self._steps: Dict[str, EvolutionStep] = {}

    def register(self, model: EvolutionModel, step: EvolutionStep) -> None:
        """Register a model and its step callable.

        Raises:
            EvolutionValidationError: on duplicate ``model_id``.
        """
        if not isinstance(model, EvolutionModel):
            raise TypeError("model must be an EvolutionModel")
        if not callable(step):
            raise TypeError("step must be callable")
        if model.model_id in self._models:
            raise EvolutionValidationError(f"duplicate model_id {model.model_id!r}")
        self._models[model.model_id] = model
        self._steps[model.model_id] = step

    def get(self, model_id: str) -> EvolutionModel:
        try:
            return self._models[model_id]
        except KeyError:
            raise EvolutionValidationError(f"unknown model_id {model_id!r}")

    def step_for(self, model_id: str) -> EvolutionStep:
        try:
            return self._steps[model_id]
        except KeyError:
            raise EvolutionValidationError(f"no step registered for model {model_id!r}")

    def query(
        self,
        *,
        object_kind: Optional[str] = None,
        regime: Optional[str] = None,
        classification: Optional[ModelClassification] = None,
        provenance: Optional[Provenance] = None,
        epoch: Optional[str] = None,
    ) -> Tuple[EvolutionModel, ...]:
        """Deterministic query — returns models in ``model_id`` order.

        All filters are optional and conjunctive.  ``epoch`` is an alias for
        ``regime`` for callers using epoch terminology.
        """
        effective_regime = regime if regime is not None else epoch
        result: List[EvolutionModel] = []
        for mid in sorted(self._models.keys()):
            m = self._models[mid]
            if object_kind is not None and object_kind not in m.applicable_object_kinds:
                # If model has no restriction, it applies to all kinds
                if m.applicable_object_kinds:
                    continue
            if effective_regime is not None:
                if m.applies_to_regimes and effective_regime not in m.applies_to_regimes:
                    continue
            if classification is not None and m.classification != classification:
                continue
            if provenance is not None and m.provenance != provenance:
                continue
            result.append(m)
        return tuple(result)

    def list_model_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._models.keys()))

    def __len__(self) -> int:
        return len(self._models)

    def to_dict(self) -> Dict:
        return {mid: m.to_dict() for mid, m in self._models.items()}
