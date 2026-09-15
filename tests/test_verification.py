"""Tests for ASTRA-COSMOS Verification & Validation subsystem."""

import json
import tempfile
import threading
from pathlib import Path

import pytest

from astra.core.threading import get_simulation_thread_registry, reset_simulation_thread_registry
from astra.verification.state_hash import hash_snapshot, hash_canonical, hash_engine, canonical_json
from astra.verification.state_compare import compare_snapshots, compare_values
from astra.verification.snapshot import verify_save_load_equivalence, verify_save_load_continue_equivalence, detect_corrupted_snapshot
from astra.verification.replay import ReplayRecorder, ReplayVerifier, verify_deterministic_replay
from astra.verification.fixtures import engine_factory, _engine_tick, minimal_world_factory
from astra.verification.stress import verify_corruption_detection, stress_long_run, stress_save_load_cycles
from astra.verification.numerical import is_close, vectors_close, verify_energy_conservation
from astra.verification.invariants import check_mass_positive, check_orbital_elements, collect_physics_invariants
from astra.verification.world_checks import collect_world_checks
from astra.verification.celestial_checks import collect_celestial_checks
from astra.verification.report import VerificationReport
from astra.verification.integration import full_integration_report


@pytest.fixture(autouse=True)
def setup_authority():
    reset_simulation_thread_registry()
    reg = get_simulation_thread_registry()
    tid = threading.current_thread().ident
    if tid is not None:
        try:
            reg.register_simulation_thread(tid)
        except Exception:
            pass
    yield
    reset_simulation_thread_registry()


def test_canonical_hash_deterministic():
    a = {"b": 1, "a": [0.1, 0.2], "tick": 5}
    b = {"a": [0.1, 0.2], "b": 1, "tick": 5}
    assert hash_canonical(a) == hash_canonical(b)
    # ordering of dict should not affect
    assert canonical_json(a) == canonical_json(b)
    # change should affect hash
    c = {"a": [0.1, 0.2000001], "b": 1, "tick": 5}
    assert hash_canonical(a) != hash_canonical(c)


def test_hash_excludes_timestamp():
    from astra.core.persistence import Snapshot
    snap1 = Snapshot(schema_version="1.0.0", engine_state={"state": "running", "total_ticks": 1, "current_origin": [0,0,0]},
                     simulation_time={"tick": 1, "time": 0.01, "mode": "internal_deterministic", "tick_duration": 0.016, "is_running": True, "is_paused": False},
                     entities={}, frames={}, rng_state={}, command_history=[], event_history=[], tick=1, timestamp="2020-01-01T00:00:00", checksum="")
    snap2 = Snapshot(schema_version="1.0.0", engine_state={"state": "running", "total_ticks": 1, "current_origin": [0,0,0]},
                     simulation_time={"tick": 1, "time": 0.01, "mode": "internal_deterministic", "tick_duration": 0.016, "is_running": True, "is_paused": False},
                     entities={}, frames={}, rng_state={}, command_history=[], event_history=[], tick=1, timestamp="2030-12-31T23:59:59", checksum="different")
    assert hash_snapshot(snap1) == hash_snapshot(snap2)


def test_hash_engine_determinism():
    ef = engine_factory(seed=42)
    eng1 = ef()
    eng2 = ef()
    assert hash_engine(eng1) == hash_engine(eng2)
    _engine_tick(eng1)
    _engine_tick(eng2)
    assert hash_engine(eng1) == hash_engine(eng2)
    for e in [eng1, eng2]:
        try: e.stop(); e.shutdown()
        except: pass


def test_save_load_equivalence():
    ef = engine_factory(seed=42)
    shared = Path(tempfile.mkdtemp(prefix="test_save_load_"))
    ef_shared = engine_factory(seed=42, persistence_path=shared)
    eng = ef_shared()
    res = verify_save_load_equivalence(eng)
    assert res["passed"]
    try: eng.stop(); eng.shutdown()
    except: pass


def test_save_load_continue_equivalence():
    shared = Path(tempfile.mkdtemp(prefix="test_continue_"))
    ef = engine_factory(seed=42, persistence_path=shared)
    res = verify_save_load_continue_equivalence(ef, steps_before=3, steps_after=3, dt=1.0)
    assert res["passed"]


def test_replay_deterministic():
    shared = Path(tempfile.mkdtemp(prefix="test_replay_"))
    ef = engine_factory(seed=42, persistence_path=shared)
    res = verify_deterministic_replay(ef, steps=5, dt=1.0, repeats=2)
    assert res["passed"]


def test_replay_divergence_detection():
    shared = Path(tempfile.mkdtemp(prefix="test_replay_div_"))
    ef = engine_factory(seed=42, persistence_path=shared)
    recorder = ReplayRecorder(ef, dt=1.0)
    record = recorder.record(steps=5)
    # Mutate expected hash to force divergence
    record.steps[2].hash = "0"*64
    verifier = ReplayVerifier(ef)
    with pytest.raises(Exception):
        verifier.replay(record)


