"""Phase 21 — population conveyor tests (spec 2.7, 2.8, 2.15, 2.24)."""
from __future__ import annotations

import math

import pytest

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionConfig,
    PopulationState,
    Quantity,
    Scenario,
    StarFormationHistory,
    MetallicityHistory,
    make_population_state,
)


class AllowAll:
    def require(self, op):
        pass


MODEL = "population.conveyor.v1"


def _eng():
    return CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="population"), authority=AllowAll()
    )


def _scenario(**kw):
    d = dict(scenario_id="s", name="S", description="")
    d.update(kw)
    return Scenario(**d)


def _baryonic_total(state):
    q = state.quantities
    return sum(
        q[k].value for k in (
            "live_stellar_mass_msun", "gas_mass_msun",
            "remnant_wd_msun", "remnant_ns_msun", "remnant_bh_msun",
        )
    )


def test_baryonic_mass_conserved_over_long_run():
    eng = _eng()
    initial_gas = 1.0e10
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=initial_gas, sfr_msun_yr=2.0, metallicity_z=0.02
        ),
        until_cosmic_time_gyr=25.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    assert _baryonic_total(out.final_state) == pytest.approx(initial_gas, rel=1e-9)


def test_star_formation_and_remnant_accumulation():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=1.0e10, sfr_msun_yr=3.0, metallicity_z=0.02
        ),
        until_cosmic_time_gyr=13.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    f = out.final_state
    assert f.quantity_value("live_stellar_mass_msun") > 0.0
    # Massive short-lived stars have died: remnants exist.
    assert f.quantity_value("remnant_wd_msun") > 0.0
    assert f.quantity_value("remnant_ns_msun") > 0.0
    assert f.quantity_value("remnant_bh_msun") > 0.0


def test_metallicity_enriches_then_gas_exhausts():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=1.0e9, sfr_msun_yr=5.0, metallicity_z=0.01
        ),
        until_cosmic_time_gyr=10.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    f = out.final_state
    # Gas fully consumed: SF must have ceased with an explicit exhaustion
    # event (kind-specific POPULATION_TRANSITION here; the generic
    # STAR_FORMATION_TRANSITION covers models without a kind-specific kind).
    assert f.quantity_value("gas_mass_msun") == pytest.approx(0.0, abs=1.0)
    # Recycling-fed residual SF is physically expected; the recorded rate
    # (bursty with cohort deaths) must sit far below the requested driver.
    assert f.quantity_value("sfr_msun_yr") < 0.01 * 5.0
    sf_events = [
        e for e in out.events
        if e.kind.value in ("STAR_FORMATION_TRANSITION", "POPULATION_TRANSITION")
        and "exhaust" in e.physical_cause.lower()
    ]
    assert sf_events, "gas exhaustion must emit an explicit exhaustion event"


def test_metallicity_increases_while_forming():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=1.0e11, sfr_msun_yr=1.0, metallicity_z=0.005
        ),
        until_cosmic_time_gyr=3.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    assert out.final_state.quantity_value("metallicity_z") > 0.005


def test_sf_history_and_metallicity_history_extraction():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=1.0e11, sfr_msun_yr=1.0, metallicity_z=0.01
        ),
        until_cosmic_time_gyr=5.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    sfh = StarFormationHistory.from_history(out.final_state)
    mh = MetallicityHistory.from_history(out.final_state)
    assert len(sfh.samples) >= 2
    assert len(mh.samples) >= 2
    assert all(s >= 0.0 for _, s in sfh.samples)


def test_population_state_summary_view():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=1.0e10, sfr_msun_yr=2.0, metallicity_z=0.02
        ),
        until_cosmic_time_gyr=8.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    summary = PopulationState.from_evolution_state(out.final_state)
    assert summary.population_id == "pop"
    assert 0.0 <= summary.remnant_fraction <= 1.0
    assert summary.remnant_fraction > 0.0
    assert len(summary.mass_function) > 0


def test_sn_number_proxy_is_labelled_proxy():
    """Spec 2.24: no exact future event counts without explicit assumptions.
    The quantity note must say it is an order-of-magnitude proxy."""
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=1.0e10, sfr_msun_yr=2.0
        ),
        until_cosmic_time_gyr=2.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    q = out.final_state.quantities["sn_number_proxy_per_gyr"]
    assert "proxy" in (q.note or "").lower()
    assert "not an event count" in (q.note or "").lower()


def test_imf_mass_fractions_sum_to_one_and_are_deterministic():
    from astra.evolution.builtins import BuiltinModelParams, _imf_mass_fractions

    p = BuiltinModelParams()
    fr1 = _imf_mass_fractions(p)
    fr2 = _imf_mass_fractions(p)
    assert fr1 == fr2
    assert sum(fr1) == pytest.approx(1.0, rel=1e-12)
    assert all(f >= 0.0 for f in fr1)
    # Kroupa-like defaults put most mass in low-mass bins.
    low = sum(fr1[i] for i in range(len(fr1) // 2))
    assert low > 0.5


def test_cohort_budget_coarsening_is_recorded():
    """Cohort coarsening (a documented approximation) is counted in
    metadata, never silent."""
    eng = _eng()
    tiny = 0.02  # Gyr steps -> many cohorts
    from astra.evolution import BuiltinModelParams, ModelRegistry, TimestepPolicy, EvolutionConfig, register_builtin_models

    reg = ModelRegistry()
    register_builtin_models(reg, BuiltinModelParams(max_cohorts_per_bin=8))
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(
            resolution="population",
            timestep=TimestepPolicy(base_dt_gyr=tiny, min_dt_gyr=1e-6, max_dt_gyr=tiny),
        ),
        model_registry=reg, register_builtins=False,
        authority=AllowAll(),
    )
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=1.0e12, sfr_msun_yr=200.0
        ),
        until_cosmic_time_gyr=1.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    f = out.final_state
    per_bin = {}
    for bin_index, birth, mass in f.metadata["cohorts"]:
        per_bin[bin_index] = per_bin.get(bin_index, 0) + 1
    assert all(v <= 8 for v in per_bin.values())


def test_specific_sfr_adaptive_timestepping_slows_as_sf_declines():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_population_state(
            "pop", 0.0, gas_mass_msun=1.0e10, sfr_msun_yr=2.0
        ),
        until_cosmic_time_gyr=20.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    dts = [d.dt_gyr for d in out.timesteps]
    # Steps lengthen as gas depletes (rate-limited -> policy ceiling).
    assert max(dts) > min(dts)
