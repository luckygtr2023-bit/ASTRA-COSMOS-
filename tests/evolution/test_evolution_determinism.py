"""Phase 21 — determinism tests (spec 2.29): identical configuration ->
identical results, proven by running the same scenario twice."""
from __future__ import annotations

import json

import pytest

from astra.evolution import (
    Quantity,
    CosmicEvolutionEngine,
    EvolutionConfig,
    Scenario,
    make_cluster_state,
    make_galaxy_state,
    make_population_state,
    make_star_state,
    make_web_state,
)


class AllowAll:
    def require(self, op):
        pass


def _outcome_payload(engine, out):
    return json.dumps(
        {
            "final": out.final_state.to_dict(),
            "events": [e.to_dict() for e in out.events],
            "timesteps": [d.to_dict() for d in out.timesteps],
            "epochs": out.epochs,
            "ledger": [e.to_dict() for e in engine.history()],
            "diagnostics": engine.diagnostics(),
        },
        sort_keys=True,
    )


def _run_star():
    eng = CosmicEvolutionEngine(authority=AllowAll())
    sc = Scenario(scenario_id="s", name="S", description="")
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 1.5),
        until_cosmic_time_gyr=13.0,
        model_id="stellar.single_star_lifecycle.v1",
        scenario=sc,
    )
    return _outcome_payload(eng, out)


def _run_population():
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="population"), authority=AllowAll()
    )
    sc = Scenario(scenario_id="s", name="S", description="")
    out = eng.evolve_object(
        initial_state=make_population_state("pop", 0.0, gas_mass_msun=1e10,
                                            sfr_msun_yr=2.0, metallicity_z=0.02),
        until_cosmic_time_gyr=20.0,
        model_id="population.conveyor.v1",
        scenario=sc,
    )
    return _outcome_payload(eng, out)


def _run_galaxy():
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="cluster"), authority=AllowAll()
    )
    sc = Scenario(scenario_id="s", name="S", description="")
    out = eng.evolve_galaxy(
        galaxy_state=make_galaxy_state("g", 0.0, stellar_mass_msun=5e10,
                                       gas_mass_msun=2e10, bh_mass_msun=1e7),
        until_cosmic_time_gyr=25.0,
        scenario=sc,
    )
    return _outcome_payload(eng, out)


def _run_web():
    eng = CosmicEvolutionEngine(config=EvolutionConfig(resolution="web"), authority=AllowAll())
    sc = Scenario(scenario_id="s", name="S", description="")

    def expansion(t, dt):
        return 1.0 + 0.001 * dt

    out = eng.evolve_cosmic_web(
        web_state=make_web_state("w", 0.0), until_cosmic_time_gyr=30.0,
        scenario=sc, expansion_ratio_fn=expansion,
    )
    return _outcome_payload(eng, out)


@pytest.mark.parametrize("runner", [_run_star, _run_population, _run_galaxy, _run_web])
def test_repeated_run_identical(runner):
    assert runner() == runner()


def test_interleaved_runs_do_not_cross_contaminate():
    a1 = _run_star()
    b1 = _run_population()
    a2 = _run_star()
    b2 = _run_population()
    assert a1 == a2
    assert b1 == b2
    assert a1 != b1


def test_event_ids_sequential_and_deterministic():
    eng = CosmicEvolutionEngine(authority=AllowAll())
    sc = Scenario(scenario_id="s", name="S", description="")
    eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0),
        until_cosmic_time_gyr=5.0,
        model_id="stellar.single_star_lifecycle.v1",
        scenario=sc,
    )
    ids = [e.event_id for e in eng.history()]
    assert ids == sorted(ids)
    assert len(set(ids)) == len(ids)
    assert all(i.startswith("evo-evt-") for i in ids)


def test_scenario_comparison_is_deterministic():
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="galaxy"), authority=AllowAll()
    )
    gal = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10)

    def compare():
        a = Scenario(scenario_id="hi", name="hi", description="")
        b = Scenario(
            scenario_id="lo", name="lo", description="",
            evolution_parameters={
                "gas_depletion_time_gyr": Quantity(value=8.0, unit="Gyr"),
            },
        )
        comp = eng.compare_scenarios(
            initial_state=gal, until_cosmic_time_gyr=5.0,
            model_id="galaxy.one_zone.v1", scenario_a=a, scenario_b=b,
        )
        return comp.quantity_deltas

    d1 = compare()
    d2 = compare()
    assert d1 == d2
    assert any(abs(delta) > 0.0 for _, _, _, delta in d1)
