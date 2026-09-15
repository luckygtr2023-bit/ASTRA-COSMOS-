"""Phase 21 — core engine tests: validation, authority, budgets, scheduling.

UNVERIFIED-scaffold tests were reconciled against the real API: evolve
calls return EvolutionOutcome records; authority is fail-closed.
"""
from __future__ import annotations

import math

import pytest

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionAuthorityError,
    EvolutionConfig,
    EvolutionEvent,
    EvolutionEventKind,
    EvolutionLimitationError,
    EvolutionNumericalError,
    EvolutionOutcome,
    EvolutionState,
    EvolutionValidationError,
    ModelClassification,
    ModelRegistry,
    ProvenanceTag,
    DataProvenance,
    ProjectionClass,
    Scenario,
    STELLAR_MODEL_ID,
    make_star_state,
)


class AllowAll:
    def __init__(self, ops=None):
        self.ops = list(ops) if ops is not None else None
        self.requested = []

    def require(self, operation: str) -> None:
        self.requested.append(operation)
        if self.ops is not None and operation not in self.ops:
            raise EvolutionAuthorityError(f"denied: {operation}", operation=operation)


class DenyAll:
    def require(self, operation: str) -> None:
        raise EvolutionAuthorityError("denied", operation=operation)


def _scenario(**kw):
    defaults = dict(
        scenario_id="s-base",
        name="Baseline",
        description="test scenario",
    )
    defaults.update(kw)
    return Scenario(**defaults)


def _engine(**kw):
    return CosmicEvolutionEngine(authority=AllowAll(), **kw)


# ---------------------------------------------------------------- happy path
def test_evolve_forward_returns_outcome():
    eng = _engine()
    out = eng.evolve_object(
        initial_state=make_star_state("o-1", 0.0, 1.0),
        until_cosmic_time_gyr=1.0,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
    )
    assert isinstance(out, EvolutionOutcome)
    assert out.final_state.cosmic_time_gyr == pytest.approx(1.0)
    assert out.final_state.object_id == "o-1"
    assert len(out.timesteps) >= 1


def test_authority_operation_named_per_mutation():
    auth = AllowAll()
    eng = CosmicEvolutionEngine(authority=auth)
    eng.evolve_object(
        initial_state=make_star_state("o-1", 0.0, 1.0),
        until_cosmic_time_gyr=0.5,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
    )
    assert auth.requested == ["evolution.evolve"]


def test_missing_authority_fails_closed():
    eng = CosmicEvolutionEngine()  # no authority injected
    with pytest.raises(EvolutionAuthorityError):
        eng.evolve_object(
            initial_state=make_star_state("o-1", 0.0, 1.0),
            until_cosmic_time_gyr=1.0,
            model_id=STELLAR_MODEL_ID,
            scenario=_scenario(),
        )


def test_denying_authority_blocks_mutation():
    eng = CosmicEvolutionEngine(authority=DenyAll())
    with pytest.raises(EvolutionAuthorityError):
        eng.evolve_object(
            initial_state=make_star_state("o-1", 0.0, 1.0),
            until_cosmic_time_gyr=1.0,
            model_id=STELLAR_MODEL_ID,
            scenario=_scenario(),
        )


# ------------------------------------------------------------- time validation
@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_target_time_rejected(bad):
    eng = _engine()
    with pytest.raises(EvolutionNumericalError):
        eng.evolve_object(
            initial_state=make_star_state("o-1", 0.0, 1.0),
            until_cosmic_time_gyr=bad,
            model_id=STELLAR_MODEL_ID,
            scenario=_scenario(),
        )


def test_backward_evolution_rejected():
    eng = _engine()
    with pytest.raises(EvolutionValidationError):
        eng.evolve_object(
            initial_state=make_star_state("o-1", 5.0, 1.0),
            until_cosmic_time_gyr=1.0,
            model_id=STELLAR_MODEL_ID,
            scenario=_scenario(),
        )


def test_zero_interval_is_noop():
    eng = _engine()
    out = eng.evolve_object(
        initial_state=make_star_state("o-1", 3.0, 1.0, age_gyr=1.0),
        until_cosmic_time_gyr=3.0,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
    )
    assert out.final_state.cosmic_time_gyr == 3.0
    assert out.timesteps == ()


