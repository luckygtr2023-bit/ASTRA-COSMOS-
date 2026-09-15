"""Tests for astra.destruction — happy path, conservation, determinism,
persistence, and REAL integration with core/physics/world/celestial/nbody/
motion/orbital (no simulated stand-ins for the integration tests).
"""
from __future__ import annotations

import json
import math

import pytest

from astra.celestial.properties import CelestialProperties
from astra.core.entities import EntityManager
from astra.core.events import EventBus
from astra.core.persistence import PersistenceManager
from astra.core.rng import DeterministicRNG
from astra.mathematics import Vector3
from astra.nbody.bodies import NBodyBody
from astra.nbody.system import NBodySystem
from astra.world.world import World

from astra.destruction import (
    AstraPhysicsAdapter,
    AuthorityError,
    CoreAuthorityProvider,
    CoreCelestialResolverAdapter,
    CoreEntityRegistrarAdapter,
    CoreEventPublisherAdapter,
    CorePersistenceHookAdapter,
    CoreWorldRegistrarAdapter,
    DamageState,
    DestructionConfig,
    DestructionSystem,
    DictPersistenceHook,
    ImpactEvent,
    LimitExceededError,
    NBodyDebrisSink,
    NumericalError,
    FragmentState,
    FragmentOrbit,
    OrbitClass,
    Provenance,
    UnsupportedBodyError,
    Vec3,
    classify_fragment_orbit,
    count_orbit_classes,
    is_valid_transition,
    motion_component_for_fragment,
)
from astra.destruction.persistence import (
    result_from_dict,
    result_to_dict,
)


# --------------------------------------------------------------- fixtures


class _AllowAll:
    def require(self, operation: str) -> None:
        return None


class _DenyAll:
    def require(self, operation: str) -> None:
        raise AuthorityError(f"denied: {operation}", operation=operation)


class _RecordingEntities:
    def __init__(self):
        self.registered = []

    def register(self, entity_id, kind, payload):
        self.registered.append((entity_id, kind, dict(payload)))

    def unregister(self, entity_id):
        self.registered = [r for r in self.registered if r[0] != entity_id]

    def exists(self, entity_id):
        return any(r[0] == entity_id for r in self.registered)


class _RecordingWorld:
    def __init__(self):
        self.objects = []

    def register_object(self, object_id, position, metadata):
        self.objects.append((object_id, tuple(position), dict(metadata)))

    def unregister_object(self, object_id):
        self.objects = [o for o in self.objects if o[0] != object_id]


class _RecordingEvents:
    def __init__(self):
        self.events = []

    def publish(self, topic, payload):
        self.events.append((topic, dict(payload)))


def _make_event(**over):
    base = dict(
        impact_id="imp-1",
        impactor_id="ast-1",
        target_id="earth",
        sim_time_s=100.0,
        impactor_mass_kg=1.0e15,
        target_mass_kg=5.972e24,
        impactor_position=Vec3(6.371e6 + 1.0e5, 0.0, 0.0),
        target_position=Vec3(0.0, 0.0, 0.0),
        impactor_velocity=Vec3(-2.0e4, 0.0, 0.0),
        target_velocity=Vec3(0.0, 0.0, 0.0),
        impactor_radius_m=1.0e3,
        target_radius_m=6.371e6,
    )
    base.update(over)
    return ImpactEvent(**base)


def _sys(authority=None, **kw):
    return DestructionSystem(
        config=DestructionConfig(),
        authority=authority if authority is not None else _AllowAll(),
        **kw,
    )


# ------------------------------------------------------------- geometry


def test_head_on_impact_basic():
    s = _sys()
    r = s.execute_impact(_make_event(), seed=1)
    assert r.geometry.is_head_on
    assert not r.geometry.is_grazing
    assert r.target_state_after in (
        DamageState.DAMAGED,
        DamageState.FRACTURED,
        DamageState.FRAGMENTED,
        DamageState.DESTROYED,
    )
    assert r.provenance == Provenance.SIMULATED_DATA
    assert r.energy.kinetic_energy_j > 0.0
    # Contact lies on the target sphere (impactor still outside it).
    dist = r.geometry.contact_point.distance_to(r.event.target_position)
    assert math.isclose(dist, r.event.target_radius_m, rel_tol=1e-9)


