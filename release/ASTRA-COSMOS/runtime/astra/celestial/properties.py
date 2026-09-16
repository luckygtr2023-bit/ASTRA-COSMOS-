"""ASTRA Celestial - physical & photometric properties.

Contract: an immutable property block with STRICT unknown-data semantics.

    - Every physical field is Optional[float]: unknown means None.
    - 0.0 is NEVER a placeholder for unknown data (a 0.0 kg star is a
      validation error, not a missing measurement).
    - Present values must be finite and physically admissible
      (mass/radius/temperature/luminosity >= 0); violations raise
      InvalidPropertyError.
    - Physics pipelines must request values through require_* accessors,
      which raise IncompletePhysicalDataError on unknown - explicit,
      specific failure instead of a downstream TypeError.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Dict, Optional

from astra.celestial.exceptions import (
    IncompletePhysicalDataError,
    InvalidPropertyError,
)
from astra.celestial.provenance import DataProvenance, ProvenanceTag

# Fields where ZERO is physically impossible for a celestial object
# (a 0.0 kg / 0.0 m / 0.0 K object does not exist): strictly positive.
_POSITIVE_FIELDS = ("mass_kg", "radius_m", "temperature_k", "luminosity_w")
# Fields where zero (or negative) is a legitimate measured value.
_NON_NEGATIVE_FIELDS = ("absolute_magnitude", "age_years", "metallicity")


@dataclass(frozen=True)
class CelestialProperties:
    """Immutable physical/photometric property block (SI units)."""

    mass_kg: Optional[float] = None
    radius_m: Optional[float] = None
    temperature_k: Optional[float] = None
    luminosity_w: Optional[float] = None
    absolute_magnitude: Optional[float] = None
    age_years: Optional[float] = None
    metallicity: Optional[float] = None
    provenance: ProvenanceTag = ProvenanceTag(DataProvenance.SIMULATED_DATA)

    def __post_init__(self):
        if not isinstance(self.provenance, ProvenanceTag):
            raise TypeError("provenance must be a ProvenanceTag")
        for name in _POSITIVE_FIELDS + _NON_NEGATIVE_FIELDS:
            value = getattr(self, name)
            if value is None:
                continue  # unknown is honored, never guessed
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise InvalidPropertyError(
                    f"{name} must be a real number or None, got {value!r}"
                )
            v = float(value)
            if math.isnan(v) or math.isinf(v):
                raise InvalidPropertyError(f"{name} cannot be NaN or Infinite")
            if name in _POSITIVE_FIELDS and v <= 0.0:
                # 0.0 is never a placeholder for unknown data: a zero mass,
                # radius, temperature or luminosity is IMPOSSIBLE, not
                # missing - reject instead of fabricating.
                raise InvalidPropertyError(
                    f"{name} must be > 0 when present (use None for unknown); "
                    f"got {v!r}"
                )
            if name in _NON_NEGATIVE_FIELDS and v < 0.0:
                raise InvalidPropertyError(f"{name} must be >= 0, got {v!r}")
            object.__setattr__(self, name, v)

    # -- physics-pipeline accessors (explicit incompleteness failures) -----
    def require_mass_kg(self) -> float:
        if self.mass_kg is None:
            raise IncompletePhysicalDataError(
                f"mass_kg is UNKNOWN for this object (provenance "
                f"{self.provenance.provenance.value}); refusing to fabricate "
                "a value for physics pipelines"
            )
        return self.mass_kg

    def require_radius_m(self) -> float:
        if self.radius_m is None:
            raise IncompletePhysicalDataError(
                f"radius_m is UNKNOWN for this object (provenance "
                f"{self.provenance.provenance.value}); refusing to fabricate "
                "a value for physics pipelines"
            )
        return self.radius_m

    # -- immutability-preserving update -------------------------------------
    def with_updates(self, **changes) -> "CelestialProperties":
        """Return a NEW block with updated fields (original untouched).

        Updated values pass the same validation; provenance may be re-tagged
        (e.g. a derived mass replaces an unknown with DERIVED_DATA).
        """
        if "provenance" in changes and not isinstance(
                changes["provenance"], ProvenanceTag):
            raise TypeError("provenance must be a ProvenanceTag")
        return replace(self, **changes)

    @property
    def is_complete_for_dynamics(self) -> bool:
        """True iff mass and radius are known (minimum for N-Body feed)."""
        return self.mass_kg is not None and self.radius_m is not None

    def to_dict(self) -> Dict:
        payload = {name: getattr(self, name)
                   for name in _POSITIVE_FIELDS + _NON_NEGATIVE_FIELDS}
        payload["provenance"] = {
            "provenance": self.provenance.provenance.value,
            "source_label": self.provenance.source_label,
        }
        return payload

    @classmethod
    def from_dict(cls, data: Dict) -> "CelestialProperties":
        prov = data.get("provenance", {})
        tag = ProvenanceTag(
            provenance=DataProvenance(prov["provenance"]),
            source_label=prov.get("source_label", "astra"),
        )
        return cls(
            mass_kg=data.get("mass_kg"),
            radius_m=data.get("radius_m"),
            temperature_k=data.get("temperature_k"),
            luminosity_w=data.get("luminosity_w"),
            absolute_magnitude=data.get("absolute_magnitude"),
            age_years=data.get("age_years"),
            metallicity=data.get("metallicity"),
            provenance=tag,
        )
