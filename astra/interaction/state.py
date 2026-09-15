"""ASTRA Interaction — exploration model (serializable, reproducible, provenance-aware).

Does not duplicate authoritative physical state — it references it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from astra.scientific.classification import Classification

from .scale import ScaleLevel
from .errors import InvalidInteractionError


@dataclass(frozen=True)
class ExplorerIdentity:
    explorer_id: str
    display_name: str = ""
    provenance: str = "astra.interaction"
    classification: Classification = Classification.SIMULATED_DATA

    def __post_init__(self):
        if not isinstance(self.explorer_id, str) or not self.explorer_id:
            raise InvalidInteractionError("explorer_id must be non-empty string")
        if not isinstance(self.display_name, str):
            raise InvalidInteractionError("display_name must be str")
        if not isinstance(self.classification, Classification):
            raise InvalidInteractionError("classification must be Classification")

    def to_dict(self) -> Dict:
        return {
            "explorer_id": self.explorer_id,
            "display_name": self.display_name,
            "provenance": self.provenance,
            "classification": self.classification.value,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ExplorerIdentity":
        return cls(
            explorer_id=d["explorer_id"],
            display_name=d.get("display_name", ""),
            provenance=d.get("provenance", "astra.interaction"),
            classification=Classification(d.get("classification", "SIMULATED_DATA")),
        )


@dataclass(frozen=True)
class NavigationContext:
    """Current navigation placement — references, not copies."""
    frame_id: Optional[str] = None
    world_id: Optional[str] = None
    scene_node_id: Optional[str] = None
    scale: ScaleLevel = ScaleLevel.LOCAL_ENVIRONMENT
    origin_hint: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    parent_scale_id: Optional[str] = None

    def __post_init__(self):
        if self.frame_id is not None and not isinstance(self.frame_id, str):
            raise InvalidInteractionError("frame_id must be str or None")
        if not isinstance(self.scale, ScaleLevel):
            raise InvalidInteractionError("scale must be ScaleLevel")
        if len(self.origin_hint) != 3:
            raise InvalidInteractionError("origin_hint must be 3-tuple")
        for v in self.origin_hint:
            import math
            if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
                raise InvalidInteractionError("origin_hint non-finite")
        object.__setattr__(self, "origin_hint", tuple(float(x) for x in self.origin_hint))

    def to_dict(self) -> Dict:
        return {
            "frame_id": self.frame_id,
            "world_id": self.world_id,
            "scene_node_id": self.scene_node_id,
            "scale": self.scale.value,
            "origin_hint": list(self.origin_hint),
            "parent_scale_id": self.parent_scale_id,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "NavigationContext":
        return cls(
            frame_id=d.get("frame_id"),
            world_id=d.get("world_id"),
            scene_node_id=d.get("scene_node_id"),
            scale=ScaleLevel(d.get("scale", "LOCAL_ENVIRONMENT")),
            origin_hint=tuple(d.get("origin_hint", (0.0,0.0,0.0))),
            parent_scale_id=d.get("parent_scale_id"),
        )


@dataclass
class ExplorationState:
    """Mutable exploration state (snapshot-able).

    Tracks references to authoritative state:
      - tick / simulation_time_s / proper_time_s (read from clocks)
      - frame/world/scene/entity/spacecraft refs
      - scale, navigation, discoveries, visited, travel, interactions
      - provenance + classification via scientific layer
    """

    explorer: ExplorerIdentity
    tick: int = 0
    simulation_time_s: float = 0.0
    proper_time_s: float = 0.0
    coordinate_time_s: float = 0.0
    navigation: NavigationContext = field(default_factory=NavigationContext)
    active_target_id: Optional[str] = None
    active_spacecraft_id: Optional[str] = None
    active_entity_id: Optional[str] = None
    # references, not full copies
    discovered_ids: Tuple[str, ...] = ()
    visited_location_ids: Tuple[str, ...] = ()
    observation_ids: Tuple[str, ...] = ()
    travel_ids: Tuple[str, ...] = ()
    interaction_ids: Tuple[str, ...] = ()
    # provenance for this snapshot
    provenance_chain_ref: Optional[str] = None
    classification: Classification = Classification.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.explorer, ExplorerIdentity):
            raise InvalidInteractionError("explorer must be ExplorerIdentity")
        if not isinstance(self.tick, int) or self.tick < 0:
            raise InvalidInteractionError("tick must be int >=0")
        import math
        for name in ("simulation_time_s","proper_time_s","coordinate_time_s"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v) or v < 0:
                raise InvalidInteractionError(f"{name} must be finite >=0")
        # canonicalize tuples
        object.__setattr__(self, "discovered_ids", tuple(self.discovered_ids))
        object.__setattr__(self, "visited_location_ids", tuple(self.visited_location_ids))
        object.__setattr__(self, "observation_ids", tuple(self.observation_ids))
        object.__setattr__(self, "travel_ids", tuple(self.travel_ids))
        object.__setattr__(self, "interaction_ids", tuple(self.interaction_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.active_target_id is not None and not isinstance(self.active_target_id, str):
            raise InvalidInteractionError("active_target_id must be str or None")
        if not isinstance(self.classification, Classification):
            raise InvalidInteractionError("classification must be Classification")

    def with_tick(self, tick: int, sim_s: float, proper_s: float, coord_s: Optional[float] = None) -> "ExplorationState":
        self.tick = tick
        self.simulation_time_s = float(sim_s)
        self.proper_time_s = float(proper_s)
        if coord_s is not None:
            self.coordinate_time_s = float(coord_s)
        else:
            self.coordinate_time_s = float(sim_s)
        return self

    def to_dict(self) -> Dict:
        return {
            "explorer": self.explorer.to_dict(),
            "tick": self.tick,
            "simulation_time_s": self.simulation_time_s,
            "proper_time_s": self.proper_time_s,
            "coordinate_time_s": self.coordinate_time_s,
            "navigation": self.navigation.to_dict(),
            "active_target_id": self.active_target_id,
            "active_spacecraft_id": self.active_spacecraft_id,
            "active_entity_id": self.active_entity_id,
            "discovered_ids": list(self.discovered_ids),
            "visited_location_ids": list(self.visited_location_ids),
            "observation_ids": list(self.observation_ids),
            "travel_ids": list(self.travel_ids),
            "interaction_ids": list(self.interaction_ids),
            "provenance_chain_ref": self.provenance_chain_ref,
            "classification": self.classification.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ExplorationState":
        return cls(
            explorer=ExplorerIdentity.from_dict(d["explorer"]),
            tick=int(d.get("tick", 0)),
            simulation_time_s=float(d.get("simulation_time_s", 0.0)),
            proper_time_s=float(d.get("proper_time_s", 0.0)),
            coordinate_time_s=float(d.get("coordinate_time_s", 0.0)),
            navigation=NavigationContext.from_dict(d.get("navigation", {})),
            active_target_id=d.get("active_target_id"),
            active_spacecraft_id=d.get("active_spacecraft_id"),
            active_entity_id=d.get("active_entity_id"),
            discovered_ids=tuple(d.get("discovered_ids", [])),
            visited_location_ids=tuple(d.get("visited_location_ids", [])),
            observation_ids=tuple(d.get("observation_ids", [])),
            travel_ids=tuple(d.get("travel_ids", [])),
            interaction_ids=tuple(d.get("interaction_ids", [])),
            provenance_chain_ref=d.get("provenance_chain_ref"),
            classification=Classification(d.get("classification", "SIMULATED_DATA")),
            metadata=dict(d.get("metadata", {})),
        )
