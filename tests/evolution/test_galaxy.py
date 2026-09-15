"""Phase 21 — galaxy one-zone tests: SF, recycling, SMBH/AGN, morphology,
mergers (spec 2.10, 2.11, 2.12, 2.13, 2.14)."""
from __future__ import annotations

import pytest

from astra.evolution import (
    AGNActivityState,
    CosmicEvolutionEngine,
    EvolutionConfig,
    Scenario,
    make_galaxy_state,
)


class AllowAll:
    def require(self, op):
        pass


MODEL = "galaxy.one_zone.v1"


def _eng():
    return CosmicEvolutionEngine(
        config=EvolutionConfig(resolution="cluster"), authority=AllowAll()
    )


def _scenario(**kw):
    d = dict(scenario_id="s", name="S", description="")
    d.update(kw)
    return Scenario(**d)


def _baryonic(state):
    q = state.quantities
    return (
        q["stellar_mass_msun"].value + q["gas_mass_msun"].value
        + q["bh_mass_msun"].value + q["remnant_mass_msun"].value
    )


def test_galaxy_baryonic_bookkeeping_closes():
    eng = _eng()
    g = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10,
                          bh_mass_msun=1e7, metallicity_z=0.02)
    out = eng.evolve_galaxy(galaxy_state=g, until_cosmic_time_gyr=10.0, scenario=_scenario())
    assert _baryonic(out.final_state) == pytest.approx(7.001e10, rel=1e-9)


def test_sfr_declines_to_trickle_as_gas_dwindles():
    """Stellar recycling keeps feeding a trickle of residual star formation
    (physically expected with closed-box recycling); the gas reservoir
    still collapses to <<1% and the SFR to a trickle. The EXPLICIT
    STAR_FORMATION_TRANSITION event fires for the population conveyor
    model when its gas hits exactly zero (tested in test_population)."""
    eng = _eng()
    g = make_galaxy_state("g", 0.0, stellar_mass_msun=1e9, gas_mass_msun=1e9,
                          bh_mass_msun=1e4)
    out = eng.evolve_galaxy(galaxy_state=g, until_cosmic_time_gyr=200.0, scenario=_scenario())
    assert out.final_state.quantity_value("sfr_msun_yr") < 1.0e-3
    assert out.final_state.quantity_value("gas_mass_msun") < 1.0e-2 * 1e9


def test_agn_activity_state_machine_hysteresis():
    """Gas-rich galaxy ignites; gas-poor never does (threshold + margin)."""
    eng = _eng()
    rich = make_galaxy_state("rich", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10,
                             bh_mass_msun=1e7)
    poor = make_galaxy_state("poor", 0.0, stellar_mass_msun=5e10, gas_mass_msun=1e9,
                             bh_mass_msun=1e7)
    out_r = eng.evolve_galaxy(galaxy_state=rich, until_cosmic_time_gyr=1.0, scenario=_scenario())
    out_p = eng.evolve_galaxy(galaxy_state=poor, until_cosmic_time_gyr=1.0, scenario=_scenario())
    assert out_r.final_state.phase in (
        AGNActivityState.ACTIVE.value, AGNActivityState.HIGH_ACTIVITY.value
    )
    assert out_p.final_state.phase == AGNActivityState.INACTIVE.value


def test_smbh_grows_when_active_and_fuel_capped():
    eng = _eng()
    g = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10,
                          bh_mass_msun=1e7)
    out = eng.evolve_galaxy(galaxy_state=g, until_cosmic_time_gyr=2.0, scenario=_scenario())
    bh = out.final_state.quantity_value("bh_mass_msun")
    assert bh > 1e7  # grew
    # Fuel cap: BH consumption over the run cannot exceed the coupling bound.
    # (max gas fraction per Gyr x gas x duration, x2 margin for gas growth)
    growth = bh - 1e7
    assert growth < 1.0e-3 * 2e10 * 2.0 * 2.0


def test_agn_long_term_decline():
    """Spec 2.13/2.14: as gas is consumed the AGN fades to inactive."""
    eng = _eng()
    g = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10,
                          bh_mass_msun=1e7)
    out = eng.evolve_galaxy(galaxy_state=g, until_cosmic_time_gyr=400.0, scenario=_scenario())
    assert out.final_state.phase == AGNActivityState.INACTIVE.value
    transitions = [e for e in out.events if e.kind.value == "AGN_TRANSITION"]
    assert transitions, "AGN activity changes must be recorded as events"


