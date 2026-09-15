"""Verification reports — deterministic, human-readable + machine-parsable.

Report schema:
  {
    "schema_version": "1.0.0",
    "title": str,
    "passed": bool,
    "timestamp": str,
    "checks": [{"name": str, "passed": bool, "details": {...}, "duration_ms": int}],
    "divergences": [...],
    "summary": str
  }
Excluded: wall-clock timing affects pass/fail; only included as duration_ms metadata.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from .exceptions import VerificationError


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    error: Optional[str] = None


@dataclass
class VerificationReport:
    title: str
    checks: List[CheckResult] = field(default_factory=list)
    schema_version: str = "1.0.0"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def summary(self) -> str:
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.passed)
        return f"{self.title}: {passed}/{total} checks passed — {'PASS' if self.passed else 'FAIL'}"

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "title": self.title,
            "passed": self.passed,
            "timestamp": self.timestamp,
            "checks": [
                {"name": c.name, "passed": c.passed, "details": c.details, "duration_ms": c.duration_ms, "error": c.error}
                for c in self.checks
            ],
            "summary": self.summary,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def save(self, path: str) -> str:
        with open(path, "w") as f:
            f.write(self.to_json())
        return path


def run_check(name: str, fn: Callable[[], Any], *, report: Optional[VerificationReport] = None) -> CheckResult:
    start = time.perf_counter()
    try:
        details = fn()
        if isinstance(details, dict):
            passed = bool(details.get("passed", True))
            # If dict has violations non-empty, mark failed
            if details.get("violations"):
                passed = not details["violations"]
        elif isinstance(details, bool):
            passed = details
            details = {"passed": passed}
        else:
            passed = True
            details = {"result": details, "passed": passed}
        duration = int((time.perf_counter() - start) * 1000)
        res = CheckResult(name=name, passed=passed, details=details if isinstance(details, dict) else {}, duration_ms=duration)
    except Exception as e:
        duration = int((time.perf_counter() - start) * 1000)
        # Preserve invariant violation details if available
        det = getattr(e, "details", {}) if hasattr(e, "details") else {"exception": str(e), "type": type(e).__name__}
        res = CheckResult(name=name, passed=False, details=det, duration_ms=duration, error=str(e))
    if report is not None:
        report.add(res)
    return res


def build_report(title: str, checks: List[tuple]) -> VerificationReport:
    """Build report from list of (name, callable) tuples."""
    report = VerificationReport(title=title)
    for name, fn in checks:
        run_check(name, fn, report=report)
    return report


__all__ = [
    "CheckResult",
    "VerificationReport",
    "run_check",
    "build_report",
]
