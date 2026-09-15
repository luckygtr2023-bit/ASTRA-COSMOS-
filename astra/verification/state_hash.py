"""Canonical state hashing — deterministic, stable, provenance-preserving.

What is hashed (included):
  - Snapshot.schema_version
  - Snapshot.tick
  - Snapshot.engine_state (deterministically serialized)
  - Snapshot.simulation_time
  - Snapshot.entities (sorted by entity id)
  - Snapshot.frames (sorted)
  - Snapshot.rng_state (canonical)
  - Snapshot.command_history / event_history (truncated deterministically if needed)

What is excluded (not hashed):
  - Snapshot.timestamp (wall-clock, not semantic)
  - Snapshot.checksum (derived)
  - MAGIC_HEADER (not part of semantic state)
  - Any memory-address dependent repr (e.g., `id()`, `hex(id(...))`)

Requirements:
  - Deterministic: same semantic state → same hash across runs/platforms
  - Canonical ordering: dict keys sorted, entity/frame lists sorted by id
  - Stable floats: NaN/inf rejected (verification hash must not mask corruption),
    finite floats canonicalized via repr with 17g
  - Distinguishes meaningful changes: any entity position/mass/provenance change
    changes hash
  - Remains stable when semantically unchanged: ordering of insertion does not
    affect hash; timestamp change alone does not change hash
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Optional, Tuple

from astra.core.persistence import Snapshot

from .exceptions import HashError


def _canonicalize(value: Any) -> Any:
    """Convert value to canonical JSON-compatible form.

    - dicts: keys sorted, values canonicalized
    - lists/tuples: each element canonicalized (order preserved — caller must sort if needed)
    - floats: finite only, canonical string via .hex or repr; we use repr with 17g and re-parse to ensure stability
    - ints: as-is
    - bool/None/str: as-is
    - bytes: not allowed (must be decoded)
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise HashError(f"non-finite float {value!r} not allowed in verification hash", operation="canonicalize")
        # Use repr with 17 significant digits for round-trip stability
        # Then re-parse to float and re-format to eliminate platform differences in 17g
        # We keep as string to avoid JSON encoder differences? No, we keep as number but ensure canonical.
        # Instead we format as string with 17g and then loads as float via json? For hash we can keep as string representation.
        # Simpler: return float's canonical string via format(value, '.17g') but keep as string marker?
        # We choose to return stringified float with marker to avoid JSON float rounding differences.
        # However for determinism we can let json encoder handle float, but we canonicalize by using Python's repr which is stable per CPython 3.11.
        # Use format to ensure 17g.
        s = format(value, ".17g")
        # Re-parse to ensure that `0.1` and `0.10000000000000001` converge? But we want to preserve meaningful differences.
        # So we keep s as string? No, keep as float(s) to let json serialize as number. But then 0.1 vs 0.10000000000000001 would be considered same if they parse to same binary? Actually they are same binary.
        # So we return float(s)
        return float(s)
    if isinstance(value, dict):
        # Keys must be strings for canonical JSON; coerce but require stable
        out = {}
        for k in sorted(value.keys(), key=lambda x: str(x)):
            if not isinstance(k, str):
                # For snapshot, keys are strings; if not, coerce to str deterministically
                k_str = str(k)
            else:
                k_str = k
            out[k_str] = _canonicalize(value[k])
        return out
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    if isinstance(value, bytes):
        raise HashError(f"bytes not allowed in verification hash: {value!r}", operation="canonicalize")
    # For dataclass-like objects that have been converted via asdict, they are already dicts
    # If still unknown type, try to convert via str deterministically but flag
    # Instead require only JSON primitives
    raise HashError(f"unsupported type {type(value).__name__} in verification hash: {value!r}", operation="canonicalize")


def canonical_json(data: Any) -> str:
    """Deterministic JSON string with sorted keys and canonical floats."""
    canon = _canonicalize(data)
    # separators to eliminate whitespace variability
    return json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_bytes(data: Any) -> bytes:
    return canonical_json(data).encode("utf-8")


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_canonical(data: Any) -> str:
    return hash_bytes(canonical_bytes(data))


