"""
ASTRA Backend — graphics-state delivery (placeholder contracts).

Rendering produces RenderState (geometry/visibility/LOD); graphics
consumes it to produce material/texture/shader bindings and
frame graph. This module owns *delivery* (§8, §3 future bridge):

  SIM → AUTHORITATIVE STATE → RUNTIME SERVICES → RENDER/GRAPHICS STATE → VISUALIZATION

It does NOT compile shaders, author materials, or run Blender.
It defines deterministic, bounded, provenance-preserving contracts
that the future MiMo Graphics / Blender Bridge will implement.

Design mirrors RenderStateDelivery: cache, serialize, stream,
explicit invalidation, never mutate authoritative state.
"""

from __future__ import annotations

import json
import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Iterable

from astra.rendering.render_state import RenderState, RenderObject

from astra.backend.exceptions import GraphicsDeliveryError
from astra.backend.cache import BoundedCache


@dataclass
class GraphicsObject:
    """
    Graphics-domain derived object.

    RenderObject id maps 1:1. Material / texture / shader fields are
    opaque placeholders that the real graphics layer will interpret.
    Provenance is preserved from the source RenderObject.
    """
    id: str
    source_render_id: str
    material_ref: Dict[str, Any] = field(default_factory=dict)
    shader_params: Dict[str, Any] = field(default_factory=dict)
    lod: str = "HIGH"
    visibility: str = "VISIBLE"
    provenance: str = "derived"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_render_id": self.source_render_id,
            "material_ref": dict(self.material_ref),
            "shader_params": dict(self.shader_params),
            "lod": self.lod,
            "visibility": self.visibility,
            "provenance": self.provenance,
            "tags": list(self.tags),
        }

    @classmethod
    def from_render_object(cls, obj: RenderObject) -> "GraphicsObject":
        return cls(
            id=obj.id,
            source_render_id=obj.id,
            material_ref={"id": obj.material.id, "kind": obj.material.kind} if hasattr(obj, "material") else {},
            shader_params={},
            lod=obj.lod.value if hasattr(obj.lod, "value") else str(obj.lod),
            visibility=obj.visibility.value if hasattr(obj.visibility, "value") else str(obj.visibility),
            provenance=getattr(obj, "provenance", "derived"),
            tags=list(getattr(obj, "tags", [])),
        )


@dataclass
class GraphicsState:
    """
    Graphics-domain snapshot for one tick.

    Bounded, deterministic, serializable. Never authoritative.
    """
    tick: int
    simulation_time_s: float
    graphics_origin: tuple = (0.0, 0.0, 0.0)
    objects: Dict[str, GraphicsObject] = field(default_factory=dict)
    order: List[str] = field(default_factory=list)
    provenance: str = "derived"
    max_objects: int = 200_000

    def count(self) -> int:
        return len(self.objects)

    def add(self, obj: GraphicsObject) -> None:
        if obj.id in self.objects:
            raise GraphicsDeliveryError(f"GraphicsObject already exists: {obj.id}", operation="add", resource=obj.id)
        if len(self.objects) >= self.max_objects:
            raise GraphicsDeliveryError(f"GraphicsState at capacity {self.max_objects}", operation="add", resource=obj.id)
        self.objects[obj.id] = obj
        self.order.append(obj.id)

    def iterate(self):
        for oid in self.order:
            yield self.objects[oid]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "simulation_time_s": self.simulation_time_s,
            "graphics_origin": list(self.graphics_origin),
            "provenance": self.provenance,
            "count": len(self.objects),
            "objects": [self.objects[oid].to_dict() for oid in self.order],
        }


