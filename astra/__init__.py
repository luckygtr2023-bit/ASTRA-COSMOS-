"""ASTRA Core - Foundational runtime layer for ASTRA simulation engine."""

__version__ = "0.1.1"
__author__ = "ASTRA Team"

from astra.core.engine import Engine, EngineState
from astra.core.exceptions import AstraError, AuthorityError, ResourceError
from astra.core.ids import EntityId, CommandId, EventId, FrameId
from astra.core.logging import get_logger
from astra.core.config import Config
from astra.core.threading import (
    SimulationThreadRegistry,
    AuthorityContext,
    get_simulation_thread_registry,
    reset_simulation_thread_registry,
)
from astra.core.events import Event, EventBus, EventPriority
from astra.core.rng import DeterministicRNG, RNGStream
from astra.core.commands import Command, CommandDispatcher, CommandHistory
from astra.core.entities import Entity, EntityManager, Component
from astra.core.coords import CoordinateFrame, OriginRebaseRequest, OriginRebaser
from astra.core.scene import Scene
from astra.core.time import SimulationClock, TimeMode
from astra.core.persistence import PersistenceManager, Snapshot
from astra.core.resources import ResourceManager, ResourceHandle
from astra.core.recovery import RecoveryPolicy, RecoveryManager
from astra.core.services import ServiceRegistry

__all__ = [
    # Version
    "__version__",
    # Engine
    "Engine",
    "EngineState",
    # Exceptions
    "AstraError",
    "AuthorityError",
    "ResourceError",
    # IDs
    "EntityId",
    "CommandId",
    "EventId",
    "FrameId",
    # Logging
    "get_logger",
    # Config
    "Config",
    # Threading
    "SimulationThreadRegistry",
    "AuthorityContext",
    "get_simulation_thread_registry",
    "reset_simulation_thread_registry",
    # Events
    "Event",
    "EventBus",
    "EventPriority",
    # RNG
    "DeterministicRNG",
    "RNGStream",
    # Commands
    "Command",
    "CommandDispatcher",
    "CommandHistory",
    # Entities
    "Entity",
    "EntityManager",
    "Component",
    # Coords
    "CoordinateFrame",
    "OriginRebaseRequest",
    "OriginRebaser",
    # Scene
    "Scene",
    # Time
    "SimulationClock",
    "TimeMode",
    # Persistence
    "PersistenceManager",
    "Snapshot",
    # Resources
    "ResourceManager",
    "ResourceHandle",
    # Recovery
    "RecoveryPolicy",
    "RecoveryManager",
    # Services
    "ServiceRegistry",
]
