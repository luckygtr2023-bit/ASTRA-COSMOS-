"""Determinism tests — identical configs produce identical results."""

from astra.evolution import (
    CosmicEvolutionEngine, EvolutionConfig, EvolutionModel, EvolutionState,
    ModelClassification, ModelRegistry, Provenance, Quantity, Scenario,
    TimestepPolicy,
)


class _AllowAll:
    def require(self, op): return None
    def has_authority(self, op): return True


def _linear(state, dt, model):
    return EvolutionState(
        object_id=state.object_id,
        cosmic_time_gyr=state.cosmic_time_gyr + dt,
        phase=state.phase,
        quantities=dict(state.quantities),
        model_id=state.model_id,
        provenance=state.provenance,
        metadata=dict(state.metadata),
    )


def _run():
    reg = ModelRegistry()
    reg.register(EvolutionModel(
        model_id="toy", name="toy", description="",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
    ), _linear)
    e = CosmicEvolutionEngine(
        config=EvolutionConfig(timestep=TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=1e-4, max_dt_gyr=1.0)),
        model_registry=reg, authority=_AllowAll(),
    )
    init = EvolutionState(
        object_id="o", cosmic_time_gyr=0.0, phase="X",
        quantities={"m": Quantity(value=1.0, unit="Msun", provenance=Provenance.SIMULATED_DATA)},
        model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    s = Scenario(scenario_id="s", name="S", description="",
                 cosmological_parameters={}, evolution_parameters={},
                 provenance=Provenance.SIMULATED_DATA, model_version="v1")
    final = e.evolve_object(initial_state=init, until_cosmic_time_gyr=1.0,
                            model_id="toy", scenario=s)
    return final.cosmic_time_gyr, tuple(sorted(final.quantities.keys())), e.diagnostics()["events_recorded"]


def test_repeated_run_identical():
    a = _run()
    b = _run()
    assert a == b


def test_scenario_comparison_deterministic():
    reg = ModelRegistry()
    reg.register(EvolutionModel(
        model_id="toy", name="toy", description="",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
    ), _linear)
    e = CosmicEvolutionEngine(
        config=EvolutionConfig(timestep=TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=1e-4, max_dt_gyr=1.0)),
        model_registry=reg, authority=_AllowAll(),
    )
    init = EvolutionState(
        object_id="o", cosmic_time_gyr=0.0, phase="X",
        quantities={}, model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    s1 = Scenario(scenario_id="a", name="A", description="",
                  cosmological_parameters={"H0": 67.0}, evolution_parameters={},
                  provenance=Provenance.SIMULATED_DATA, model_version="v1")
    s2 = Scenario(scenario_id="b", name="B", description="",
                  cosmological_parameters={"H0": 70.0}, evolution_parameters={},
                  provenance=Provenance.SIMULATED_DATA, model_version="v1")
    r1 = e.compare_scenarios(initial_state=init, until_cosmic_time_gyr=1.0,
                             model_id="toy", scenarios=[s1, s2])
    # Run again — should be identical ordering and values
    e2 = CosmicEvolutionEngine(
        config=EvolutionConfig(timestep=TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=1e-4, max_dt_gyr=1.0)),
        model_registry=reg, authority=_AllowAll(),
    )
    # Need fresh registry for e2 because reg already has toy; reuse
    e2.model_registry = reg
    r2 = e2.compare_scenarios(initial_state=init, until_cosmic_time_gyr=1.0,
                              model_id="toy", scenarios=[s2, s1])
    assert set(r1.keys()) == set(r2.keys())
    for k in r1:
        assert r1[k].cosmic_time_gyr == r2[k].cosmic_time_gyr


def test_timestep_determinism():
    from astra.evolution.timestep import AdaptiveTimestepController
    from astra.evolution.config import TimestepPolicy
    policy = TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=1e-4, max_dt_gyr=1.0)
    ctrl = AdaptiveTimestepController(policy)
    d1 = ctrl.choose(remaining_gyr=0.5, rate_scale=1.0, model_id="toy")
    d2 = ctrl.choose(remaining_gyr=0.5, rate_scale=1.0, model_id="toy")
    assert d1.dt_gyr == d2.dt_gyr
    assert d1.reason == d2.reason


def test_registry_query_determinism():
    from astra.evolution import ModelRegistry, EvolutionModel, ModelClassification, Provenance
    def step(s, dt, m): return s
    r = ModelRegistry()
    for mid in ["z", "a", "m"]:
        r.register(EvolutionModel(model_id=mid, name=mid, description="",
                                  classification=ModelClassification.SIMULATION,
                                  provenance=Provenance.SIMULATED_DATA), step)
    assert [m.model_id for m in r.query()] == ["a", "m", "z"]
    assert [m.model_id for m in r.query()] == ["a", "m", "z"]
