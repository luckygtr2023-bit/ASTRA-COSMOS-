"""ASTRA Scientific — validity checking (§2.8).

Multi-dimensional checker that reports violations, closest boundary and
severity without silently accepting out-of-domain use.  The policy
(§2.15) decides whether to warn or reject.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from .models import ValidityDomain
from .warnings import WarningCode, WarningSeverity


@dataclass(frozen=True)
class ValidityViolation:
    """Single dimension violation."""

    dimension: str
    value: float
    allowed: Tuple[float, float]

    def distance_to_boundary(self) -> float:
        lo, hi = self.allowed
        if self.value < lo:
            return lo - self.value
        if self.value > hi:
            return self.value - hi
        return 0.0


@dataclass(frozen=True)
class ValidityResult:
    """Result of a validity check (§2.8 enhanced)."""

    is_valid: bool
    violations: Tuple[ValidityViolation, ...]
    severity: WarningSeverity
    warning_code: WarningCode
    # Closest boundary per violated dimension (for diagnostics)
    closest_boundary: Dict[str, Tuple[float, float]]

    @property
    def violated_dimensions(self) -> Tuple[str, ...]:
        return tuple(v.dimension for v in self.violations)


class ValidityChecker:
    """Multi-dimensional validity checker (stateless)."""

    @staticmethod
    def check(domain: ValidityDomain, values: Dict[str, float]) -> ValidityResult:
        """Check ``values`` against ``domain``.

        Dimensions absent from ``values`` are skipped (not violated).
        Non-numeric or non-finite values are treated as violations with
        WARNING severity.

        Returns:
            ValidityResult with is_valid, violations, severity, warning_code,
            and closest_boundary map.
        """
        if not isinstance(domain, ValidityDomain):
            raise TypeError("domain must be a ValidityDomain")
        if not isinstance(values, dict):
            raise TypeError("values must be a dict")

        violations: list[ValidityViolation] = []
        closest: Dict[str, Tuple[float, float]] = {}

        for dim, (lo, hi) in sorted(domain.dimensions.items()):
            if dim not in values:
                continue
            raw = values[dim]
            # Validate numeric
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                # Non-numeric is a violation (treated as out-of-domain)
                violations.append(ValidityViolation(dim, float("nan"), (lo, hi)))
                closest[dim] = (lo, hi)
                continue
            import math
            try:
                v = float(raw)
            except (TypeError, ValueError):
                violations.append(ValidityViolation(dim, float("nan"), (lo, hi)))
                closest[dim] = (lo, hi)
                continue
            if math.isnan(v) or math.isinf(v):
                violations.append(ValidityViolation(dim, v, (lo, hi)))
                closest[dim] = (lo, hi)
                continue
            if not (lo <= v <= hi):
                violations.append(ValidityViolation(dim, v, (lo, hi)))
                closest[dim] = (lo, hi)

        if not violations:
            return ValidityResult(
                is_valid=True,
                violations=(),
                severity=WarningSeverity.INFO,
                warning_code=WarningCode.MODEL_OUTSIDE_VALID_RANGE,
                closest_boundary={},
            )
        # Any violation is at least WARNING; too many violations escalate to ERROR
        # but the checker itself reports WARNING — policy may escalate to BLOCKING
        # via enforce().  Here we report WARNING for single violations, ERROR for 3+.
        if len(violations) >= 3:
            severity = WarningSeverity.ERROR
        else:
            severity = WarningSeverity.WARNING
        return ValidityResult(
            is_valid=False,
            violations=tuple(violations),
            severity=severity,
            warning_code=WarningCode.MODEL_OUTSIDE_VALID_RANGE,
            closest_boundary=closest,
        )

    @staticmethod
    def is_valid(domain: ValidityDomain, values: Dict[str, float]) -> bool:
        """Convenience: just the boolean."""
        return ValidityChecker.check(domain, values).is_valid
