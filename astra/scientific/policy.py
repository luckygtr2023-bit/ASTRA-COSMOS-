"""ASTRA Scientific — policy enforcement (§2.15 enhanced).

Policy affects validation behavior ONLY.  It never rewrites equations,
removes provenance, or suppresses warnings.
"""

from __future__ import annotations

from .config import ScientificConfig
from .errors import ScientificBlockingError, ScientificWarningError
from .warnings import ScientificWarning, WarningSeverity


def enforce(config: ScientificConfig, warnings: tuple[ScientificWarning, ...]) -> None:
    """Raise if any warning escalates to rejection under the active policy.

    Never silently drops warnings — callers must record them regardless.
    The sink still contains all warnings after this call; only the decision
    to raise changes.

    Raises:
        ScientificBlockingError: if any warning should be rejected (STRICT: ERROR/BLOCKING, STANDARD: BLOCKING).
        ScientificWarningError: never raised directly by this function (kept for API compat; callers may raise it manually).
    """
    if not isinstance(config, ScientificConfig):
        raise TypeError("config must be a ScientificConfig")
    for w in warnings:
        if not isinstance(w, ScientificWarning):
            raise TypeError("warnings must be ScientificWarning instances")
        if config.should_reject(w.severity):
            # For compatibility with the reference scaffold, every rejection
            # raises ScientificBlockingError (whether ERROR or BLOCKING).
            # ScientificWarningError remains importable for direct use.
            raise ScientificBlockingError(
                f"[{w.severity.value}] {w.code.value}: {w.message}"
                + (f" context={w.context}" if w.context else "")
            )
