"""Observation & Cosmic History — exceptions.

All observation errors derive from AstraError. Validation errors also
derive from ValueError for ergonomic catching. History unavailable is
explicit — never silently fabricated.
"""

from __future__ import annotations

from astra.core.exceptions import AstraError


class ObservationError(AstraError):
    """Base for observation & cosmic history errors."""


class InvalidObserverError(ObservationError, ValueError):
    """Invalid observer configuration (identity, position, velocity, frame)."""


class InvalidTargetError(ObservationError, ValueError):
    """Invalid target / source specification."""


class InvalidReferenceFrameError(ObservationError, ValueError):
    """Unknown or unsupported reference frame."""


class HistoryUnavailableError(ObservationError):
    """Required historical state not recorded — honest failure."""


class PropagationError(ObservationError, ValueError):
    """Inconsistent or impossible propagation request (e.g. t_emit > t_obs)."""


class CausalInaccessibilityError(ObservationError):
    """Event is not causally accessible / not yet observable."""


class UnsupportedObservationalConfigurationError(ObservationError, ValueError):
    """Requested observational configuration not supported."""


class TemporalHistoryUnavailableError(HistoryUnavailableError):
    """Alias for compatibility with astra.temporal history errors."""

    # Re-export name used by temporal layer; same semantics.
    pass


__all__ = [
    "ObservationError",
    "InvalidObserverError",
    "InvalidTargetError",
    "InvalidReferenceFrameError",
    "HistoryUnavailableError",
    "TemporalHistoryUnavailableError",
    "PropagationError",
    "CausalInaccessibilityError",
    "UnsupportedObservationalConfigurationError",
]
