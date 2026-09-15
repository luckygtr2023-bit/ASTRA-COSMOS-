"""ASTRA COSMOS — Phase 21: configuration and performance budget.

All policy lives in explicit, validated configuration objects — the engine
contains no hidden defaults and no fixed timescale/assertion constants
(spec 2.4/2.12/2.31/2.38: timescale support and epoch/scenario realities
are configuration, never hard-wired).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .epoch import EpochBoundaries
from .errors import EvolutionValidationError
from .provenance import ProjectionClass

RESOLUTIONS = ("individual", "population", "galaxy", "cluster", "web")


@dataclass(frozen=True)
class TimestepPolicy:
    """Explicit timestep policy (spec 2.31). No hidden defaults.

    base_dt_gyr : preferred step under unit rate
    min_dt_gyr  : floor for RATE-LIMITED candidates only; a remaining
                  interval smaller than min_dt is taken as-is and recorded
                  as an explicit REMAINDER decision (never silently clamped)
    max_dt_gyr  : ceiling for every decision
    rate_scale_floor : rate values at or below this are treated as "no
                  rate information" (unit rate) instead of dividing by ~0
    allow_event_driven : when False, caller-scheduled events refuse rather
                  than shorten steps
    """

    base_dt_gyr: float = 0.01
    min_dt_gyr: float = 1.0e-6
    max_dt_gyr: float = 1.0
    rate_scale_floor: float = 1.0e-12
    allow_event_driven: bool = True

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        for name in ("base_dt_gyr", "min_dt_gyr", "max_dt_gyr", "rate_scale_floor"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise EvolutionValidationError(f"TimestepPolicy.{name} must be numeric")
            if v != v or v in (float("inf"), float("-inf")):
                raise EvolutionValidationError(f"TimestepPolicy.{name} must be finite")
        if self.min_dt_gyr <= 0.0:
            raise EvolutionValidationError("TimestepPolicy.min_dt_gyr must be > 0")
        if self.max_dt_gyr < self.min_dt_gyr:
            raise EvolutionValidationError("TimestepPolicy.max_dt_gyr must be >= min_dt_gyr")
        if self.base_dt_gyr < self.min_dt_gyr or self.base_dt_gyr > self.max_dt_gyr:
            raise EvolutionValidationError(
                "TimestepPolicy.base_dt_gyr must lie within [min_dt_gyr, max_dt_gyr]"
            )
        if self.rate_scale_floor <= 0.0:
            raise EvolutionValidationError("TimestepPolicy.rate_scale_floor must be > 0")

    def to_dict(self):
        return {
            "base_dt_gyr": self.base_dt_gyr,
            "min_dt_gyr": self.min_dt_gyr,
            "max_dt_gyr": self.max_dt_gyr,
            "rate_scale_floor": self.rate_scale_floor,
            "allow_event_driven": self.allow_event_driven,
        }

    @classmethod
    def from_dict(cls, d) -> "TimestepPolicy":
        return cls(
            base_dt_gyr=d["base_dt_gyr"],
            min_dt_gyr=d["min_dt_gyr"],
            max_dt_gyr=d["max_dt_gyr"],
            rate_scale_floor=d["rate_scale_floor"],
            allow_event_driven=d.get("allow_event_driven", True),
        )


@dataclass(frozen=True)
class PerformanceBudget:
    """Documented, enforced targets (spec 2.36). Exceeding any budget is an
    explicit BUDGET_EXCEEDED limitation — never a silent slowdown."""

    max_objects_evolved: int = 1_000_000
    max_events_total: int = 100_000
    max_steps_per_object: int = 100_000
    max_history_samples_per_object: int = 1024
    max_wall_time_s_per_gyr: float = 5.0
    max_memory_mb: int = 2048

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        for name in (
            "max_objects_evolved",
            "max_events_total",
            "max_steps_per_object",
            "max_history_samples_per_object",
        ):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                raise EvolutionValidationError(f"PerformanceBudget.{name} must be an int >= 1")
        for name in ("max_wall_time_s_per_gyr", "max_memory_mb"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
                raise EvolutionValidationError(f"PerformanceBudget.{name} must be > 0")

    def to_dict(self):
        return dict(
            max_objects_evolved=self.max_objects_evolved,
            max_events_total=self.max_events_total,
            max_steps_per_object=self.max_steps_per_object,
            max_history_samples_per_object=self.max_history_samples_per_object,
            max_wall_time_s_per_gyr=self.max_wall_time_s_per_gyr,
            max_memory_mb=self.max_memory_mb,
        )

    @classmethod
    def from_dict(cls, d) -> "PerformanceBudget":
        return cls(**d)


@dataclass(frozen=True)
class EvolutionConfig:
    """Engine configuration: timestep policy, budget, tolerances, resolution,
    and the configured epoch boundaries."""

    timestep: TimestepPolicy = field(default_factory=TimestepPolicy)
    budget: PerformanceBudget = field(default_factory=PerformanceBudget)
    epoch_boundaries: EpochBoundaries = field(default_factory=EpochBoundaries)
    model_version: str = "astra.evolution.v1"
    rng_stream_name: str = "evolution.cosmic"
    rtol: float = 1.0e-10
    atol: float = 1.0e-15
    resolution: str = "individual"

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        self.timestep.validate()
        self.budget.validate()
        self.epoch_boundaries.validate()
        if isinstance(self.rtol, bool) or not isinstance(self.rtol, (int, float)) or self.rtol <= 0.0:
            raise EvolutionValidationError("EvolutionConfig.rtol must be > 0")
        if isinstance(self.atol, bool) or not isinstance(self.atol, (int, float)) or self.atol < 0.0:
            raise EvolutionValidationError("EvolutionConfig.atol must be >= 0")
        if self.resolution not in RESOLUTIONS:
            raise EvolutionValidationError(
                f"EvolutionConfig.resolution must be one of {RESOLUTIONS}"
            )
        if not isinstance(self.model_version, str) or not self.model_version:
            raise EvolutionValidationError("model_version must be a non-empty string")
        if not isinstance(self.rng_stream_name, str) or not self.rng_stream_name:
            raise EvolutionValidationError("rng_stream_name must be a non-empty string")

    def to_dict(self):
        return {
            "timestep": self.timestep.to_dict(),
            "budget": self.budget.to_dict(),
            "epoch_boundaries": self.epoch_boundaries.to_dict(),
            "model_version": self.model_version,
            "rng_stream_name": self.rng_stream_name,
            "rtol": self.rtol,
            "atol": self.atol,
            "resolution": self.resolution,
        }

    @classmethod
    def from_dict(cls, d) -> "EvolutionConfig":
        return cls(
            timestep=TimestepPolicy.from_dict(d["timestep"]),
            budget=PerformanceBudget.from_dict(d["budget"]),
            epoch_boundaries=EpochBoundaries.from_dict(d["epoch_boundaries"]),
            model_version=d.get("model_version", "astra.evolution.v1"),
            rng_stream_name=d.get("rng_stream_name", "evolution.cosmic"),
            rtol=d.get("rtol", 1.0e-10),
            atol=d.get("atol", 1.0e-15),
            resolution=d.get("resolution", "individual"),
        )


__all__ = [
    "TimestepPolicy",
    "PerformanceBudget",
    "EvolutionConfig",
    "RESOLUTIONS",
    "ProjectionClass",
]
