"""ASTRA Core scene management."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import threading

from astra.core.entities import EntityManager, Entity, Query
from astra.core.coords import FrameRegistry, CoordinateFrame, OriginRebaser
from astra.core.logging import get_logger


@dataclass
class SceneState:
    """Snapshot of scene state."""

    tick: int = 0
    entity_count: int = 0
    frame_count: int = 0
    origin: tuple = (0.0, 0.0, 0.0)


class Scene:
    """Main scene container for the simulation."""

    def __init__(self):
        self.entity_manager = EntityManager()
        self.frame_registry = FrameRegistry()
        self.origin_rebaser = OriginRebaser()
        self._current_tick = 0
        self._lock = threading.RLock()
        self._logger = get_logger("scene")

    def set_tick(self, tick: int):
        """Set the current simulation tick."""
        self._current_tick = tick
        self.entity_manager.set_current_tick(tick)

    def get_tick(self) -> int:
        """Get the current simulation tick."""
        return self._current_tick

    def create_entity(self, name: str = "") -> Entity:
        """Create a new entity in the scene."""
        return self.entity_manager.create_entity(name)

    def destroy_entity(self, entity_id: str):
        """Destroy an entity in the scene."""
        self.entity_manager.destroy_entity(entity_id)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get an entity by ID."""
        return self.entity_manager.get_entity(entity_id)

    def query_entities(self, query: Query) -> List[Entity]:
        """Query entities in the scene."""
        return self.entity_manager.query(query)

    def register_frame(self, frame: CoordinateFrame):
        """Register a coordinate frame."""
        self.frame_registry.register(frame)

    def get_frame(self, frame_id: str) -> Optional[CoordinateFrame]:
        """Get a coordinate frame by ID."""
        return self.frame_registry.get_frame(frame_id)

    def request_origin_rebase(
        self,
        new_origin: tuple,
        reason: str = "",
    ):
        """Request an origin rebase."""
        return self.origin_rebaser.request_rebase(
            new_origin=new_origin,
            reason=reason,
            tick=self._current_tick,
        )

    def execute_origin_rebase(self) -> Any:
        """Execute a pending origin rebase."""
        frames = self.frame_registry.get_all_frames()
        return self.origin_rebaser.execute_rebase(frames)

    def get_state(self) -> SceneState:
        """Get current scene state."""
        return SceneState(
            tick=self._current_tick,
            entity_count=self.entity_manager.get_entity_count(),
            frame_count=len(self.frame_registry.get_all_frames()),
            origin=self.origin_rebaser.get_current_origin(),
        )

    def clear(self):
        """Clear all scene contents."""
        self.entity_manager.clear()
        self.frame_registry.clear()
        self.origin_rebaser.clear_history()
        self._logger.debug("Scene cleared")
