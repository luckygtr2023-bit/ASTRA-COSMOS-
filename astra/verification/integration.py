"""Integration verification across subsystems.

Runs a subset of representative cross-system checks and aggregates into a report.
Bounds are explicit: we do not simulate full physics; we check wiring and
determinism contracts that hold regardless of content.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from .fixtures import engine_factory, minimal_world_factory
from .report import VerificationReport, run_check
from .snapshot import verify_save_load_equivalence, verify_save_load_continue_equivalence
from .replay import verify_deterministic_replay
from .stress import stress_long_run, stress_save_load_cycles, verify_corruption_detection
from .invariants import collect_physics_invariants
from .world_checks import collect_world_checks
from .celestial_checks import collect_celestial_checks


def verify_engine_world_isolation() -> Dict[str, Any]:
    """Ensure separate engines/worlds do not share mutable state."""
    from .fixtures import _engine_tick  # type: ignore
    ef = engine_factory()
    eng_a = ef()
    eng_b = ef()
    # Mutate A
    _engine_tick(eng_a, 1.0)
    # Hash B should be unchanged from fresh
    from .state_hash import hash_engine
    h_b = hash_engine(eng_b)
    eng_ref = ef()
    h_ref = hash_engine(eng_ref)
    passed = h_b == h_ref
    for e in [eng_a, eng_b, eng_ref]:
        try:
            e.stop(); e.shutdown()
        except Exception:
            pass
    return {"passed": bool(passed), "hash_b": h_b, "hash_ref": h_ref}


def full_integration_report(*, steps: int = 20, dt: float = 1.0) -> VerificationReport:
    report = VerificationReport(title="ASTRA-COSMOS Integration Verification")
    # Use shared persistence for save/load checks to ensure snapshot visibility
    import tempfile
    from pathlib import Path

    shared_path = Path(tempfile.mkdtemp(prefix="astra_integ_shared_"))
    ef_shared = engine_factory(seed=42, persistence_path=shared_path)
    # For isolated checks, use fresh factory
    ef = engine_factory()
    wf = minimal_world_factory()

    # Snapshot save-load (shared)
    def check_save_load():
        eng = ef_shared()
        res = verify_save_load_equivalence(eng)
        try:
            eng.stop(); eng.shutdown()
        except Exception:
            pass
        return res

    run_check("snapshot.save_load_equivalence", check_save_load, report=report)

    # Save-load-continue (shared factory ensures same persistence dir)
    def check_continue():
        return verify_save_load_continue_equivalence(ef_shared, steps_before=5, steps_after=5, dt=dt)

    run_check("snapshot.save_load_continue", check_continue, report=report)

    # Deterministic replay (shared also)
    def check_replay():
        return verify_deterministic_replay(ef_shared, steps=steps, dt=dt, repeats=2)

    run_check("replay.deterministic", check_replay, report=report)

    # Long-run stress (short) - uses shared for determinism
    def check_long():
        return stress_long_run(ef_shared, steps=100, dt=dt, hash_every=25)

    run_check("stress.long_run", check_long, report=report)

    # Save-load cycles (shared)
    def check_cycles():
        return stress_save_load_cycles(ef_shared, cycles=3, dt=dt)

    run_check("stress.save_load_cycles", check_cycles, report=report)

    # Corruption detection
    def check_corrupt():
        return verify_corruption_detection()

    run_check("stress.corruption_detection", check_corrupt, report=report)

    # Physics invariants (best-effort)
    def check_physics():
        from .fixtures import _engine_tick as _tick  # type: ignore
        eng = ef()
        for _ in range(5):
            _tick(eng, dt)
        res = collect_physics_invariants(eng)
        try:
            eng.stop(); eng.shutdown()
        except Exception:
            pass
        return res

    run_check("invariants.physics", check_physics, report=report)

    # World checks
    def check_world():
        world = wf()
        return collect_world_checks(world)

    run_check("world.consistency", check_world, report=report)

    # Isolation
    def check_isolation():
        return verify_engine_world_isolation()

    run_check("integration.isolation", check_isolation, report=report)

    return report


__all__ = ["verify_engine_world_isolation", "full_integration_report"]
