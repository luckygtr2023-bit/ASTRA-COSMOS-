"""ASTRA Scientific — uncertainty metadata (§2.9–2.10).

Uncertainty absence is first-class (UNCERTAINTY_UNKNOWN), never fabricated
zero.  Propagation respects the capabilities of the existing Mathematics
system; when unavailable, callers receive UNCERTAINTY_UNKNOWN and
LimitationState.UNCERTAINTY_PROPAGATION_UNAVAILABLE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .errors import ScientificValidationError


class UncertaintyKind(str, Enum):
    ABSOLUTE = "ABSOLUTE"
    RELATIVE = "RELATIVE"
    STATISTICAL = "STATISTICAL"
    SYSTEMATIC = "SYSTEMATIC"
    MODEL = "MODEL"
    CONFIDENCE_INTERVAL = "CONFIDENCE_INTERVAL"
    COVARIANCE = "COVARIANCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Uncertainty:
    """Quantitative uncertainty (§2.9).

    One of ``value`` (absolute/relative) or ``(lower, upper)`` interval must
    be present for known uncertainties; for UNKNOWN both are None.
    """

    kind: UncertaintyKind
    value: Optional[float] = None
    lower: Optional[float] = None
    upper: Optional[float] = None
    coverage: Optional[float] = None
    covariance: Optional[tuple] = None
    notes: str = ""

    def __post_init__(self):
        if not isinstance(self.kind, UncertaintyKind):
            raise TypeError("kind must be an UncertaintyKind")
        if not isinstance(self.notes, str):
            raise TypeError("notes must be a string")
        # Validate numeric fields are finite when present
        for name, v in [("value", self.value), ("lower", self.lower),
                        ("upper", self.upper), ("coverage", self.coverage)]:
            if v is None:
                continue
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ScientificValidationError(f"{name} must be numeric or None, got {v!r}")
            fv = float(v)
            if math.isnan(fv) or math.isinf(fv):
                raise ScientificValidationError(f"{name} must be finite, got {v!r}")
            if name == "value" and fv < 0.0:
                raise ScientificValidationError("uncertainty value must be >= 0")
            if name == "coverage" and not (0.0 < fv <= 1.0):
                raise ScientificValidationError("coverage must be in (0, 1]")
            object.__setattr__(self, name, fv)
        if self.covariance is not None:
            # Expect tuple of floats or None; validate finite
            try:
                tup = tuple(self.covariance)
            except TypeError:
                raise ScientificValidationError("covariance must be a tuple or None")
            for i, c in enumerate(tup):
                if isinstance(c, bool) or not isinstance(c, (int, float)):
                    raise ScientificValidationError(f"covariance[{i}] must be numeric")
                if math.isnan(float(c)) or math.isinf(float(c)):
                    raise ScientificValidationError(f"covariance[{i}] must be finite")
            object.__setattr__(self, "covariance", tuple(float(c) for c in tup))

        # Kind vs presence consistency: UNKNOWN must have no value
        if self.kind == UncertaintyKind.UNKNOWN and self.value is not None:
            raise ScientificValidationError("UNKNOWN uncertainty must have value=None")
        # CONFIDENCE_INTERVAL should have lower/upper
        if self.kind == UncertaintyKind.CONFIDENCE_INTERVAL:
            if self.lower is None or self.upper is None:
                raise ScientificValidationError("CONFIDENCE_INTERVAL requires lower and upper")

    @property
    def is_unknown(self) -> bool:
        return self.kind == UncertaintyKind.UNKNOWN

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "value": self.value,
            "lower": self.lower,
            "upper": self.upper,
            "coverage": self.coverage,
            "covariance": list(self.covariance) if self.covariance is not None else None,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Uncertainty":
        return cls(
            kind=UncertaintyKind(d["kind"]),
            value=d.get("value"),
            lower=d.get("lower"),
            upper=d.get("upper"),
            coverage=d.get("coverage"),
            covariance=tuple(d["covariance"]) if d.get("covariance") is not None else None,
            notes=d.get("notes", ""),
        )


# Canonical unknown sentinel — never fabricate zero.
UNCERTAINTY_UNKNOWN = Uncertainty(kind=UncertaintyKind.UNKNOWN)


class UncertaintyPropagator:
    """Scaffold propagator (§2.10).

    This class DOES NOT invent statistics. If propagation is not supported
    for the requested combination, it returns UNCERTAINTY_UNKNOWN —
    never a fabricated value.  Callers that need precise propagation should
    invoke ``astra.mathematics`` utilities directly and wrap the result in
    an ``Uncertainty``.
    """

    @staticmethod
    def propagate(inputs: tuple[Uncertainty, ...]) -> Uncertainty:
        """Propagate a tuple of uncertainties.

        Rules (§2.9 enhanced):
        - If any input is UNKNOWN → result is UNKNOWN (no fabrication).
        - If inputs is empty → UNKNOWN.
        - Otherwise, without a specific formula, returns UNKNOWN (limitation).

        The caller receives ``UNCERTAINTY_UNKNOWN`` and may record
        ``LimitationState.UNCERTAINTY_PROPAGATION_UNAVAILABLE`` via warnings.
        """
        if not inputs:
            return UNCERTAINTY_UNKNOWN
        for u in inputs:
            if not isinstance(u, Uncertainty):
                raise TypeError("propagate expects Uncertainty instances")
            if u.is_unknown:
                return UNCERTAINTY_UNKNOWN
        # No specific formula available in this reduced propagator
        return UNCERTAINTY_UNKNOWN

    @staticmethod
    def combine_absolute(values: tuple[float, ...], uncertainties: tuple[Uncertainty, ...]) -> Uncertainty:
        """Toy linear combination (quadrature) where supported.

        If any uncertainty is UNKNOWN or non-ABSOLUTE, returns UNKNOWN.
        Otherwise returns sqrt(sum σ_i^2) as ABSOLUTE (standard uncorrelated).
        """
        if len(values) != len(uncertainties):
            raise ScientificValidationError("values and uncertainties length mismatch")
        for u in uncertainties:
            if u.is_unknown:
                return UNCERTAINTY_UNKNOWN
            if u.kind not in (UncertaintyKind.ABSOLUTE, UncertaintyKind.STATISTICAL, UncertaintyKind.SYSTEMATIC):
                return UNCERTAINTY_UNKNOWN
            if u.value is None:
                return UNCERTAINTY_UNKNOWN
        import math
        total = math.sqrt(sum((u.value or 0.0) ** 2 for u in uncertainties))
        return Uncertainty(kind=UncertaintyKind.ABSOLUTE, value=total)
