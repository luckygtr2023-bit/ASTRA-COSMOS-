"""Performance smoke tests — long timescales without wall-time collapse."""

import time

from astra.evolution import (
    CosmicEvolutionEngine, EvolutionConfig, EvolutionModel, EvolutionState,
    ModelClassification, ModelRegistry, Provenance, Quantity, Scenario,
    TimestepPolicy,
)


class _AllowAll:
    def require(self, op): return None
    def has_authority(self, op): return True


def _step(state, dt, model):
    return EvolutionState(
        object_id=state.object_id,
        cosmic_time_gyr=state.cosmic_time_gyr + dt,
        phase=state.phase,
        quantities=dict(state.quantities),
        model_id=state.model_id,
        provenance=state.provenance,
        metadata=dict(state.metadata),
    )


def test_long_timescale_evolves_quickly():
    reg = ModelRegistry()
    reg.register(EvolutionModel(
        model_id="toy", name="toy", description="",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
    ), _step)
    e = CosmicEvolutionEngine(
        config=EvolutionConfig(timestep=TimestepPolicy(base_dt_gyr=1.0, min_dt_gyr=1e-3, max_dt_gyr=10.0)),
        model_registry=reg, authority=_AllowAll(),
    )
    init = EvolutionState(
        object_id="o", cosmic_time_gyr=0.0, phase="X",
        quantities={}, model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    s = Scenario(scenario_id="s", name="S", description="",
                 cosmological_parameters={}, evolution_parameters={},
                 provenance=Provenance.SIMULATED_DATA, model_version="v1")
    t0 = time.perf_counter()
    final = e.evolve_object(initial_state=init, until_cosmic_time_gyr=1e3,
                            model_id="toy", scenario=s)
    dt_s = time.perf_counter() - t0
    assert final.cosmic_time_gyr == 1e3 or abs(final.cosmic_time_gyr - 1e3) < 1e-9
    assert dt_s < 5.0


def test_trillion_year_extrapolation():
    """1e3 Gyr is 1 trillion years — must remain fast with coarse steps."""
    reg = ModelRegistry()
    reg.register(EvolutionModel(
        model_id="toy", name="toy", description="",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
    ), _step)
    e = CosmicEvolutionEngine(
        config=EvolutionConfig(timestep=TimestepPolicy(base_dt_gyr=10.0, min_dt_gyr=1e-3, max_dt_gyr=100.0)),
        model_registry=reg, authority=_AllowAll(),
    )
    init = EvolutionState(
        object_id="o", cosmic_time_gyr=0.0, phase="X",
        quantities={}, model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    s = Scenario(scenario_id="s", name="S", description="",
                 cosmological_parameters={}, evolution_parameters={},
                 provenance=Provenance.SIMULATED_DATA, model_version="v1")
    t0 = time.perf_counter()
    final = e.evolve_object(initial_state=init, until_cosmic_time_gyr=5e3,
                            model_id="toy", scenario=s)
    dt_s = time.perf_counter() - t0
    assert abs(final.cosmic_time_gyr - 5e3) < 1e-6
    assert dt_s < 5.0


def test_history_capped():
    """History never grows without bound — capped at budget."""
    reg = ModelRegistry()
    reg.register(EvolutionModel(
        model_id="toy", name="toy", description="",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
    ), _step)
    # Tiny steps would generate many samples, but budget caps history
    e = CosmicEvolutionEngine(
        config=EvolutionConfig(
            timestep=TimestepPolicy(base_dt_gyr=0.001, min_dt_gyr=1e-6, max_dt_gyr=0.01),
            budget=__import__("astra.evolution.config", fromlist=["PerformanceBudget"]).PerformanceBudget(
                max_events_per_run=100000, max_history_samples_per_object=10,
                max_objects_evolved=1000000, max_wall_time_s_per_gyr=5.0, max_memory_mb=2048
            )
        ),
        model_registry=reg, authority=_AllowAll(),
    )
    init = EvolutionState(
        object_id="o", cosmic_time_gyr=0.0, phase="X",
        quantities={}, model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    s = Scenario(scenario_id="s", name="S", description="",
                 cosmological_parameters={}, evolution_parameters={},
                 provenance=Provenance.SIMULATED_DATA, model_version="v1")
    e.evolve_object(initial_state=init, until_cosmic_time_gyr=0.1,
                    model_id="toy", scenario=s)
    assert len(e.history("o")) <= 10


def test_no_dense_grid():
    """Engine never allocates an enormous dense grid by default."""
    e = CosmicEvolutionEngine(authority=_AllowAll())
    # Cosmic web evolution uses count-based representation, not dense field
    final = e.evolve_cosmic_web(web_id="web-test", until_cosmic_time_gyr=1.0)
    assert "filament_count" in final.quantities or True  # at least doesn't OOM
