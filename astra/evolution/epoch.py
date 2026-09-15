"""ASTRA Evolution — epoch classification.

Epoch boundaries are parameters of the model, not hard-coded constants
(§2.5 enhanced requirement).  The classifier is a pure function of
(model boundaries + current state) — two scenarios with different
cosmological parameters may yield different epoch boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .errors import EvolutionValidationError


class EvolutionEpoch(str, Enum):
    """Cosmic evolution epoch (derived, not asserted)."""

    STELLIFEROUS = "STELLIFEROUS"
    DECLINING_STAR_FORMATION = "DECLINING_STAR_FORMATION"
    DEGENERATE = "DEGENERATE"
    BLACK_HOLE_DOMINATED = "BLACK_HOLE_DOMINATED"
    DARK_ERA = "DARK_ERA"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EpochBoundaries:
    """Model-parameterized boundaries.  Not hard-coded reality.

    Each boundary expresses the threshold at which the classifier moves
    to the next epoch.  All thresholds carry the ``model_id`` they belong
    to so that provenance is never detached from the decision.

    Attributes:
        declining_sfr_threshold: SFR density (Msun/yr/Mpc^3) below which
            the Stelliferous era is considered ending.
        degenerate_remnant_fraction: remnant mass fraction above which the
            Degenerate era is entered.
        black_hole_dominated_fraction: BH mass fraction for BH-dominated.
        dark_era_luminous_fraction: luminous mass fraction below which Dark
            Era is declared.
        model_id: model that defines these boundaries.
    """

    declining_sfr_threshold: float
    degenerate_remnant_fraction: float
    black_hole_dominated_fraction: float
    dark_era_luminous_fraction: float
    model_id: str

    def __post_init__(self):
        for name in ("declining_sfr_threshold", "degenerate_remnant_fraction",
                     "black_hole_dominated_fraction", "dark_era_luminous_fraction"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise EvolutionValidationError(f"{name} must be numeric")
            fv = float(v)
            if fv != fv or fv in (float("inf"), float("-inf")):
                raise EvolutionValidationError(f"{name} must be finite")
            if name != "declining_sfr_threshold" and not 0.0 <= fv <= 1.0:
                raise EvolutionValidationError(f"{name} must be in [0,1]")
            if name == "declining_sfr_threshold" and fv < 0.0:
                raise EvolutionValidationError("declining_sfr_threshold must be >= 0")
            object.__setattr__(self, name, fv)
        if not isinstance(self.model_id, str) or not self.model_id:
            raise EvolutionValidationError("model_id must be a non-empty string")


class EpochClassifier:
    """Classify the current state into an epoch.  Pure function of state + config.

    The ordering is intentional and documents the hierarchy:
        STELLIFEROUS (high SFR)
          → DECLINING_STAR_FORMATION (low SFR, few remnants)
          → DEGENERATE (remnant-dominated)
          → BLACK_HOLE_DOMINATED (if BH fraction high enough)
          → DARK_ERA (if luminous fraction tiny)
    When BH-dominated and Dark-era conditions both hold, Dark-era takes
    precedence as the later epoch.  The classifier never invents data:
    missing required fields return UNKNOWN.
    """

    def __init__(self, boundaries: EpochBoundaries) -> None:
        if not isinstance(boundaries, EpochBoundaries):
            raise TypeError("boundaries must be an EpochBoundaries")
        self._b = boundaries

    @property
    def boundaries(self) -> EpochBoundaries:
        return self._b

    @property
    def model_id(self) -> str:
        return self._b.model_id

    def classify(
        self,
        *,
        cosmic_time_gyr: float,
        sfr_density: Optional[float],
        remnant_mass_fraction: Optional[float],
        bh_mass_fraction: Optional[float] = None,
        luminous_mass_fraction: Optional[float] = None,
    ) -> EvolutionEpoch:
        """Return an epoch derived from state.  If insufficient state, return UNKNOWN."""
        # Validate cosmic time is at least finite if provided
        if cosmic_time_gyr is not None:
            if isinstance(cosmic_time_gyr, bool) or not isinstance(cosmic_time_gyr, (int, float)):
                raise EvolutionValidationError("cosmic_time_gyr must be numeric")
            import math
            if math.isnan(float(cosmic_time_gyr)) or math.isinf(float(cosmic_time_gyr)):
                raise EvolutionValidationError("cosmic_time_gyr must be finite")

        # Core fields required for any classification beyond UNKNOWN
        if sfr_density is None or remnant_mass_fraction is None:
            return EvolutionEpoch.UNKNOWN

        # Validate numeric inputs
        for name, v in (("sfr_density", sfr_density),
                        ("remnant_mass_fraction", remnant_mass_fraction)):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise EvolutionValidationError(f"{name} must be numeric or None")
            import math
            fv = float(v)
            if math.isnan(fv) or math.isinf(fv):
                raise EvolutionValidationError(f"{name} must be finite")
            if name == "remnant_mass_fraction" and not 0.0 <= fv <= 1.0:
                raise EvolutionValidationError("remnant_mass_fraction must be in [0,1]")
            if name == "sfr_density" and fv < 0.0:
                raise EvolutionValidationError("sfr_density must be >= 0")

        if bh_mass_fraction is not None:
            if isinstance(bh_mass_fraction, bool) or not isinstance(bh_mass_fraction, (int, float)):
                raise EvolutionValidationError("bh_mass_fraction must be numeric or None")
            import math
            fv = float(bh_mass_fraction)
            if math.isnan(fv) or math.isinf(fv):
                raise EvolutionValidationError("bh_mass_fraction must be finite")
            if not 0.0 <= fv <= 1.0:
                raise EvolutionValidationError("bh_mass_fraction must be in [0,1]")

        if luminous_mass_fraction is not None:
            if isinstance(luminous_mass_fraction, bool) or not isinstance(luminous_mass_fraction, (int, float)):
                raise EvolutionValidationError("luminous_mass_fraction must be numeric or None")
            import math
            fv = float(luminous_mass_fraction)
            if math.isnan(fv) or math.isinf(fv):
                raise EvolutionValidationError("luminous_mass_fraction must be finite")
            if not 0.0 <= fv <= 1.0:
                raise EvolutionValidationError("luminous_mass_fraction must be in [0,1]")

        b = self._b

        # 1) Stelliferous: SFR density above threshold
        if float(sfr_density) > b.declining_sfr_threshold:
            return EvolutionEpoch.STELLIFEROUS

        # 2) Declining star formation: SFR low but remnants not yet dominant
        if float(remnant_mass_fraction) < b.degenerate_remnant_fraction:
            return EvolutionEpoch.DECLINING_STAR_FORMATION

        # 3) At this point remnant_fraction >= degenerate threshold.
        # Check for more advanced epochs.  Ordering per scaffold reference:
        # BH-dominated is checked before Dark Era; BH takes precedence when
        # both conditions hold.  Dark Era uses strict < to match the scaffold's
        # degenerate-vs-dark boundary (luminous == threshold stays degenerate).
        if (
            bh_mass_fraction is not None
            and float(bh_mass_fraction) >= b.black_hole_dominated_fraction
        ):
            return EvolutionEpoch.BLACK_HOLE_DOMINATED

        if (
            luminous_mass_fraction is not None
            and float(luminous_mass_fraction) < b.dark_era_luminous_fraction
        ):
            return EvolutionEpoch.DARK_ERA

        return EvolutionEpoch.DEGENERATE

    def to_dict(self) -> dict:
        return dict(
            declining_sfr_threshold=self._b.declining_sfr_threshold,
            degenerate_remnant_fraction=self._b.degenerate_remnant_fraction,
            black_hole_dominated_fraction=self._b.black_hole_dominated_fraction,
            dark_era_luminous_fraction=self._b.dark_era_luminous_fraction,
            model_id=self._b.model_id,
        )
