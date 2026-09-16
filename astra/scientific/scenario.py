"""ASTRA Scientific — scenario identity (§2.16).

Scenarios are immutable configuration objects with explicit identity.
Two different scenarios must not silently merge; the registry rejects
duplicate IDs and comparison is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .classification import Classification
from .errors import ScientificValidationError


@dataclass(frozen=True)
class ScenarioIdentity:
    """Explicit scenario identity (§2.16).

    Attributes:
        scenario_id: stable identifier.
        description: scientific description.
        model_config: model configuration dict.
        initial_conditions: initial-conditions dict.
        parameter_values: parameter values dict.
        random_seed: optional seed (int).
        resolution: optional resolution label.
        timestep_strategy: optional strategy label.
        software_version: optional software version string.
        model_versions: mapping model_id → version.
        classification: overall epistemic classification (often the weakest
            of its constituent models).
    """

    scenario_id: str
    description: str
    model_config: Dict[str, object] = field(default_factory=dict)
    initial_conditions: Dict[str, object] = field(default_factory=dict)
    parameter_values: Dict[str, object] = field(default_factory=dict)
    random_seed: Optional[int] = None
    resolution: Optional[str] = None
    timestep_strategy: Optional[str] = None
    software_version: Optional[str] = None
    model_versions: Dict[str, str] = field(default_factory=dict)
    classification: Classification = Classification.SIMULATED_DATA

    def __post_init__(self):
        if not isinstance(self.scenario_id, str) or not self.scenario_id:
            raise ScientificValidationError("scenario_id required: non-empty string")
        if not isinstance(self.description, str):
            raise TypeError("description must be a string")
        if not isinstance(self.model_config, dict):
            raise TypeError("model_config must be a dict")
        if not isinstance(self.initial_conditions, dict):
            raise TypeError("initial_conditions must be a dict")
        if not isinstance(self.parameter_values, dict):
            raise TypeError("parameter_values must be a dict")
        if self.random_seed is not None and not isinstance(self.random_seed, int):
            raise TypeError("random_seed must be int or None")
        if self.resolution is not None and not isinstance(self.resolution, str):
            raise TypeError("resolution must be string or None")
        if self.timestep_strategy is not None and not isinstance(self.timestep_strategy, str):
            raise TypeError("timestep_strategy must be string or None")
        if self.software_version is not None and not isinstance(self.software_version, str):
            raise TypeError("software_version must be string or None")
        if not isinstance(self.model_versions, dict):
            raise TypeError("model_versions must be a dict")
        for k, v in self.model_versions.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ScientificValidationError("model_versions keys/values must be strings")
        if not isinstance(self.classification, Classification):
            raise TypeError("classification must be a Classification")
        # Normalize
        object.__setattr__(self, "model_config", dict(self.model_config))
        object.__setattr__(self, "initial_conditions", dict(self.initial_conditions))
        object.__setattr__(self, "parameter_values", dict(self.parameter_values))
        object.__setattr__(self, "model_versions", dict(self.model_versions))

    def to_dict(self) -> Dict:
        return {
            "scenario_id": self.scenario_id,
            "description": self.description,
            "model_config": dict(self.model_config),
            "initial_conditions": dict(self.initial_conditions),
            "parameter_values": dict(self.parameter_values),
            "random_seed": self.random_seed,
            "resolution": self.resolution,
            "timestep_strategy": self.timestep_strategy,
            "software_version": self.software_version,
            "model_versions": dict(self.model_versions),
            "classification": self.classification.value,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ScenarioIdentity":
        return cls(
            scenario_id=d["scenario_id"],
            description=d.get("description", ""),
            model_config=dict(d.get("model_config", {})),
            initial_conditions=dict(d.get("initial_conditions", {})),
            parameter_values=dict(d.get("parameter_values", {})),
            random_seed=d.get("random_seed"),
            resolution=d.get("resolution"),
            timestep_strategy=d.get("timestep_strategy"),
            software_version=d.get("software_version"),
            model_versions=dict(d.get("model_versions", {})),
            classification=Classification(d.get("classification", Classification.SIMULATED_DATA.value)),
        )


class ScenarioRegistry:
    """Registry of scenario identities (deterministic ordering)."""

    def __init__(self) -> None:
        self._items: Dict[str, ScenarioIdentity] = {}

    def register(self, s: ScenarioIdentity) -> None:
        if not isinstance(s, ScenarioIdentity):
            raise TypeError("s must be a ScenarioIdentity")
        if s.scenario_id in self._items:
            raise ScientificValidationError(f"duplicate scenario_id {s.scenario_id!r}")
        self._items[s.scenario_id] = s

    def get(self, sid: str) -> ScenarioIdentity:
        try:
            return self._items[sid]
        except KeyError:
            raise ScientificValidationError(f"unknown scenario {sid!r}")

    def contains(self, sid: str) -> bool:
        return sid in self._items

    def list_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._items.keys()))

    def list_scenarios(self) -> Tuple[ScenarioIdentity, ...]:
        return tuple(self._items[k] for k in sorted(self._items.keys()))

    def compare(self, a_id: str, b_id: str) -> Dict[str, object]:
        """Compare two scenarios field-by-field without selecting a winner (§2.17)."""
        a = self.get(a_id)
        b = self.get(b_id)
        return {
            "scenario_ids": (a_id, b_id),
            "classification": (a.classification.value, b.classification.value),
            "model_config_diff": {k: (a.model_config.get(k), b.model_config.get(k))
                                  for k in sorted(set(a.model_config) | set(b.model_config))
                                  if a.model_config.get(k) != b.model_config.get(k)},
            "parameter_diff": {k: (a.parameter_values.get(k), b.parameter_values.get(k))
                               for k in sorted(set(a.parameter_values) | set(b.parameter_values))
                               if a.parameter_values.get(k) != b.parameter_values.get(k)},
            "random_seed": (a.random_seed, b.random_seed),
            "software_version": (a.software_version, b.software_version),
        }

    def __len__(self) -> int:
        return len(self._items)
