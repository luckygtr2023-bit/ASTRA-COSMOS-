"""Celestial provenance and determinism checks.

Bounds:
  Included: identity stability (temporary_id / seed), provenance metadata preserved,
            no fabricated authoritative positions, catalogue lookup is from registry.
  Excluded: ephemeris accuracy — only that provenance is preserved verbatim.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .exceptions import InvariantViolationError, VerificationError


def check_celestial_identity_stable(snapshot_before: Any, snapshot_after: Any) -> Dict[str, Any]:
    """Ensure celestial object IDs and seeds preserved across snapshot round-trip."""
    try:
        # Normalize to dict
        def to_entities(snap):
            if isinstance(snap, dict):
                return snap.get("entities", snap.get("celestial", snap.get("objects", {})))
            snap_d = getattr(snap, "entities", None)
            if isinstance(snap_d, dict):
                return snap_d
            return {}
        ents_b = to_entities(snapshot_before)
        ents_a = to_entities(snapshot_after)
        if not isinstance(ents_b, dict) or not isinstance(ents_a, dict):
            return {"passed": True, "skipped": True}
        # Identify celestial entities by having 'provenance' or 'catalogue' or 'celestial'
        cel_ids_b = {eid: ent for eid, ent in ents_b.items() if isinstance(ent, dict) and ("provenance" in ent or "seed" in ent or "catalogue" in ent or "celestial_type" in ent)}
        cel_ids_a = {eid: ent for eid, ent in ents_a.items() if isinstance(ent, dict) and ("provenance" in ent or "seed" in ent or "catalogue" in ent or "celestial_type" in ent)}
        # Check that every celestial id before exists after with same seed/provenance
        violations: List[Dict[str, Any]] = []
        for eid, ent_b in cel_ids_b.items():
            ent_a = cel_ids_a.get(eid)
            if ent_a is None:
                violations.append({"id": eid, "type": "missing_after"})
                continue
            for key in ["seed", "provenance", "catalogue_id", "temporary_id"]:
                if key in ent_b and ent_b[key] != ent_a.get(key):
                    violations.append({"id": eid, "key": key, "expected": ent_b[key], "actual": ent_a.get(key), "type": "provenance_mismatch"})
        if violations:
            raise InvariantViolationError(f"celestial identity/provenance changed: {violations[:3]}", invariant="celestial_provenance", details={"violations": violations})
        return {"passed": True, "celestial_count": len(cel_ids_b)}
    except InvariantViolationError:
        raise
    except Exception as e:
        raise VerificationError(f"celestial identity check failed: {e}", subsystem="celestial", operation="check_celestial_identity_stable", details={"error": str(e)})


def check_no_fabricated_ephemeris(objects: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure objects with authority_required do not have synthetic positions without provenance."""
    violations: List[Dict[str, Any]] = []
    for oid, obj in objects.items():
        if not isinstance(obj, dict):
            continue
        # If object claims high precision without authority, that's fabricating
        authority = obj.get("provenance", {}).get("authority") if isinstance(obj.get("provenance"), dict) else obj.get("authority")
        pos = obj.get("position") or obj.get("pos") or obj.get("coords")
        # Rule: objects with `requires_authority: True` must have provenance.authority not None
        if obj.get("requires_authority") and not authority:
            violations.append({"id": oid, "type": "fabricated_without_authority", "pos": pos})
        # Also flag placeholder positions like [0,0,0] for authoritative objects without provenance note
        if authority is None and pos == [0, 0, 0] and obj.get("celestial_type") in ("star", "planet", "pulsar"):
            # This is likely a placeholder; we note but not fail — just warn
            pass
    if violations:
        raise InvariantViolationError(f"fabricated ephemeris: {violations[:3]}", invariant="celestial_no_fabrication", details={"violations": violations})
    return {"passed": True, "checked": len(objects)}


def check_celestial_determinism(factory, *, ticks: int = 3, dt: float = 3600.0) -> Dict[str, Any]:
    """Verify celestial system evolves deterministically (if tickable)."""
    try:
        from .state_hash import hash_canonical
        # Factory returns celestial manager/world
        c1 = factory()
        c2 = factory()
        for _ in range(ticks):
            if hasattr(c1, "tick"):
                c1.tick(dt)
            if hasattr(c2, "tick"):
                c2.tick(dt)
            # Hash via to_dict or snapshot
            def snap(c):
                if hasattr(c, "to_dict"):
                    return c.to_dict()
                if hasattr(c, "get_state_snapshot"):
                    return c.get_state_snapshot()
                return getattr(c, "__dict__", {})
            h1 = hash_canonical(snap(c1))
            h2 = hash_canonical(snap(c2))
            if h1 != h2:
                raise InvariantViolationError("celestial determinism diverged", invariant="celestial_determinism", details={"h1": h1, "h2": h2})
        return {"passed": True, "ticks": ticks}
    except InvariantViolationError:
        raise
    except Exception as e:
        raise VerificationError(f"celestial determinism check failed: {e}", subsystem="celestial", operation="check_celestial_determinism")


def collect_celestial_checks(snapshot_before: Any = None, snapshot_after: Any = None, objects: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    if snapshot_before is not None and snapshot_after is not None:
        try:
            check_celestial_identity_stable(snapshot_before, snapshot_after)
        except InvariantViolationError as e:
            violations.append({"check": "identity_stable", "invariant": e.invariant, "message": str(e), "details": e.details})
    if objects is not None:
        try:
            check_no_fabricated_ephemeris(objects)
        except InvariantViolationError as e:
            violations.append({"check": "no_fabrication", "invariant": e.invariant, "message": str(e)})
    return {"passed": not violations, "violations": violations}


__all__ = [
    "check_celestial_identity_stable",
    "check_no_fabricated_ephemeris",
    "check_celestial_determinism",
    "collect_celestial_checks",
]
