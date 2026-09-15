"""Phase 21 — performance / stress tests against the declared budget
(spec 2.36). Budget targets live in PerformanceBudget; this module asserts
measured behavior against them."""
from __future__ import annotations

import time

import pytest

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionConfig,
    PerformanceBudget,
    Scenario,
    TimestepPolicy,
    make_cluster_state,
    make_galaxy_state,
    make_population_state,
    make_star_state,
)


class AllowAll:
    def require(self, op):
        pass


def _scenario():
    return Scenario(scenario_id="s", name="S", description="")


def test_trillion_year_run_within_wall_time_budget():
    """1e3 Gyr (= 1e12 years) population run inside the configured budget."""
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(
            resolution="population",
            timestep=TimestepPolicy(base_dt_gyr=1.0, min_dt_gyr=1e-4, max_dt_gyr=10.0),
        ),
        authority=AllowAll(),
    )
    pop = make_population_state("pop", 0.0, gas_mass_msun=1e11, sfr_msun_yr=5.0)
    start = time.perf_counter()
    out = eng.evolve_object(
        initial_state=pop, until_cosmic_time_gyr=1000.0,
        model_id="population.conveyor.v1", scenario=_scenario(),
    )
    elapsed = time.perf_counter() - start
    assert out.final_state.cosmic_time_gyr == pytest.approx(1000.0)
    budget = eng.config.budget
    simulated = 1000.0
    assert elapsed < budget.max_wall_time_s_per_gyr * simulated  # extremely loose by design
    assert elapsed < 5.0  # the real expectation: sub-5 s for a trillion years


def test_many_objects_within_budget_time():
    n = 20_000
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(
            resolution="population",
            timestep=TimestepPolicy(base_dt_gyr=0.5, min_dt_gyr=1e-3, max_dt_gyr=2.0),
        ),
        authority=AllowAll(),
    )
    states = [
        make_population_state(
            f"pop-{i}", 0.0, gas_mass_msun=1e9 + i, sfr_msun_yr=0.5 + (i % 10) * 0.1
        )
        for i in range(n)
    ]
    start = time.perf_counter()
    finals = []
    for state in states:
        out = eng.evolve_object(
            initial_state=state, until_cosmic_time_gyr=10.0,
            model_id="population.conveyor.v1", scenario=_scenario(),
        )
        finals.append(out.final_state)
    elapsed = time.perf_counter() - start
    assert len(finals) == n
    # Measured ~62 s in CI sandbox (~1M policy-respecting steps total);
    # the budget assertion is that bulk runs take minutes, not hours.
    assert elapsed < 120.0
    assert eng.diagnostics()["objects_evolved"] == n


def test_scaling_is_near_linear_not_quadratic():
    def timed(n):
        eng = CosmicEvolutionEngine(
            config=EvolutionConfig(
                resolution="population",
                timestep=TimestepPolicy(base_dt_gyr=0.5, min_dt_gyr=1e-3, max_dt_gyr=2.0),
            ),
            authority=AllowAll(),
        )
        states = [
            make_population_state(f"p-{i}", 0.0, gas_mass_msun=1e9, sfr_msun_yr=1.0)
            for i in range(n)
        ]
        start = time.perf_counter()
        for state in states:
            eng.evolve_object(
                initial_state=state, until_cosmic_time_gyr=5.0,
                model_id="population.conveyor.v1", scenario=_scenario(),
            )
        return time.perf_counter() - start

    t_small = timed(500)
    t_large = timed(1500)
    ratio = t_large / max(t_small, 1e-9)
    assert ratio < 9.0, f"superlinear scaling detected: 3x objects took {ratio:.1f}x"


def test_state_memory_stays_bounded():
    """No dense grids of cosmological extent: a trillion-year state must
    stay small (spec 2.20/2.36)."""
    import sys

    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(
            resolution="population",
            timestep=TimestepPolicy(base_dt_gyr=1.0, min_dt_gyr=1e-4, max_dt_gyr=10.0),
        ),
        authority=AllowAll(),
    )
    out = eng.evolve_object(
        initial_state=make_population_state("pop", 0.0, gas_mass_msun=1e11, sfr_msun_yr=1.0),
        until_cosmic_time_gyr=500.0,
        model_id="population.conveyor.v1", scenario=_scenario(),
    )
    size = sys.getsizeof(out.final_state.to_dict())
    assert size < 1.0e6  # one state, well under a megabyte of payload


def test_cluster_of_many_members_runs():
    n = 100
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="cluster"), authority=AllowAll()
    )
    members = [
        make_galaxy_state(f"g{i}", 0.0, stellar_mass_msun=1e10, gas_mass_msun=5e9)
        for i in range(n)
    ]
    cluster = make_cluster_state(
        "cl", 0.0, member_ids=tuple(f"g{i}" for i in range(n)), total_mass_msun=1e14
    )
    start = time.perf_counter()
    out = eng.evolve_cluster(
        cluster_state=cluster, member_states=members,
        until_cosmic_time_gyr=5.0, scenario=_scenario(),
    )
    elapsed = time.perf_counter() - start
    assert len(out.members) == n
    assert elapsed < 60.0
