import threading
import pytest
from astra.core.entities import EntityManager
from astra.core.threading import (
    AuthorityContext, get_simulation_thread_registry,
    reset_simulation_thread_registry,
)
from astra.core.exceptions import AuthorityError
from astra.mathematics import Vector3
from astra.motion import (
    MotionSystem, MotionComponent, MotionState,
    SemiImplicitEulerIntegrator,
)


@pytest.fixture(autouse=True)
def sim_thread():
    reset_simulation_thread_registry()
    reg = get_simulation_thread_registry()
    tid = threading.current_thread().ident
    reg.register_simulation_thread(tid)
    yield
    reset_simulation_thread_registry()


def _make_em():
    em = EntityManager()
    em.set_current_tick(0)
    return em


class TestMotionSystem:
    def test_step_requires_authority(self):
        em = _make_em()
        sys = MotionSystem(em)
        with pytest.raises(AuthorityError):
            sys.step(0.01, require_authority=True)

    def test_step_with_authority(self):
        em = _make_em()
        e = em.create_entity("ship")
        c = MotionComponent(state=MotionState())
        c.state.velocity = Vector3(1.0, 0.0, 0.0)
        e.add_component(c)
        sys = MotionSystem(em)
        with AuthorityContext("test.motion"):
            n = sys.step(1.0)
        assert n == 1
        assert c.state.position.x == pytest.approx(1.0, abs=1e-12)

    def test_deterministic_order(self):
        em = _make_em()
        ids = []
        for i in range(5):
            e = em.create_entity(f"e{i}")
            c = MotionComponent(state=MotionState())
            c.state.velocity = Vector3(1.0, 0.0, 0.0)
            e.add_component(c)
            ids.append(e.id.value)
        sys = MotionSystem(em)
        with AuthorityContext("test.motion"):
            sys.step(1.0)
        for eid in ids:
            e = em.get_entity(eid)
            c = e.get_component(MotionComponent)
            assert c.state.position.x == pytest.approx(1.0, abs=1e-12)

    def test_disabled_component_skipped(self):
        em = _make_em()
        e = em.create_entity("ship")
        c = MotionComponent(state=MotionState(), enabled=False)
        e.add_component(c)
        sys = MotionSystem(em)
        with AuthorityContext("test.motion"):
            n = sys.step(1.0)
        assert n == 0

    def test_snapshot_restore_roundtrip(self):
        em = _make_em()
        e = em.create_entity("ship")
        c = MotionComponent(state=MotionState())
        c.state.velocity = Vector3(2.0, 0.0, 0.0)
        e.add_component(c)
        sys = MotionSystem(em)
        with AuthorityContext("test.motion"):
            sys.step(1.0)
        snap = sys.snapshot()
        assert e.id.value in snap
        c.state.position = Vector3(99, 99, 99)
        sys.restore_from_snapshot(snap)
        c2 = em.get_entity(e.id.value).get_component(MotionComponent)
        assert c2.state.position.x == pytest.approx(2.0, abs=1e-12)

    def test_repeated_run_deterministic(self):
        def run():
            em = _make_em()
            for i in range(3):
                e = em.create_entity(f"e{i}")
                c = MotionComponent(state=MotionState())
                c.state.velocity = Vector3(1.0 + i, 0.0, 0.0)
                c.state.acceleration = Vector3(0.0, -0.5, 0.0)
                e.add_component(c)
            sys = MotionSystem(em, SemiImplicitEulerIntegrator())
            with AuthorityContext("test.motion"):
                for _ in range(100):
                    sys.step(0.01)
            return [ (eid, c.state.position.to_tuple(), c.state.velocity.to_tuple())
                     for eid, c in sys._iter_components() ]
        r1 = run()
        r2 = run()
        assert r1 == r2
