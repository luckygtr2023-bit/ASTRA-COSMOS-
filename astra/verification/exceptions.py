"""Verification exceptions — explicit failure boundaries."""

from __future__ import annotations

from typing import Any, Dict, Optional


class VerificationError(Exception):
    """Base for verification failures."""

    def __init__(self, message: str, *, subsystem: str = "verification", operation: str = "", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.subsystem = subsystem
        self.operation = operation
        self.details = details or {}

    def __str__(self):
        return f"[{self.subsystem}:{self.operation}] {super().__str__()} {self.details}"


class HashError(VerificationError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "state_hash")
        super().__init__(message, **kw)


class ComparisonError(VerificationError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "state_compare")
        super().__init__(message, **kw)


class SnapshotVerificationError(VerificationError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "snapshot")
        super().__init__(message, **kw)


class ReplayDivergenceError(VerificationError):
    def __init__(self, message: str, *, step: int = -1, expected_hash: str = "", actual_hash: str = "", divergence: Optional[Dict[str, Any]] = None, **kw):
        kw.setdefault("subsystem", "replay")
        kw.setdefault("operation", "replay")
        details = kw.get("details") or {}
        details.update({"step": step, "expected_hash": expected_hash, "actual_hash": actual_hash, "divergence": divergence or {}})
        kw["details"] = details
        super().__init__(message, **kw)
        self.step = step
        self.expected_hash = expected_hash
        self.actual_hash = actual_hash
        self.divergence = divergence or {}


class InvariantViolationError(VerificationError):
    def __init__(self, message: str, *, invariant: str = "", **kw):
        kw.setdefault("subsystem", "invariants")
        details = kw.get("details") or {}
        details["invariant"] = invariant
        kw["details"] = details
        super().__init__(message, **kw)
        self.invariant = invariant


class CorruptedStateError(VerificationError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "persistence")
        super().__init__(message, **kw)


__all__ = [
    "VerificationError",
    "HashError",
    "ComparisonError",
    "SnapshotVerificationError",
    "ReplayDivergenceError",
    "InvariantViolationError",
    "CorruptedStateError",
]
