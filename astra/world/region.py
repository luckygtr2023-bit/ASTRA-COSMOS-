"""ASTRA World - region lifecycle management.

Contract: Manages region state transitions for streaming support.
Supports loaded/unloaded, active/inactive states with explicit transitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from enum import Enum
import threading

from astra.world.identities import RegionId
from astra.world.exceptions import LifecycleError
from astra.core.logging import get_logger


class RegionState(Enum):
    """Region lifecycle state."""
    
    UNLOADED = "unloaded"      # Not in memory
    LOADING = "loading"        # Being loaded asynchronously
    LOADED = "loaded"          # In memory, ready for use
    UNLOADING = "unloading"    # Being unloaded


class RegionLifecycle:
    """Manages region lifecycle transitions.
    
    Valid transitions:
    - UNLOADED -> LOADING (start async load)
    - LOADING -> LOADED (load complete)
    - LOADING -> UNLOADED (load failed/cancelled)
    - LOADED -> UNLOADING (start unload)
    - UNLOADING -> UNLOADED (unload complete)
    """
    
    VALID_TRANSITIONS = {
        RegionState.UNLOADED: {RegionState.LOADING},
        RegionState.LOADING: {RegionState.LOADED, RegionState.UNLOADED},
        RegionState.LOADED: {RegionState.UNLOADING},
        RegionState.UNLOADING: {RegionState.UNLOADED},
    }
    
    def __init__(self):
        self._states: Dict[str, RegionState] = {}
        self._lock = threading.RLock()
        self._logger = get_logger("region_lifecycle")
    
    def register_region(self, region_id: str, initial_state: RegionState = RegionState.UNLOADED) -> None:
        """Register a region with an initial state."""
        with self._lock:
            if region_id in self._states:
                raise LifecycleError(f"Region already registered: {region_id}")
            self._states[region_id] = initial_state
            self._logger.debug(f"Registered region {region_id} with state {initial_state.value}")
    
    def unregister_region(self, region_id: str) -> None:
        """Unregister a region."""
        with self._lock:
            self._states.pop(region_id, None)
            self._logger.debug(f"Unregistered region: {region_id}")
    
    def get_state(self, region_id: str) -> Optional[RegionState]:
        """Get the current state of a region."""
        return self._states.get(region_id)
    
    def transition(self, region_id: str, new_state: RegionState) -> bool:
        """Attempt a state transition.
        
        Returns True if the transition was valid and executed.
        Raises LifecycleError for invalid transitions.
        """
        with self._lock:
            if region_id not in self._states:
                raise LifecycleError(f"Region not registered: {region_id}")
            
            current_state = self._states[region_id]
            valid_next = self.VALID_TRANSITIONS.get(current_state, set())
            
            if new_state not in valid_next:
                raise LifecycleError(
                    f"Invalid transition: {current_state.value} -> {new_state.value}",
                )
            
            self._states[region_id] = new_state
            self._logger.debug(f"Region {region_id}: {current_state.value} -> {new_state.value}")
            return True
    
    def is_loaded(self, region_id: str) -> bool:
        """Check if a region is loaded."""
        return self._states.get(region_id) == RegionState.LOADED
    
    def is_unloaded(self, region_id: str) -> bool:
        """Check if a region is unloaded."""
        return self._states.get(region_id) == RegionState.UNLOADED
    
    def is_loading(self, region_id: str) -> bool:
        """Check if a region is loading."""
        return self._states.get(region_id) == RegionState.LOADING
    
    def is_unloading(self, region_id: str) -> bool:
        """Check if a region is unloading."""
        return self._states.get(region_id) == RegionState.UNLOADING
    
    def get_all_states(self) -> Dict[str, RegionState]:
        """Get all region states."""
        with self._lock:
            return dict(self._states)
    
    def get_regions_in_state(self, state: RegionState) -> List[str]:
        """Get all regions in a particular state."""
        with self._lock:
            return [rid for rid, s in self._states.items() if s == state]
    
    def clear(self) -> None:
        """Clear all region states."""
        with self._lock:
            self._states.clear()
            self._logger.debug("Cleared region lifecycle states")


@dataclass
class WorldRegion:
    """A world region with lifecycle state.
    
    This combines spatial bounds with lifecycle management for streaming.
    """
    
    id: str
    name: str
    parent_id: Optional[str] = None
    
    # Spatial extent (simple sphere for now)
    center: tuple = (0.0, 0.0, 0.0)
    radius: float = 1000.0
    
    # State
    state: RegionState = RegionState.UNLOADED
    enabled: bool = True
    simulated: bool = True
    
    # Object references
    object_ids: Set[str] = field(default_factory=set)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id or not isinstance(self.id, str):
            raise ValueError("Region ID must be a non-empty string")
        if self.radius <= 0:
            raise ValueError("Region radius must be positive")
