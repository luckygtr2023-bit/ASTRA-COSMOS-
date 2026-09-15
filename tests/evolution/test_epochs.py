"""Phase 21 — epoch classification tests (state-derived, config-driven)."""
from __future__ import annotations

import math

import pytest

from astra.evolution import (
    EpochBoundaries,
    EpochClassifier,
    EvolutionEpoch,
    EvolutionValidationError,
    Quantity,
    Scenario,
    make_galaxy_state,
    make_population_state,
    make_star_state,
)
from astra.evolution.epoch import epoch_inputs_from_state
from astra.evolution.state import DataProvenance


def _classifier(**overrides):
    defaults = dict(
        declining_sfr_threshold=0.1,
        degenerate_remnant_fraction=0.5,
        black_hole_dominated_fraction=0.7,
        dark_era_luminous_fraction=0.01,
    )
    defaults.update(overrides)
    return EpochClassifier(EpochBoundaries(**defaults))


def _inputs(**kw):
    from astra.evolution.epoch import EpochInputs

    return EpochInputs(**kw)


def test_stelliferous_when_sfr_high():
    e = _classifier().classify_inputs(
        _inputs(specific_sfr_per_gyr=0.5, remnant_mass_fraction=0.1,
                bh_mass_fraction=0.001, luminous_mass_fraction=0.9)
    )
    assert e is EvolutionEpoch.STELLIFEROUS


def test_declining_when_sfr_low_but_remnants_low():
    e = _classifier().classify_inputs(
        _inputs(specific_sfr_per_gyr=0.01, remnant_mass_fraction=0.2,
                bh_mass_fraction=0.01, luminous_mass_fraction=0.7)
    )
    assert e is EvolutionEpoch.DECLINING_STAR_FORMATION


def test_degenerate_when_remnants_dominate():
    e = _classifier().classify_inputs(
        _inputs(specific_sfr_per_gyr=0.0, remnant_mass_fraction=0.7,
                bh_mass_fraction=0.1, luminous_mass_fraction=0.2)
    )
    assert e is EvolutionEpoch.DEGENERATE


def test_bh_dominated():
    e = _classifier().classify_inputs(
        _inputs(specific_sfr_per_gyr=0.0, remnant_mass_fraction=0.9,
                bh_mass_fraction=0.8, luminous_mass_fraction=0.05)
    )
    assert e is EvolutionEpoch.BLACK_HOLE_DOMINATED


def test_dark_era_requires_remnants_not_just_no_stars():
    # A pristine gas reservoir (no stars YET) is not a dark era.
    e = _classifier().classify_inputs(
        _inputs(specific_sfr_per_gyr=None, remnant_mass_fraction=0.0,
                bh_mass_fraction=0.0, luminous_mass_fraction=0.0)
    )
    assert e is EvolutionEpoch.UNKNOWN
    # A true dark era: stars gone, remnants dominate.
    e2 = _classifier().classify_inputs(
        _inputs(specific_sfr_per_gyr=0.0, remnant_mass_fraction=0.95,
                bh_mass_fraction=0.2, luminous_mass_fraction=0.001)
    )
    assert e2 is EvolutionEpoch.DARK_ERA


def test_unknown_when_state_incomplete():
    e = _classifier().classify_inputs(_inputs())
    assert e is EvolutionEpoch.UNKNOWN


def test_partial_state_uses_applicable_subset():
    # Only remnant info available: still classifies on that subset.
    e = _classifier().classify_inputs(_inputs(remnant_mass_fraction=0.9))
    assert e is EvolutionEpoch.DEGENERATE


def test_precedence_is_documented_and_deterministic():
    c = _classifier()
    inputs = _inputs(
        specific_sfr_per_gyr=1.0,       # would say STELLIFEROUS
        remnant_mass_fraction=0.99,     # DEGENERATE-level remnants
        bh_mass_fraction=0.99,          # BH-dominated
        luminous_mass_fraction=0.0,     # dark
    )
    assert c.classify_inputs(inputs) is EvolutionEpoch.DARK_ERA
    inputs2 = _inputs(
        specific_sfr_per_gyr=1.0, remnant_mass_fraction=0.0,
        bh_mass_fraction=0.99, luminous_mass_fraction=0.0,
    )
    assert c.classify_inputs(inputs2) is EvolutionEpoch.BLACK_HOLE_DOMINATED


# --------------------------------------------------- boundaries are validated
def test_boundaries_validated():
    with pytest.raises(EvolutionValidationError):
        EpochBoundaries(
            declining_sfr_threshold=0.1, degenerate_remnant_fraction=1.5,
            black_hole_dominated_fraction=0.7, dark_era_luminous_fraction=0.01,
        )
    with pytest.raises(Exception):
        EpochBoundaries(
            declining_sfr_threshold=float("nan"), degenerate_remnant_fraction=0.5,
            black_hole_dominated_fraction=0.5, dark_era_luminous_fraction=0.01,
        )


