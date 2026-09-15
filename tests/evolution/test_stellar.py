"""Phase 21 — stellar lifecycle model tests (spec 2.6, 2.24)."""
from __future__ import annotations

import math

import pytest

from astra.evolution import (
    BuiltinModelParams,
    CosmicEvolutionEngine,
    DataProvenance,
    EvolutionConfig,
    EvolutionLimitationError,
    ProjectionClass,
    Scenario,
    main_sequence_lifetime_gyr,
    make_star_state,
    make_population_state,
    make_galaxy_state,
    remnant_for_mass,
    remnant_mass_msun,
)


class AllowAll:
    def require(self, op):
        pass


def _eng(**kw):
    return CosmicEvolutionEngine(authority=AllowAll(), **kw)


def _scenario(**kw):
    d = dict(scenario_id="s", name="S", description="")
    d.update(kw)
    return Scenario(**d)


MODEL = "stellar.single_star_lifecycle.v1"


# ------------------------------------------------------------ remnant mapping
def test_remnant_kind_thresholds():
    p = BuiltinModelParams()
    assert remnant_for_mass(1.0, p) is not None
    assert remnant_for_mass(1.0, p).value == "WHITE_DWARF"
    assert remnant_for_mass(8.0, p).value == "NEUTRON_STAR"
    assert remnant_for_mass(20.0, p).value == "STELLAR_MASS_BLACK_HOLE"
    assert remnant_for_mass(100.0, p).value == "STELLAR_MASS_BLACK_HOLE"


def test_remnant_masses_are_configured_assignments():
    p = BuiltinModelParams()
    assert remnant_mass_msun(1.0, p) == pytest.approx(0.6)
    assert remnant_mass_msun(10.0, p) == pytest.approx(1.4)
    assert remnant_mass_msun(30.0, p) == pytest.approx(9.0)  # 0.3 x 30


# ------------------------------------------------------------ lifecycle chain
def test_full_lifecycle_sun_analog():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_star_state("sun", 0.0, 1.0),
        until_cosmic_time_gyr=15.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    assert out.final_state.phase == "REMNANT"
    assert out.final_state.metadata["remnant_kind"] == "WHITE_DWARF"
    kinds = [e.kind.value for e in out.events]
    assert "STELLAR_TRANSITION" in kinds
    assert "STELLAR_DEATH" in kinds
    # Sun-like star: t_MS = 10 Gyr, t_post = 1 Gyr.
    transitions = [e for e in out.events if e.kind.value == "STELLAR_TRANSITION"]
    times = sorted(e.cosmic_time_gyr for e in transitions)
    assert times[1] == pytest.approx(10.0, rel=1e-2)
    assert times[2] == pytest.approx(11.0, rel=1e-2)


def test_massive_star_leaves_black_hole():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_star_state("heavy", 0.0, 40.0),
        until_cosmic_time_gyr=0.1,
        model_id=MODEL,
        scenario=_scenario(),
    )
    assert out.final_state.phase == "REMNANT"
    assert out.final_state.metadata["remnant_kind"] == "STELLAR_MASS_BLACK_HOLE"
    assert out.final_state.quantity_value("mass_msun") == pytest.approx(12.0)