# ------------------------------------------------------------ model resolution
def test_unknown_model_rejected():
    eng = _engine()
    with pytest.raises(EvolutionValidationError):
        eng.evolve_object(
            initial_state=make_star_state("o-1", 0.0, 1.0),
            until_cosmic_time_gyr=1.0,
            model_id="no.such.model",
            scenario=_scenario(),
        )


def test_model_kind_mismatch_is_limitation():
    eng = _engine(config=EvolutionConfig(resolution="population"))
    with pytest.raises(EvolutionLimitationError) as excinfo:
        eng.evolve_object(
            initial_state=make_star_state("o-1", 0.0, 1.0),
            until_cosmic_time_gyr=1.0,
            model_id="population.conveyor.v1",
            scenario=_scenario(),
        )
    assert excinfo.value.state.value == "INCOMPATIBLE_MODEL"


def test_scenario_conflict_detected():
    eng = _engine()
    eng.evolve_object(
        initial_state=make_star_state("o-1", 0.0, 1.0),
        until_cosmic_time_gyr=0.1,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
    )
    with pytest.raises(EvolutionValidationError):
        eng.evolve_object(
            initial_state=make_star_state("o-2", 0.0, 1.0),
            until_cosmic_time_gyr=0.1,
            model_id=STELLAR_MODEL_ID,
            scenario=_scenario(name="Different definition, same id"),
        )


def test_scenario_auto_registered_deterministically():
    eng = _engine()
    sc = _scenario()
    eng.evolve_object(
        initial_state=make_star_state("o-1", 0.0, 1.0),
        until_cosmic_time_gyr=0.1,
        model_id=STELLAR_MODEL_ID,
        scenario=sc,
    )
    assert eng.scenario_registry.list_ids() == ("s-base",)


# ------------------------------------------------------------- invalid states
def test_nan_initial_state_time_rejected():
    with pytest.raises(Exception):
        make_star_state("o-1", float("nan"), 1.0)


def test_bad_quantity_rejected():
    from astra.evolution import Quantity

    with pytest.raises(Exception):
        Quantity(value=float("inf"), unit="Msun")
    with pytest.raises(Exception):
        Quantity(value=1.0, unit="Msun", uncertainty=-1.0)


# ------------------------------------------------------------ scheduled events
def test_scheduled_event_records_at_boundary():
    eng = _engine()
    scheduled = EvolutionEvent(
        event_id="caller-evt-1",
        kind=EvolutionEventKind.CALLER_SCHEDULED,
        cosmic_time_gyr=0.5,
        source_object_ids=("o-1",),
        resulting_object_ids=(),
        physical_cause="caller-scheduled external event",
        model_id="caller",
    )
    out = eng.evolve_object(
        initial_state=make_star_state("o-1", 0.0, 1.0),
        until_cosmic_time_gyr=1.0,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
        scheduled_events=[scheduled],
    )
    reasons = [d.reason.value for d in out.timesteps]
    assert "EVENT_DRIVEN" in reasons
    recorded = [e for e in out.events if e.event_id == "caller-evt-1"]
    assert len(recorded) == 1
    assert recorded[0].causal_parent_event_id is not None
    # the step lands exactly on the boundary: some recorded state has t == 0.5
    times = [s.cosmic_time_gyr for s in eng.object_history("o-1")]
    assert any(abs(t - 0.5) < 1e-12 for t in times)


def test_scheduled_event_outside_interval_rejected():
    eng = _engine()
    scheduled = EvolutionEvent(
        event_id="caller-evt-2",
        kind=EvolutionEventKind.CALLER_SCHEDULED,
        cosmic_time_gyr=5.0,
        source_object_ids=("o-1",),
        resulting_object_ids=(),
        physical_cause="outside",
        model_id="caller",
    )
    with pytest.raises(EvolutionValidationError):
        eng.evolve_object(
            initial_state=make_star_state("o-1", 0.0, 1.0),
            until_cosmic_time_gyr=1.0,
            model_id=STELLAR_MODEL_ID,
            scenario=_scenario(),
            scheduled_events=[scheduled],
        )