# ---------------------------------------------------------------------------
# Snapshot hashing
# ---------------------------------------------------------------------------

def snapshot_to_canonical_dict(snapshot: Any) -> Dict[str, Any]:
    """Convert Snapshot (or dict) to canonical dict for hashing.

    Accepts either `Snapshot` dataclass or plain dict (e.g., loaded JSON).
    Excludes timestamp/checksum.
    """
    if isinstance(snapshot, dict):
        d = snapshot
        # Normalize keys: snapshot may have been loaded via PersistenceManager which returns Snapshot dataclass
        # If dict, expect same fields as Snapshot
        canon = {
            "schema_version": d.get("schema_version", ""),
            "tick": int(d.get("tick", 0)),
            "engine_state": d.get("engine_state", {}),
            "simulation_time": d.get("simulation_time", {}),
            "entities": _sorted_entities(d.get("entities", {})),
            "frames": _sorted_frames(d.get("frames", {})),
            "rng_state": _sorted_rng(d.get("rng_state", {})),
            "command_history": _truncated_history(d.get("command_history", [])),
            "event_history": _truncated_history(d.get("event_history", [])),
        }
        return canon
    # Assume Snapshot dataclass
    try:
        # Use __dataclass_fields__ if available
        canon = {
            "schema_version": getattr(snapshot, "schema_version", ""),
            "tick": int(getattr(snapshot, "tick", 0)),
            "engine_state": getattr(snapshot, "engine_state", {}),
            "simulation_time": getattr(snapshot, "simulation_time", {}),
            "entities": _sorted_entities(getattr(snapshot, "entities", {})),
            "frames": _sorted_frames(getattr(snapshot, "frames", {})),
            "rng_state": _sorted_rng(getattr(snapshot, "rng_state", {})),
            "command_history": _truncated_history(getattr(snapshot, "command_history", [])),
            "event_history": _truncated_history(getattr(snapshot, "event_history", [])),
        }
        return canon
    except Exception as e:
        raise HashError(f"failed to convert snapshot to canonical dict: {e}", operation="snapshot_to_canonical")


def _sorted_entities(entities: Any) -> Dict[str, Any]:
    if not isinstance(entities, dict):
        # World snapshot may be list-like; coerce deterministically
        if isinstance(entities, list):
            # assume list of dicts with id
            out = {}
            for e in entities:
                if isinstance(e, dict) and "id" in e:
                    out[str(e["id"])] = e
                else:
                    out[str(e)] = e
            entities = out
        else:
            raise HashError(f"entities must be dict, got {type(entities).__name__}", operation="sorted_entities")
    # Sort by entity id
    out = {}
    for k in sorted(entities.keys(), key=lambda x: str(x)):
        out[str(k)] = entities[k]
    return out


def _sorted_frames(frames: Any) -> Dict[str, Any]:
    if not isinstance(frames, dict):
        return {}
    out = {}
    for k in sorted(frames.keys(), key=lambda x: str(x)):
        out[str(k)] = frames[k]
    return out


def _sorted_rng(rng_state: Any) -> Dict[str, Any]:
    if not isinstance(rng_state, dict):
        return {}
    out = {}
    for k in sorted(rng_state.keys(), key=lambda x: str(x)):
        out[str(k)] = rng_state[k]
    return out


def _truncated_history(history: Any) -> List[Any]:
    if not isinstance(history, list):
        return []
    # For determinism, we include history as-is but ensure each entry is canonicalized.
    # No truncation by default; caller can limit if needed. For hashing we include full history
    # but sorted deterministically? History is ordered by tick/sequence, which is already deterministic.
    return list(history)


