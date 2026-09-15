"""Phase 21 — numerical safety + model-contract tests (spec 2.32, 2.40)."""
from __future__ import annotations

import math

import pytest

from astra.evolution import (
    BuiltinModelParams,
    CosmicEvolutionEngine,
    EvolutionConfig,
    EvolutionLimitationError,
    EvolutionNumericalError,
    EvolutionValidationError,
    EvolutionModel,
    ModelClassification,
    ModelRegistry,
    DataProvenance,
    Scenario,
    make_star_state,
    register_builtin_models,
)


class AllowAll:
    def require(self, op):
        pass


def _scenario():
    return Scenario(scenario_id="s", name="S", description="")


def _eng():
    return CosmicEvolutionEngine(authority=AllowAll())


def test_builtin_params_validated():
    with pytest.raises(EvolutionValidationError):
        BuiltinModelParams(t_ms_sun_gyr=-1.0)
    with pytest.raises(EvolutionValidationError):
        BuiltinModelParams(m_ns_threshold_msun=30.0, m_bh_threshold_msun=20.0)
    with pytest.raises(EvolutionValidationError):
        BuiltinModelParams(population_bins=1)
    with pytest.raises(EvolutionValidationError):
        BuiltinModelParams(stellar_return_fraction=1.5)
    with pytest.raises(EvolutionValidationError):
        BuiltinModelParams(agn_fuel_active_threshold=0.01, agn_fuel_inactive_threshold=0.5)


def test_stellar_mass_must_be_positive():
    with pytest.raises(Exception):
        make_star_state("o", 0.0, 0.0)
    with pytest.raises(Exception):
        make_star_state("o", 0.0, -5.0)


def test_model_time_bookkeeping_violation_detected():
    """A misbehaving custom model must trip NUMERICAL_INSTABILITY, never
    silently corrupt the timeline."""
    reg = ModelRegistry()

    def bad_step(state, dt, model):
        from dataclasses import replace

        return replace(state, cosmic_time_gyr=state.cosmic_time_gyr + dt * 0.5)

    reg.register(
        EvolutionModel(
            model_id="bad.model", name="bad", description="violates time contract",
            classification=ModelClassification.SIMULATION,
            provenance=DataProvenance.SIMULATED_DATA,
            applicable_object_kinds=("STAR",),
        ),
        bad_step,
    )
    eng = CosmicEvolutionEngine(model_registry=reg, register_builtins=False, authority=AllowAll())
    with pytest.raises(EvolutionLimitationError) as excinfo:
        eng.evolve_object(
            initial_state=make_star_state("o", 0.0, 1.0), until_cosmic_time_gyr=1.0,
            model_id="bad.model", scenario=_scenario(),
        )
    assert excinfo.value.state is not None
    assert excinfo.value.state.value == "NUMERICAL_INSTABILITY"


def test_model_returning_non_state_rejected():
    reg = ModelRegistry()
    reg.register(
        EvolutionModel(
            model_id="worse.model", name="worse", description="returns dict",
            classification=ModelClassification.SIMULATION,
            provenance=DataProvenance.SIMULATED_DATA,
            applicable_object_kinds=("STAR",),
        ),
        lambda s, dt, m: {"not": "a state"},
    )
    eng = CosmicEvolutionEngine(model_registry=reg, register_builtins=False, authority=AllowAll())
    with pytest.raises(EvolutionValidationError):
        eng.evolve_object(
            initial_state=make_star_state("o", 0.0, 1.0), until_cosmic_time_gyr=1.0,
            model_id="worse.model", scenario=_scenario(),
        )


def test_negative_rate_scale_rejected():
    reg = ModelRegistry()

    def step(state, dt, model):
        from dataclasses import replace

        return replace(state, cosmic_time_gyr=state.cosmic_time_gyr + dt)

    model = EvolutionModel(
        model_id="neg.rate", name="neg", description="bad rate",
        classification=ModelClassification.SIMULATION,
        provenance=DataProvenance.SIMULATED_DATA,
        applicable_object_kinds=("STAR",),
        rate_scale=lambda s, m: -1.0,
    )
    reg.register(model, step)
    eng = CosmicEvolutionEngine(model_registry=reg, register_builtins=False, authority=AllowAll())
    with pytest.raises(EvolutionValidationError):
        eng.evolve_object(
            initial_state=make_star_state("o", 0.0, 1.0), until_cosmic_time_gyr=1.0,
            model_id="neg.rate", scenario=_scenario(),
        )


def test_config_validation():
    with pytest.raises(EvolutionValidationError):
        EvolutionConfig(rtol=0.0)
    with pytest.raises(EvolutionValidationError):
        EvolutionConfig(atol=-1.0)
    with pytest.raises(EvolutionValidationError):
        EvolutionConfig(resolution="quantum")
    with pytest.raises(EvolutionValidationError):
        EvolutionConfig(model_version="")


def test_lifetime_relation_monotonic():
    p = BuiltinModelParams()
    masses = [0.1, 0.5, 1.0, 2.0, 10.0, 100.0]
    lifetimes = [main_sequence_lifetime_msun(m, p) for m in masses]
    assert lifetimes == sorted(lifetimes, reverse=True)


def main_sequence_lifetime_msun(m, p):
    from astra.evolution.builtins import main_sequence_lifetime_gyr

    return main_sequence_lifetime_gyr(m, p)


def test_no_nonfinite_outputs_over_long_run():
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="population"), authority=AllowAll()
    )
    out = eng.evolve_object(
        initial_state=make_star_state("x", 0.0, 1.0), until_cosmic_time_gyr=0.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=_scenario(),
    )
    from astra.evolution import make_population_state

    out2 = eng.evolve_object(
        initial_state=make_population_state("p", 0.0, gas_mass_msun=1e12, sfr_msun_yr=50.0),
        until_cosmic_time_gyr=40.0,
        model_id="population.conveyor.v1", scenario=_scenario(),
    )
    for state in (out.final_state, out2.final_state):
        for key, q in state.quantities.items():
            assert math.isfinite(q.value), f"{key} became non-finite"
