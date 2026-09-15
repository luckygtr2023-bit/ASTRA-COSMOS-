"""ASTRA COSMOS — Phase 21: epoch classification.

Epochs (spec 2.5) are DERIVED from the current simulated state through
configured boundaries — never asserted from cosmic time alone and never
from boundaries written into the code as fixed reality. Two scenarios with
different ``EpochBoundaries`` classify the same state differently; the
classifier is a pure function of (state inputs, boundaries).

Classification precedence (documented, deterministic — evaluated in this
order and the first matching label wins):

    1. DARK_ERA                luminous (living-star) fraction <= dark bound
                               AND remnant fraction >= degenerate bound
                               (a gas reservoir that has not yet formed
                               stars is NOT a dark era)
    2. BLACK_HOLE_DOMINATED    BH fraction of baryonic constituency >= bh bound
    3. DEGENERATE              remnant fraction >= degenerate bound
    4. DECLINING_STAR_FORMATION  specific SFR <= declining bound
    5. STELLIFEROUS            otherwise (specific SFR above the bound)

Inputs the caller cannot supply are simply not discriminated on: if NONE
of the inputs are available the label is UNKNOWN; if some are available
the classifier uses the applicable subset (documented behaviour, never a
guess).

All boundaries live in ``EpochBoundaries`` (validated, carries a model_id)
and can be overridden per scenario or per engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from .errors import EvolutionValidationError, EvolutionNumericalError
from .state import (
    KIND_STAR,
    EvolutionState,
    RemnantKind,
    _MASS_KEYS_LIVE,
    _REMNANT_KEYS,
)


class EvolutionEpoch(str, Enum):
    STELLIFEROUS = "STELLIFEROUS"
    DECLINING_STAR_FORMATION = "DECLINING_STAR_FORMATION"
    DEGENERATE = "DEGENERATE"
    BLACK_HOLE_DOMINATED = "BLACK_HOLE_DOMINATED"
    DARK_ERA = "DARK_ERA"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EpochBoundaries:
    """Configured epoch boundaries. Model parameters, not asserted reality.

    sfr_units are 1/Gyr (stellar mass formed per living stellar mass per
    Gyr): total SFR requires a comoving volume, which no in-repo system
    provides (Phase 21 limitation L1); specific SFR is always computable
    from the state. The defaults below are REGISTRY DEFAULTS (documented
    configuration, not asserted reality); override them per config or per
    scenario.
    """

    declining_sfr_threshold: float = 0.01          # specific SFR (1/Gyr)
    degenerate_remnant_fraction: float = 0.5       # remnants / baryonic constituents
    black_hole_dominated_fraction: float = 0.5     # BH mass / baryonic constituents
    dark_era_luminous_fraction: float = 0.01       # living stars / baryonic constituents
    model_id: str = "astra.evolution.epoch_boundaries.v1"

    def __post_init__(self):
        for name in (
            "declining_sfr_threshold",
            "degenerate_remnant_fraction",
            "black_hole_dominated_fraction",
            "dark_era_luminous_fraction",
        ):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise EvolutionNumericalError(f"EpochBoundaries.{name} must be numeric")
            if v != v or v in (float("inf"), float("-inf")):
                raise EvolutionNumericalError(f"EpochBoundaries.{name} must be finite")
        for name in (
            "degenerate_remnant_fraction",
            "black_hole_dominated_fraction",
            "dark_era_luminous_fraction",
        ):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise EvolutionValidationError(f"EpochBoundaries.{name} must be in [0, 1]")
        if self.declining_sfr_threshold < 0.0:
            raise EvolutionValidationError("EpochBoundaries.declining_sfr_threshold must be >= 0")
        if not isinstance(self.model_id, str) or not self.model_id:
            raise EvolutionValidationError("EpochBoundaries.model_id must be a non-empty string")

    def validate(self) -> None:
        """Re-run validation (used when boundaries are deserialized)."""
        EpochBoundaries(
            declining_sfr_threshold=self.declining_sfr_threshold,
            degenerate_remnant_fraction=self.degenerate_remnant_fraction,
            black_hole_dominated_fraction=self.black_hole_dominated_fraction,
            dark_era_luminous_fraction=self.dark_era_luminous_fraction,
            model_id=self.model_id,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "declining_sfr_threshold": self.declining_sfr_threshold,
            "degenerate_remnant_fraction": self.degenerate_remnant_fraction,
            "black_hole_dominated_fraction": self.black_hole_dominated_fraction,
            "dark_era_luminous_fraction": self.dark_era_luminous_fraction,
            "model_id": self.model_id,
        }

    @classmethod
    def from_dict(cls, d) -> "EpochBoundaries":
        return cls(
            declining_sfr_threshold=d["declining_sfr_threshold"],
            degenerate_remnant_fraction=d["degenerate_remnant_fraction"],
            black_hole_dominated_fraction=d["black_hole_dominated_fraction"],
            dark_era_luminous_fraction=d["dark_era_luminous_fraction"],
            model_id=d.get("model_id", "astra.evolution.epoch_boundaries.v1"),
        )


@dataclass(frozen=True)
class EpochInputs:
    """The state-derived inputs the classifier consumes. ``None`` means
    'not available in this state' (handled per the documented precedence)."""

    specific_sfr_per_gyr: Optional[float] = None
    remnant_mass_fraction: Optional[float] = None
    bh_mass_fraction: Optional[float] = None
    luminous_mass_fraction: Optional[float] = None

    def is_empty(self) -> bool:
        return all(
            v is None
            for v in (
                self.specific_sfr_per_gyr,
                self.remnant_mass_fraction,
                self.bh_mass_fraction,
                self.luminous_mass_fraction,
            )
        )


def epoch_inputs_from_state(state: EvolutionState) -> EpochInputs:
    """Extract epoch inputs from an EvolutionState (pure, documented keys).

    STAR states: living/remnant status comes from the lifecycle phase.
    Aggregate states: from the documented mass-bookkeeping quantity keys.
    """
    sfr: Optional[float] = None
    remnant_fraction: Optional[float] = None
    bh_fraction: Optional[float] = None
    luminous_fraction: Optional[float] = None

    sfr_q = state.quantities.get("sfr_msun_yr")
    live = 0.0
    have_live = False
    for key in _MASS_KEYS_LIVE:
        q = state.quantities.get(key)
        if q is not None:
            live += q.value
            have_live = True
    remnants = 0.0
    have_remnants = False
    for key in _REMNANT_KEYS:
        q = state.quantities.get(key)
        if q is not None:
            remnants += q.value
            have_remnants = True
    bh_q = state.quantities.get("remnant_bh_msun")
    if bh_q is None:
        bh_q = state.quantities.get("bh_mass_msun")
    bh = bh_q.value if bh_q is not None else 0.0
    gas_q = state.quantities.get("gas_mass_msun")
    gas = gas_q.value if gas_q is not None else 0.0

    if state.object_kind == KIND_STAR:
        initial_q = state.quantities.get("initial_mass_msun")
        mass_q = state.quantities.get("mass_msun")
        if initial_q is not None and mass_q is not None:
            total = initial_q.value
            if state.phase == "REMNANT":
                remnant_fraction = 1.0
                luminous_fraction = 0.0
                bh_fraction = 1.0 if state.metadata.get("remnant_kind") == RemnantKind.STELLAR_MASS_BLACK_HOLE.value else 0.0
            else:
                remnant_fraction = 0.0
                luminous_fraction = (mass_q.value / total) if total > 0 else None
                bh_fraction = 0.0
    else:
        total = gas + live + remnants
        if have_live or have_remnants or gas_q is not None:
            if total > 0.0:
                remnant_fraction = remnants / total
                luminous_fraction = live / total
                bh_fraction = bh / total

    if sfr_q is not None and have_live and live > 0.0:
        # Classification uses the EXTERNAL star-formation driver when the
        # model exposes one (metadata "sfr_requested_msun_yr"): the
        # instantaneous recorded SFR of a gas-starved aggregate bursts with
        # each recycled cohort, which would flip the epoch label step to
        # step. The driver is the physically meaningful epoch input.
        sfr_value = sfr_q.value
        driver = state.metadata.get("sfr_requested_msun_yr")
        if isinstance(driver, (int, float)) and float(driver) >= 0.0:
            sfr_value = float(driver)
        # (Msun/yr * 1e9 yr/Gyr) / Msun -> 1/Gyr
        sfr = (sfr_value * 1.0e9) / live

    return EpochInputs(
        specific_sfr_per_gyr=sfr,
        remnant_mass_fraction=remnant_fraction,
        bh_mass_fraction=bh_fraction,
        luminous_mass_fraction=luminous_fraction,
    )


class EpochClassifier:
    """Classify state inputs into an epoch. Pure function of state+config."""

    def __init__(self, boundaries: EpochBoundaries) -> None:
        if not isinstance(boundaries, EpochBoundaries):
            raise EvolutionValidationError("EpochClassifier requires EpochBoundaries")
        self._b = boundaries

    @property
    def boundaries(self) -> EpochBoundaries:
        return self._b

    def classify_inputs(self, inputs: EpochInputs) -> EvolutionEpoch:
        if inputs.is_empty():
            return EvolutionEpoch.UNKNOWN
        b = self._b
        if (
            inputs.luminous_mass_fraction is not None
            and inputs.luminous_mass_fraction <= b.dark_era_luminous_fraction
            and inputs.remnant_mass_fraction is not None
            and inputs.remnant_mass_fraction >= b.degenerate_remnant_fraction
        ):
            # Dark era = stars gone AND remnants dominate. A pristine gas
            # reservoir (no stars yet) is explicitly NOT a dark era.
            return EvolutionEpoch.DARK_ERA
        if inputs.bh_mass_fraction is not None and (
            inputs.bh_mass_fraction >= b.black_hole_dominated_fraction
        ):
            return EvolutionEpoch.BLACK_HOLE_DOMINATED
        if inputs.remnant_mass_fraction is not None and (
            inputs.remnant_mass_fraction >= b.degenerate_remnant_fraction
        ):
            return EvolutionEpoch.DEGENERATE
        if inputs.specific_sfr_per_gyr is not None:
            if inputs.specific_sfr_per_gyr <= b.declining_sfr_threshold:
                return EvolutionEpoch.DECLINING_STAR_FORMATION
            return EvolutionEpoch.STELLIFEROUS
        return EvolutionEpoch.UNKNOWN

    def classify(self, state: EvolutionState) -> EvolutionEpoch:
        return self.classify_inputs(epoch_inputs_from_state(state))


__all__ = [
    "EvolutionEpoch",
    "EpochBoundaries",
    "EpochInputs",
    "EpochClassifier",
    "epoch_inputs_from_state",
]
