"""ASTRA COSMOS — Phase 21: scientific model registry.

The registry is the single authority for WHICH evolution models exist,
what they claim, and where they are valid. Each registered model exposes:

    model_id                 unique id (deterministic ordering everywhere)
    name / description       human-readable metadata
    classification           ModelClassification (epistemic status of the
                             MODEL itself: DERIVED_MODEL, THEORETICAL, ...)
    provenance               DataProvenance of the model's outputs
    parameters               documented model parameters (Quantities)
    assumptions              tuple of ModelAssumption (regime of validity,
                             behaviour outside it) — spec 2.8/2.37
    limitations              tuple of stated limitation strings
    applicable_object_kinds  object kinds the model can evolve
    applies_to_regimes       epoch labels the model targets (optional)
    max_valid_cosmic_time_gyr  validity horizon; the engine refuses to run
                             the model beyond it (spec 2.40: no silent
                             extrapolation)

The registry is QUERYABLE (spec 2.37): ``query`` filters by object kind,
epoch regime, and classification, always returning models sorted by
model_id — deterministic, no trial and error.

Model LOGIC is a pure step function ``EvolutionStep(state, dt_gyr, model)
-> state``; the same model metadata may be registered with exactly one
step. Steps must be deterministic and copy-on-write (they receive frozen
states and return new ones).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Optional, Protocol, Tuple

from astra.celestial.provenance import DataProvenance

from .errors import EvolutionValidationError
from .quantity import Quantity
from .state import EvolutionState


class ModelClassification(str, Enum):
    """Epistemic classification of an evolution MODEL (spec 2.37/2.39).

    This classifies MODELS, not data: data provenance remains the single
    canonical ``astra.celestial.provenance.DataProvenance`` taxonomy.

    DERIVED_MODEL : established functional forms with approximate,
                    literature-scale parameters (e.g. power-law
                    mass-lifetime relation)
    SIMULATION    : engine-internal numerical model (e.g. cohort conveyor)
    THEORETICAL   : physically motivated but not validated end-to-end
    HYPOTHETICAL  : depends on an assumed scenario parameterization
    SPECULATIVE   : illustrative extrapolation, never a prediction
    """

    DERIVED_MODEL = "DERIVED_MODEL"
    SIMULATION = "SIMULATION"
    THEORETICAL = "THEORETICAL"
    HYPOTHETICAL = "HYPOTHETICAL"
    SPECULATIVE = "SPECULATIVE"


@dataclass(frozen=True)
class ModelAssumption:
    """Explicit statement of one model assumption and its regime."""

    statement: str
    valid_regime: str
    outside_behaviour: str

    def __post_init__(self):
        for name in ("statement", "valid_regime", "outside_behaviour"):
            v = getattr(self, name)
            if not isinstance(v, str) or not v:
                raise EvolutionValidationError(f"ModelAssumption.{name} must be a non-empty string")


class EvolutionStep(Protocol):
    """Signature of a registered model's step function."""

    def __call__(
        self, state: EvolutionState, dt_gyr: float, model: "EvolutionModel"
    ) -> EvolutionState: ...


class RateScale(Protocol):
    """Optional per-model rate callback driving adaptive timestepping.

    Receives the state AND the effective model (with any scenario
    parameter overrides applied) so the rate always reflects the exact
    parameterization in use. No rate information ever travels through
    state metadata."""

    def __call__(self, state: EvolutionState, model: "EvolutionModel") -> float: ...


