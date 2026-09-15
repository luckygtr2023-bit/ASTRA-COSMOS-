"""Phase 21 — provenance and scientific-integrity tests (spec 2.39)."""
from __future__ import annotations

import pytest

from astra.celestial.provenance import DataProvenance

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionConfig,
    ProjectionClass,
    Quantity,
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


def _scenario(**kw):
    d = dict(scenario_id="s", name="S", description="")
    d.update(kw)
    return Scenario(**d)


def _evolved_states():
    """Run every built-in model briefly and collect final states."""
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="web"), authority=AllowAll()
    )
    sc = _scenario()
    states = []
    states.append(eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0), until_cosmic_time_gyr=3.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=sc,
    ).final_state)
    states.append(eng.evolve_object(
        initial_state=make_population_state("p", 0.0, gas_mass_msun=1e10, sfr_msun_yr=2.0),
        until_cosmic_time_gyr=3.0, model_id="population.conveyor.v1", scenario=sc,
    ).final_state)
    states.append(eng.evolve_object(
        initial_state=make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10),
        until_cosmic_time_gyr=3.0, model_id="galaxy.one_zone.v1", scenario=sc,
    ).final_state)
    states.append(eng.evolve_object(
        initial_state=make_cluster_state("cl", 0.0, member_ids=()), until_cosmic_time_gyr=3.0,
        model_id="cluster.member_aggregate.v1", scenario=sc,
    ).final_state)

    def flat(t, dt):
        return 1.0

    states.append(eng.evolve_cosmic_web(
        web_state=make_web_state("w", 0.0), until_cosmic_time_gyr=3.0,
        scenario=sc, expansion_ratio_fn=flat,
    ).final_state)
    return states


def test_every_quantity_carries_provenance():
    for state in _evolved_states():
        for key, q in state.quantities.items():
            assert isinstance(q.provenance, DataProvenance), f"{key} lacks provenance"
            assert q.unit


def test_engine_outputs_never_claim_real_data():
    for state in _evolved_states():
        assert state.provenance is not DataProvenance.REAL_DATA
        assert state.provenance is not DataProvenance.DERIVED_DATA
        for q in state.quantities.values():
            assert q.provenance is not DataProvenance.REAL_DATA
            assert q.provenance is not DataProvenance.DERIVED_DATA


def test_model_provenance_follows_classification():
    from astra.evolution.builtins import classification_provenance
    from astra.evolution.models import ModelClassification

    assert classification_provenance(ModelClassification.DERIVED_MODEL) is DataProvenance.SIMULATED_DATA
    assert classification_provenance(ModelClassification.SIMULATION) is DataProvenance.SIMULATED_DATA
    assert classification_provenance(ModelClassification.THEORETICAL) is DataProvenance.THEORETICAL_MODEL
    assert classification_provenance(ModelClassification.HYPOTHETICAL) is DataProvenance.THEORETICAL_MODEL
    assert classification_provenance(ModelClassification.SPECULATIVE) is DataProvenance.SPECULATIVE_MODEL


def test_registry_models_declare_provenance():
    from astra.evolution import ModelRegistry, register_builtin_models, BuiltinModelParams

    reg = ModelRegistry()
    register_builtin_models(reg, BuiltinModelParams())
    for mid in reg.list_model_ids():
        model = reg.get(mid)
        assert isinstance(model.provenance, DataProvenance)


def test_quantity_uncertainty_validation():
    with pytest.raises(Exception):
        Quantity(value=1.0, unit="Msun", uncertainty=-0.5)
    with pytest.raises(Exception):
        Quantity(value=float("nan"), unit="Msun")
    q = Quantity(value=10.0, unit="Msun", uncertainty=1.0, model_id="m", note="n")
    assert q.uncertainty == 1.0


def test_projection_class_required_for_future_scenarios():
    sc = _scenario(projection_class=ProjectionClass.SPECULATIVE)
    assert sc.projection_class is ProjectionClass.SPECULATIVE


def test_provenance_summary_counts():
    eng = CosmicEvolutionEngine(authority=AllowAll())
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0), until_cosmic_time_gyr=1.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=_scenario(),
    )
    summary = eng.provenance_summary(out.final_state)
    assert sum(v for k, v in summary.items() if not k.startswith("state:")) >= 1
    assert any("SIMULATED_DATA" in k for k in summary)


def test_quantities_carry_model_id():
    for state in _evolved_states():
        produced = [q for q in state.quantities.values() if q.model_id]
        assert produced, "engine-updated quantities should cite their model"


def test_future_events_are_never_real_data():
    """All events emitted for projected runs carry projection-safe provenance."""
    eng = CosmicEvolutionEngine(authority=AllowAll())
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0), until_cosmic_time_gyr=14.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=_scenario(),
    )
    for e in out.events:
        assert e.provenance in (
            DataProvenance.SIMULATED_DATA,
            DataProvenance.THEORETICAL_MODEL,
            DataProvenance.SPECULATIVE_MODEL,
        )
