"""Phase 21 — REAL integration adapter tests against actual core systems
(astra.core threading/events/persistence), following the
astra.destruction adapter-test pattern."""
from __future__ import annotations

import json

import pytest

from astra.core.events import EventBus
from astra.core.persistence import PersistenceManager

from astra.evolution import (
    CoreAuthorityProvider,
    CoreEventPublisherAdapter,
    CorePersistenceHookAdapter,
    CosmicEvolutionEngine,
    DictPersistenceHook,
    EvolutionAuthorityError,
    Scenario,
    make_star_state,
    STELLAR_MODEL_ID,
)


class StubAuthority:
    def require(self, operation):
        pass


def _scenario():
    return Scenario(scenario_id="s", name="S", description="")


def test_real_core_authority_granted_and_denied():
    import threading

    from astra.core.threading import (
        AuthorityContext,
        get_simulation_thread_registry,
        reset_simulation_thread_registry,
    )

    reset_simulation_thread_registry()
    registry = get_simulation_thread_registry()
    tid = threading.current_thread().ident
    try:
        registry.register_simulation_thread(tid)
        eng = CosmicEvolutionEngine(authority=CoreAuthorityProvider())
        # Outside any AuthorityContext: denied by the real core gate.
        with pytest.raises(EvolutionAuthorityError):
            eng.evolve_object(
                initial_state=make_star_state("o", 0.0, 1.0),
                until_cosmic_time_gyr=0.5,
                model_id=STELLAR_MODEL_ID,
                scenario=_scenario(),
            )
        # Inside a real AuthorityContext (empty grant set grants all ops).
        with AuthorityContext("evolution"):
            out = eng.evolve_object(
                initial_state=make_star_state("o", 0.0, 1.0),
                until_cosmic_time_gyr=0.5,
                model_id=STELLAR_MODEL_ID,
                scenario=_scenario(),
            )
        assert out.final_state.cosmic_time_gyr == pytest.approx(0.5)
        # After the context exits: denied again.
        with pytest.raises(EvolutionAuthorityError):
            eng.evolve_object(
                initial_state=make_star_state("o2", 0.0, 1.0),
                until_cosmic_time_gyr=0.5,
                model_id=STELLAR_MODEL_ID,
                scenario=_scenario(),
            )
    finally:
        reset_simulation_thread_registry()


def test_real_event_bus_delivery():
    bus = EventBus()
    received = []
    bus.subscribe("evolution.event", lambda event: received.append(event))
    adapter = CoreEventPublisherAdapter(bus)
    eng = CosmicEvolutionEngine(authority=StubAuthority(), events=adapter)
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0),
        until_cosmic_time_gyr=14.0,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
    )
    assert len(received) == len(out.events)
    names = {event.name for event in received}
    assert names == {"evolution.event"}
    payload = received[0].data
    assert payload["kind"] in {e.kind.value for e in out.events}


def test_real_event_bus_handler_failure_collected():
    bus = EventBus()
    bus.subscribe("evolution.event", lambda event: 1 / 0)
    adapter = CoreEventPublisherAdapter(bus)
    eng = CosmicEvolutionEngine(authority=StubAuthority(), events=adapter)
    eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0),
        until_cosmic_time_gyr=1.0,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
    )
    assert len(adapter.handler_failures) > 0
    assert isinstance(adapter.handler_failures[0], ZeroDivisionError)


def test_real_persistence_manager_round_trip(tmp_path):
    manager = PersistenceManager(base_path=str(tmp_path))
    hook = CorePersistenceHookAdapter(manager)
    eng = CosmicEvolutionEngine(authority=StubAuthority(), persistence=hook)
    out = eng.evolve_object(
        initial_state=make_star_state("o", 0.0, 2.0),
        until_cosmic_time_gyr=14.0,
        model_id=STELLAR_MODEL_ID,
        scenario=_scenario(),
    )
    eng.save("snap")

    eng2 = CosmicEvolutionEngine(authority=StubAuthority(), persistence=hook)
    eng2.restore_ledger(hook.load("snap"))
    assert [e.event_id for e in eng2.history()] == [e.event_id for e in eng.history()]


def test_dict_persistence_hook_enforces_json():
    hook = DictPersistenceHook()
    hook.save("k", {"a": [1, 2, {"b": "c"}]})
    assert hook.load("k") == {"a": [1, 2, {"b": "c"}]}
    with pytest.raises(TypeError):
        hook.save("k2", {"bad": object()})


def test_core_authority_error_type_duality():
    """EvolutionAuthorityError is catchable as BOTH the evolution error and
    the core authority error (repository convention)."""
    from astra.core.exceptions import AuthorityError as CoreAuthorityError

    provider = CoreAuthorityProvider()
    with pytest.raises(CoreAuthorityError):
        provider.require("evolution.evolve")
