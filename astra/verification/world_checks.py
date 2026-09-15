"""World / scene consistency checks.

Bounds:
  Included: hierarchy consistency, transform propagation, region lifecycle,
            duplication, orphan detection, view isolation.
  Excluded: rendering correctness (pixels) — covered elsewhere.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .exceptions import InvariantViolationError, VerificationError


def check_hierarchy_parent_child_consistency(world: Any) -> Dict[str, Any]:
    """Ensure every child's parent points back and vice versa."""
    violations: List[Dict[str, Any]] = []
    try:
        # Resolve world data via snapshot
        snap = world.get_state_snapshot() if hasattr(world, "get_state_snapshot") else None
        if snap is None and hasattr(world, "to_dict"):
            snap = world.to_dict()
        if snap is None:
            # Fallback: inspect internal regions/entities
            snap = getattr(world, "__dict__", {})

        # Attempt to extract hierarchy map
        # World.region etc.; we handle generic structures
        # Look for entities dict with parent field
        entities: Dict[str, Any] = {}
        if isinstance(snap, dict):
            entities = snap.get("entities", snap.get("nodes", snap.get("children", {})))
            if not isinstance(entities, dict):
                entities = {}
        else:
            entities = {}

        # Parent map
        parent_map: Dict[str, Optional[str]] = {}
        children_map: Dict[str, List[str]] = {}
        for eid, ent in entities.items():
            if isinstance(ent, dict):
                parent = ent.get("parent") or ent.get("parent_id")
                parent_map[str(eid)] = str(parent) if parent is not None else None
                # children
                ch = ent.get("children", ent.get("child_ids", []))
                if isinstance(ch, list):
                    children_map[str(eid)] = [str(c) for c in ch]
            else:
                parent_map[str(eid)] = None

        for eid, parent in parent_map.items():
            if parent is not None:
                if parent not in parent_map and parent not in children_map:
                    # Allow root parent not in map if world root is not an entity
                    pass
                # Check that parent's children includes eid if children_map available
                if parent in children_map and eid not in children_map[parent]:
                    violations.append({"type": "parent_child_mismatch", "child": eid, "parent": parent, "detail": f"parent {parent} children does not include {eid}"})

        # Also check orphans: child listed but not parent-consistent
        for parent, children in children_map.items():
            for child in children:
                if parent_map.get(child) != parent:
                    violations.append({"type": "child_parent_mismatch", "child": child, "expected_parent": parent, "actual_parent": parent_map.get(child)})

        passed = not violations
        if not passed:
            raise InvariantViolationError(f"hierarchy inconsistencies: {violations[:3]}", invariant="world_hierarchy", operation="check_hierarchy_parent_child_consistency", details={"violations": violations})
        return {"passed": True, "entities": len(parent_map), "violations": violations}
    except InvariantViolationError:
        raise
    except Exception as e:
        raise VerificationError(f"hierarchy check failed: {e}", subsystem="world", operation="check_hierarchy_parent_child_consistency", details={"error": str(e)})


def check_no_duplicate_ids(world: Any) -> Dict[str, Any]:
    """Ensure no duplicate entity/region identifiers."""
    try:
        snap = world.get_state_snapshot() if hasattr(world, "get_state_snapshot") else None
        if snap is None and hasattr(world, "to_dict"):
            snap = world.to_dict()
        ids: List[str] = []
        if isinstance(snap, dict):
            # Collect from various containers
            for key in ["entities", "regions", "nodes", "objects", "frames"]:
                v = snap.get(key)
                if isinstance(v, dict):
                    ids.extend([str(k) for k in v.keys()])
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and "id" in item:
                            ids.append(str(item["id"]))
                        elif isinstance(item, str):
                            ids.append(item)
        seen: Set[str] = set()
        dups: List[str] = []
        for i in ids:
            if i in seen:
                dups.append(i)
            seen.add(i)
        if dups:
            raise InvariantViolationError(f"duplicate ids: {dups}", invariant="world_no_duplicates", details={"dups": dups})
        return {"passed": True, "total_ids": len(ids)}
    except InvariantViolationError:
        raise
    except Exception as e:
        raise VerificationError(f"duplicate check failed: {e}", subsystem="world", operation="check_no_duplicate_ids")


def check_regions_lifecycle(world: Any) -> Dict[str, Any]:
    """Regions marked active/inactive must not have active entities in inactive regions (if applicable)."""
    # Best-effort: if world has regions with entities, check consistency
    try:
        snap = world.get_state_snapshot() if hasattr(world, "get_state_snapshot") else None
        if snap is None:
            return {"passed": True, "skipped": True, "reason": "no snapshot"}
        if not isinstance(snap, dict):
            return {"passed": True, "skipped": True}
        regions = snap.get("regions", {})
        entities = snap.get("entities", {})
        violations: List[Dict[str, Any]] = []
        if isinstance(regions, dict) and isinstance(entities, dict):
            for rid, region in regions.items():
                if isinstance(region, dict) and region.get("active") is False:
                    # Check if any entity claims this region
                    for eid, ent in entities.items():
                        if isinstance(ent, dict) and ent.get("region") == rid and ent.get("active", True):
                            violations.append({"region": rid, "entity": eid, "type": "active_in_inactive_region"})
        if violations:
            raise InvariantViolationError(f"region lifecycle violations: {violations[:3]}", invariant="world_regions", details={"violations": violations})
        return {"passed": True, "regions": len(regions) if isinstance(regions, dict) else 0}
    except InvariantViolationError:
        raise
    except Exception as e:
        raise VerificationError(f"region lifecycle check failed: {e}", subsystem="world", operation="check_regions_lifecycle")


def check_world_determinism(factory, *, ticks: int = 5, dt: float = 1.0) -> Dict[str, Any]:
    """Verify world evolves deterministically over ticks (hash stable)."""
    from .state_hash import hash_world
    w1 = factory()
    w2 = factory()
    for _ in range(ticks):
        if hasattr(w1, "tick"):
            w1.tick(dt)
        if hasattr(w2, "tick"):
            w2.tick(dt)
        h1 = hash_world(w1)
        h2 = hash_world(w2)
        if h1 != h2:
            raise InvariantViolationError(f"world determinism diverged at tick {getattr(w1, 'tick', '?')}", invariant="world_determinism", details={"h1": h1, "h2": h2})
    return {"passed": True, "ticks": ticks}


def collect_world_checks(world: Any) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    checks = [check_hierarchy_parent_child_consistency, check_no_duplicate_ids, check_regions_lifecycle]
    passed = 0
    for fn in checks:
        try:
            fn(world)
            passed += 1
        except InvariantViolationError as e:
            violations.append({"check": fn.__name__, "invariant": e.invariant, "message": str(e), "details": e.details})
        except VerificationError as e:
            violations.append({"check": fn.__name__, "message": str(e), "details": e.details})
    return {"passed": not violations, "violations": violations, "passed_count": passed, "total": len(checks)}


__all__ = [
    "check_hierarchy_parent_child_consistency",
    "check_no_duplicate_ids",
    "check_regions_lifecycle",
    "check_world_determinism",
    "collect_world_checks",
]
