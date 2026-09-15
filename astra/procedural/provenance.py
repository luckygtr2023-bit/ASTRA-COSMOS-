"""Procedural provenance — strict data boundaries for universe generation.

This module defines the authoritative provenance taxonomy for the procedural
layer. It is intentionally distinct from `astra.celestial.provenance` (which
tags observed catalog data) and from the simulation's `DataProvenance` in the
ingestion pipeline. The five classes are:

  REAL_DATA        — verified catalog observation (authoritative, never generated)
  DERIVED_DATA     — deterministic calculation from REAL_DATA (e.g., distance from parallax)
  GENERATED_DATA   — deterministically procedurally generated (seeded, reproducible)
  THEORETICAL_DATA — standard astrophysical model (e.g., IMF, mass-luminosity)
  SPECULATIVE_DATA — exotic/unconfirmed (e.g., traversable wormhole metric)

Every procedurally emitted state dictionary carries a `metadata.provenance`
field with one of these values, plus `generation_version` and `seed_used`.
Downstream consumers (celestial, physics, world, verification) can therefore
never mistake a placeholder for an observation.

Version tracking prevents silent corruption: if the generation algorithm or
schema changes, `GenerationVersion` is bumped and old snapshots are detected
via `schema_version` mismatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DataProvenance(Enum):
    """Origin class for procedural data."""

    REAL_DATA = "REAL_DATA"
    DERIVED_DATA = "DERIVED_DATA"
    GENERATED_DATA = "GENERATED_DATA"
    THEORETICAL_DATA = "THEORETICAL_DATA"
    SPECULATIVE_DATA = "SPECULATIVE_DATA"


class GenerationVersion:
    """Algorithm and schema versioning for procedural generation.

    Bump `CURRENT_ALGORITHM_VERSION` when generation logic changes.
    Bump `CURRENT_SCHEMA_VERSION` when output dict structure changes.
    Both are emitted in every generated state's metadata.
    """

    CURRENT_ALGORITHM_VERSION = "1.0.0"
    CURRENT_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ProvenanceTag:
    """Immutable provenance stamp for a procedural property block."""

    provenance: DataProvenance
    source_label: str = "astra.procedural"
    generation_version: str = GenerationVersion.CURRENT_ALGORITHM_VERSION
    schema_version: str = GenerationVersion.CURRENT_SCHEMA_VERSION
    seed_used: int | None = None

    def __post_init__(self):
        if not isinstance(self.provenance, DataProvenance):
            raise TypeError("provenance must be a DataProvenance")
        if not isinstance(self.source_label, str) or not self.source_label:
            raise ValueError("source_label must be non-empty string")

    def to_dict(self) -> dict:
        return {
            "provenance": self.provenance.value,
            "source_label": self.source_label,
            "generation_version": self.generation_version,
            "schema_version": self.schema_version,
            "seed_used": self.seed_used,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProvenanceTag":
        return cls(
            provenance=DataProvenance(data["provenance"]),
            source_label=data.get("source_label", "astra.procedural"),
            generation_version=data.get("generation_version", GenerationVersion.CURRENT_ALGORITHM_VERSION),
            schema_version=data.get("schema_version", GenerationVersion.CURRENT_SCHEMA_VERSION),
            seed_used=data.get("seed_used"),
        )

    @property
    def is_real(self) -> bool:
        return self.provenance == DataProvenance.REAL_DATA

    @property
    def is_generated(self) -> bool:
        return self.provenance == DataProvenance.GENERATED_DATA

    # Mapping to celestial provenance for interop (best-effort, no loss)
    def to_celestial_provenance(self):
        """Map to `astra.celestial.provenance.DataProvenance` for hand-off."""
        try:
            from astra.celestial.provenance import DataProvenance as CelProv
            mapping = {
                DataProvenance.REAL_DATA: CelProv.REAL_DATA,
                DataProvenance.DERIVED_DATA: CelProv.DERIVED_DATA,
                DataProvenance.GENERATED_DATA: CelProv.SIMULATED_DATA,
                DataProvenance.THEORETICAL_DATA: CelProv.THEORETICAL_MODEL,
                DataProvenance.SPECULATIVE_DATA: CelProv.SPECULATIVE_MODEL,
            }
            return mapping[self.provenance]
        except Exception:
            return self.provenance


__all__ = ["DataProvenance", "GenerationVersion", "ProvenanceTag"]
