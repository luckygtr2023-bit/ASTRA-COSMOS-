"""ASTRA Scientific — config + policy (§2.15).

Policies affect validation behavior ONLY.  A permissive mode never removes
provenance or warnings — it only changes whether they escalate to rejection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .warnings import WarningSeverity


class Policy(str, Enum):
    """Scientific policy governing validity compromise handling."""

    STRICT = "STRICT"          # reject out-of-domain models
    STANDARD = "STANDARD"      # allow with warnings (default)
    EXPLORATORY = "EXPLORATORY"  # permit broader experimentation
    SPECULATIVE = "SPECULATIVE"  # permit hypothetical models while maintaining classification


@dataclass(frozen=True)
class ScientificConfig:
    """Scientific integrity configuration."""

    policy: Policy = Policy.STANDARD
    validate_every_n_steps: int = 1
    max_warnings_per_operation: int = 1024
    software_version: str = "astra.scientific.v1"

    def __post_init__(self):
        if not isinstance(self.policy, Policy):
            raise TypeError("policy must be a Policy")
        if not isinstance(self.validate_every_n_steps, int) or self.validate_every_n_steps < 1:
            raise ValueError("validate_every_n_steps must be int >= 1")
        if not isinstance(self.max_warnings_per_operation, int) or self.max_warnings_per_operation < 1:
            raise ValueError("max_warnings_per_operation must be int >= 1")
        if not isinstance(self.software_version, str) or not self.software_version:
            raise ValueError("software_version must be a non-empty string")

    def should_reject(self, severity: WarningSeverity) -> bool:
        """Return True if the given severity should be rejected under this policy.

        Policy matrix (§2.15 enhanced):

        | Severity | STRICT | STANDARD | EXPLORATORY | SPECULATIVE |
        |----------|--------|----------|-------------|-------------|
        | INFO     | allow  | allow    | allow       | allow       |
        | NOTICE   | allow  | allow    | allow       | allow       |
        | WARNING  | allow  | allow    | allow       | allow       |
        | ERROR    | reject | allow    | allow       | allow       |
        | BLOCKING | reject | reject   | allow       | allow       |
        """
        if not isinstance(severity, WarningSeverity):
            raise TypeError("severity must be a WarningSeverity")
        if self.policy == Policy.STRICT:
            return severity in (WarningSeverity.ERROR, WarningSeverity.BLOCKING)
        if self.policy == Policy.STANDARD:
            return severity == WarningSeverity.BLOCKING
        # EXPLORATORY and SPECULATIVE permit all (warnings preserved, not dropped)
        return False

    def should_warn(self, severity: WarningSeverity) -> bool:
        """All severities are warned under every policy (warnings never suppressed)."""
        if not isinstance(severity, WarningSeverity):
            raise TypeError("severity must be a WarningSeverity")
        return True

    def to_dict(self) -> dict:
        return {
            "policy": self.policy.value,
            "validate_every_n_steps": self.validate_every_n_steps,
            "max_warnings_per_operation": self.max_warnings_per_operation,
            "software_version": self.software_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScientificConfig":
        return cls(
            policy=Policy(d.get("policy", Policy.STANDARD.value)),
            validate_every_n_steps=d.get("validate_every_n_steps", 1),
            max_warnings_per_operation=d.get("max_warnings_per_operation", 1024),
            software_version=d.get("software_version", "astra.scientific.v1"),
        )
