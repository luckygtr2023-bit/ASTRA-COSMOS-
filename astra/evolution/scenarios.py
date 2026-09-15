"""ASTRA COSMOS — Phase 21: scenario registry.

Scenarios (spec 2.38) are CONFIGURATION OBJECTS, never hard-wired
realities. A scenario bundles:

    cosmological_parameters : named dimensionless/parameter values the
        injected UniverseEvolutionProvider (or a future cosmic background
        system) is CONTRACTED to honor. Phase 21 itself never interprets
        them as physics and never derives expansion from them.
    evolution_parameters    : named Quantities consumed by registered
        models (e.g. scaled star-formation efficiency).
    projection_class        : epistemic depth of states produced under this
        scenario (NONE / MODEL_PROJECTED / HYPOTHETICAL / SPECULATIVE).
    epoch_boundaries        : OPTIONAL per-scenario epoch boundaries — two
        scenarios may legitimately classify epochs differently.
    present_epoch_gyr       : the cosmic time the caller designates as
        'present'; states beyond it are projections under
        scenario.projection_class.

Registries are deterministic (listings sorted by id) and reject duplicate
ids.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from astra.celestial.provenance import DataProvenance

from .epoch import EpochBoundaries
from .errors import EvolutionValidationError
from .provenance import ProjectionClass
from .quantity import Quantity, require_finite_number


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    name: str
    description: str
    cosmological_parameters: Dict[str, float] = field(default_factory=dict)
    evolution_parameters: Dict[str, Quantity] = field(default_factory=dict)
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA
    model_version: str = "astra.evolution.v1"
    projection_class: ProjectionClass = ProjectionClass.MODEL_PROJECTED
    epoch_boundaries: Optional[EpochBoundaries] = None
    present_epoch_gyr: float = 13.8

    def __post_init__(self):
        if not isinstance(self.scenario_id, str) or not self.scenario_id:
            raise EvolutionValidationError("scenario_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise EvolutionValidationError("name must be a non-empty string")
        if not isinstance(self.description, str):
            raise EvolutionValidationError("description must be a string")
        for key, v in self.cosmological_parameters.items():
            if not isinstance(key, str) or not key:
                raise EvolutionValidationError("cosmological parameter names must be non-empty strings")
            require_finite_number(v, f"cosmological_parameters[{key!r}]")
        for key, q in self.evolution_parameters.items():
            if not isinstance(key, str) or not key:
                raise EvolutionValidationError("evolution parameter names must be non-empty strings")
            if not isinstance(q, Quantity):
                raise EvolutionValidationError(
                    f"evolution_parameters[{key!r}] must be a Quantity"
                )
        if not isinstance(self.provenance, DataProvenance):
            raise EvolutionValidationError("provenance must be a DataProvenance member")
        if not isinstance(self.model_version, str) or not self.model_version:
            raise EvolutionValidationError("model_version must be a non-empty string")
        if not isinstance(self.projection_class, ProjectionClass):
            raise EvolutionValidationError("projection_class must be a ProjectionClass member")
        if self.epoch_boundaries is not None and not isinstance(self.epoch_boundaries, EpochBoundaries):
            raise EvolutionValidationError("epoch_boundaries must be EpochBoundaries or None")
        require_finite_number(self.present_epoch_gyr, "present_epoch_gyr")
        if self.present_epoch_gyr < 0.0:
            raise EvolutionValidationError("present_epoch_gyr must be >= 0")

    def evolution_parameter(self, key: str, default: Optional[Quantity] = None) -> Optional[Quantity]:
        return self.evolution_parameters.get(key, default)

    def to_dict(self) -> Dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "cosmological_parameters": dict(self.cosmological_parameters),
            "evolution_parameters": {
                k: q.to_dict() for k, q in self.evolution_parameters.items()
            },
            "provenance": self.provenance.value,
            "model_version": self.model_version,
            "projection_class": self.projection_class.value,
            "epoch_boundaries": None if self.epoch_boundaries is None else self.epoch_boundaries.to_dict(),
            "present_epoch_gyr": self.present_epoch_gyr,
        }

    @classmethod
    def from_dict(cls, d) -> "Scenario":
        boundaries = d.get("epoch_boundaries")
        return cls(
            scenario_id=d["scenario_id"],
            name=d["name"],
            description=d.get("description", ""),
            cosmological_parameters=dict(d.get("cosmological_parameters", {})),
            evolution_parameters={
                k: Quantity.from_dict(v) for k, v in d.get("evolution_parameters", {}).items()
            },
            provenance=DataProvenance(d.get("provenance", "SIMULATED_DATA")),
            model_version=d.get("model_version", "astra.evolution.v1"),
            projection_class=ProjectionClass(d.get("projection_class", "MODEL_PROJECTED")),
            epoch_boundaries=None if boundaries is None else EpochBoundaries.from_dict(boundaries),
            present_epoch_gyr=d.get("present_epoch_gyr", 13.8),
        )


class ScenarioRegistry:
    """Deterministic scenario registry."""

    def __init__(self) -> None:
        self._scenarios: Dict[str, Scenario] = {}

    def register(self, scenario: Scenario) -> None:
        if not isinstance(scenario, Scenario):
            raise EvolutionValidationError("register requires a Scenario")
        if scenario.scenario_id in self._scenarios:
            raise EvolutionValidationError(f"duplicate scenario_id {scenario.scenario_id}")
        self._scenarios[scenario.scenario_id] = scenario

    def get(self, scenario_id: str) -> Scenario:
        try:
            return self._scenarios[scenario_id]
        except KeyError:
            raise EvolutionValidationError(f"unknown scenario {scenario_id}") from None

    def has(self, scenario_id: str) -> bool:
        return scenario_id in self._scenarios

    def list_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._scenarios.keys()))

    def __len__(self) -> int:
        return len(self._scenarios)


__all__ = ["Scenario", "ScenarioRegistry"]
