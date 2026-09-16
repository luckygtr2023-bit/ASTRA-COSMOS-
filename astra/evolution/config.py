"""ASTRA Evolution — configuration and performance budget.

No hidden defaults: every policy field is explicit, validated, and
round-trippable via ``to_dict`` / ``from_dict``.  Timescales and budgets
are configuration-driven, never hard-coded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class TimestepPolicy:
    """Explicit timestep policy.  No hidden defaults (§2.31)."""

    base_dt_gyr: float = 0.01
    min_dt_gyr: float = 1e-6
    max_dt_gyr: float = 1.0
    rate_scale_floor: float = 1e-12  # avoid division by zero
    allow_event_driven: bool = True

    def validate(self) -> None:
        if self.min_dt_gyr <= 0.0:
            raise ValueError("min_dt_gyr must be > 0")
        if self.max_dt_gyr < self.min_dt_gyr:
            raise ValueError("max_dt_gyr must be >= min_dt_gyr")
        if self.base_dt_gyr < self.min_dt_gyr or self.base_dt_gyr > self.max_dt_gyr:
            raise ValueError("base_dt_gyr must be within [min_dt_gyr, max_dt_gyr]")
        if self.rate_scale_floor <= 0.0:
            raise ValueError("rate_scale_floor must be > 0")
        if self.min_dt_gyr in (float("inf"), float("-inf")) or self.max_dt_gyr in (float("inf"), float("-inf")):
            raise ValueError("timestep bounds must be finite")

    def to_dict(self) -> Dict:
        return dict(
            base_dt_gyr=self.base_dt_gyr,
            min_dt_gyr=self.min_dt_gyr,
            max_dt_gyr=self.max_dt_gyr,
            rate_scale_floor=self.rate_scale_floor,
            allow_event_driven=self.allow_event_driven,
        )

    @classmethod
    def from_dict(cls, d: Dict) -> "TimestepPolicy":
        return cls(**d)


@dataclass(frozen=True)
class PerformanceBudget:
    """Documented performance targets (§2.36). Tests assert against these."""

    max_objects_evolved: int = 1_000_000
    max_events_per_run: int = 100_000
    max_history_samples_per_object: int = 1024
    max_wall_time_s_per_gyr: float = 5.0  # wall time per simulated Gyr
    max_memory_mb: int = 2048

    def validate(self) -> None:
        for name in ("max_objects_evolved", "max_events_per_run",
                     "max_history_samples_per_object", "max_memory_mb"):
            v = getattr(self, name)
            if not isinstance(v, int) or v <= 0:
                raise ValueError(f"{name} must be int > 0")
        if self.max_wall_time_s_per_gyr <= 0.0:
            raise ValueError("max_wall_time_s_per_gyr must be > 0")

    def to_dict(self) -> Dict:
        return dict(
            max_objects_evolved=self.max_objects_evolved,
            max_events_per_run=self.max_events_per_run,
            max_history_samples_per_object=self.max_history_samples_per_object,
            max_wall_time_s_per_gyr=self.max_wall_time_s_per_gyr,
            max_memory_mb=self.max_memory_mb,
        )

    @classmethod
    def from_dict(cls, d: Dict) -> "PerformanceBudget":
        return cls(**d)


@dataclass(frozen=True)
class EvolutionConfig:
    """Top-level evolution configuration.

    Attributes:
        timestep: timestep policy.
        budget: performance budget.
        model_version: version string for provenance.
        rng_stream_name: DeterministicRNG stream name.
        rtol/atol: numerical tolerances.
        resolution: multi-resolution selector (§2.30).
    """

    timestep: TimestepPolicy = field(default_factory=TimestepPolicy)
    budget: PerformanceBudget = field(default_factory=PerformanceBudget)
    model_version: str = "astra.evolution.v1"
    rng_stream_name: str = "evolution.cosmic"
    rtol: float = 1e-10
    atol: float = 1e-15
    resolution: str = "population"  # individual | population | galaxy | cluster | web

    def validate(self) -> None:
        self.timestep.validate()
        self.budget.validate()
        if not isinstance(self.model_version, str) or not self.model_version:
            raise ValueError("model_version must be a non-empty string")
        if not isinstance(self.rng_stream_name, str) or not self.rng_stream_name:
            raise ValueError("rng_stream_name must be a non-empty string")
        if self.rtol <= 0.0 or self.atol < 0.0:
            raise ValueError("invalid tolerances: rtol > 0, atol >= 0 required")
        if self.resolution not in ("individual", "population", "galaxy", "cluster", "web"):
            raise ValueError(f"invalid resolution {self.resolution!r}")

    def to_dict(self) -> Dict:
        return dict(
            timestep=self.timestep.to_dict(),
            budget=self.budget.to_dict(),
            model_version=self.model_version,
            rng_stream_name=self.rng_stream_name,
            rtol=self.rtol,
            atol=self.atol,
            resolution=self.resolution,
        )

    @classmethod
    def from_dict(cls, d: Dict) -> "EvolutionConfig":
        return cls(
            timestep=TimestepPolicy.from_dict(d.get("timestep", {})) if "timestep" in d else TimestepPolicy(),
            budget=PerformanceBudget.from_dict(d.get("budget", {})) if "budget" in d else PerformanceBudget(),
            model_version=d.get("model_version", "astra.evolution.v1"),
            rng_stream_name=d.get("rng_stream_name", "evolution.cosmic"),
            rtol=d.get("rtol", 1e-10),
            atol=d.get("atol", 1e-15),
            resolution=d.get("resolution", "population"),
        )