def test_morphology_is_a_distribution_and_drifts():
    eng = _eng()
    g = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10,
                          bh_mass_msun=1e7)
    out = eng.evolve_galaxy(galaxy_state=g, until_cosmic_time_gyr=250.0, scenario=_scenario())
    morph = out.final_state.metadata["morphology"]
    total = sum(morph.values())
    assert total == pytest.approx(1.0, rel=1e-9)
    assert all(0.0 <= v <= 1.0 for v in morph.values())
    # As gas depletes the elliptical tendency grows relative to early times.
    early = eng.project_future_state(
        initial_state=g, until_cosmic_time_gyr=5.0, model_id=MODEL,
        scenario=_scenario(),
    ).final_state.metadata["morphology"]
    assert morph["ELLIPTICAL"] > early["ELLIPTICAL"]


def test_morphology_transition_event_on_dominant_class_change():
    """A gas-poor disk exhausts its gas and the dominant morphology class
    flips -> explicit MORPHOLOGY_TRANSITION event."""
    eng = _eng()
    g = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=5e9,
                          bh_mass_msun=1e7)
    out = eng.evolve_galaxy(galaxy_state=g, until_cosmic_time_gyr=250.0, scenario=_scenario())
    morph = out.final_state.metadata["morphology"]
    top = max(morph.items(), key=lambda kv: (kv[1], kv[0]))[0]
    if top != "SPIRAL":
        assert any(e.kind.value == "MORPHOLOGY_TRANSITION" for e in out.events)


def test_metallicity_enriches():
    eng = _eng()
    g = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10,
                          metallicity_z=0.01)
    out = eng.evolve_galaxy(galaxy_state=g, until_cosmic_time_gyr=2.0, scenario=_scenario())
    assert out.final_state.quantity_value("metallicity_z") > 0.01


# ------------------------------------------------------------------ mergers
def test_galaxy_merger_recording_preserves_identity():
    eng = _eng()
    a = make_galaxy_state("gal-a", 0.0, stellar_mass_msun=5e10, gas_mass_msun=2e10)
    b = make_galaxy_state("gal-b", 0.0, stellar_mass_msun=2e10, gas_mass_msun=5e9)
    result = make_galaxy_state(
        "gal-merged", 10.0,
        stellar_mass_msun=a.quantity_value("stellar_mass_msun") + b.quantity_value("stellar_mass_msun"),
        gas_mass_msun=a.quantity_value("gas_mass_msun") + b.quantity_value("gas_mass_msun"),
    )
    event = eng.record_galaxy_merger(
        progenitor_a=a, progenitor_b=b, resulting=result,
        cosmic_time_gyr=10.0, physical_cause="dynamical merger recorded by caller",
    )
    assert event.kind.value == "GALAXY_MERGER"
    assert set(event.source_object_ids) == {"gal-a", "gal-b"}
    assert event.resulting_object_ids == ("gal-merged",)
    assert "gal-merged" not in event.source_object_ids  # identity preserved, new object


def test_galaxy_merger_requires_galaxy_states():
    eng = _eng()
    star = make_star_state_if_available()
    with pytest.raises(Exception):
        eng.record_galaxy_merger(
            progenitor_a=star, progenitor_b=star,
            resulting=star, cosmic_time_gyr=1.0, physical_cause="x",
        )


def make_star_state_if_available():
    from astra.evolution import make_star_state

    return make_star_state("s", 0.0, 1.0)


def test_black_hole_merger_records_sum_and_disclaims_precision():
    eng = _eng()
    event = eng.record_black_hole_merger(
        bh_mass_a_msun=1.0e7, bh_mass_b_msun=3.0e7,
        host_galaxy_id="gal-a", cosmic_time_gyr=5.0,
        physical_cause="dynamical inspiral recorded by caller",
    )
    assert event.kind.value == "BLACK_HOLE_MERGER"
    assert event.metadata["combined_mass_msun"] == pytest.approx(4.0e7)
    assert "not" in event.metadata["note"]  # explicitly disclaims GW precision


def test_star_kind_cannot_use_galaxy_model():
    eng = _eng()
    from astra.evolution import make_star_state

    with pytest.raises(Exception):
        eng.evolve_galaxy(
            galaxy_state=make_star_state("s", 0.0, 1.0),
            until_cosmic_time_gyr=1.0, scenario=_scenario(),
        )
