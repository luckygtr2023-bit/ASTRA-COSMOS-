"""ASTRA COSMOS — Extreme Spacetime & Travel Engine.

Reconciled implementation — scaffold API preserved, internals delegate
to authoritative ASTRA modules. Travel is represented as a spacetime/
geometric process, never as teleportation.
"""
from .config import TravelConfig
from .errors import (
    TravelError,
    TravelValidationError,
    TravelAuthorityError,
    TravelCausalityError,
    TravelNumericalError,
    TravelUnsupportedError,
)
from .state import TravelState, Transition, is_valid_transition
from .types import (
    ArrivalState,
    CausalStatus,
    Mechanism,
    ObservationRecord,
    Provenance,
    TravelEvent,
    TravelRequest,
    Vec3,
    Worldline,
    WorldlineSample,
)
from .engine import TravelEngine

# Re-export wormhole / warp / white-hole public types for evaluation
from .wormhole import Wormhole, WormholeMouth
from .warp import WarpBubble, WarpConfig
from .white_hole import WhiteHoleConfig

__all__ = [
    "TravelEngine",
    "TravelConfig",
    "TravelState",
    "Transition",
    "is_valid_transition",
    "TravelRequest",
    "TravelEvent",
    "ArrivalState",
    "Worldline",
    "WorldlineSample",
    "Mechanism",
    "CausalStatus",
    "ObservationRecord",
    "Provenance",
    "TravelError",
    "TravelValidationError",
    "TravelAuthorityError",
    "TravelCausalityError",
    "TravelNumericalError",
    "TravelUnsupportedError",
    # exotic geometry descriptors
    "Wormhole",
    "WormholeMouth",
    "WarpBubble",
    "WarpConfig",
    "WhiteHoleConfig",
    "Vec3",
]

__version__ = "1.0.0"