class GraphicsStateDelivery:
    """
    Derives GraphicsState from RenderState (pure, cached, bounded).

    Degrades gracefully if graphics backend disabled (returns minimal state
    with placeholder materials). Never mutates RenderState or simulation.
    """

    def __init__(
        self,
        *,
        cache: Optional[BoundedCache] = None,
        enabled: bool = True,
        max_state_bytes: int = 16 * 1024 * 1024,
        chunk_size: int = 2000,
    ):
        self._cache: BoundedCache = cache or BoundedCache(max_entries=512, max_memory_bytes=64 * 1024 * 1024, default_ttl_s=60.0, name="graphics_delivery")
        self._enabled = bool(enabled)
        self._max_bytes = max_state_bytes
        self._chunk_size = max(1, int(chunk_size))
        self._lock = threading.RLock()
        self._deliveries = 0
        self._cache_hits = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def cache(self) -> BoundedCache:
        return self._cache

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._enabled = bool(enabled)

    def invalidate_tick(self, tick: int) -> int:
        return self._cache.invalidate_prefix(f"graphics:tick:{tick}:")

    def invalidate_all(self) -> int:
        return self._cache.invalidate_prefix("graphics:")

    def derive(self, render_state: RenderState, *, use_cache: bool = True) -> GraphicsState:
        if not isinstance(render_state, RenderState):
            raise GraphicsDeliveryError(f"render_state must be RenderState, got {type(render_state).__name__}", operation="derive")
        # cache key: tick + fingerprint of render order
        try:
            order_hash = hashlib.sha256(",".join(render_state.order).encode()).hexdigest()[:8]
        except Exception:
            order_hash = "nohash"
        key = f"graphics:tick:{render_state.tick}:o{order_hash}:p{render_state.provenance}:en{int(self._enabled)}"

        if use_cache:
            entry = self._cache.get(key)
            if entry is not None and isinstance(entry.value, GraphicsState):
                with self._lock:
                    self._cache_hits += 1
                return entry.value

        with self._lock:
            # double-check
            if use_cache:
                entry = self._cache.get(key)
                if entry is not None and isinstance(entry.value, GraphicsState):
                    self._cache_hits += 1
                    return entry.value

            # Pure derivation: 1:1 from render objects
            g = GraphicsState(
                tick=render_state.tick,
                simulation_time_s=render_state.simulation_time_s,
                graphics_origin=render_state.render_origin.to_tuple() if hasattr(render_state.render_origin, "to_tuple") else (0.0, 0.0, 0.0),
                provenance=render_state.provenance,
            )
            # Bounded iteration; if graphics disabled, still produce placeholders so future bridge can detect enabled=False
            for ro in render_state.iterate():
                go = GraphicsObject.from_render_object(ro)
                if not self._enabled:
                    go.shader_params = {"placeholder": True, "enabled": False}
                g.add(go)

            est_bytes = g.count() * 384
            self._cache.put(key, g, provenance=g.provenance, source_tick=g.tick, tags={"tick", f"tick:{g.tick}"}, size_bytes=est_bytes)
            self._deliveries += 1
            return g

    def serialize(self, state: GraphicsState, *, pretty: bool = False) -> bytes:
        if not isinstance(state, GraphicsState):
            raise GraphicsDeliveryError("state must be GraphicsState", operation="serialize")
        try:
            d = state.to_dict()
            payload = json.dumps(d, sort_keys=True, separators=(",", ":") if not pretty else (",", ": "), indent=2 if pretty else None)
            raw = payload.encode("utf-8")
        except Exception as e:
            raise GraphicsDeliveryError(f"serialize failed: {e}", operation="serialize", cause=e)
        if len(raw) > self._max_bytes:
            raise GraphicsDeliveryError(f"serialized graphics state exceeds {self._max_bytes} bytes ({len(raw)})", operation="serialize", resource=f"tick:{state.tick}", recoverable=False)
        return raw

    def stream(self, state: GraphicsState, *, chunk_objects: Optional[int] = None) -> Iterable[Dict[str, Any]]:
        if not isinstance(state, GraphicsState):
            raise GraphicsDeliveryError("state must be GraphicsState", operation="stream")
        cs = int(chunk_objects) if chunk_objects else self._chunk_size
        objs = list(state.iterate())
        total = (len(objs) + cs - 1) // cs if objs else 1
        header = {
            "tick": state.tick,
            "simulation_time_s": state.simulation_time_s,
            "provenance": state.provenance,
            "total_chunks": total,
            "graphics_origin": list(state.graphics_origin),
            "enabled": self._enabled,
        }
        if not objs:
            yield {"header": header, "chunk_index": 0, "total_chunks": 1, "objects": []}
            return
        for idx in range(total):
            chunk = objs[idx * cs : (idx + 1) * cs]
            yield {
                "header": header if idx == 0 else None,
                "chunk_index": idx,
                "total_chunks": total,
                "objects": [o.to_dict() for o in chunk],
                "provenance": state.provenance,
            }

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._enabled,
                "deliveries": self._deliveries,
                "cache_hits": self._cache_hits,
                "max_state_bytes": self._max_bytes,
                "chunk_size": self._chunk_size,
                "cache": self._cache.stats().to_dict() if hasattr(self._cache, "stats") else {},
            }


__all__ = ["GraphicsObject", "GraphicsState", "GraphicsStateDelivery"]
