"""State comparison and divergence detection.

Provides deterministic, tolerance-aware comparison for verification hashes
and field-level diffs.

Tolerances:
  - Floats: abs(a-b) <= atol + rtol*abs(b)  (default atol=1e-9, rtol=1e-9)
  - For orbital / celestial, caller may supply tighter/looser tolerances
  - Integer/string/bool: exact equality
  - Ordering: dict keys compared sorted; lists ordered (deterministic traversal)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .exceptions import ComparisonError
from .state_hash import hash_snapshot, hash_canonical, canonical_json


def _float_equal(a: float, b: float, atol: float, rtol: float) -> bool:
    if not math.isfinite(a) or not math.isfinite(b):
        return a == b  # NaN never equal, inf equality as per IEEE
    diff = abs(a - b)
    return diff <= atol + rtol * abs(b)


def compare_values(a: Any, b: Any, *, atol: float = 1e-9, rtol: float = 1e-9, path: str = "") -> List[Dict[str, Any]]:
    """Compare two values tolerance-aware, returning list of diffs (empty if equal)."""
    diffs: List[Dict[str, Any]] = []
    if type(a) != type(b):
        # Allow int/float cross comparison
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if _float_equal(float(a), float(b), atol, rtol):
                return diffs
            diffs.append({"path": path or "<root>", "expected": a, "actual": b, "diff": float(a) - float(b), "type": "float_mismatch"})
            return diffs
        diffs.append({"path": path or "<root>", "expected": f"{type(a).__name__}:{a!r}", "actual": f"{type(b).__name__}:{b!r}", "type": "type_mismatch"})
        return diffs
    if isinstance(a, float):
        if not _float_equal(a, b, atol, rtol):
            diffs.append({"path": path, "expected": a, "actual": b, "diff": a - b, "abs_diff": abs(a - b), "type": "float_mismatch"})
        return diffs
    if isinstance(a, (int, bool, str)) or a is None:
        if a != b:
            diffs.append({"path": path, "expected": a, "actual": b, "type": "value_mismatch"})
        return diffs
    if isinstance(a, dict):
        keys = set(a.keys()) | set(b.keys())
        for k in sorted(keys, key=lambda x: str(x)):
            sub_path = f"{path}.{k}" if path else str(k)
            if k not in a:
                diffs.append({"path": sub_path, "expected": "<missing>", "actual": b[k], "type": "missing_in_expected"})
            elif k not in b:
                diffs.append({"path": sub_path, "expected": a[k], "actual": "<missing>", "type": "missing_in_actual"})
            else:
                diffs.extend(compare_values(a[k], b[k], atol=atol, rtol=rtol, path=sub_path))
        return diffs
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            diffs.append({"path": path, "expected_len": len(a), "actual_len": len(b), "type": "length_mismatch"})
            # Still compare up to min length
            m = min(len(a), len(b))
        else:
            m = len(a)
        for i in range(m):
            sub_path = f"{path}[{i}]"
            diffs.extend(compare_values(a[i], b[i], atol=atol, rtol=rtol, path=sub_path))
        return diffs
    # Fallback: use equality
    if a != b:
        diffs.append({"path": path, "expected": repr(a), "actual": repr(b), "type": "value_mismatch"})
    return diffs


def compare_snapshots(a: Any, b: Any, *, atol: float = 1e-9, rtol: float = 1e-9) -> Dict[str, Any]:
    """Compare two snapshots (Snapshot dataclass or dict) deterministically.

    Returns:
      {
        "equal": bool,
        "hash_equal": bool,
        "expected_hash": str,
        "actual_hash": str,
        "diffs": [...],
        "summary": "...",
      }
    """
    from .state_hash import snapshot_to_canonical_dict
    try:
        canon_a = snapshot_to_canonical_dict(a)
        canon_b = snapshot_to_canonical_dict(b)
        hash_a = hash_snapshot(a)
        hash_b = hash_snapshot(b)
    except Exception as e:
        raise ComparisonError(f"failed to hash snapshots: {e}", operation="compare_snapshots", details={"error": str(e)})
    diffs = compare_values(canon_a, canon_b, atol=atol, rtol=rtol, path="")
    hash_equal = hash_a == hash_b
    # If hashes equal but diffs non-empty, likely tolerance hid difference; still report diffs
    equal = hash_equal and not diffs
    # If hashes differ but no diffs within tolerance, report as tolerance-forgiven
    # For verification, hash equality is stricter than tolerance; we surface both
    summary = f"hash_equal={hash_equal}, diffs={len(diffs)}, equal={equal}"
    return {"equal": equal, "hash_equal": hash_equal, "expected_hash": hash_a, "actual_hash": hash_b, "diffs": diffs[:100], "diff_count": len(diffs), "summary": summary}


def compare_canonical(a: Any, b: Any, *, atol: float = 1e-9, rtol: float = 1e-9) -> Dict[str, Any]:
    """Compare arbitrary canonical data with tolerance."""
    hash_a = hash_canonical(a)
    hash_b = hash_canonical(b)
    diffs = compare_values(a, b, atol=atol, rtol=rtol, path="")
    return {"equal": not diffs and hash_a == hash_b, "hash_equal": hash_a == hash_b, "expected_hash": hash_a, "actual_hash": hash_b, "diffs": diffs[:100], "diff_count": len(diffs)}


def first_divergence(sequence_a: List[Any], sequence_b: List[Any], *, atol: float = 1e-9, rtol: float = 1e-9) -> Optional[Dict[str, Any]]:
    """Find first divergence index between two hash sequences."""
    n = min(len(sequence_a), len(sequence_b))
    for i in range(n):
        if sequence_a[i] != sequence_b[i]:
            # Optionally do field-level diff if entries are dicts
            diffs = []
            if isinstance(sequence_a[i], dict) and isinstance(sequence_b[i], dict):
                diffs = compare_values(sequence_a[i], sequence_b[i], atol=atol, rtol=rtol, path=f"[{i}]")
            return {"index": i, "expected": sequence_a[i], "actual": sequence_b[i], "diffs": diffs}
    if len(sequence_a) != len(sequence_b):
        return {"index": n, "expected_len": len(sequence_a), "actual_len": len(sequence_b), "type": "length_mismatch"}
    return None


def assert_snapshots_equal(a: Any, b: Any, *, atol: float = 1e-9, rtol: float = 1e-9) -> None:
    """Raise ComparisonError if snapshots differ."""
    res = compare_snapshots(a, b, atol=atol, rtol=rtol)
    if not res["equal"]:
        raise ComparisonError(f"snapshots differ: {res['summary']}", operation="assert_snapshots_equal", details=res)


__all__ = [
    "compare_values",
    "compare_snapshots",
    "compare_canonical",
    "first_divergence",
    "assert_snapshots_equal",
]
