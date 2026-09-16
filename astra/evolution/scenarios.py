"""ASTRA Evolution — scenario registry (configuration objects, not hard-coded reality).

Scenarios are immutable configuration objects (§2.38).  They carry
cosmological parameters, evolution parameters (as Quantities with
provenance), and a classification so that speculative late-time
cosmologies can never be mistaken for the baseline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from .errors import EvolutionValidationError
from .provenance import Provenance, Quantity


@dataclass(frozen=True)
class Scenario:
    """A cosmological / evolutionary scenario.

    Attributes:
        scenario_id: stable identifier (e.g. ``"baseline_LCDM"``).
        name: human-readable name.
        description: scientific description, including domain of validity.
        cosmological_parameters: free-form cosmological params (H0, Omega_m,
            Omega_L etc.) in natural units; callers validate domain.
        evolution_parameters: evolution-tunable parameters as Quantities
            (with unit + provenance).  Kept separate so that provenance
            is never detached from the value.
        provenance: classification of this scenario's assumptions.
        model_version: version string linking to the evolution models this
            scenario is compatible with.
    """

    scenario_id: str
    name: str
    description: str
    cosmological_parameters: Dict[str, float] = field(default_factory=dict)
    evolution_parameters: Dict[str, Quantity] = field(default_factory=dict)
    provenance: Provenance = Provenance.SIMULATED_DATA
    model_version: str = "astra.evolution.v1"

    def __post_init__(self):
        if not isinstance(self.scenario_id, str) or not self.scenario_id:
            raise EvolutionValidationError("scenario_id required: non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise EvolutionValidationError("name must be a non-empty string")
        if not isinstance(self.description, str):
            raise EvolutionValidationError("description must be a string")
        if not isinstance(self.cosmological_parameters, dict):
            raise TypeError("cosmological_parameters must be a dict")
        for k, v in self.cosmological_parameters.items():
            if not isinstance(k, str):
                raise EvolutionValidationError("cosmological parameter keys must be strings")
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise EvolutionValidationError(f"cosmological parameter {k!r} must be numeric")
            import math
            if math.isnan(float(v)) or math.isinf(float(v)):
                raise EvolutionValidationError(f"cosmological parameter {k!r} must be finite")
        if not isinstance(self.evolution_parameters, dict):
            raise TypeError("evolution_parameters must be a dict")
        for k, v in self.evolution_parameters.items():
            if not isinstance(k, str):
                raise EvolutionValidationError("evolution parameter keys must be strings")
            if not isinstance(v, Quantity):
                raise EvolutionValidationError(f"evolution parameter {k!r} must be a Quantity")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be a Provenance")
        if not isinstance(self.model_version, str) or not self.model_version:
            raise EvolutionValidationError("model_version must be a non-empty string")
        object.__setattr__(self, "cosmological_parameters", dict(self.cosmological_parameters))
        object.__setattr__(self, "evolution_parameters", dict(self.evolution_parameters))

    def to_dict(self) -> Dict:
        return dict(
            scenario_id=self.scenario_id,
            name=self.name,
            description=self.description,
            cosmological_parameters=dict(self.cosmological_parameters),
            evolution_parameters={
                k: dict(value=v.value, unit=v.unit,
                        provenance=v.provenance.value,
                        uncertainty=v.uncertainty,
                        model_id=v.model_id,
                        note=v.note)
                for k, v in self.evolution_parameters.items()
            },
            provenance=self.provenance.value,
            model_version=self.model_version,
        )

    @classmethod
    def from_dict(cls, d: Dict) -> "Scenario":
        evo_params = {}
        for k, v in d.get("evolution_parameters", {}).items():
            evo_params[k] = Quantity(
                value=v["value"], unit=v["unit"],
                provenance=Provenance(v["provenance"]),
                uncertainty=v.get("uncertainty"),
                model_id=v.get("model_id"),
                note=v.get("note"),
            )
        return cls(
            scenario_id=d["scenario_id"],
            name=d["name"],
            description=d.get("description", ""),
            cosmological_parameters=dict(d.get("cosmological_parameters", {})),
            evolution_parameters=evo_params,
            provenance=Provenance(d.get("provenance", Provenance.SIMULATED_DATA.value)),
            model_version=d.get("model_version", "astra.evolution.v1"),
        )


class ScenarioRegistry:
    """Registry of scenarios — configuration objects, not hard-coded realities."""

    def __init__(self) -> None:
        self._scenarios: Dict[str, Scenario] = {}

    def register(self, scenario: Scenario) -> None:
        if not isinstance(scenario, Scenario):
            raise TypeError("scenario must be a Scenario")
        if scenario.scenario_id in self._scenarios:
            raise EvolutionValidationError(f"duplicate scenario_id {scenario.scenario_id!r}")
        self._scenarios[scenario.scenario_id] = scenario

    def get(self, scenario_id: str) -> Scenario:
        try:
            return self._scenarios[scenario_id]
        except KeyError:
            raise EvolutionValidationError(f"unknown scenario {scenario_id!r}")

    def list_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._scenarios.keys()))

    def query(self, *, provenance: Provenance | None = None,
              model_version: str | None = None) -> Tuple[Scenario, ...]:
        """Deterministic query by provenance / model_version, sorted by id."""
        result = []
        for sid in sorted(self._scenarios.keys()):
            s = self._scenarios[sid]
            if provenance is not None and s.provenance != provenance:
                continue
            if model_version is not None and s.model_version != model_version:
                continue
            result.append(s)
        return tuple(result)

    def __len__(self) -> int:
        return len(self._scenarios)

    def to_dict(self) -> Dict:
        return {sid: s.to_dict() for sid, s in self._scenarios.items()}
