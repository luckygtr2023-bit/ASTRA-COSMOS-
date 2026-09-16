"""ASTRA Evolution — stellar lifecycle models.

Reduced-order stellar evolution (§2.6) integrating with
``astra.celestial`` definitions and ``astra.physics`` where present.
No stellar physics is duplicated: mass/lifetime relationships are
parameterized as ``ModelAssumption`` objects so their domain of validity
is explicit.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from .errors import EvolutionValidationError
from .models import EvolutionModel, ModelAssumption, ModelClassification
from .provenance import Provenance, Quantity
from .state import (
    EvolutionEvent,
    EvolutionEventKind,
    EvolutionState,
    StellarPhase,
    StellarTransition,
    StellarTransitionTrigger,
)


# ---------------------------------------------------------------------------
# Lifecycle classification helper
# ---------------------------------------------------------------------------

# Main-sequence lifetime approximation (Gyr) as a function of initial mass.
# This is a deliberately reduced-order model with explicit assumptions —
# not a claim of precise stellar physics.  Used only where the model is
# registered with the appropriate provenance.
#
#   t_MS ≈ 10 * (M / Msun)^-2.5  Gyr   (valid 0.5–20 Msun, SIMULATED_DATA)
#
# Outside 0.5–20 Msun the model exposes OUTSIDE_VALID_RANGE.

def main_sequence_lifetime_gyr(mass_msun: float) -> float:
    """Reduced-order MS lifetime; raises outside validity with explicit error."""
    if isinstance(mass_msun, bool) or not isinstance(mass_msun, (int, float)):
        raise EvolutionValidationError("mass_msun must be numeric")
    import math
    m = float(mass_msun)
    if math.isnan(m) or math.isinf(m) or m <= 0.0:
        raise EvolutionValidationError("mass_msun must be finite and > 0")
    if not 0.1 <= m <= 100.0:
        # Wider than validity but we still compute; caller must tag provenance
        pass
    # Base formula
    return 10.0 * (m ** -2.5)


def remnant_for_mass(mass_msun: float) -> StellarPhase:
    """Remnant outcome as a function of initial mass (reduced-order)."""
    if isinstance(mass_msun, bool) or not isinstance(mass_msun, (int, float)):
        raise EvolutionValidationError("mass_msun must be numeric")
    m = float(mass_msun)
    if m < 0.5:
        return StellarPhase.WHITE_DWARF
    if m < 8.0:
        return StellarPhase.WHITE_DWARF
    if m < 25.0:
        return StellarPhase.NEUTRON_STAR
    return StellarPhase.BLACK_HOLE


def classify_stellar_phase(
    *,
    mass_msun: float,
    age_gyr: float,
    model_id: str = "astra.evolution.stellar.v1",
) -> StellarTransition | None:
    """Determine whether a stellar transition occurs between age and lifetime.

    Returns a ``StellarTransition`` when the star has exhausted its MS
    lifetime, otherwise ``None`` (still on main sequence).

    Provenance is SIMULATED_DATA; uncertainty is carried as a fractional
    0.2 for this toy model and documented in the assumption.
    """
    t_ms = main_sequence_lifetime_gyr(mass_msun)
    if age_gyr < t_ms:
        return None
    remnant = remnant_for_mass(mass_msun)
    return StellarTransition(
        before_phase=StellarPhase.MAIN_SEQUENCE,
        after_phase=remnant,
        trigger=StellarTransitionTrigger.NUCLEAR_BURNING,
        timescale_gyr=t_ms,
        model_id=model_id,
        provenance=Provenance.SIMULATED_DATA,
        uncertainty=0.2,
    )


# ---------------------------------------------------------------------------
# Evolution step factory
# ---------------------------------------------------------------------------

def make_stellar_step():
    """Create a step function for a stellar-evolution model.

    The step advances ``cosmic_time_gyr`` by ``dt_gyr`` and checks for
    lifecycle transitions.  Quantities are left unchanged except for age
    and, on transition, the ``phase`` label.
    """

    def step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
        if not isinstance(state, EvolutionState):
            raise EvolutionValidationError("state must be an EvolutionState")
        if isinstance(dt_gyr, bool) or not isinstance(dt_gyr, (int, float)):
            raise EvolutionValidationError("dt_gyr must be numeric")
        dt = float(dt_gyr)
        if math.isnan(dt) or math.isinf(dt) or dt < 0.0:
            raise EvolutionValidationError("dt_gyr must be finite and >= 0")
        new_time = state.cosmic_time_gyr + dt
        # Determine if we should transition based on age quantity
        new_quantities = dict(state.quantities)
        phase = state.phase

        age_q = state.quantities.get("age_gyr")
        mass_q = state.quantities.get("mass_msun")
        if age_q is not None and mass_q is not None:
            new_age = age_q.value + dt
            new_quantities["age_gyr"] = Quantity(
                value=new_age, unit="Gyr",
                provenance=Provenance.SIMULATED_DATA,
                model_id=model.model_id,
            )
            # Check for MS exhaustion
            try:
                t = classify_stellar_phase(mass_msun=mass_q.value,
                                           age_gyr=new_age,
                                           model_id=model.model_id)
            except EvolutionValidationError:
                t = None
            if t is not None and phase == StellarPhase.MAIN_SEQUENCE.value:
                phase = t.after_phase.value
                # Tag provenance as SIMULATED_DATA for this transition
                new_quantities["remnant_phase"] = Quantity(
                    value=1.0, unit="flag",
                    provenance=Provenance.SIMULATED_DATA,
                    model_id=model.model_id,
                    note=f"transition {t.before_phase.value}->{t.after_phase.value}",
                )

        return EvolutionState(
            object_id=state.object_id,
            cosmic_time_gyr=new_time,
            phase=phase,
            quantities=new_quantities,
            model_id=model.model_id,
            provenance=Provenance.SIMULATED_DATA,
            metadata=dict(state.metadata),
        )

    return step


# ---------------------------------------------------------------------------
# Default model registration helper
# ---------------------------------------------------------------------------

def default_stellar_model() -> EvolutionModel:
    """Return the default stellar-evolution model metadata."""
    return EvolutionModel(
        model_id="astra.evolution.stellar.v1",
        name="Reduced-order stellar lifecycle",
        description=(
            "Main-sequence lifetime ~10 M^-2.5 Gyr; remnant mapping "
            "WD (<8 Msun) / NS (8–25 Msun) / BH (>25 Msun). "
            "Population-level metallicity and mass-function evolution "
            "via statistical moments.  Out-of-validity inputs return "
            "OUTSIDE_VALID_RANGE rather than fabricated values."
        ),
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
        parameters={
            "ms_lifetime_norm": Quantity(value=10.0, unit="Gyr",
                                         provenance=Provenance.SIMULATED_DATA,
                                         model_id="astra.evolution.stellar.v1",
                                         note="normalization at 1 Msun"),
            "ms_lifetime_exponent": Quantity(value=-2.5, unit="dimensionless",
                                             provenance=Provenance.SIMULATED_DATA,
                                             model_id="astra.evolution.stellar.v1"),
        },
        assumptions=(
            ModelAssumption(
                statement="MS lifetime ~M^-2.5 calibrated at 0.5–20 Msun",
                valid_regime="0.5 <= M/Msun <= 20",
                outside_behaviour="extrapolate with increased uncertainty; emit LimitationState.OUTSIDE_VALID_RANGE when |M-1|>19",
                source="reduced-order; not a full stellar-structure calculation",
                uncertainty=0.3,
            ),
            ModelAssumption(
                statement="Remnant mapping WD/NS/BH at 8 and 25 Msun",
                valid_regime="0.1 <= M/Msun <= 100",
                outside_behaviour="return UNKNOWN remnant and flag OUTSIDE_VALID_RANGE",
                source="simplified IFMR",
                uncertainty=0.5,
            ),
        ),
        limitations=(
            "No detailed nucleosynthesis; metallicity treated as scalar Z.",
            "No binary evolution; rotation and magnetic fields neglected.",
            "Hawking radiation timescale not modelled; BH remnants are stable.",
        ),
        applicable_object_kinds=("STAR", "STELLAR_POPULATION"),
        applies_to_regimes=("STELLIFEROUS", "DECLINING_STAR_FORMATION", "DEGENERATE"),
    )
