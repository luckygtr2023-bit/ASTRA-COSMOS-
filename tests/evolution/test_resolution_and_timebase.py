"""Phase 21 — resolution ladder + time interop tests (spec 2.30, 2.4)."""
from __future__ import annotations

import pytest

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionConfig,
    EvolutionLimitationError,
    Scenario,
    make_cluster_state,
    make_galaxy_state,
    make_population_state,
    make_star_state,
    make_web_state,
    gyr_to_seconds,
    seconds_to_gyr,
    temporal_state_for,
)
from astra.evolution.state import kind_rank, resolution_rank


class AllowAll:
    def require(self, op):
        pass


def _scenario():
    return Scenario(scenario_id="s", name="S", description="")


# ------------------------------------------------------------- resolution ladder
def test_rank_ordering():
    assert resolution_rank("individual") < resolution_rank("population")
    assert resolution_rank("population") < resolution_rank("galaxy")
    assert resolution_rank("galaxy") < resolution_rank("cluster")
    assert resolution_rank("cluster") < resolution_rank("web")
    assert kind_rank("STAR") < kind_rank("POPULATION") < kind_rank("GALAXY")
    assert kind_rank("GALAXY") < kind_rank("CLUSTER") < kind_rank("COSMIC_WEB")


@pytest.mark.parametrize("resolution,kind,model,state_factory", [
    ("individual", "POPULATION", "population.conveyor.v1",
     lambda: make_population_state("p", 0.0, gas_mass_msun=1e10, sfr_msun_yr=1.0)),
    ("population", "GALAXY", "galaxy.one_zone.v1",
     lambda: make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10)),
    ("galaxy", "CLUSTER", "cluster.member_aggregate.v1",
     lambda: make_cluster_state("cl", 0.0, member_ids=())),
    ("cluster", "COSMIC_WEB", "web.regime_evolution.v1",
     lambda: make_web_state("w", 0.0)),
])
def test_resolution_gating_refuses_finER_than_configured(resolution, kind, model, state_factory):
    del kind
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution=resolution), authority=AllowAll()
    )
    with pytest.raises(EvolutionLimitationError) as excinfo:
        if model == "web.regime_evolution.v1":
            def flat(t, dt):
                return 1.0
            eng.evolve_cosmic_web(
                web_state=state_factory(), until_cosmic_time_gyr=1.0,
                scenario=_scenario(), expansion_ratio_fn=flat,
            )
        else:
            eng.evolve_object(
                initial_state=state_factory(), until_cosmic_time_gyr=1.0,
                model_id=model, scenario=_scenario(),
            )
    assert excinfo.value.state.value == "INSUFFICIENT_RESOLUTION"


def test_resolution_raisable_explicitly():
    """Users trade accuracy/resolution/performance explicitly (spec 2.30)."""
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="population"), authority=AllowAll()
    )
    out = eng.evolve_object(
        initial_state=make_population_state("p", 0.0, gas_mass_msun=1e10, sfr_msun_yr=1.0),
        until_cosmic_time_gyr=2.0,
        model_id="population.conveyor.v1", scenario=_scenario(),
    )
    assert out.final_state.cosmic_time_gyr == pytest.approx(2.0)


def test_star_evolution_allowed_at_every_resolution():
    for resolution in ("individual", "population", "galaxy", "cluster", "web"):
        eng = CosmicEvolutionEngine(
            config=EvolutionConfig(resolution=resolution), authority=AllowAll()
        )
        out = eng.evolve_object(
            initial_state=make_star_state("o", 0.0, 1.0), until_cosmic_time_gyr=0.5,
            model_id="stellar.single_star_lifecycle.v1", scenario=_scenario(),
        )
        assert out.final_state.cosmic_time_gyr == pytest.approx(0.5)


# ------------------------------------------------------------------ time interop
def test_gyr_second_round_trip():
    for t in (0.0, 1.0, 13.8, 1000.0, 1.0e6):
        assert seconds_to_gyr(gyr_to_seconds(t)) == pytest.approx(t, rel=1e-12)


def test_gyr_second_exact_definitions():
    # Julian year = exactly 31557600 s (unit definition); 1 Gyr = 1e9 yr.
    from astra.evolution.timebase import SECONDS_PER_GYR, SECONDS_PER_JULIAN_YEAR

    assert SECONDS_PER_JULIAN_YEAR == 31557600.0
    assert SECONDS_PER_GYR == 1.0e9 * SECONDS_PER_JULIAN_YEAR


def test_temporal_state_interop():
    from astra.evolution import make_star_state

    state = make_star_state("o", 13.8, 1.0)
    ts = temporal_state_for(state, observer="cosmic")
    assert ts.simulation_time_s == pytest.approx(gyr_to_seconds(13.8))
    assert ts.coordinate_time_s == ts.simulation_time_s
    assert ts.proper_time_s == ts.simulation_time_s  # comoving rate 1
    assert ts.observer == "cosmic"
    assert ts.rate == 1.0


def test_temporal_state_rejects_bad_rate():
    from astra.evolution import make_star_state

    with pytest.raises(Exception):
        temporal_state_for(make_star_state("o", 1.0, 1.0), proper_rate=0.0)