def test_oblique_impact_is_not_head_on():
    s = _sys()
    ev = _make_event(impactor_velocity=Vec3(-2.0e4, 1.5e4, 0.0))
    r = s.execute_impact(ev, seed=2)
    assert not r.geometry.is_head_on
    assert not r.geometry.is_grazing  # cos(incidence)=0.8 >> 0.15 threshold
    assert 0.0 <= r.geometry.incidence_angle_rad <= math.pi


def test_grazing_impact_flag():
    s = _sys()
    # Relative velocity nearly tangential to the local surface plane.
    ev = _make_event(
        impactor_position=Vec3(0.0, 6.371e6 + 1e5, 0.0),
        impactor_velocity=Vec3(-2.0e4, -1.0, 0.0),
    )
    r = s.execute_impact(ev, seed=3)
    assert r.geometry.is_grazing
    assert r.geometry.incidence_angle_rad > math.pi / 2.0 - 0.15


# ------------------------------------------------- energy and momentum


def test_energy_partitioning_sums():
    s = _sys()
    r = s.execute_impact(_make_event(impactor_mass_kg=1e20), seed=15)
    e = r.energy
    reconstructed = (
        e.fragmentation_energy_j + e.thermal_energy_j + e.residual_kinetic_energy_j
    )
    assert abs(reconstructed - e.kinetic_energy_j) < 1e-6 * max(e.kinetic_energy_j, 1.0)
    assert e.fragmentation_energy_j >= 0.0
    assert e.thermal_energy_j >= 0.0
    assert e.residual_kinetic_energy_j >= 0.0


def test_momentum_transfer_partition():
    s = _sys()
    r = s.execute_impact(_make_event(), seed=16)
    m = r.momentum
    p_sum = m.transferred_momentum_kg_m_s + m.residual_momentum_kg_m_s
    err = (p_sum - m.relative_momentum_kg_m_s).magnitude()
    assert err <= 1e-9 * max(m.relative_momentum_kg_m_s.magnitude(), 1.0)


def test_mass_conservation_fragments():
    s = _sys()
    ev = _make_event(impactor_mass_kg=1e20, impactor_velocity=Vec3(-5e4, 0, 0))
    r = s.execute_impact(ev, seed=6)
    assert r.fragments  # FRACTURED at this energy
    total = sum(f.mass_kg for f in r.fragments)
    assert 0.0 < total <= ev.target_mass_kg * (1.0 + 1e-9)


def test_fragment_cloud_preserves_target_momentum():
    s = _sys()
    ev = _make_event(impactor_mass_kg=1e22)  # FRAGMENTED
    r = s.execute_impact(ev, seed=7)
    assert r.fragments
    p = Vector3(0.0, 0.0, 0.0)
    for f in r.fragments:
        p = p + f.velocity * f.mass_kg
    # Target velocity is zero, so the fragment cloud's net momentum must
    # also be ~zero (perturbations are mean-subtracted with mass weights).
    assert p.magnitude() / ev.target_mass_kg < 1e-9


# ------------------------------------------------------------ determinism


def test_determinism_repeated_impacts():
    def run():
        s = _sys()
        return s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=42)

    a, b = run(), run()
    assert [f.mass_kg for f in a.fragments] == [f.mass_kg for f in b.fragments]
    assert [f.velocity.to_tuple() for f in a.fragments] == [
        f.velocity.to_tuple() for f in b.fragments
    ]
    assert [p.velocity.to_tuple() for p in a.ejecta] == [
        p.velocity.to_tuple() for p in b.ejecta
    ]
    assert a.energy.kinetic_energy_j == b.energy.kinetic_energy_j
    assert a.target_state_after == b.target_state_after


def test_seed_changes_fragmentation():
    ev = _make_event(impactor_mass_kg=1e22)
    r1 = _sys().execute_impact(ev, seed=1)
    r2 = _sys().execute_impact(ev, seed=2)
    assert r1.fragments and r2.fragments
    assert [f.mass_kg for f in r1.fragments] != [f.mass_kg for f in r2.fragments]


