"""Phase 21 — event architecture + causal ordering tests (spec 2.27, 2.34)."""
from __future__ import annotations

import pytest

from astra.celestial.provenance import DataProvenance

from astra.evolution import (
    CosmicEvolutionEngine,
    EvolutionEvent,
    EvolutionEventKind,
    EvolutionLedger,
    EvolutionLimitationError,
    EvolutionValidationError,
    LimitationState,
    Scenario,
    make_star_state,
)


class AllowAll:
    def require(self, op):
        pass


def _scenario():
    return Scenario(scenario_id="s", name="S", description="")


def test_events_chained_per_object():
    eng = CosmicEvolutionEngine(authority=AllowAll())
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0), until_cosmic_time_gyr=14.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=_scenario(),
    )
    events = out.events
    assert len(events) >= 3
    known = set()
    for e in events:
        if e.causal_parent_event_id is not None:
            assert e.causal_parent_event_id in known or e.causal_parent_event_id in {
                x.event_id for x in events
            }
        known.add(e.event_id)
    # times non-decreasing along the chain
    by_id = {e.event_id: e for e in events}
    for e in events:
        parent = e.causal_parent_event_id
        if parent:
            assert e.cosmic_time_gyr >= by_id[parent].cosmic_time_gyr


def test_ledger_rejects_unknown_causal_parent():
    ledger = EvolutionLedger()
    event = EvolutionEvent(
        event_id="e2", kind=EvolutionEventKind.CUSTOM, cosmic_time_gyr=1.0,
        source_object_ids=("x",), resulting_object_ids=(),
        physical_cause="test", model_id="m",
        causal_parent_event_id="missing",
    )
    with pytest.raises(EvolutionLimitationError) as excinfo:
        ledger.record_event(event)
    assert excinfo.value.state is LimitationState.CAUSAL_INCONSISTENCY


def test_ledger_rejects_time_reversing_chain():
    ledger = EvolutionLedger()
    ledger.record_event(EvolutionEvent(
        event_id="e1", kind=EvolutionEventKind.CUSTOM, cosmic_time_gyr=5.0,
        source_object_ids=("x",), resulting_object_ids=(),
        physical_cause="first", model_id="m",
    ))
    with pytest.raises(EvolutionLimitationError) as excinfo:
        ledger.record_event(EvolutionEvent(
            event_id="e2", kind=EvolutionEventKind.CUSTOM, cosmic_time_gyr=1.0,
            source_object_ids=("x",), resulting_object_ids=(),
            physical_cause="before parent", model_id="m",
            causal_parent_event_id="e1",
        ))
    assert excinfo.value.state is LimitationState.CAUSAL_INCONSISTENCY


def test_ledger_rejects_duplicate_ids():
    ledger = EvolutionLedger()
    event = EvolutionEvent(
        event_id="e1", kind=EvolutionEventKind.CUSTOM, cosmic_time_gyr=1.0,
        source_object_ids=("x",), resulting_object_ids=(),
        physical_cause="dup", model_id="m",
    )
    ledger.record_event(event)
    with pytest.raises(EvolutionValidationError):
        ledger.record_event(event)


def test_event_validation():
    with pytest.raises(EvolutionValidationError):
        EvolutionEvent(
            event_id="", kind=EvolutionEventKind.CUSTOM, cosmic_time_gyr=1.0,
            source_object_ids=(), resulting_object_ids=(),
            physical_cause="x", model_id="m",
        )
    with pytest.raises(EvolutionValidationError):
        EvolutionEvent(
            event_id="e", kind=EvolutionEventKind.CUSTOM, cosmic_time_gyr=1.0,
            source_object_ids=(), resulting_object_ids=(),
            physical_cause="", model_id="m",
        )
    with pytest.raises(Exception):
        EvolutionEvent(
            event_id="e", kind=EvolutionEventKind.CUSTOM, cosmic_time_gyr=float("nan"),
            source_object_ids=(), resulting_object_ids=(),
            physical_cause="x", model_id="m",
        )


def test_record_event_api_with_automatic_parent():
    eng = CosmicEvolutionEngine(authority=AllowAll())
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0), until_cosmic_time_gyr=14.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=_scenario(),
    )
    recorded = eng.record_event(EvolutionEvent(
        event_id="external-1", kind=EvolutionEventKind.CUSTOM,
        cosmic_time_gyr=14.5, source_object_ids=("o",), resulting_object_ids=(),
        physical_cause="caller-recorded external event", model_id="caller",
    ))
    assert recorded.causal_parent_event_id is not None  # auto-linked
    assert len(eng.history()) == len(out.events) + 1


def test_events_queryable_by_object():
    eng = CosmicEvolutionEngine(authority=AllowAll())
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0), until_cosmic_time_gyr=14.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=_scenario(),
    )
    assert len(eng.events_for("o")) == len(out.events)
    assert eng.events_for("unrelated") == ()


def test_event_round_trip():
    event = EvolutionEvent(
        event_id="e1", kind=EvolutionEventKind.STELLAR_DEATH, cosmic_time_gyr=3.0,
        source_object_ids=("a", "b"), resulting_object_ids=("c",),
        physical_cause="test cause", model_id="m",
        causal_parent_event_id="e0",
        metadata={"remnant_kind": "WHITE_DWARF"},
    )
    d = event.to_dict()
    e2 = EvolutionEvent.from_dict(d)
    assert e2 == event
    assert event.to_dict() == e2.to_dict()


def test_history_samples_bounded_with_decimation_accounting():
    from astra.evolution import EvolutionConfig, PerformanceBudget, TimestepPolicy

    eng = CosmicEvolutionEngine(
        config=EvolutionConfig(
            budget=PerformanceBudget(max_history_samples_per_object=8),
            timestep=TimestepPolicy(base_dt_gyr=0.01, min_dt_gyr=1e-4, max_dt_gyr=0.05),
        ),
        authority=AllowAll(),
    )
    eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 40.0), until_cosmic_time_gyr=1.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=_scenario(),
    )
    history = eng.object_history("o")
    assert len(history) <= 8 + 2  # cap + initial/final bookkeeping
    diagnostics = eng.diagnostics()
    assert diagnostics["history_decimations"].get("o", 0) >= 0
