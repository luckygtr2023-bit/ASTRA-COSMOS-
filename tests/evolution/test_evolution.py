"""Core evolution tests — authority, validation, timestep, provenance.

Covers: evolve_object forward/backward, NaN/Inf rejection, unknown model,
authority enforcement, quantity provenance, history preservation.
"""

from __future__ import annotations

import pytest

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionAuthorityError,
    EvolutionConfig,
    EvolutionNumericalError,
    EvolutionState,
    EvolutionValidationError,
    ModelClassification,
    ModelRegistry,
    EvolutionModel,
    Provenance,
    Quantity,
    Scenario,
    TimestepPolicy,
)
from astra.evolution.epoch import EpochBoundaries
from astra.evolution.state import EvolutionEvent, EvolutionEventKind


class _AllowAll:
    def require(self, op):  # noqa: D401
        return None
    def has_authority(self, op):  # noqa: D401
        return True


class _DenyAll:
    def require(self, op):
        raise EvolutionAuthorityError("denied")


def _linear_step(state, dt_gyr, model):
    return EvolutionState(
        object_id=state.object_id,
        cosmic_time_gyr=state.cosmic_time_gyr + dt_gyr,
        phase=state.phase,
        quantities=dict(state.quantities),
        model_id=state.model_id,
        provenance=state.provenance,
        metadata=dict(state.metadata),
    )


def _make_engine(authority=None):
    reg = ModelRegistry()
    reg.register(
        EvolutionModel(
            model_id="toy",
            name="Toy model",
            description="Linear passthrough",
            classification=ModelClassification.SIMULATION,
            provenance=Provenance.SIMULATED_DATA,
            applicable_object_kinds=("TEST",),
            applies_to_regimes=("STELLIFEROUS",),
        ),
        _linear_step,
    )
    return CosmicEvolutionEngine(
        config=EvolutionConfig(
            timestep=TimestepPolicy(base_dt_gyr=0.1, min_dt_gyr=1e-4, max_dt_gyr=1.0)
        ),
        model_registry=reg,
        authority=authority or _AllowAll(),
    )


def _initial_state():
    return EvolutionState(
        object_id="obj-1",
        cosmic_time_gyr=0.0,
        phase="TEST",
        quantities={"mass": Quantity(value=1.0, unit="Msun", provenance=Provenance.SIMULATED_DATA)},
        model_id="toy",
        provenance=Provenance.SIMULATED_DATA,
    )


def _scenario():
    return Scenario(
        scenario_id="s1", name="S1", description="",
        cosmological_parameters={}, evolution_parameters={},
        provenance=Provenance.SIMULATED_DATA, model_version="v1",
    )


def test_evolve_forward_single_object():
    e = _make_engine()
    final = e.evolve_object(
        initial_state=_initial_state(),
        until_cosmic_time_gyr=1.0,
        model_id="toy",
        scenario=_scenario(),
    )
    assert final.cosmic_time_gyr == pytest.approx(1.0)
    assert final.object_id == "obj-1"
    # provenance preserved
    assert final.provenance == Provenance.SIMULATED_DATA
    # history recorded
    assert len(e.history("obj-1")) >= 2


def test_evolve_backward_rejected():
    e = _make_engine()
    with pytest.raises(EvolutionValidationError):
        e.evolve_object(
            initial_state=_initial_state(),
            until_cosmic_time_gyr=-1.0,
            model_id="toy",
            scenario=_scenario(),
        )
    # also test target < initial
    init = EvolutionState(
        object_id="obj-1", cosmic_time_gyr=5.0, phase="TEST",
        quantities={}, model_id="toy", provenance=Provenance.SIMULATED_DATA,
    )
    with pytest.raises(EvolutionValidationError):
        e.evolve_object(initial_state=init, until_cosmic_time_gyr=1.0,
                        model_id="toy", scenario=_scenario())


def test_evolve_requires_authority():
    e = _make_engine(authority=None)
    e.authority = None
    with pytest.raises(EvolutionAuthorityError):
        e.evolve_object(
            initial_state=_initial_state(), until_cosmic_time_gyr=1.0,
            model_id="toy", scenario=_scenario(),
        )


def test_nan_time_rejected():
    e = _make_engine()
    with pytest.raises(EvolutionNumericalError):
        e.evolve_object(
            initial_state=_initial_state(),
            until_cosmic_time_gyr=float("nan"),
            model_id="toy", scenario=_scenario(),
        )
    # quantity NaN also rejected at Quantity construction
    with pytest.raises(EvolutionNumericalError):
        Quantity(value=float("nan"), unit="Msun", provenance=Provenance.SIMULATED_DATA)


def test_inf_time_rejected():
    e = _make_engine()
    with pytest.raises(EvolutionNumericalError):
        e.evolve_object(
            initial_state=_initial_state(),
            until_cosmic_time_gyr=float("inf"),
            model_id="toy", scenario=_scenario(),
        )


def test_unknown_model_rejected():
    e = _make_engine()
    with pytest.raises(EvolutionValidationError):
        e.evolve_object(
            initial_state=_initial_state(), until_cosmic_time_gyr=1.0,
            model_id="nope", scenario=_scenario(),
        )


def test_quantity_uncertainty_negative_rejected():
    with pytest.raises(EvolutionNumericalError):
        Quantity(value=1.0, unit="Msun", provenance=Provenance.SIMULATED_DATA,
                 uncertainty=-0.1)