def test_same_state_different_boundaries_different_labels():
    """Epoch classification is a function of state AND config (spec 2.5)."""
    from astra.evolution.epoch import EpochInputs

    inputs = EpochInputs(
        specific_sfr_per_gyr=0.0, remnant_mass_fraction=0.45,
        bh_mass_fraction=0.2, luminous_mass_fraction=0.5,
    )
    strict = EpochClassifier(EpochBoundaries(degenerate_remnant_fraction=0.4))
    loose = EpochClassifier(EpochBoundaries(degenerate_remnant_fraction=0.6))
    assert strict.classify_inputs(inputs) is EvolutionEpoch.DEGENERATE
    assert loose.classify_inputs(inputs) is EvolutionEpoch.DECLINING_STAR_FORMATION


# ------------------------------------------------- state extraction (STAR etc.)
def test_star_state_extraction_living_and_remnant():
    living = make_star_state("s1", 0.0, 1.0, age_gyr=1.0)
    inputs = epoch_inputs_from_state(living)
    assert inputs.luminous_mass_fraction == pytest.approx(1.0)
    assert inputs.remnant_mass_fraction == 0.0

    from astra.evolution import BuiltinModelParams, ModelRegistry, register_builtin_models

    reg = ModelRegistry()
    register_builtin_models(reg, BuiltinModelParams())
    step = reg.step_for("stellar.single_star_lifecycle.v1")
    model = reg.get("stellar.single_star_lifecycle.v1")
    dead = make_star_state("s2", 0.0, 1.0, age_gyr=9.0)
    dead = step(dead, 2.0, model)   # crosses t_MS -> POST_MAIN_SEQUENCE
    assert dead.phase == "POST_MAIN_SEQUENCE"
    dead = step(dead, 5.0, model)   # crosses t_end -> REMNANT
    assert dead.phase == "REMNANT"
    inputs2 = epoch_inputs_from_state(dead)
    assert inputs2.remnant_mass_fraction == 1.0
    assert inputs2.luminous_mass_fraction == 0.0


def test_population_state_extraction():
    pop = make_population_state("p", 0.0, gas_mass_msun=1e10, sfr_msun_yr=2.0)
    inputs = epoch_inputs_from_state(pop)
    # No living stars yet: no specific SFR computable -> None (honest).
    assert inputs.specific_sfr_per_gyr is None
    assert inputs.remnant_mass_fraction == 0.0


# ------------------------------------- engine-level epoch transitions recorded
def test_engine_records_epoch_transitions():
    from astra.evolution import CosmicEvolutionEngine, EvolutionConfig

    class AllowAll:
        def require(self, op):
            pass

    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="population"), authority=AllowAll()
    )
    scenario = Scenario(scenario_id="s", name="S", description="")
    pop = make_population_state("p", 0.0, gas_mass_msun=1e10, sfr_msun_yr=2.0)
    out = eng.evolve_object(
        initial_state=pop, until_cosmic_time_gyr=40.0,
        model_id="population.conveyor.v1", scenario=scenario,
    )
    labels = [label for _, label in out.epochs]
    assert labels[0] in ("UNKNOWN", "STELLIFEROUS")
    assert "STELLIFEROUS" in labels
    kinds = {e.kind for e in out.events}
    assert any(k.value == "EPOCH_TRANSITION" for k in kinds)
    # Epoch transition events carry from/to metadata.
    for e in out.events:
        if e.kind.value == "EPOCH_TRANSITION":
            assert "from" in e.metadata and "to" in e.metadata


def test_scenario_epoch_boundaries_override_config():
    from astra.evolution import CosmicEvolutionEngine, EvolutionConfig

    class AllowAll:
        def require(self, op):
            pass

    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="population"), authority=AllowAll()
    )
    scenario = Scenario(
        scenario_id="s", name="S", description="",
        epoch_boundaries=EpochBoundaries(
            declining_sfr_threshold=1.0e9,  # everything looks "declining"
        ),
    )
    pop = make_population_state("p", 0.0, gas_mass_msun=1e10, sfr_msun_yr=2.0)
    out = eng.evolve_object(
        initial_state=pop, until_cosmic_time_gyr=2.0,
        model_id="population.conveyor.v1", scenario=scenario,
    )
    labels = [label for _, label in out.epochs]
    assert "DECLINING_STAR_FORMATION" in labels
    # The default boundaries classify the same state differently.
    out_default = eng.evolve_object(
        initial_state=make_population_state("p2", 0.0, gas_mass_msun=1e10, sfr_msun_yr=2.0),
        until_cosmic_time_gyr=2.0,
        model_id="population.conveyor.v1",
        scenario=Scenario(scenario_id="s-default", name="S", description=""),
    )
    assert "STELLIFEROUS" in [label for _, label in out_default.epochs]
