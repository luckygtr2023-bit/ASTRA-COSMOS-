"""Phase 21 — persistence round-trip tests (repository convention)."""
from __future__ import annotations

import pytest

from astra.celestial.provenance import DataProvenance

from astra.evolution import (
    Quantity,
    CosmicEvolutionEngine,
    DictPersistenceHook,
    EvolutionConfig,
    EvolutionLedger,
    EvolutionState,
    MetallicityHistory,
    ProjectionClass,
    Scenario,
    ScenarioRegistry,
    StarFormationHistory,
    make_population_state,
    make_star_state,
)
from astra.evolution.persistence import (
    event_from_dict,
    event_to_dict,
    metallicity_history_from_dict,
    metallicity_history_to_dict,
    population_state_from_dict,
    population_state_to_dict,
    quantity_from_dict,
    quantity_to_dict,
    sfh_from_dict,
    sfh_to_dict,
    state_from_dict,
    state_to_dict,
)
from astra.evolution.provenance import ProjectionClass as PC


class AllowAll:
    def require(self, op):
        pass


def test_quantity_round_trip():
    q = Quantity(value=1.5, unit="Msun", provenance=DataProvenance.SIMULATED_DATA,
                 uncertainty=0.1, model_id="m", note="n")
    d = quantity_to_dict(q)
    q2 = quantity_from_dict(d)
    assert q2 == q
    assert quantity_to_dict(q2) == d


def test_state_round_trip():
    s = make_population_state("pop", 1.5, gas_mass_msun=1e10, sfr_msun_yr=1.0,
                              metallicity_z=0.02, parent_object_id="gal")
    d = state_to_dict(s)
    s2 = state_from_dict(d)
    assert state_to_dict(s2) == d
    assert s2.object_id == "pop"
    assert s2.projection_class is ProjectionClass.NONE


def test_state_with_cohorts_round_trip():
    from astra.evolution import EvolutionConfig

    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="population"), authority=AllowAll()
    )
    out = eng.evolve_object(
        initial_state=make_population_state("pop", 0.0, gas_mass_msun=1e10,
                                            sfr_msun_yr=2.0),
        until_cosmic_time_gyr=2.0, model_id="population.conveyor.v1",
        scenario=Scenario(scenario_id="s", name="S", description=""),
    )
    d = state_to_dict(out.final_state)
    s2 = state_from_dict(d)
    assert state_to_dict(s2) == d
    # cohorts survive as JSON-safe lists
    import json

    json.dumps(d)  # must not raise


def test_event_round_trip():
    from astra.evolution import EvolutionEvent, EvolutionEventKind

    e = EvolutionEvent(
        event_id="x1", kind=EvolutionEventKind.EPOCH_TRANSITION, cosmic_time_gyr=9.0,
        source_object_ids=("o",), resulting_object_ids=(),
        physical_cause="c", model_id="m", provenance=DataProvenance.SIMULATED_DATA,
        causal_parent_event_id="x0", metadata={"from": "A", "to": "B"},
    )
    d = event_to_dict(e)
    assert event_from_dict(d) == e


def test_scenario_round_trip():
    from astra.evolution import EpochBoundaries

    sc = Scenario(
        scenario_id="s1", name="S1", description="d",
        cosmological_parameters={"h_only_setting": 0.7},
        evolution_parameters={"gas_depletion_time_gyr": Quantity(value=2.0, unit="Gyr")},
        provenance=DataProvenance.SIMULATED_DATA,
        model_version="astra.evolution.v1",
        projection_class=PC.HYPOTHETICAL,
        epoch_boundaries=EpochBoundaries(degenerate_remnant_fraction=0.4),
        present_epoch_gyr=13.8,
    )
    d = sc.to_dict()
    sc2 = Scenario.from_dict(d)
    assert sc2 == sc
    assert Scenario.from_dict(sc2.to_dict()) == sc2


def test_sfh_and_metallicity_history_round_trip():
    sfh = StarFormationHistory("o", ((0.0, 1.0), (1.0, 2.0)), "m")
    d = sfh_to_dict(sfh)
    assert sfh_from_dict(d) == sfh
    mh = MetallicityHistory("o", ((0.0, 0.01),), "m")
    d2 = metallicity_history_to_dict(mh)
    assert metallicity_history_from_dict(d2) == mh


def test_population_state_summary_round_trip():
    from astra.evolution import PopulationState

    state = make_population_state("p", 0.0, gas_mass_msun=1e10, sfr_msun_yr=1.0)
    summary = PopulationState.from_evolution_state(state)
    d = population_state_to_dict(summary)
    import json

    json.dumps(d)
    summary2 = population_state_from_dict(d)
    assert population_state_to_dict(summary2) == d
    assert summary2.population_id == "p"


def test_config_round_trip():
    cfg = EvolutionConfig(resolution="galaxy")
    d = cfg.to_dict()
    cfg2 = EvolutionConfig.from_dict(d)
    assert cfg2 == cfg
    assert cfg2.to_dict() == d


def test_engine_save_and_restore_ledger():
    hook = DictPersistenceHook()
    eng = CosmicEvolutionEngine(authority=AllowAll(), persistence=hook)
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0), until_cosmic_time_gyr=14.0,
        model_id="stellar.single_star_lifecycle.v1",
        scenario=Scenario(scenario_id="s", name="S", description=""),
    )
    eng.save("snap-1")

    eng2 = CosmicEvolutionEngine(authority=AllowAll(), persistence=hook)
    payload = hook.load("snap-1")
    eng2.restore_ledger(payload)
    assert len(eng2.history()) == len(eng.history())
    assert [e.event_id for e in eng2.history()] == [e.event_id for e in eng.history()]
    assert eng2.validate_history() == eng.validate_history()
    # restored ledger still causal
    eng2.validate_history()


def test_ledger_round_trip_direct():
    ledger = EvolutionLedger()
    ledger.record_event(event_from_dict(event_to_dict(
        __import__("astra.evolution", fromlist=["EvolutionEvent"]).EvolutionEvent(
            event_id="e1", kind=__import__(
                "astra.evolution", fromlist=["EvolutionEventKind"]).EvolutionEventKind.CUSTOM,
            cosmic_time_gyr=1.0, source_object_ids=("a",), resulting_object_ids=(),
            physical_cause="x", model_id="m",
        )
    )))
    d = ledger.to_dict()
    ledger2 = EvolutionLedger()
    ledger2.load_dict(d)
    assert ledger2.events() == ledger.events()
    with pytest.raises(Exception):
        ledger2.load_dict(d)  # loading into non-empty ledger refused


def test_scenario_registry_persistence():
    reg = ScenarioRegistry()
    reg.register(Scenario(scenario_id="b", name="B", description=""))
    reg.register(Scenario(scenario_id="a", name="A", description=""))
    assert reg.list_ids() == ("a", "b")
    d = reg.get("a").to_dict()
    assert Scenario.from_dict(d).scenario_id == "a"