def test_scheduled_event_claiming_observation_rejected():
    """Future events are projections; REAL_DATA provenance is impossible."""
    eng = _engine()
    scheduled = EvolutionEvent(
        event_id="caller-evt-3",
        kind=EvolutionEventKind.CALLER_SCHEDULED,
        cosmic_time_gyr=0.5,
        source_object_ids=("o-1",),
        resulting_object_ids=(),
        physical_cause="claims to be observed",
        model_id="caller",
        provenance=DataProvenance.REAL_DATA,
    )
    with pytest.raises(EvolutionValidationError):
        eng.evolve_object(
            initial_state=make_star_state("o-1", 0.0, 1.0),
            until_cosmic_time_gyr=1.0,
            model_id=STELLAR_MODEL_ID,
            scenario=_scenario(),
            scheduled_events=[scheduled],
        )


# -------------------------------------------------------------- ledger forking
def test_forking_recorded_timeline_refused():
    eng = _engine()
    state = make_star_state("o-1", 0.0, 1.0)
    eng.evolve_object(
        initial_state=state, until_cosmic_time_gyr=2.0,
        model_id=STELLAR_MODEL_ID, scenario=_scenario(),
    )
    with pytest.raises(EvolutionValidationError) as excinfo:
        eng.evolve_object(
            initial_state=state, until_cosmic_time_gyr=1.0,
            model_id=STELLAR_MODEL_ID, scenario=_scenario(),
        )
    assert "fork" in str(excinfo.value)


def test_continuation_of_recorded_worldline_allowed():
    eng = _engine()
    state = make_star_state("o-1", 0.0, 1.0)
    out1 = eng.evolve_object(
        initial_state=state, until_cosmic_time_gyr=2.0,
        model_id=STELLAR_MODEL_ID, scenario=_scenario(),
    )
    out2 = eng.evolve_object(
        initial_state=out1.final_state, until_cosmic_time_gyr=3.0,
        model_id=STELLAR_MODEL_ID, scenario=_scenario(),
    )
    assert out2.final_state.cosmic_time_gyr == pytest.approx(3.0)
    count, edges = eng.validate_history()
    assert count == len(eng.history())


# ------------------------------------------------------------------- budgets
def test_step_budget_enforced():
    tiny = EvolutionConfig(
        timestep=__import__("astra.evolution", fromlist=["TimestepPolicy"]).TimestepPolicy(
            base_dt_gyr=1e-6, min_dt_gyr=1e-6, max_dt_gyr=1e-6
        ),
        budget=__import__("astra.evolution", fromlist=["PerformanceBudget"]).PerformanceBudget(
            max_steps_per_object=5
        ),
    )
    eng = CosmicEvolutionEngine(config=tiny, authority=AllowAll())
    with pytest.raises(EvolutionLimitationError) as excinfo:
        eng.evolve_object(
            initial_state=make_star_state("o-1", 0.0, 1.0),
            until_cosmic_time_gyr=1.0,
            model_id=STELLAR_MODEL_ID,
            scenario=_scenario(),
        )
    assert excinfo.value.state.value == "BUDGET_EXCEEDED"


# ------------------------------------------------------------- projection API
def test_projection_does_not_touch_ledger():
    eng = _engine()
    before = len(eng.history())
    out = eng.project_future_state(
        initial_state=make_star_state("o-1", 0.0, 2.0),
        until_cosmic_time_gyr=15.0,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
    )
    assert out.final_state.phase == "REMNANT"
    assert len(eng.history()) == before
    assert all(
        q.provenance is not DataProvenance.REAL_DATA
        for q in out.final_state.quantities.values()
    )


def test_projection_scenario_class_stamped():
    eng = _engine()
    out = eng.project_future_state(
        initial_state=make_star_state("o-1", 0.0, 2.0),
        until_cosmic_time_gyr=15.0,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(projection_class=ProjectionClass.HYPOTHETICAL),
    )
    assert out.final_state.projection_class is ProjectionClass.HYPOTHETICAL