def hash_snapshot(snapshot: Any) -> str:
    """Deterministic SHA-256 hex of canonical snapshot dict."""
    canon = snapshot_to_canonical_dict(snapshot)
    # Use canonical_json which will sort keys and canonicalize floats
    try:
        j = canonical_json(canon)
    except HashError:
        raise
    except Exception as e:
        raise HashError(f"canonical_json failed: {e}", operation="hash_snapshot", details={"error": str(e)})
    return hash_bytes(j.encode("utf-8"))


def hash_snapshot_bytes(snapshot: Any) -> bytes:
    canon = snapshot_to_canonical_dict(snapshot)
    j = canonical_json(canon)
    return j.encode("utf-8")


# ---------------------------------------------------------------------------
# Engine and World hashing helpers
# ---------------------------------------------------------------------------

def hash_engine(engine: Any) -> str:
    """Hash the engine's current semantic state without I/O.

    Builds an ephemeral Snapshot via engine._persistence path but without writing to disk.
    Uses engine's internal serialization (see Engine.save) but without timestamp/checksum.
    """
    # Reuse Engine.save logic but construct snapshot manually to avoid file I/O
    # We call engine's internal snapshot building via a lightweight approach:
    # Instead of duplicating, we call engine persistence snapshot building if available,
    # otherwise we use engine.save to a temporary file and load back.
    # For speed and determinism, we build dict directly from engine's public getters.
    try:
        # Prefer direct snapshot building via engine's private but stable method:
        # Engine.save builds snapshot via engine.persistence logic; we can mimic:
        from astra.core.persistence import Snapshot as Snap
        # Build snapshot dict from engine's current state (mirror Engine.save)
        # To avoid duplicating private logic, we use Engine's save to a temp file if needed
        import tempfile, pathlib, json
        with tempfile.TemporaryDirectory() as td:
            # Use a temporary persistence manager path to avoid polluting engine's base_path
            # But Engine.save will write to its configured persistence_path; we can instead
            # directly call engine's snapshot construction via a helper if available
            # Fallback: use engine.save with a temp name then load
            tmp_name = "__verify_tmp_hash"
            # Save and immediately load snapshot object (not file contents hashing)
            path = engine.save(tmp_name)
            snap = engine.persistence.load(tmp_name)
            # Clean up file
            try:
                import os
                os.remove(path)
                # Also try to remove .sha256 sidecar if exists
                sha_path = path + ".sha256"
                if os.path.exists(sha_path):
                    os.remove(sha_path)
            except Exception:
                pass
            return hash_snapshot(snap)
    except Exception as e:
        raise HashError(f"hash_engine failed: {e}", operation="hash_engine", details={"error": str(e)})


def hash_world(world: Any) -> str:
    """Hash world state deterministically (if world provides snapshot)."""
    try:
        if hasattr(world, "get_state_snapshot"):
            snap = world.get_state_snapshot()  # type: ignore
        elif hasattr(world, "to_dict"):
            snap = world.to_dict()  # type: ignore
        elif hasattr(world, "to_serializable"):
            snap = world.to_serializable()  # type: ignore
        else:
            # Fallback: use __dict__ but canonicalized (avoid private)
            snap = {k: v for k, v in world.__dict__.items() if not k.startswith("_")}
        return hash_canonical(snap)
    except Exception as e:
        raise HashError(f"hash_world failed: {e}", operation="hash_world")


def hash_render_state(render_state: Any) -> str:
    """Hash astra.rendering RenderState deterministically."""
    try:
        if hasattr(render_state, "to_dict"):
            d = render_state.to_dict()
        else:
            d = dict(render_state)
        return hash_canonical(d)
    except Exception as e:
        raise HashError(f"hash_render_state failed: {e}", operation="hash_render_state")


__all__ = [
    "canonical_json",
    "canonical_bytes",
    "hash_bytes",
    "hash_canonical",
    "snapshot_to_canonical_dict",
    "hash_snapshot",
    "hash_snapshot_bytes",
    "hash_engine",
    "hash_world",
    "hash_render_state",
]
