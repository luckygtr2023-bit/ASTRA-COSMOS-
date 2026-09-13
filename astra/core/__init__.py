"""ASTRA Core module - foundational runtime components."""

from astra.core.exceptions import AstraError, AuthorityError, ResourceError
from astra.core.ids import EntityId, CommandId, EventId, FrameId
from astra.core.logging import get_logger
from astra.core.config import Config
from astra.core.threading import SimulationThread, AuthorityContext
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
from astra.core.engine import Engine, EngineState

__all__ = [
    "AstraError",
    "AuthorityError",
    "ResourceError",
    "EntityId",
    "CommandId",
    "EventId",
    "FrameId",
    "get_logger",
    "Config",
    "SimulationThread",
    "AuthorityContext",
    "Event",
    "EventBus",
    "EventPriority",
    "DeterministicRNG",
    "RNGStream",
    "Command",
    "CommandDispatcher",
    "CommandHistory",
    "Entity",
    "EntityManager",
    "Component",
    "CoordinateFrame",
    "OriginRebaseRequest",
    "OriginRebaser",
    "Scene",
    "SimulationClock",
    "TimeMode",
    "PersistenceManager",
    "Snapshot",
    "ResourceManager",
    "ResourceHandle",
    "RecoveryPolicy",
    "RecoveryManager",
    "ServiceRegistry",
    "Engine",
    "EngineState",
]
