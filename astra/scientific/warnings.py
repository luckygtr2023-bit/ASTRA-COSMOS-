"""ASTRA Scientific — machine-readable warnings (§2.21–2.22).

Every warning carries (code, severity, message, context_dict).
Free-text may accompany but never replaces the code.  Warnings are
collected in a deterministic WarningSink; policy decides escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class WarningSeverity(str, Enum):
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKING = "BLOCKING"


class WarningCode(str, Enum):
    MODEL_OUTSIDE_VALID_RANGE = "MODEL_OUTSIDE_VALID_RANGE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    SPECULATIVE_MODEL = "SPECULATIVE_MODEL"
    HYPOTHETICAL_SCENARIO = "HYPOTHETICAL_SCENARIO"
    MISSING_PROVENANCE = "MISSING_PROVENANCE"
    APPROXIMATION_ACTIVE = "APPROXIMATION_ACTIVE"
    NUMERICAL_LIMITATION = "NUMERICAL_LIMITATION"
    OBSERVATIONAL_LIMITATION = "OBSERVATIONAL_LIMITATION"
    UNSUPPORTED_PARAMETER = "UNSUPPORTED_PARAMETER"
    # Extension codes
    CLASSIFICATION_CONFLICT = "CLASSIFICATION_CONFLICT"
    UNCERTAINTY_UNKNOWN = "UNCERTAINTY_UNKNOWN"
    SCENARIO_MISMATCH = "SCENARIO_MISMATCH"


@dataclass(frozen=True)
class ScientificWarning:
    """Machine-readable scientific warning (§2.21 enhanced)."""

    code: WarningCode
    severity: WarningSeverity
    message: str
    context: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.code, WarningCode):
            raise TypeError("code must be a WarningCode")
        if not isinstance(self.severity, WarningSeverity):
            raise TypeError("severity must be a WarningSeverity")
        if not isinstance(self.message, str):
            raise TypeError("message must be a string")
        object.__setattr__(self, "context", dict(self.context))

    def to_dict(self) -> Dict:
        return {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
            "context": dict(self.context),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ScientificWarning":
        return cls(
            code=WarningCode(d["code"]),
            severity=WarningSeverity(d["severity"]),
            message=d["message"],
            context=dict(d.get("context", {})),
        )


class WarningSink:
    """Collects warnings for a single operation. Deterministic ordering.

    Warnings are appended in emission order; ``all()`` returns a tuple sorted
    only by emission order (no re-sorting), preserving causality.  ``highest_severity``
    is computed deterministically.
    """

    # Severity order for highest_severity()
    _ORDER = {
        WarningSeverity.INFO: 0,
        WarningSeverity.NOTICE: 1,
        WarningSeverity.WARNING: 2,
        WarningSeverity.ERROR: 3,
        WarningSeverity.BLOCKING: 4,
    }

    def __init__(self) -> None:
        self._warnings: List[ScientificWarning] = []

    def emit(self, w: ScientificWarning) -> None:
        if not isinstance(w, ScientificWarning):
            raise TypeError("w must be a ScientificWarning")
        self._warnings.append(w)

    def emit_code(self, code: WarningCode, severity: WarningSeverity,
                  message: str, context: Dict | None = None) -> ScientificWarning:
        w = ScientificWarning(code, severity, message, context or {})
        self.emit(w)
        return w

    def all(self) -> tuple[ScientificWarning, ...]:
        return tuple(self._warnings)

    def for_code(self, code: WarningCode) -> tuple[ScientificWarning, ...]:
        return tuple(w for w in self._warnings if w.code == code)

    def for_severity(self, sev: WarningSeverity) -> tuple[ScientificWarning, ...]:
        return tuple(w for w in self._warnings if w.severity == sev)

    def highest_severity(self) -> Optional[WarningSeverity]:
        if not self._warnings:
            return None
        return max(self._warnings, key=lambda w: self._ORDER[w.severity]).severity

    def has_blocking(self) -> bool:
        return any(w.severity == WarningSeverity.BLOCKING for w in self._warnings)

    def clear(self) -> None:
        self._warnings.clear()

    def __len__(self) -> int:
        return len(self._warnings)

    def to_dict(self) -> List[Dict]:
        return [w.to_dict() for w in self._warnings]
