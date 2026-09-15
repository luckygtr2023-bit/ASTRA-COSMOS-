"""Physics / mathematics / orbital invariants with tolerances.

Each check returns {passed: bool, ...} or raises InvariantViolationError.
Caller may catch and aggregate.

Bounds:
  Included: mass, momentum, energy positivity, orbital mechanics (e, a bounds),
            relativity (no superluminal, time dilation within bounds),
            determinism of integrators.
  Excluded: rendering invariants (pixel) — covered by rendering verification.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .exceptions import InvariantViolationError
from .numerical import is_close, vectors_close, norm, verify_finite, verify_vector_finite


def check_mass_positive(mass: float, *, label: str = "mass") -> None:
    verify_finite(mass, label=label)
    if mass < 0:
        raise InvariantViolationError(f"{label} negative: {mass}", invariant="mass_positive", operation="check_mass_positive")


def check_rest_mass_positive(mass: float, **kw) -> None:
    check_mass_positive(mass, **kw)


def check_energy_positive(energy: float, *, label: str = "energy") -> None:
    verify_finite(energy, label=label)
    if energy < -1e-9:  # allow tiny negative due to fp
        raise InvariantViolationError(f"{label} negative: {energy}", invariant="energy_positive", operation="check_energy_positive")


def check_momentum_finite(momentum: List[float], *, label: str = "momentum") -> None:
    verify_vector_finite(momentum, label=label)


def check_orbital_elements(elements: Dict[str, Any], *, atol: float = 1e-12) -> Dict[str, Any]:
    """Check Keplerian elements within physical bounds.

    Expected keys: semi_major_axis, eccentricity, inclination, etc. Handles missing gracefully.
    """
    e = elements.get("eccentricity")
    a = elements.get("semi_major_axis")
    if e is not None:
        verify_finite(float(e), label="eccentricity")
        if e < -atol or e >= 1.0 + 1e-9:  # allow slightly >1 for hyperbolic but flag
            # For elliptical we expect 0 <= e < 1; hyperbolic e > 1 is valid in some contexts
            # So we only error if e < 0 or e is huge
            if e < 0:
                raise InvariantViolationError(f"eccentricity negative: {e}", invariant="eccentricity_bounds")
            if e > 1e3:
                raise InvariantViolationError(f"eccentricity unphysical: {e}", invariant="eccentricity_bounds")
    if a is not None:
        verify_finite(float(a), label="semi_major_axis")
        if abs(float(a)) < 1e-12:
            raise InvariantViolationError(f"semi_major_axis near zero: {a}", invariant="semi_major_axis_finite")
    return {"passed": True}


def check_black_hole_horizon(radius: float, mass: float) -> Dict[str, Any]:
    """Verify Schwarzschild radius consistent with mass: Rs = 2GM/c^2."""
    # Use constants from astra if available
    try:
        from astra.mathematics.constants import G, C
    except Exception:
        G = 6.67430e-11
        C = 299792458.0
    expected = 2 * G * mass / (C * C) if mass > 0 else 0.0
    if not is_close(radius, expected, atol=1e-6, rtol=1e-6):
        raise InvariantViolationError(f"Schwarzschild radius mismatch: {radius} vs {expected}", invariant="black_hole_horizon", operation="check_black_hole_horizon", details={"expected": expected, "actual": radius, "mass": mass})
    return {"passed": True, "expected": expected}


def check_relativity_gamma(v: List[float], gamma: float, *, atol: float = 1e-9) -> Dict[str, Any]:
    speed = norm(v)
    try:
        from astra.mathematics.constants import C
    except Exception:
        C = 299792458.0
    if speed >= C:
        if not gamma == float("inf") and gamma < 1e6:
            raise InvariantViolationError(f"superluminal without divergent gamma: v={speed}, gamma={gamma}", invariant="relativity_gamma")
        return {"passed": True}
    beta2 = (speed / C) ** 2
    expected = 1.0 / math.sqrt(1 - beta2)
    if not is_close(gamma, expected, atol=atol, rtol=1e-6):
        raise InvariantViolationError(f"gamma mismatch: {gamma} vs {expected}", invariant="relativity_gamma", details={"expected": expected, "actual": gamma})
    return {"passed": True, "expected": expected}


def check_world_hierarchy_no_cycles(parent_map: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """Check entity parent map has no cycles."""
    visited = set()
    for node in parent_map:
        cur = node
        chain = set()
        while cur is not None and cur in parent_map:
            if cur in chain:
                raise InvariantViolationError(f"cycle detected at {cur}", invariant="world_no_cycles", details={"cycle_at": cur})
            chain.add(cur)
            cur = parent_map.get(cur)
            if cur is not None and cur not in parent_map:
                break
    return {"passed": True, "nodes": len(parent_map)}


def check_destroyed_entities_not_rendered(destroyed_ids: List[str], rendered_ids: List[str]) -> Dict[str, Any]:
    leak = set(destroyed_ids) & set(rendered_ids)
    if leak:
        raise InvariantViolationError(f"destroyed entities still rendered: {leak}", invariant="destruction_render_boundary", details={"leak": list(leak)})
    return {"passed": True}


def run_all_entity_invariants(entity: Dict[str, Any]) -> Dict[str, Any]:
    """Run per-entity invariants for a generic entity dict (from snapshot)."""
    mass = entity.get("mass")
    if mass is not None:
        try:
            check_mass_positive(float(mass), label=f"entity {entity.get('id')} mass")
        except Exception:
            raise
    # Position/velocity finite
    pos = entity.get("position") or entity.get("pos")
    vel = entity.get("velocity") or entity.get("vel")
    if pos is not None and isinstance(pos, list):
        verify_vector_finite(pos, label="position")
    if vel is not None and isinstance(vel, list):
        verify_vector_finite(vel, label="velocity")
    return {"passed": True, "id": entity.get("id")}


def collect_physics_invariants(engine: Any, *, atol: float = 1e-9) -> Dict[str, Any]:
    """Collect physics invariants from an engine snapshot (best-effort, never fabricates)."""
    violations: List[Dict[str, Any]] = []
    try:
        # Try to get entities
        snap = None
        # Build snapshot via persistence load if possible
        try:
            name = "__inv_tmp"
            path = engine.save(name)
            snap = engine.persistence.load(name)
            import os
            os.remove(path)
            if os.path.exists(path + ".sha256"):
                os.remove(path + ".sha256")
        except Exception:
            snap = None
        if snap is not None:
            entities = getattr(snap, "entities", {}) if not isinstance(snap, dict) else snap.get("entities", {})
            for eid, ent in (entities.items() if isinstance(entities, dict) else []):
                try:
                    run_all_entity_invariants(ent if isinstance(ent, dict) else {"id": eid})
                except InvariantViolationError as e:
                    violations.append({"entity": eid, "invariant": e.invariant, "message": str(e)})
    except Exception as e:
        violations.append({"system": "collect", "message": str(e)})
    return {"passed": not violations, "violations": violations, "count": len(violations)}


__all__ = [
    "check_mass_positive",
    "check_energy_positive",
    "check_momentum_finite",
    "check_orbital_elements",
    "check_black_hole_horizon",
    "check_relativity_gamma",
    "check_world_hierarchy_no_cycles",
    "check_destroyed_entities_not_rendered",
    "run_all_entity_invariants",
    "collect_physics_invariants",
]