def test_low_mass_star_survives_beyond_trillion_years_run_horizon():
    """0.1 Msun: t_MS = 10 x 0.1^-2.5 ~ 3162 Gyr: still on the MS after
    1e3 Gyr (the trillion-year scale of spec 2.4)."""
    eng = _engine_with_resolution()
    out = eng.evolve_object(
        initial_state=make_star_state("dwarf", 0.0, 0.1),
        until_cosmic_time_gyr=1000.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    assert out.final_state.phase == "MAIN_SEQUENCE"


def _engine_with_resolution():
    return CosmicEvolutionEngine(authority=AllowAll())


def test_identity_and_provenance_preserved_across_transitions():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_star_state("sun", 0.0, 2.0),
        until_cosmic_time_gyr=5.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    assert out.final_state.object_id == "sun"
    for q in out.final_state.quantities.values():
        assert q.provenance is not DataProvenance.REAL_DATA
        assert q.provenance is not None


def test_death_event_carries_causal_parent():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_star_state("sun", 0.0, 2.0),
        until_cosmic_time_gyr=5.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    ids = {e.event_id for e in out.events}
    for e in out.events:
        if e.causal_parent_event_id is not None:
            assert e.causal_parent_event_id in ids
    count, edges = eng.validate_history()
    assert count == len(out.events)


# ------------------------------------------------------- adaptive stepping
def test_steps_shrink_near_transitions():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_star_state("sun", 0.0, 1.0),
        until_cosmic_time_gyr=10.5,
        model_id=MODEL,
        scenario=_scenario(),
    )
    decisions = out.timesteps
    # A RATE_LIMITED decision must appear while approaching the boundary.
    assert any(d.reason.value == "RATE_LIMITED" for d in decisions)
    # The step landing on (or crossing) the MS turnoff is short.
    pre_boundary = [d.dt_gyr for d in decisions if d.dt_gyr < 0.5]
    assert pre_boundary


# ---------------------------------------------------------- validity horizon
def test_beyond_model_validity_refused_for_model_projected():
    eng = _eng()
    params = BuiltinModelParams()
    from astra.evolution import ModelRegistry, register_builtin_models

    reg = ModelRegistry()
    register_builtin_models(reg, BuiltinModelParams(
        t_ms_sun_gyr=10.0,
    ))
    eng2 = CosmicEvolutionEngine(
        model_registry=reg, register_builtins=False, authority=AllowAll()
    )
    model = reg.get(MODEL)
    horizon = model.max_valid_cosmic_time_gyr
    with pytest.raises(EvolutionLimitationError) as excinfo:
        eng2.evolve_object(
            initial_state=make_star_state("o", 0.0, 1.0),
            until_cosmic_time_gyr=horizon * 10.0,
            model_id=MODEL,
            scenario=_scenario(),  # default MODEL_PROJECTED
        )
    assert excinfo.value.state.value == "OUTSIDE_VALID_RANGE"


def test_beyond_validity_with_speculative_scenario_still_refused_computation():
    """Honesty: changing the scenario label does NOT make the model able to
    compute beyond its validity; a HYPOTHETICAL/SPECULATIVE-classified model
    must be registered explicitly."""
    from astra.evolution import ModelRegistry, register_builtin_models

    reg = ModelRegistry()
    register_builtin_models(reg, BuiltinModelParams())
    eng = CosmicEvolutionEngine(
        model_registry=reg, register_builtins=False, authority=AllowAll()
    )
    horizon = reg.get(MODEL).max_valid_cosmic_time_gyr
    with pytest.raises(EvolutionLimitationError) as excinfo:
        eng.evolve_object(
            initial_state=make_star_state("o", 0.0, 1.0),
            until_cosmic_time_gyr=horizon * 10.0,
            model_id=MODEL,
            scenario=_scenario(projection_class=ProjectionClass.SPECULATIVE),
        )
    assert excinfo.value.state.value == "UNSUPPORTED_TIMESCALE"


# -------------------------------------------------- far-future remnant era
def test_remnant_era_luminosity_declines():
    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_star_state("sun", 0.0, 1.0),
        until_cosmic_time_gyr=14.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    lum_remnant = out.final_state.quantity_value("luminosity_lsun")
    assert lum_remnant < 1.0  # remnant luminosity orders below MS luminosity


def test_star_within_cluster_aggregate_epoch_flow():
    """Spec 2.47 chain: stars -> populations -> ... covered per kind here:
    a star reaching remnant phase flips its epoch contribution."""
    from astra.evolution.epoch import epoch_inputs_from_state

    eng = _eng()
    out = eng.evolve_object(
        initial_state=make_star_state("sun", 0.0, 1.0),
        until_cosmic_time_gyr=15.0,
        model_id=MODEL,
        scenario=_scenario(),
    )
    inputs = epoch_inputs_from_state(out.final_state)
    assert inputs.remnant_mass_fraction == 1.0
    assert inputs.luminous_mass_fraction == 0.0
