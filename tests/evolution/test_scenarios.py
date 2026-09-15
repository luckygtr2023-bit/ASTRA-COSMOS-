"""Phase 21 — scenario registry + epoch advance + compare tests (spec 2.38, 2.41)."""
from __future__ import annotations

import pytest

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionConfig,
    Quantity,
    Scenario,
    ScenarioRegistry,
    EvolutionValidationError,
    make_galaxy_state,
    make_population_state,
    make_star_state,
)


class AllowAll:
    def require(self, op):
        pass


def test_registry_deterministic_and_rejects_duplicates():
    reg = ScenarioRegistry()
    reg.register(Scenario(scenario_id="z", name="Z", description=""))
    reg.register(Scenario(scenario_id="a", name="A", description=""))
    assert reg.list_ids() == ("a", "z")
    with pytest.raises(EvolutionValidationError):
        reg.register(Scenario(scenario_id="a", name="A2", description=""))


def test_scenario_validates_parameters():
    with pytest.raises(Exception):
        Scenario(scenario_id="", name="N", description="")
    with pytest.raises(Exception):
        Scenario(scenario_id="s", name="N", description="",
                 cosmological_parameters={"bad": float("nan")})
    with pytest.raises(Exception):
        Scenario(scenario_id="s", name="N", description="",
                 evolution_parameters={"x": 1.0})  # must be Quantity


def test_scenario_registry_round_trip():
    from astra.evolution import EpochBoundaries

    reg = ScenarioRegistry()
    sc = Scenario(
        scenario_id="alt", name="Alt", description="alternative cosmology setting",
        cosmological_parameters={"w_setting": -1.0},
        projection_class= __import__(
            "astra.evolution", fromlist=["ProjectionClass"]).ProjectionClass.HYPOTHETICAL,
        epoch_boundaries=EpochBoundaries(black_hole_dominated_fraction=0.3),
    )
    reg.register(sc)
    sc2 = Scenario.from_dict(reg.get("alt").to_dict())
    assert sc2 == sc


def test_advance_cosmic_epoch_report():
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="cluster"), authority=AllowAll()
    )
    sc = Scenario(scenario_id="s", name="S", description="")
    states = [
        make_star_state("s1", 0.0, 2.0),
        make_galaxy_state("g1", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10),
    ]
    report = eng.advance_cosmic_epoch(
        states=states, until_cosmic_time_gyr=10.0, scenario=sc,
        model_for_kind={
            "STAR": "stellar.single_star_lifecycle.v1",
            "GALAXY": "galaxy.one_zone.v1",
        },
    )
    ids = [sid for sid, _ in report.outcomes]
    assert ids == ["g1", "s1"]  # deterministic sorted order
    for _, outcome in report.outcomes:
        assert outcome.final_state.cosmic_time_gyr == pytest.approx(10.0)
    assert report.ensemble_epoch_before in ("UNKNOWN", "STELLIFEROUS", "DECLINING_STAR_FORMATION")


def test_advance_epoch_requires_model_for_every_kind():
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="cluster"), authority=AllowAll()
    )
    sc = Scenario(scenario_id="s", name="S", description="")
    with pytest.raises(EvolutionValidationError):
        eng.advance_cosmic_epoch(
            states=[make_star_state("s1", 0.0, 1.0)], until_cosmic_time_gyr=1.0,
            scenario=sc, model_for_kind={},
        )


def test_compare_scenarios_reports_deltas_and_honesty_note():
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="galaxy"), authority=AllowAll()
    )
    gal = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10)
    hi = Scenario(
        scenario_id="hi", name="High SF", description="",
        evolution_parameters={"gas_depletion_time_gyr": Quantity(value=0.5, unit="Gyr")},
    )
    lo = Scenario(
        scenario_id="lo", name="Low SF", description="",
        evolution_parameters={"gas_depletion_time_gyr": Quantity(value=20.0, unit="Gyr")},
    )
    comp = eng.compare_scenarios(
        initial_state=gal, until_cosmic_time_gyr=3.0,
        model_id="galaxy.one_zone.v1", scenario_a=hi, scenario_b=lo,
    )
    assert comp.scenario_a_id == "hi" and comp.scenario_b_id == "lo"
    deltas = {k: d for k, _, _, d in comp.quantity_deltas}
    assert deltas["gas_mass_msun"] != 0.0
    assert "not observational" in comp.note


def test_high_sf_scenario_forms_more_stars():
    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="galaxy"), authority=AllowAll()
    )
    gal = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10)
    hi = Scenario(
        scenario_id="hi", name="High SF", description="",
        evolution_parameters={"gas_depletion_time_gyr": Quantity(value=0.5, unit="Gyr")},
    )
    # Early in the run the shorter depletion time yields the higher SFR...
    early_hi = eng.project_future_state(
        initial_state=gal, until_cosmic_time_gyr=0.5, model_id="galaxy.one_zone.v1", scenario=hi,
    )
    early_base = eng.project_future_state(
        initial_state=gal, until_cosmic_time_gyr=0.5, model_id="galaxy.one_zone.v1",
        scenario=Scenario(scenario_id="base", name="B", description=""),
    )
    assert early_hi.final_state.quantity_value("sfr_msun_yr") > early_base.final_state.quantity_value("sfr_msun_yr")
    # ...and late in the run it has burned out and fallen below the baseline.
    late_hi = eng.project_future_state(
        initial_state=gal, until_cosmic_time_gyr=4.0, model_id="galaxy.one_zone.v1", scenario=hi,
    )
    late_base = eng.project_future_state(
        initial_state=gal, until_cosmic_time_gyr=4.0, model_id="galaxy.one_zone.v1",
        scenario=Scenario(scenario_id="base", name="B", description=""),
    )
    assert late_hi.final_state.quantity_value("sfr_msun_yr") < late_base.final_state.quantity_value("sfr_msun_yr")