def test_injected_core_rngstream_is_deterministic():
    def run(stream_seed):
        mgr = DeterministicRNG(global_seed=99)
        stream = mgr.create_stream("destruction.test", seed=stream_seed)
        s = _sys(rng=stream)
        return s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=777)

    a, b = run(123), run(123)
    assert [f.mass_kg for f in a.fragments] == [f.mass_kg for f in b.fragments]
    c = run(124)
    assert [f.mass_kg for f in a.fragments] != [f.mass_kg for f in c.fragments]
    # Stream state is snapshotable through core's RNGState machinery.
    mgr = DeterministicRNG(global_seed=99)
    stream = mgr.create_stream("destruction.test", seed=123)
    state_before = stream.get_state()
    s = _sys(rng=stream)
    r1 = s.execute_impact(_make_event(impactor_mass_kg=1e22, impact_id="imp-a"), seed=1)
    stream.restore_state(state_before)
    r2 = s.execute_impact(_make_event(impactor_mass_kg=1e22, impact_id="imp-a"), seed=1)
    assert [f.mass_kg for f in r1.fragments] == [f.mass_kg for f in r2.fragments]


def test_fragment_identity_uniqueness():
    s = _sys()
    ev = _make_event(impactor_mass_kg=1e22)
    r = s.execute_impact(ev, seed=7)
    ids = [f.fragment_id for f in r.fragments]
    assert len(ids) == len(set(ids))
    debris_ids = [d.debris_id for d in r.debris]
    assert len(debris_ids) == len(set(debris_ids))


# ---------------------------------------------------------------- damage


def test_damage_state_transitions_forward_only():
    assert is_valid_transition(DamageState.INTACT, DamageState.DAMAGED)
    assert is_valid_transition(DamageState.INTACT, DamageState.FRAGMENTED)  # catastrophic jump
    assert is_valid_transition(DamageState.DAMAGED, DamageState.FRACTURED)
    assert is_valid_transition(DamageState.FRACTURED, DamageState.FRAGMENTED)
    assert is_valid_transition(DamageState.FRAGMENTED, DamageState.DESTROYED)
    assert is_valid_transition(DamageState.DESTROYED, DamageState.DESTROYED)
    assert not is_valid_transition(DamageState.DESTROYED, DamageState.INTACT)
    assert not is_valid_transition(DamageState.DAMAGED, DamageState.INTACT)
    assert not is_valid_transition(DamageState.FRAGMENTED, DamageState.DAMAGED)


def test_damage_progression_never_regresses():
    s = _sys()
    weak = _make_event(impactor_mass_kg=1e15)  # DAMAGED
    r1 = s.execute_impact(weak, seed=1)
    assert s.get_damage_state("earth") == r1.target_state_after
    strong = _make_event(impact_id="imp-2", impactor_mass_kg=1e22,
                         impactor_velocity=Vec3(-1e6, 0, 0))  # DESTROYED
    r2 = s.execute_impact(strong, seed=2)
    assert r2.target_state_before == r1.target_state_after
    assert r2.target_state_after == DamageState.DESTROYED
    # A later weak hit cannot repair the body.
    weak2 = _make_event(impact_id="imp-3", impactor_mass_kg=1e15)
    r3 = s.execute_impact(weak2, seed=3)
    assert r3.target_state_after == DamageState.DESTROYED


# ------------------------------------------------- ejecta / debris counts


def test_ejecta_generated_and_bounded():
    s = _sys()
    r = s.execute_impact(_make_event(), seed=11)
    assert 0 < len(r.ejecta) <= s.config.limits.max_ejecta_per_impact
    assert len(r.debris) == len(r.fragments) + len(r.ejecta)
    assert len(r.debris) <= s.config.limits.max_debris_per_impact
    for p in r.ejecta:
        assert p.kinetic_energy_j >= 0.0


# ------------------------------------------------- registration (generic)


def test_entity_world_event_registration():
    ent, wld, evt = _RecordingEntities(), _RecordingWorld(), _RecordingEvents()
    s = _sys(entities=ent, world=wld, events=evt)
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=11)
    assert len(ent.registered) == len(r.fragments) + len(r.ejecta) + len(r.debris)
    assert len(wld.objects) == len(r.debris)
    assert any(t == "destruction.impact.executed" for t, _ in evt.events)
    assert s.diagnostics()["entities_created"] == len(ent.registered)


