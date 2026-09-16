"""ASTRA Interaction — error taxonomy.

All failures are explicit, structured, and never silently teleported or ignored.
"""

from __future__ import annotations


class InteractionError(Exception):
    """Base for interaction layer failures."""

class InvalidInteractionError(InteractionError):
    """Requested interaction is structurally invalid."""

class StateTransitionError(InteractionError):
    """Exploration state machine rejected a transition."""

class NavigationError(InteractionError):
    """Navigation request invalid or cannot be satisfied via authoritative coords."""

class TravelError(InteractionError):
    """Travel request rejected by authoritative Travel Engine."""

class TargetError(InteractionError):
    """Targeting/selection failed (unknown, unavailable, ambiguous)."""

class ObservationError(InteractionError):
    """Observation/measurement cannot be satisfied (history missing, causality)."""

class DiscoveryError(InteractionError):
    """Discovery recording failed."""

class ControlError(InteractionError):
    """Player control input cannot be translated to valid simulation input."""

class TemporalError(InteractionError):
    """Temporal interaction invalid (pause/resume/seek boundary)."""

class AuthorityError(InteractionError):
    """Caller lacked required authority for mutating interaction."""

class CausalityError(InteractionError):
    """Interaction would violate causality / light-propagation invariants."""
