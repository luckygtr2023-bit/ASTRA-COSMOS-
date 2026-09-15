"""Travel configuration. Reconciled.

Provides deterministic sampling and tolerances while delegating
heavy physics to authoritative ASTRA modules.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TravelConfig:
    """Immutable travel engine configuration."""

    # Sampling density for worldline construction
    worldline_min_samples: int = 8
    worldline_max_samples: int = 4096

    # Numerical tolerances
    velocity_c_tolerance: float = 1e-9  # |v| must be < c by this margin for TIMELIKE
    ctol_singularity: float = 1e-12

    # Wormhole defaults (all hypothetical; do not present as fact)
    wormhole_default_stability: float = 0.5

    # Warp defaults (hypothetical)
    warp_default_bubble_radius_m: float = 100.0

    # Authority + provenance
    rng_stream_name: str = "travel.worldline"
    model_version: str = "astra.travel.v1"

    def validate(self) -> None:
        if self.worldline_min_samples < 2:
            raise ValueError("worldline_min_samples must be >= 2")
        if self.worldline_max_samples < self.worldline_min_samples:
            raise ValueError("worldline_max_samples must be >= worldline_min_samples")
        if not isinstance(self.velocity_c_tolerance, float) and not isinstance(
            self.velocity_c_tolerance, int
        ):
            raise ValueError("velocity_c_tolerance must be numeric")
