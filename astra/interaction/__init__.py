"""ASTRA Interaction & Exploration Engine (Phase 23).

Interaction is an interface to the simulation, not a bypass.

Architecture:
  Data / Engines (Core, World, Celestial, Spacecraft, Temporal, Theoretical, Scientific)
      ↓
  Interaction Engine (this package) — validates, delegates, records
      ↓
  Provenance / Classification / Warnings / History / Observations
"""

from .scale import ScaleLevel, scale_order, is_coarser, is_finer, scale_transition_steps, all_scales
from .target import TargetKind, Target, TargetRegistry
from .state import ExplorerIdentity, NavigationContext, ExplorationState
from .commands import InteractionType, InteractionAction, InteractionResult, make_action_id
from .controls import ThrottleCommand, OrientationCommand, TrajectoryControl, CameraControl, ControlInput, ControlTranslator
from .navigation import NavigationRequest, NavigationResult, NavigationService
from .travel import TravelMethod, TravelConstraints, TravelRequest, TravelResult, DelegatingTravelService, TravelProvider, NullTravelProvider
from .observation import ObservationContext, Discovery, DiscoveryRegistry, ObservationService
from .history import HistoryEventKind, ExplorationEvent, ExplorationHistory
from .statemachine import ExplorationStateType, ExplorationStateMachine
from .engine import InteractionEngine, InteractionEngineConfig
from .errors import (
    InteractionError, InvalidInteractionError, StateTransitionError, NavigationError,
    TravelError, TargetError, ObservationError, DiscoveryError, ControlError,
    TemporalError, CausalityError,
)
from .persistence import (
    state_to_dict, state_from_dict, history_to_dict, history_from_dict,
    target_registry_to_dict, target_registry_from_dict,
    discovery_registry_to_dict, discovery_registry_from_dict,
    statemachine_to_dict, statemachine_from_dict,
    full_snapshot, full_snapshot_from_dict,
)

__all__ = [
    # scale
    "ScaleLevel", "scale_order", "is_coarser", "is_finer", "scale_transition_steps", "all_scales",
    # target
    "TargetKind", "Target", "TargetRegistry",
    # state
    "ExplorerIdentity", "NavigationContext", "ExplorationState",
    # commands
    "InteractionType", "InteractionAction", "InteractionResult", "make_action_id",
    # controls
    "ThrottleCommand", "OrientationCommand", "TrajectoryControl", "CameraControl", "ControlInput", "ControlTranslator",
    # navigation
    "NavigationRequest", "NavigationResult", "NavigationService",
    # travel
    "TravelMethod", "TravelConstraints", "TravelRequest", "TravelResult", "DelegatingTravelService", "TravelProvider", "NullTravelProvider",
    # observation
    "ObservationContext", "Discovery", "DiscoveryRegistry", "ObservationService",
    # history
    "HistoryEventKind", "ExplorationEvent", "ExplorationHistory",
    # statemachine
    "ExplorationStateType", "ExplorationStateMachine",
    # engine
    "InteractionEngine", "InteractionEngineConfig",
    # errors
    "InteractionError", "InvalidInteractionError", "StateTransitionError", "NavigationError",
    "TravelError", "TargetError", "ObservationError", "DiscoveryError", "ControlError", "TemporalError", "CausalityError",
    # persistence
    "state_to_dict", "state_from_dict", "history_to_dict", "history_from_dict",
    "target_registry_to_dict", "target_registry_from_dict",
    "discovery_registry_to_dict", "discovery_registry_from_dict",
    "statemachine_to_dict", "statemachine_from_dict",
    "full_snapshot", "full_snapshot_from_dict",
]
