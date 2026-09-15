"""Configuration + performance budget."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PerformanceBudget:
    """Documented performance targets. Tests will assert against these."""
    max_galaxies: int = 1_000_000
    max_groups: int = 100_000
    max_clusters: int = 10_000
    max_superclusters: int = 1_000
    max_web_nodes: int = 1_000_000
    max_web_filaments: int = 5_000_000
    max_query_ms: int = 100        # single-structure query
    max_hierarchy_traverse_ms: int = 1000
    max_cosmic_web_build_ms: int = 10_000
    max_memory_mb: int = 2048


@dataclass(frozen=True)
class GalacticConfig:
    budget: PerformanceBudget = field(default_factory=PerformanceBudget)
    model_version: str = "astra.galactic.v1"
    rng_stream_name: str = "galactic.structure"

    # Numerical tolerances
    rtol: float = 1e-10
    atol: float = 1e-15

    # Validity ranges for physical quantities
    min_scale_factor: float = 1e-6
    max_redshift: float = 20.0
    min_kpc: float = 1e-6
    max_mpc: float = 1e6

    # Hierarchy rules
    max_hierarchy_depth: int = 6

    # Cosmology defaults (documented, not fabricated as observation)
    hubble_constant_kms_mpc: float = 70.0  # H0, THEORETICAL default
    matter_density: float = 0.3
    dark_energy_density: float = 0.7

    def validate(self) -> None:
        if self.rtol <= 0.0 or self.atol < 0.0:
            raise ValueError("invalid tolerances")
        if self.max_hierarchy_depth < 1:
            raise ValueError("max_hierarchy_depth must be >= 1")
        if self.min_scale_factor <= 0.0:
            raise ValueError("min_scale_factor must be > 0")
        if self.hubble_constant_kms_mpc <= 0.0:
            raise ValueError("hubble_constant_kms_mpc must be > 0")
        if not (0.0 < self.matter_density < 2.0):
            raise ValueError("matter_density must be (0,2)")
        if not (0.0 <= self.dark_energy_density < 2.0):
            raise ValueError("dark_energy_density must be [0,2)")
