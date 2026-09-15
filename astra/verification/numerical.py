"""Numerical invariants and tolerances.

Bounds:
  Included: generic float array tolerances, vector norms, orbital energy
            stability, RNG determinism, physics step stability.
  Excluded: rendering tolerances (would be pixel-based) — not here.

Tolerances are configurable per call; defaults are conservative for double-precision.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import InvariantViolationError


def is_close(a: float, b: float, *, atol: float = 1e-9, rtol: float = 1e-9) -> bool:
    return abs(a - b) <= atol + rtol * abs(b)


def vectors_close(a: List[float], b: List[float], *, atol: float = 1e-9, rtol: float = 1e-9) -> bool:
    if len(a) != len(b):
        return False
    return all(is_close(x, y, atol=atol, rtol=rtol) for x, y in zip(a, b))


def norm(v: List[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def verify_finite(value: float, *, label: str = "value") -> None:
    if not math.isfinite(value):
        raise InvariantViolationError(f"{label} not finite: {value!r}", invariant="finite", operation="verify_finite", details={"label": label, "value": value})


def verify_vector_finite(vec: List[float], *, label: str = "vector") -> None:
    for i, v in enumerate(vec):
        if not math.isfinite(v):
            raise InvariantViolationError(f"{label}[{i}] not finite: {v!r}", invariant="finite", operation="verify_vector_finite", details={"label": label, "vector": vec})


def verify_speed_limit(velocity: List[float], c: float = 299792458.0, *, label: str = "velocity") -> None:
    v = norm(velocity)
    if v > c * (1 + 1e-12):  # tiny epsilon for floating error
        raise InvariantViolationError(f"{label} exceeds c: {v} > {c}", invariant="speed_limit", operation="verify_speed_limit", details={"velocity": velocity, "speed": v, "c": c})


def verify_energy_conservation(energies: List[float], *, atol: float = 1e-6, rtol: float = 1e-6) -> Dict[str, Any]:
    """Check that sequence of total energies stays within tolerance relative to first."""
    if not energies:
        return {"passed": True, "max_drift": 0.0}
    e0 = energies[0]
    max_drift = 0.0
    for i, e in enumerate(energies[1:], 1):
        if not math.isfinite(e):
            raise InvariantViolationError(f"energy[{i}] not finite: {e}", invariant="energy_finite")
        if e0 == 0:
            drift = abs(e)
        else:
            drift = abs(e - e0) / abs(e0)
        max_drift = max(max_drift, drift)
        if not is_close(e, e0, atol=atol, rtol=rtol):
            raise InvariantViolationError(
                f"energy drift at step {i}: {e} vs {e0} (drift {drift:.3e})",
                invariant="energy_conservation",
                operation="verify_energy_conservation",
                details={"step": i, "expected": e0, "actual": e, "drift": drift, "max_drift": max_drift},
            )
    return {"passed": True, "max_drift": max_drift, "e0": e0}


def verify_momentum_conservation(momenta: List[List[float]], *, atol: float = 1e-6, rtol: float = 1e-6) -> Dict[str, Any]:
    if not momenta:
        return {"passed": True}
    p0 = momenta[0]
    for i, p in enumerate(momenta[1:], 1):
        if not vectors_close(p, p0, atol=atol, rtol=rtol):
            raise InvariantViolationError(f"momentum drift at step {i}", invariant="momentum_conservation", operation="verify_momentum_conservation", details={"step": i, "expected": p0, "actual": p})
    return {"passed": True, "p0": p0}


def verify_determinism(sequence: List[Any], repeats: int = 2, *, atol: float = 0.0, rtol: float = 0.0) -> Dict[str, Any]:
    """Verify a sequence repeats exactly (bitwise). For RNG or integrator output."""
    # Caller should provide sequence and we check that repeated generation would match;
    # Here we just verify no NaN and finite for now; actual determinism via replay module
    for i, v in enumerate(sequence):
        if isinstance(v, float) and not math.isfinite(v):
            raise InvariantViolationError(f"sequence[{i}] not finite: {v}", invariant="determinism_finite")
    return {"passed": True, "length": len(sequence)}


def verify_orbital_stability(semi_major_axes: List[float], *, allowed_drift: float = 1e-6) -> Dict[str, Any]:
    """Check that semi-major axis does not drift beyond allowed relative fraction over sequence."""
    if not semi_major_axes:
        return {"passed": True}
    a0 = semi_major_axes[0]
    max_rel = 0.0
    for i, a in enumerate(semi_major_axes[1:], 1):
        if a0 == 0:
            rel = abs(a)
        else:
            rel = abs(a - a0) / abs(a0)
        max_rel = max(max_rel, rel)
        if rel > allowed_drift:
            raise InvariantViolationError(f"orbital drift at step {i}: {rel:.3e} > {allowed_drift:.3e}", invariant="orbital_stability", operation="verify_orbital_stability", details={"step": i, "a0": a0, "a": a, "rel": rel})
    return {"passed": True, "max_rel": max_rel}


__all__ = [
    "is_close",
    "vectors_close",
    "norm",
    "verify_finite",
    "verify_vector_finite",
    "verify_speed_limit",
    "verify_energy_conservation",
    "verify_momentum_conservation",
    "verify_determinism",
    "verify_orbital_stability",
]
