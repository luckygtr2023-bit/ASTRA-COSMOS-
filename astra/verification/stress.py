"""Stress, long-run, and failure/corrupted-state detection.

Bounds:
  Included: long-run tick without leak/divergence, corrupted JSON,
            invalid schema, command replay under load.
  Excluded: performance timing assertions beyond smoke (we only verify determinism).
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .exceptions import VerificationError, CorruptedStateError
from .state_hash import hash_engine
from .snapshot import detect_corrupted_snapshot

try:
    from .fixtures import _engine_tick  # type: ignore
except Exception:  # pragma: no cover
    def _engine_tick(engine, dt=None):
        if hasattr(engine, "step"):
            engine.step()
        elif hasattr(engine, "tick"):
            try:
                engine.tick(dt if dt is not None else 1.0)
            except TypeError:
                engine.tick()  # type: ignore
        else:
            raise AttributeError("engine has no step/tick")


def stress_long_run(factory: Callable[[], Any], *, steps: int = 500, dt: float = 1.0, hash_every: int = 50) -> Dict[str, Any]:
    """Run `steps` ticks and collect hashes at intervals to detect non-deterministic drift.

    Returns {passed, hashes, diverged} — compares two independent runs.
    """
    eng_a = factory()
    hashes_a: List[str] = []
    for i in range(steps):
        _engine_tick(eng_a, dt)
        if i % hash_every == 0:
            hashes_a.append(hash_engine(eng_a))
    eng_b = factory()
    hashes_b: List[str] = []
    for i in range(steps):
        _engine_tick(eng_b, dt)
        if i % hash_every == 0:
            hashes_b.append(hash_engine(eng_b))
    # Shutdown
    for e in [eng_a, eng_b]:
        try:
            e.stop(); e.shutdown()
        except Exception:
            pass
    diverged: Optional[int] = None
    for idx, (ha, hb) in enumerate(zip(hashes_a, hashes_b)):
        if ha != hb:
            diverged = idx * hash_every
            break
    passed = diverged is None and hashes_a == hashes_b
    result = {"passed": bool(passed), "hashes_a": hashes_a, "hashes_b": hashes_b, "diverged_at": diverged, "steps": steps, "dt": dt}
    if not passed:
        raise VerificationError(f"long-run determinism diverged at {diverged}", subsystem="stress", operation="stress_long_run", details=result)
    return result


def stress_save_load_cycles(factory: Callable[[], Any], *, cycles: int = 10, dt: float = 1.0) -> Dict[str, Any]:
    """Repeatedly save → load and ensure hash stable across cycles."""
    from .state_hash import hash_snapshot
    engine = factory()
    hashes: List[str] = []
    shared_base = None
    try:
        shared_base = Path(engine.persistence.persistence_path) if hasattr(engine.persistence, "persistence_path") else None
    except Exception:
        shared_base = None
    for c in range(cycles):
        _engine_tick(engine, dt)
        name = f"__stress_cycle_{c}"
        path = engine.save(name)
        snap = engine.persistence.load(name)
        h = hash_snapshot(snap)
        hashes.append(h)
        # Reload into new engine and verify same - ensure same persistence dir
        # Create eng2 with same base path if possible
        if shared_base is not None:
            import tempfile as _tf
            from astra.core.config import Config
            from astra.core.engine import Engine as EngCls
            import threading
            from astra.core.threading import get_simulation_thread_registry
            cfg2 = Config(global_seed=42, persistence_path=str(shared_base))
            eng2 = EngCls(cfg2)
            try:
                _t = threading.current_thread().ident
                reg = get_simulation_thread_registry()
                if _t is not None and not reg.is_simulation_thread(_t):
                    try:
                        reg.register_simulation_thread(_t)
                    except Exception:
                        pass
                eng2.initialize(); eng2.start()
            except Exception:
                pass
        else:
            eng2 = factory()
        # Ensure snapshot file visible to eng2 if different base
        try:
            base2 = Path(eng2.persistence.persistence_path) if hasattr(eng2.persistence, "persistence_path") else None
            if base2 is not None and base2 != Path(path).parent:
                import shutil
                target = Path(base2) / Path(path).name
                shutil.copy2(path, target)
                sha_a = path + ".sha256"
                if os.path.exists(sha_a):
                    shutil.copy2(sha_a, str(target) + ".sha256")
        except Exception:
            pass
        eng2.load(name)
        snap2 = eng2.persistence.load(name)
        h2 = hash_snapshot(snap2)
        if h != h2:
            raise VerificationError(f"save-load cycle {c} hash mismatch", subsystem="stress", operation="stress_save_load_cycles", details={"cycle": c, "h": h, "h2": h2})
        try:
            eng2.stop(); eng2.shutdown()
        except Exception:
            pass
        try:
            os.remove(path)
            if os.path.exists(path + ".sha256"):
                os.remove(path + ".sha256")
        except Exception:
            pass
    try:
        engine.stop(); engine.shutdown()
    except Exception:
        pass
    return {"passed": True, "cycles": cycles, "hashes": hashes}


def inject_corrupted_snapshot(persistence_path: Path, payload: Dict[str, Any], *, corrupt: str = "json") -> Path:
    """Write a corrupted snapshot for testing detection.

    `corrupt` can be "json" (truncate), "checksum" (wrong sha), "schema" (missing version).
    Returns path to corrupted file.
    """
    persistence_path.mkdir(parents=True, exist_ok=True)
    name = "corrupted_probe"
    path = persistence_path / f"{name}.json"
    if corrupt == "json":
        path.write_text('{"schema_version": "1.0.0", "engine_state": { broken')
        # No sidecar
    elif corrupt == "checksum":
        path.write_text(json.dumps({"schema_version": "1.0.0", "engine_state": {}, "tick": 0, "simulation_time": {}, "entities": {}, "frames": {}, "rng_state": {}}))
        sidecar = Path(str(path) + ".sha256")
        sidecar.write_text("0" * 64)
    elif corrupt == "schema":
        path.write_text(json.dumps({"engine_state": {}, "tick": 0}))
        import hashlib
        sidecar = Path(str(path) + ".sha256")
        sidecar.write_text(hashlib.sha256(path.read_bytes()).hexdigest())
    else:
        raise ValueError(f"unknown corrupt mode {corrupt}")
    return path


def verify_corruption_detection(persistence_path: Optional[Path] = None) -> Dict[str, Any]:
    """Test that corrupted snapshots are detected by our verification."""
    tmp = persistence_path or Path(tempfile.mkdtemp(prefix="astra_verify_stress_"))
    results: Dict[str, Any] = {}
    for mode in ["json", "checksum", "schema"]:
        p = inject_corrupted_snapshot(tmp, {}, corrupt=mode)
        res = detect_corrupted_snapshot(str(p))
        results[mode] = res
        if res["valid"]:
            raise VerificationError(f"corruption not detected for {mode}", subsystem="stress", operation="verify_corruption_detection", details=res)
        try:
            os.remove(p)
            sc = Path(str(p) + ".sha256")
            if sc.exists():
                os.remove(sc)
        except Exception:
            pass
    return {"passed": True, "results": results}


def verify_determinism_under_load(factory: Callable[[], Any], *, steps: int = 50, dt: float = 1.0, parallel: int = 3) -> Dict[str, Any]:
    """Run `parallel` independent engines in sequence and ensure all hashes match at end."""
    finals: List[str] = []
    for _ in range(parallel):
        eng = factory()
        for _ in range(steps):
            _engine_tick(eng, dt)
        finals.append(hash_engine(eng))
        try:
            eng.stop(); eng.shutdown()
        except Exception:
            pass
    if len(set(finals)) != 1:
        raise VerificationError(f"parallel determinism diverged: {finals[:3]}", subsystem="stress", operation="verify_determinism_under_load", details={"finals": finals})
    return {"passed": True, "final_hash": finals[0], "parallel": parallel}


__all__ = [
    "stress_long_run",
    "stress_save_load_cycles",
    "inject_corrupted_snapshot",
    "verify_corruption_detection",
    "verify_determinism_under_load",
]
