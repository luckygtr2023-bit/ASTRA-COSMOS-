"""ASTRA Temporal - exceptions.

Contract: every Temporal-layer error derives from
``astra.core.exceptions.AstraError``. Validation errors additionally derive
from ``ValueError``.

Temporal history is never fabricated: when the recorded history of an
object cannot cover the required emission time, the explicit
:class:`TemporalHistoryUnavailableError` is raised - callers receive an
honest "unavailable", never an invented state.
"""

from astra.core.exceptions import AstraError


class TemporalError(AstraError):
    """Base Temporal-layer error."""


class InvalidTemporalStateError(TemporalError, ValueError):
    """Raised when a temporal state/timestamp/rate input is invalid
    (non-finite, negative rate, unknown observer reference)."""


class InvalidWorldlineError(TemporalError, ValueError):
    """Raised when a worldline cannot support the requested temporal
    operation (too few samples, unordered parameters, wrong chart)."""


class TemporalHistoryUnavailableError(TemporalError):
    """Raised when lookback requires history that was never recorded.

    ASTRA does not fabricate astronomical history: observation requests
    that reach before the available record fail explicitly.
    """