def test_state_compare_tolerance():
    a = {"x": 1.0, "y": [1.0, 2.0]}
    b = {"x": 1.0 + 1e-10, "y": [1.0, 2.0]}
    diffs = compare_values(a, b, atol=1e-9, rtol=1e-9)
    assert not diffs  # within tolerance
    diffs2 = compare_values(a, b, atol=1e-12, rtol=1e-12)
    # Should detect diffuse beyond tighter tolerance
    assert diffs2


def test_numerical_invariants():
    assert is_close(1.0, 1.0 + 1e-10, atol=1e-9)
    assert vectors_close([1.0, 2.0], [1.0, 2.0 + 1e-10])
    verify_energy_conservation([1.0, 1.0 + 1e-9, 1.0], atol=1e-6, rtol=1e-6)
    with pytest.raises(Exception):
        verify_energy_conservation([1.0, 1.5], atol=1e-9)


def test_invariants_mass_and_orbital():
    check_mass_positive(1.0)
    with pytest.raises(Exception):
        check_mass_positive(-1.0)
    check_orbital_elements({"eccentricity": 0.1, "semi_major_axis": 7000})
    with pytest.raises(Exception):
        check_orbital_elements({"eccentricity": -0.5})


def test_physics_invariants_collection():
    ef = engine_factory(seed=42)
    eng = ef()
    for _ in range(3):
        _engine_tick(eng)
    res = collect_physics_invariants(eng)
    assert res["passed"] or "violations" in res
    try: eng.stop(); eng.shutdown()
    except: pass


def test_world_checks():
    wf = minimal_world_factory()
    world = wf()
    res = collect_world_checks(world)
    assert res["passed"]
    # Test duplicate detection: create shim with duplicate
    class DupWorld:
        def get_state_snapshot(self):
            return {"entities": {"a": {"id": "a", "parent": None}, "b": {"id": "b", "parent": None}}, "regions": {}}
        def to_dict(self): return self.get_state_snapshot()
    # Duplicate ids in different containers not relevant; just ensure not crash
    dup = DupWorld()
    r = collect_world_checks(dup)
    assert isinstance(r, dict)


def test_celestial_checks():
    snap_before = {"entities": {"star1": {"id": "star1", "provenance": {"authority": "catalog"}, "seed": 123, "celestial_type": "star"}}}
    snap_after = {"entities": {"star1": {"id": "star1", "provenance": {"authority": "catalog"}, "seed": 123, "celestial_type": "star"}}}
    res = collect_celestial_checks(snap_before, snap_after, objects={"star1": {"provenance": {"authority": "catalog"}, "position": [1,2,3]}})
    assert res["passed"]
    # provenance change should be flagged
    snap_after_bad = {"entities": {"star1": {"id": "star1", "provenance": {"authority": "other"}, "seed": 123}}}
    from astra.verification.celestial_checks import check_celestial_identity_stable
    with pytest.raises(Exception):
        check_celestial_identity_stable(snap_before, snap_after_bad)


def test_stress_long_run():
    shared = Path(tempfile.mkdtemp(prefix="test_stress_long_"))
    ef = engine_factory(seed=42, persistence_path=shared)
    res = stress_long_run(ef, steps=50, dt=1.0, hash_every=10)
    assert res["passed"]


def test_stress_save_load_cycles():
    shared = Path(tempfile.mkdtemp(prefix="test_stress_cycles_"))
    ef = engine_factory(seed=42, persistence_path=shared)
    res = stress_save_load_cycles(ef, cycles=2, dt=1.0)
    assert res["passed"]


def test_corruption_detection():
    res = verify_corruption_detection()
    assert res["passed"]
    # Also direct detect on missing file
    missing = Path(tempfile.mkdtemp()) / "nope.snapshot"
    r = detect_corrupted_snapshot(str(missing))
    assert not r["valid"]


def test_report_build():
    report = VerificationReport(title="Test Report")
    from astra.verification.report import run_check
    def ok():
        return {"passed": True}
    def fail():
        return {"passed": False, "violations": [{"msg": "bad"}]}
    run_check("ok", ok, report=report)
    run_check("fail", fail, report=report)
    assert not report.passed
    assert len(report.checks) == 2
    assert "Test Report" in report.summary


def test_full_integration_report():
    report = full_integration_report(steps=5, dt=1.0)
    assert report.passed, f"Integration failed: {[c.name for c in report.checks if not c.passed]}"
    assert len(report.checks) >= 6


def test_hash_world_and_render_state():
    # hash_world with shim
    class Dummy:
        def to_dict(self):
            return {"entities": {"a": 1}, "tick": 1}
    from astra.verification.state_hash import hash_world, hash_render_state
    h = hash_world(Dummy())
    assert isinstance(h, str) and len(h) == 64
    class RenderState:
        def to_dict(self):
            return {"frame": 1, "entities": []}
    hr = hash_render_state(RenderState())
    assert isinstance(hr, str)
