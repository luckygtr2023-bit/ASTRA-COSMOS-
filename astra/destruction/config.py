"""Configuration for Destruction & Impact."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LimitsConfig:
    """Deterministic, configurable simulation limits.

    Integer limits must be >= 0. Note that ``max_fragments_per_impact``
    values below 2 are inconsistent with the fragmentation model (a
    fractured body yields at least 2 fragments) and cause
    ``LimitExceededError`` when fragmentation is actually required;
    ``max_ejecta_per_impact == 0`` simply disables ejecta.
    """

    max_fragments_per_impact: int = 64
    max_ejecta_per_impact: int = 128
    max_debris_per_impact: int = 256
    max_secondary_impacts: int = 32
    max_recursion_depth: int = 4
    min_fragment_mass_kg: float = 1.0e-6
    min_impact_energy_j: float = 1.0e3
    min_relative_speed_m_s: float = 1.0e-3


@dataclass(frozen=True)
class DestructionConfig:
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    model_version: str = "astra.destruction.v1"
    rng_stream_name: str = "destruction.impact"
    # Energy partitioning: fractions of the DEPOSITED energy; sum must be <= 1
    # (the remainder, plus the non-deposited kinetic energy, is residual KE).
    fragmentation_energy_fraction: float = 0.3
    thermal_energy_fraction: float = 0.4
    # Momentum transfer efficiency for the impact (0..1)
    momentum_transfer_efficiency: float = 0.5
    # Grazing test: an impact is grazing when sin(grazing_elevation) <= this.
    # grazing_elevation = pi/2 - incidence, i.e. the angle of approach above
    # the local surface plane; equiv. cos(incidence) <= threshold.
    grazing_sin_threshold: float = 0.15
    # Head-on test: incidence angle (from surface normal) at or below this.
    head_on_angle_threshold_rad: float = 0.0872665  # ~5 degrees

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not (0.0 <= self.fragmentation_energy_fraction <= 1.0):
            raise ValueError("fragmentation_energy_fraction must be in [0,1]")
        if not (0.0 <= self.thermal_energy_fraction <= 1.0):
            raise ValueError("thermal_energy_fraction must be in [0,1]")
        if self.fragmentation_energy_fraction + self.thermal_energy_fraction > 1.0 + 1e-12:
            raise ValueError("fragmentation + thermal fractions must sum to <= 1")
        if not (0.0 <= self.momentum_transfer_efficiency <= 1.0):
            raise ValueError("momentum_transfer_efficiency must be in [0,1]")
        if not (0.0 <= self.grazing_sin_threshold <= 1.0):
            raise ValueError("grazing_sin_threshold must be in [0,1]")
        if not (0.0 <= self.head_on_angle_threshold_rad <= 3.141592653589793):
            raise ValueError("head_on_angle_threshold_rad must be in [0, pi]")
        if not isinstance(self.model_version, str) or not self.model_version:
            raise ValueError("model_version must be a non-empty string")
        if not isinstance(self.rng_stream_name, str) or not self.rng_stream_name:
            raise ValueError("rng_stream_name must be a non-empty string")
        lim = self.limits
        for name in (
            "max_fragments_per_impact",
            "max_ejecta_per_impact",
            "max_debris_per_impact",
            "max_secondary_impacts",
            "max_recursion_depth",
        ):
            v = getattr(lim, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValueError(f"{name} must be an int >= 0")
        for name in ("min_fragment_mass_kg", "min_impact_energy_j", "min_relative_speed_m_s"):
            v = getattr(lim, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0.0:
                raise ValueError(f"{name} must be a number >= 0")