@dataclass(frozen=True)
class EvolutionModel:
    """Metadata for one registered evolution model."""

    model_id: str
    name: str
    description: str
    classification: ModelClassification
    provenance: DataProvenance
    parameters: Dict[str, Quantity] = field(default_factory=dict)
    assumptions: Tuple[ModelAssumption, ...] = ()
    limitations: Tuple[str, ...] = ()
    applicable_object_kinds: Tuple[str, ...] = ()
    applies_to_regimes: Tuple[str, ...] = ()
    max_valid_cosmic_time_gyr: Optional[float] = None
    rate_scale: Optional[Callable[[EvolutionState, "EvolutionModel"], float]] = None

    def __post_init__(self):
        if not isinstance(self.model_id, str) or not self.model_id:
            raise EvolutionValidationError("model_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise EvolutionValidationError("name must be a non-empty string")
        if not isinstance(self.description, str) or not self.description:
            raise EvolutionValidationError("description must be a non-empty string")
        if not isinstance(self.classification, ModelClassification):
            raise EvolutionValidationError("classification must be a ModelClassification member")
        if not isinstance(self.provenance, DataProvenance):
            raise EvolutionValidationError("provenance must be a DataProvenance member")
        for key, q in self.parameters.items():
            if not isinstance(q, Quantity):
                raise EvolutionValidationError(f"parameter {key!r} must be a Quantity")
        for a in self.assumptions:
            if not isinstance(a, ModelAssumption):
                raise EvolutionValidationError("assumptions must be ModelAssumption entries")
        if self.max_valid_cosmic_time_gyr is not None:
            v = self.max_valid_cosmic_time_gyr
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                raise EvolutionValidationError("max_valid_cosmic_time_gyr must be > 0 when set")

    def to_dict(self) -> Dict[str, object]:
        """Serializable metadata (the step callable is NOT serialized)."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "description": self.description,
            "classification": self.classification.value,
            "provenance": self.provenance.value,
            "parameters": {k: q.to_dict() for k, q in self.parameters.items()},
            "assumptions": [
                {
                    "statement": a.statement,
                    "valid_regime": a.valid_regime,
                    "outside_behaviour": a.outside_behaviour,
                }
                for a in self.assumptions
            ],
            "limitations": list(self.limitations),
            "applicable_object_kinds": list(self.applicable_object_kinds),
            "applies_to_regimes": list(self.applies_to_regimes),
            "max_valid_cosmic_time_gyr": self.max_valid_cosmic_time_gyr,
        }

    @classmethod
    def metadata_from_dict(cls, d) -> "EvolutionModel":
        return cls(
            model_id=d["model_id"],
            name=d["name"],
            description=d["description"],
            classification=ModelClassification(d["classification"]),
            provenance=DataProvenance(d["provenance"]),
            parameters={k: Quantity.from_dict(v) for k, v in d.get("parameters", {}).items()},
            assumptions=tuple(
                ModelAssumption(
                    statement=a["statement"],
                    valid_regime=a["valid_regime"],
                    outside_behaviour=a["outside_behaviour"],
                )
                for a in d.get("assumptions", [])
            ),
            limitations=tuple(d.get("limitations", ())),
            applicable_object_kinds=tuple(d.get("applicable_object_kinds", ())),
            applies_to_regimes=tuple(d.get("applies_to_regimes", ())),
            max_valid_cosmic_time_gyr=d.get("max_valid_cosmic_time_gyr"),
        )


class ModelRegistry:
    """Registry of evolution models. Deterministic: all listings sorted."""

    def __init__(self) -> None:
        self._models: Dict[str, EvolutionModel] = {}
        self._steps: Dict[str, EvolutionStep] = {}

    def register(self, model: EvolutionModel, step: EvolutionStep) -> None:
        if not callable(step):
            raise EvolutionValidationError("step must be callable")
        if model.model_id in self._models:
            raise EvolutionValidationError(f"duplicate model_id {model.model_id}")
        self._models[model.model_id] = model
        self._steps[model.model_id] = step

    def get(self, model_id: str) -> EvolutionModel:
        try:
            return self._models[model_id]
        except KeyError:
            raise EvolutionValidationError(f"unknown model_id {model_id}") from None

    def step_for(self, model_id: str) -> EvolutionStep:
        try:
            return self._steps[model_id]
        except KeyError:
            raise EvolutionValidationError(f"no step registered for model {model_id}") from None

    def query(
        self,
        *,
        object_kind: Optional[str] = None,
        regime: Optional[str] = None,
        classification: Optional[ModelClassification] = None,
        provenance: Optional[DataProvenance] = None,
    ) -> Tuple[EvolutionModel, ...]:
        """Deterministic filtered query, sorted by model_id."""
        result = []
        for mid in sorted(self._models.keys()):
            m = self._models[mid]
            if object_kind is not None and object_kind not in m.applicable_object_kinds:
                continue
            if regime is not None and regime not in m.applies_to_regimes:
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


__all__ = [
    "ModelClassification",
    "ModelAssumption",
    "EvolutionModel",
    "EvolutionStep",
    "RateScale",
    "ModelRegistry",
]