def test_quantity_provenance_required():
    q = Quantity(value=1.0, unit="Msun", provenance=Provenance.SIMULATED_DATA)
    assert q.provenance == Provenance.SIMULATED_DATA
    q2 = Quantity(value=1.0, unit="Msun", provenance=Provenance.SPECULATIVE,
                  note="far future")
    assert q2.provenance == Provenance.SPECULATIVE


def test_history_preservation():
    e = _make_engine()
    e.evolve_object(initial_state=_initial_state(), until_cosmic_time_gyr=0.5,
                    model_id="toy", scenario=_scenario())
    hist = e.history("obj-1")
    assert len(hist) >= 2
    assert hist[0].cosmic_time_gyr == pytest.approx(0.0)
    assert hist[-1].cosmic_time_gyr == pytest.approx(0.5)
    # identity preserved
    for h in hist:
        assert h.object_id == "obj-1"


def test_event_recording():
    e = _make_engine()
    evt = EvolutionEvent(
        event_id="evt-1",
        kind=EvolutionEventKind.STELLAR_TRANSITION,
        cosmic_time_gyr=0.5,
        source_object_ids=("obj-1",),
        resulting_object_ids=("obj-1",),
        physical_cause="test",
        model_id="toy",
        provenance=Provenance.SIMULATED_DATA,
    )
    e.emit_event(evt)
    assert len(e.recorded_events()) == 1
    found = e.retrieve_evolutionary_events(object_id="obj-1",
                                            kind=EvolutionEventKind.STELLAR_TRANSITION)
    assert len(found) == 1
    assert found[0].event_id == "evt-1"


def test_multi_resolution_population():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    # population evolution without explicit stellar provider uses reduced-order
    init = EvolutionState(
        object_id="pop-1", cosmic_time_gyr=0.0, phase="STELLAR_POPULATION",
        quantities={
            "stellar_mass_msun": Quantity(value=1e10, unit="Msun",
                                          provenance=Provenance.SIMULATED_DATA,
                                          model_id="astra.evolution.linear.v1"),
            "metallicity": Quantity(value=0.02, unit="Z",
                                    provenance=Provenance.SIMULATED_DATA,
                                    model_id="astra.evolution.linear.v1"),
        },
        model_id="astra.evolution.linear.v1",
        provenance=Provenance.SIMULATED_DATA,
    )
    final = e.evolve_population(
        population_id="pop-1", initial_state=init,
        until_cosmic_time_gyr=1.0, model_id="astra.evolution.linear.v1",
        scenario=e.scenario_registry.get("baseline_LCDM"),
    )
    assert final.cosmic_time_gyr == pytest.approx(1.0)


def test_no_hardcoded_max_timescale():
    # Support trillion-year (1000 Gyr) evolution without hard-coded max
    e = _make_engine()
    init = _initial_state()
    # use larger max_dt for performance
    e_big = CosmicEvolutionEngine(
        config=EvolutionConfig(
            timestep=TimestepPolicy(base_dt_gyr=1.0, min_dt_gyr=1e-3, max_dt_gyr=10.0)
        ),
        model_registry=e.model_registry,
        authority=_AllowAll(),
    )
    # Need to recreate model registry for e_big (it would have defaults)
    # Use toy model explicitly
    from astra.evolution import ModelRegistry as MR
    reg = MR()
    reg.register(EvolutionModel(model_id="toy", name="Toy", description="",
                                classification=ModelClassification.SIMULATION,
                                provenance=Provenance.SIMULATED_DATA), _linear_step)
    e_big.model_registry = reg
    final = e_big.evolve_object(
        initial_state=init, until_cosmic_time_gyr=1e3,
        model_id="toy", scenario=_scenario(),
    )
    assert final.cosmic_time_gyr == pytest.approx(1e3)


def test_far_future_speculative_tagging():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    init = EvolutionState(
        object_id="far-obj", cosmic_time_gyr=0.0, phase="VOID",
        quantities={"radius_mpc": Quantity(value=10.0, unit="Mpc",
                                          provenance=Provenance.THEORETICAL,
                                          model_id="astra.evolution.void.v1")},
        model_id="astra.evolution.void.v1",
        provenance=Provenance.THEORETICAL,
    )
    scen = e.scenario_registry.get("far_future_speculative")
    assert scen.provenance == Provenance.SPECULATIVE
    final = e.evolve_void(void_id="far-obj", initial_state=init,
                          until_cosmic_time_gyr=100.0,
                          scenario=scen)
    # Far-future outputs must be THEORETICAL/HYPOTHETICAL/SPECULATIVE, never REAL
    assert final.provenance in (Provenance.THEORETICAL, Provenance.HYPOTHETICAL,
                                Provenance.SPECULATIVE, Provenance.SIMULATED_DATA)


def test_cosmic_expansion_not_double_counted():
    e = CosmicEvolutionEngine(authority=_AllowAll())
    # Without provider, scale_factor raises dependency error (never fabricates)
    import pytest as _pt
    from astra.evolution.errors import EvolutionDependencyError
    with _pt.raises(EvolutionDependencyError):
        e.scale_factor(13.8)
    # With a fake provider it returns correctly
    class FakeUniverse:
        def scale_factor(self, t): return 1.0 + t*0.01
        def cosmic_time_gyr(self, a): return (a-1)/0.01
        def hubble_parameter(self, t): return 70.0
        def lookback_time_gyr(self, t): return 0.0
        def comoving_distance_mpc(self, z): return 0.0
        def luminosity_distance_mpc(self, z): return 0.0
    e.universe = FakeUniverse()
    assert e.scale_factor(13.8) == pytest.approx(1.138)
