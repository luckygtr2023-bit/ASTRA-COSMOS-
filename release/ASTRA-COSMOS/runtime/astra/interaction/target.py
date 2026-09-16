"""ASTRA Interaction — structured targeting.

Targets reference authoritative entities/objects (never a duplicate DB).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from .errors import TargetError
from astra.scientific.classification import Classification


class TargetKind(str, Enum):
    PLANET = "PLANET"
    MOON = "MOON"
    STAR = "STAR"
    ASTEROID = "ASTEROID"
    COMET = "COMET"
    SPACECRAFT = "SPACECRAFT"
    BLACK_HOLE = "BLACK_HOLE"
    GALAXY = "GALAXY"
    CLUSTER = "CLUSTER"
    COSMIC_WEB_STRUCTURE = "COSMIC_WEB_STRUCTURE"
    PHENOMENON = "PHENOMENON"
    OBSERVATION_TARGET = "OBSERVATION_TARGET"
    SIMULATION_REGION = "SIMULATION_REGION"
    CELESTIAL_OBJECT = "CELESTIAL_OBJECT"
    WORLD_NODE = "WORLD_NODE"
    SCENE_NODE = "SCENE_NODE"
    ENTITY = "ENTITY"


@dataclass(frozen=True)
class Target:
    """Immutable targeting descriptor referencing an authoritative object."""

    target_id: str
    kind: TargetKind
    authoritative_id: str  # the real id in celestial/world/entity layer
    display_name: str = ""
    position_hint: Optional[Tuple[float, float, float]] = None
    frame_id: Optional[str] = None
    classification: Classification = Classification.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.target_id, str) or not self.target_id:
            raise TargetError("target_id must be non-empty string")
        if not isinstance(self.kind, TargetKind):
            raise TargetError("kind must be TargetKind")
        if not isinstance(self.authoritative_id, str) or not self.authoritative_id:
            raise TargetError("authoritative_id must be non-empty string")
        if self.position_hint is not None:
            if len(self.position_hint) != 3:
                raise TargetError("position_hint must be 3-tuple")
            for v in self.position_hint:
                import math
                if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
                    raise TargetError("position_hint contains non-finite")
        if self.frame_id is not None and not isinstance(self.frame_id, str):
            raise TargetError("frame_id must be str or None")
        if not isinstance(self.classification, Classification):
            raise TargetError("classification must be Classification")
        object.__setattr__(self, "metadata", dict(self.metadata))
        if self.position_hint is not None:
            object.__setattr__(self, "position_hint", tuple(float(x) for x in self.position_hint))

    def to_dict(self) -> Dict:
        return {
            "target_id": self.target_id,
            "kind": self.kind.value,
            "authoritative_id": self.authoritative_id,
            "display_name": self.display_name,
            "position_hint": list(self.position_hint) if self.position_hint else None,
            "frame_id": self.frame_id,
            "classification": self.classification.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Target":
        return cls(
            target_id=d["target_id"],
            kind=TargetKind(d["kind"]),
            authoritative_id=d["authoritative_id"],
            display_name=d.get("display_name", ""),
            position_hint=tuple(d["position_hint"]) if d.get("position_hint") else None,
            frame_id=d.get("frame_id"),
            classification=Classification(d.get("classification", "SIMULATED_DATA")),
            metadata=dict(d.get("metadata", {})),
        )


class TargetRegistry:
    """Lazy, queryable registry of known targets.

    Does NOT duplicate celestial DB; it is an index/cache that references
    authoritative ids. Supports spatial queries via caller's provider.
    """

    def __init__(self):
        self._by_id: Dict[str, Target] = {}
        self._by_authoritative: Dict[str, str] = {}

    def register(self, t: Target) -> None:
        if t.target_id in self._by_id:
            raise TargetError(f"target already registered: {t.target_id!r}")
        if t.authoritative_id in self._by_authoritative:
            # allow multiple target_ids -> same authoritative? No, prevent ambiguity
            raise TargetError(f"authoritative_id already bound: {t.authoritative_id!r}")
        self._by_id[t.target_id] = t
        self._by_authoritative[t.authoritative_id] = t.target_id

    def unregister(self, target_id: str) -> None:
        t = self._by_id.pop(target_id, None)
        if t is None:
            raise TargetError(f"target not found: {target_id!r}")
        self._by_authoritative.pop(t.authoritative_id, None)

    def get(self, target_id: str) -> Optional[Target]:
        return self._by_id.get(target_id)

    def get_or_raise(self, target_id: str) -> Target:
        t = self._by_id.get(target_id)
        if t is None:
            raise TargetError(f"target not found: {target_id!r}")
        return t

    def resolve_authoritative(self, authoritative_id: str) -> Optional[Target]:
        tid = self._by_authoritative.get(authoritative_id)
        return self._by_id.get(tid) if tid else None

    def all(self) -> Tuple[Target, ...]:
        # deterministic order by target_id
        return tuple(sorted(self._by_id.values(), key=lambda x: x.target_id))

    def query_by_kind(self, kind: TargetKind) -> Tuple[Target, ...]:
        return tuple(t for t in self.all() if t.kind == kind)

    def query_by_classification(self, c: Classification) -> Tuple[Target, ...]:
        return tuple(t for t in self.all() if t.classification == c)

    def nearby(self, center: Tuple[float, float, float], radius: float,
               limit: int = 100) -> Tuple[Target, ...]:
        """Range query over position_hint; delegates to spatial index when available.

        Purely on cached hints; does not load the universe.
        """
        import math
        if limit <= 0:
            raise TargetError("limit must be >0")
        out = []
        for t in self.all():
            if t.position_hint is None:
                continue
            dx = tuple(a - b for a, b in zip(t.position_hint, center))
            dist = math.sqrt(dx[0]*dx[0] + dx[1]*dx[1] + dx[2]*dx[2])
            if dist <= radius:
                out.append((dist, t))
        out.sort(key=lambda x: (x[0], x[1].target_id))
        return tuple(t for _, t in out[:limit])

    def clear(self) -> None:
        self._by_id.clear()
        self._by_authoritative.clear()

    def to_dict(self) -> list:
        return [t.to_dict() for t in self.all()]

    @classmethod
    def from_dict(cls, data: list) -> "TargetRegistry":
        r = cls()
        for d in data:
            r.register(Target.from_dict(d))
        return r