# ----------------------------------------------- REAL core authority test


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
        s = DestructionSystem(
            config=DestructionConfig(), authority=CoreAuthorityProvider()
        )
        # Outside any AuthorityContext: denied by the real core gate.
        with pytest.raises(AuthorityError):
            s.execute_impact(_make_event(), seed=1)
        # Inside a real AuthorityContext (empty grant set grants all ops).
        with AuthorityContext("destruction"):
            r = s.execute_impact(_make_event(), seed=1)
        assert r.target_state_after is not None
        assert s.get_damage_state("earth") == r.target_state_after
        # After the context exits: denied again.
        with pytest.raises(AuthorityError):
            s.set_damage_state("earth", DamageState.INTACT)
    finally:
        reset_simulation_thread_registry()


# ------------------------------------ REAL entity manager / events / world


def test_real_entity_manager_registration():
    em = EntityManager()
    adapter = CoreEntityRegistrarAdapter(em)
    s = _sys(entities=adapter)
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=12)
    expected = len(r.fragments) + len(r.ejecta) + len(r.debris)
    assert em.get_entity_count() == expected
    f0 = r.fragments[0]
    assert adapter.exists(f0.fragment_id)
    core_id = adapter.core_id_for(f0.fragment_id)
    assert core_id is not None and core_id.startswith("entity_")
    entity = em.get_entity(core_id)
    assert f0.fragment_id in entity.name
    assert "fragment" in entity.tags
    payload = adapter.payload_for(f0.fragment_id)
    assert payload["mass_kg"] == f0.mass_kg
    adapter.unregister(f0.fragment_id)
    assert not adapter.exists(f0.fragment_id)
    assert em.get_entity_count() == expected - 1


def test_real_event_bus_receives_impact_event():
    bus = EventBus()
    received = []
    bus.subscribe("destruction.impact.executed", received.append)
    adapter = CoreEventPublisherAdapter(bus, tick=7)
    s = _sys(events=adapter)
    r = s.execute_impact(_make_event(), seed=13)
    assert len(received) == 1
    event = received[0]
    assert event.name == "destruction.impact.executed"
    assert event.tick == 7
    assert event.source == "astra.destruction"
    assert event.data["impact_id"] == r.event.impact_id
    assert event.data["state_after"] == r.target_state_after.value
    # EventId.generate is deterministic: evt_{tick:012d}_{sequence:06d}.
    assert event.id.value == "evt_000000000007_000001"
    assert adapter.handler_failures == []


def test_real_world_spatial_index_registration():
    world = World()
    adapter = CoreWorldRegistrarAdapter(world)
    s = _sys(world=adapter)
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=14)
    hits = world.query_objects_in_radius((0.0, 0.0, 0.0), 5.0e7)
    debris_ids = {d.debris_id for d in r.debris}
    assert debris_ids.issubset(set(hits))
    meta = adapter.metadata_for(r.debris[0].debris_id)
    assert meta["origin_impact_id"] == r.event.impact_id
    for d in r.debris[:3]:
        adapter.unregister_object(d.debris_id)
    hits_after = world.query_objects_in_radius((0.0, 0.0, 0.0), 5.0e7)
    assert debris_ids - set(hits_after) != set()


# ------------------------------------------------------ REAL persistence


def test_real_persistence_manager_roundtrip(tmp_path):
    pm = PersistenceManager(base_path=str(tmp_path))
    hook = CorePersistenceHookAdapter(pm, tick=3)
    s = _sys(persistence=hook)
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=17)
    assert hook.load("impact-1") is None
    s.save_result("impact-1", r)
    loaded_payload = hook.load("impact-1")
    assert loaded_payload is not None
    r2 = result_from_dict(loaded_payload)
    assert result_to_dict(r2) == result_to_dict(r)
    # Continuation: ledger snapshots survive independently.
    s2 = _sys(persistence=hook)
    s2.restore_damage_ledger(s.damage_ledger_snapshot())
    assert s2.get_damage_state("earth") == r.target_state_after


def test_dict_persistence_hook_json_roundtrip():
    hook = DictPersistenceHook()
    s = _sys(persistence=hook)
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=18)
    s.save_result("k", r)
    payload = hook.load("k")
    # Payload crossed a JSON boundary inside the hook already; verify here too.
    assert json.loads(json.dumps(payload)) == payload
    r2 = result_from_dict(payload)
    assert r2.event.impact_id == r.event.impact_id
    assert r2.rng_seed_used == 18
    assert [f.mass_kg for f in r2.fragments] == [f.mass_kg for f in r.fragments]


def test_result_dict_is_json_serializable():
    s = _sys()
    r = s.execute_impact(
        _make_event(impactor_mass_kg=1e22, metadata={"run": "alpha", "index": 3}),
        seed=19,
    )
    d = result_to_dict(r)
    assert json.loads(json.dumps(d)) == d
    r2 = result_from_dict(json.loads(json.dumps(d)))
    assert r2.event.metadata["run"] == "alpha"
    assert r2.target_state_after == r.target_state_after


def test_damage_ledger_snapshot_restore():
    s = _sys()
    s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=20)
    snap = s.damage_ledger_snapshot()
    json.dumps(snap)  # must be JSON-serialisable
    fresh = _sys()
    assert fresh.get_damage_state("earth") == DamageState.INTACT
    fresh.restore_damage_ledger(snap)
    assert fresh.get_damage_state("earth") == s.get_damage_state("earth")
    with pytest.raises(AuthorityError):
        DestructionSystem(config=DestructionConfig(), authority=None).restore_damage_ledger(snap)


# ---------------------------------------------------- REAL physics adapter


def test_real_physics_adapter_crosscheck():
    physics = AstraPhysicsAdapter()
    ke = physics.kinetic_energy_j(1.0e15, Vec3(-2.0e4, 0.0, 0.0))
    assert math.isclose(ke, 0.5 * 1.0e15 * (2.0e4) ** 2, rel_tol=1e-15)
    p = physics.momentum_kg_m_s(1.0e15, Vec3(-2.0e4, 0.0, 0.0))
    assert math.isclose(p.x, -2.0e19, rel_tol=1e-15)
    s = _sys(physics=physics)
    ev = _make_event(impactor_mass_kg=1e22)
    r = s.execute_impact(ev, seed=21)
    # reduced-mass KE must never exceed the impactor's body KE (m_red <= m1).
    ke_body = physics.kinetic_energy_j(ev.impactor_mass_kg, ev.relative_velocity())
    assert r.energy.kinetic_energy_j <= ke_body + 1e-6 * max(ke_body, 1.0)


# --------------------------------------------------- REAL celestial layer


def test_real_celestial_resolver():
    props = CelestialProperties(mass_kg=5.972e24, radius_m=6.371e6)
    resolver = CoreCelestialResolverAdapter({"earth": props})
    assert resolver.exists("earth")
    assert not resolver.exists("pluto")
    assert resolver.get_mass_kg("earth") == 5.972e24
    assert resolver.get_radius_m("earth") == 6.371e6
    with pytest.raises(UnsupportedBodyError):
        resolver.get_mass_kg("pluto")
    # Unknown physical data is refused, not fabricated.
    empty = CelestialProperties()
    resolver2 = CoreCelestialResolverAdapter({"ghost": empty})
    with pytest.raises(UnsupportedBodyError):
        resolver2.get_mass_kg("ghost")
    # Object-with-properties (CelestialObject-style) also resolves.
    import types as _types

    resolver3 = CoreCelestialResolverAdapter(
        {"earth": _types.SimpleNamespace(properties=props)}
    )
    assert resolver3.get_radius_m("earth") == 6.371e6
    # End-to-end: celestial-resolved mass/radius drive an impact.
    s = _sys(celestial=resolver)
    ev = _make_event(
        target_mass_kg=resolver.get_mass_kg("earth"),
        target_radius_m=resolver.get_radius_m("earth"),
        impactor_mass_kg=1e22,
    )
    r = s.execute_impact(ev, seed=22)
    assert r.event.target_mass_kg == 5.972e24


# --------------------------------------------------------------- REAL nbody


def test_real_nbody_sink_registers_fragments():
    target = NBodyBody(
        id="earth",
        mass=5.972e24,
        position=Vector3(0.0, 0.0, 0.0),
        velocity=Vector3(0.0, 0.0, 0.0),
    )
    system = NBodySystem(bodies=[target])
    sink = NBodyDebrisSink(system)
    s = _sys()
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=23)
    n_added = sink.register_fragments(r.fragments)
    assert n_added == len(r.fragments) == 64
    assert len(system) == 65
    accels = system.accelerations()
    assert len(accels) == 65
    assert all(a.is_finite() for a in accels)
    assert system.is_finite()
    ids = {b.id for b in system.bodies}
    assert {f.fragment_id for f in r.fragments}.issubset(ids)


# -------------------------------------------------------------- REAL motion


def test_real_motion_system_integrates_fragment():
    from astra.motion.system import MotionSystem

    s = _sys()
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=24)
    fragment = r.fragments[0]

    def run_once():
        em = EntityManager()
        entity = em.create_entity(name="frag-0")
        entity.add_component(motion_component_for_fragment(fragment))
        ms = MotionSystem(em)
        assert ms.step(10.0, require_authority=False) == 1
        return ms.snapshot()

    a, b = run_once(), run_once()
    assert a == b  # deterministic integration
    (state,) = a.values()
    moved = state["state"]["position"]
    expected = fragment.position + fragment.velocity * 10.0
    assert math.isclose(moved[0], expected.x, rel_tol=1e-12)
    assert math.isclose(moved[1], expected.y, rel_tol=1e-12)
    assert math.isclose(moved[2], expected.z, rel_tol=1e-12)


# ------------------------------------------------------------- REAL orbital


def _fragment(vx, vy, frag_id="f"):
    return FragmentState(
        fragment_id=frag_id,
        parent_id="earth",
        impact_id="imp-x",
        mass_kg=1.0e10,
        position=Vec3(6.371e6, 0.0, 0.0),
        velocity=Vec3(vx, vy, 0.0),
        created_at_s=100.0,
    )


def test_real_orbital_classification_bound_and_escaping():
    common = dict(
        central_mass_kg=5.972e24,
        central_position=Vec3(0.0, 0.0, 0.0),
        central_velocity=Vec3(0.0, 0.0, 0.0),
    )
    slow = classify_fragment_orbit(_fragment(0.0, 7.5e3, "slow"), **common)
    fast = classify_fragment_orbit(_fragment(0.0, 1.5e4, "fast"), **common)
    assert slow.orbit_class == OrbitClass.BOUND
    assert slow.specific_orbital_energy_j_kg < 0.0
    assert fast.orbit_class == OrbitClass.HYPERBOLIC
    assert fast.specific_orbital_energy_j_kg > 0.0
    assert isinstance(slow, FragmentOrbit)
    # Escape speed at r: mu/r = G*M/r -> v_esc ~ 11.2 km/s; 7.5 < v_esc < 15.
    assert math.isclose(slow.mu_m3_s2, 6.67430e-11 * (5.972e24 + 1e10), rel_tol=1e-12)
    tally = count_orbit_classes([slow, fast])
    assert tally == {"BOUND": 1, "PARABOLIC": 0, "HYPERBOLIC": 1}


# ------------------------------------------------------- misc / provenance


def test_provenance_never_real_data():
    s = _sys()
    r = s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=25)
    assert r.provenance == Provenance.SIMULATED_DATA
    assert r.energy.provenance == Provenance.SIMULATED_DATA
    assert r.momentum.provenance == Provenance.SIMULATED_DATA
    for f in r.fragments:
        assert f.provenance == Provenance.SIMULATED_DATA
    for p in r.ejecta:
        assert p.provenance == Provenance.SIMULATED_DATA
    for d in r.debris:
        assert d.provenance == Provenance.SIMULATED_DATA


def test_aliases_are_canonical_types():
    from astra.celestial.provenance import DataProvenance
    from astra.mathematics import Vector3

    assert Vec3 is Vector3
    assert Provenance is DataProvenance


def test_large_coordinates_supported():
    s = _sys()
    far = 1e15
    ev = _make_event(
        impactor_position=Vec3(far + 1.0, 0.0, 0.0),
        target_position=Vec3(far, 0.0, 0.0),
        target_radius_m=1.0,
        impactor_radius_m=0.1,
    )
    r = s.execute_impact(ev, seed=26)
    assert r.energy.kinetic_energy_j > 0
    assert r.geometry.contact_point.is_finite()


def test_diagnostics():
    ent = _RecordingEntities()
    s = _sys(entities=ent)
    s.execute_impact(_make_event(impactor_mass_kg=1e22), seed=27)
    diag = s.diagnostics()
    assert diag["impacts_executed"] == 1
    assert diag["tracked_damage_states"] == 1
    assert diag["entities_created"] > 0
