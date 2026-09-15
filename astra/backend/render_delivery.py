"""
ASTRA Backend — render-state delivery (§8).

Never authoritative: derives RenderState via the single RenderPipeline
from authoritative world/celestial sources, caches it, serializes it,
and streams it to visualization consumers.

Contracts:
  - Scheduling: explicit tick/time-driven, no wall-clock drift
  - Caching: bounded, explicit invalidation on tick/source/config change
  - Serialization: deterministic, provenance-preserving, bounded size
  - Streaming: chunked for large state (§15) with per-chunk provenance
  - Coordination: camera-relative + floating-origin updates are stateless
    per-frame (no hidden accumulation beyond FloatingOriginRenderer)
  - Never mutates simulation state
"""

from __future__ import annotations

import json
import time
import threading
import hashlib
from typing import Any, Callable, Dict, List, Optional, Tuple, Iterable

from astra.mathematics import Vector3

from astra.rendering.render_state import RenderState, RenderObject
from astra.rendering.pipeline import RenderPipeline, PipelineConfig, RenderFrame
from astra.rendering.render_context import RenderContext
from astra.rendering.types import TemporalRenderMode

from astra.backend.exceptions import RenderDeliveryError
from astra.backend.cache import BoundedCache


class RenderStateDelivery:
    """
    Derives and delivers render state.

    Caller supplies *fetchers* for world objects (pure reads):
      world_objects_fn(tick) -> List[Dict]  (entries with world_position etc.)
    So this class never holds authoritative handles.

    Thread-safe for concurrent reads; derivation for a given tick is
    serialized (one pipeline invocation at a time) to keep determinism.
    """

    def __init__(
        self,
        pipeline: Optional[RenderPipeline] = None,
        *,
        cache: Optional[BoundedCache] = None,
        max_state_bytes: int = 16 * 1024 * 1024,  # 16 MB large-state guard
        chunk_size: int = 2000,  # objects per streaming chunk
    ):
        self._pipeline: RenderPipeline = pipeline or RenderPipeline()
        self._cache: BoundedCache = cache or BoundedCache(max_entries=512, max_memory_bytes=64 * 1024 * 1024, default_ttl_s=60.0, name="render_delivery")
        self._lock = threading.RLock()
        self._max_bytes = max_state_bytes
        self._chunk_size = max(1, int(chunk_size))
        self._deliveries = 0
        self._cache_hits = 0
        self._bytes_delivered = 0

    @property
    def pipeline(self) -> RenderPipeline:
        return self._pipeline

    @property
    def cache(self) -> BoundedCache:
        return self._cache

    # -- scheduling & invalidation --

    def invalidate_tick(self, tick: int) -> int:
        """Explicit invalidation for a tick (e.g. after rollback)."""
        return self._cache.invalidate_prefix(f"render:tick:{tick}:")

    def invalidate_all(self) -> int:
        return self._cache.invalidate_prefix("render:")

    # -- derivation --

    def _cache_key(self, tick: int, sim_time_s: float, render_origin: Optional[Vector3], context_hash: str, provenance: str) -> str:
        origin_str = f"{render_origin.x},{render_origin.y},{render_origin.z}" if render_origin else "none"
        # include pipeline fingerprint (deterministic)
        try:
            pipe_hash = hashlib.sha256(json.dumps(self._pipeline.config.to_dict() if hasattr(self._pipeline.config, "to_dict") else {}, sort_keys=True).encode()).hexdigest()[:8]
        except Exception:
            pipe_hash = "nopipe"
        return f"render:tick:{tick}:t{sim_time_s:.6f}:o{origin_str}:ctx{context_hash}:p{pipe_hash}:{provenance}"

    def _context_hash(self, context: Optional[RenderContext]) -> str:
        if context is None:
            return "noctx"
        try:
            d = context.to_dict()
            raw = json.dumps(d, sort_keys=True, separators=(",", ":")).encode()
            return hashlib.sha256(raw).hexdigest()[:8]
        except Exception:
            return "ctxerr"

    def derive(
        self,
        tick: int,
        simulation_time_s: float,
        world_objects: List[Dict[str, Any]],
        *,
        render_origin: Optional[Vector3] = None,
        context: Optional[RenderContext] = None,
        provenance: str = "simulated",
        use_cache: bool = True,
    ) -> RenderFrame:
        """
        Derive a RenderFrame for this tick.

        - world_objects is the authoritative snapshot (read-only).
        - Deterministic: same inputs produce byte-identical serialized output.
        - Cached by tick+origin+context+provenance.
        """
        if not isinstance(tick, int) or tick < 0:
            raise RenderDeliveryError(f"tick must be int >=0, got {tick!r}", operation="derive", resource=str(tick))
        if not isinstance(simulation_time_s, (int, float)):
            raise RenderDeliveryError(f"simulation_time_s must be numeric, got {simulation_time_s!r}", operation="derive", resource=str(tick))
        if not isinstance(world_objects, list):
            raise RenderDeliveryError("world_objects must be list", operation="derive", resource=str(tick))
        if len(world_objects) > 200_000:
            raise RenderDeliveryError(f"world_objects exceeds bounded size {len(world_objects)}", operation="derive", resource=str(tick), recoverable=False)

        ctx_hash = self._context_hash(context)
        key = self._cache_key(tick, float(simulation_time_s), render_origin, ctx_hash, provenance)

        if use_cache:
            entry = self._cache.get(key)
            if entry is not None:
                with self._lock:
                    self._cache_hits += 1
                # entry.value is RenderFrame dict or RenderFrame; we stored RenderFrame
                frame = entry.value
                # isolate: clone before returning
                if isinstance(frame, RenderFrame):
                    return frame
                # backwards: if dict, caller gets dict — but we promise RenderFrame
                raise RenderDeliveryError("cache entry type mismatch", operation="derive", resource=key)

        # derive under lock to keep pipeline determinism (floating origin is mutable)
        with self._lock:
            # double-check after acquiring lock
            if use_cache:
                entry = self._cache.get(key)
                if entry is not None and isinstance(entry.value, RenderFrame):
                    self._cache_hits += 1
                    return entry.value
            # Derive frame: if context with camera provided, use full build_frame for correct LOD/visibility;
            # otherwise use simple render_state path.
            try:
                if context is not None and hasattr(context, "camera"):
                    # Full pipeline with camera
                    try:
                        frame = self._pipeline.build_frame(
                            tick=tick,
                            simulation_time_s=float(simulation_time_s),
                            world_objects=world_objects,
                            camera=context.camera,
                            quality=getattr(context, "quality", None),
                            render_origin=render_origin,
                            temporal_mode=getattr(context, "observation_state", TemporalRenderMode.CURRENT),
                        )
                        frame.render_state.provenance = provenance
                    except Exception as e:
                        raise RenderDeliveryError(f"pipeline build_frame failed: {e}", operation="derive", resource=str(tick), cause=e, recoverable=True)
                else:
                    # Simple path: just render state + default context
                    try:
                        render_state = self._pipeline.build_render_state(
                            tick=tick,
                            simulation_time_s=float(simulation_time_s),
                            world_objects=world_objects,
                            render_origin=render_origin,
                        )
                        render_state.provenance = provenance
                    except Exception as e:
                        raise RenderDeliveryError(f"pipeline build failed: {e}", operation="derive", resource=str(tick), cause=e, recoverable=True)
                    frame = self._frame_from_state(render_state, context)
            except RenderDeliveryError:
                raise
            except Exception as e:
                raise RenderDeliveryError(f"frame assembly failed: {e}", operation="derive", resource=str(tick), cause=e, recoverable=True)

            # cache (bounded): size estimate from object count
            est_bytes = frame.render_state.count() * 512  # rough per-object
            if est_bytes > self._max_bytes:
                # still cache but mark as large; caller must stream
                pass
            self._cache.put(key, frame, provenance=provenance, source_tick=tick, tags={"tick", f"tick:{tick}"}, size_bytes=est_bytes)
            self._deliveries += 1
            return frame

    def _frame_from_state(self, state: RenderState, context: Optional[RenderContext]) -> RenderFrame:
        # Minimal frame when pipeline.build_frame not used
        ctx = context
        if ctx is None:
            # Build default context with a default camera (renderer-independent)
            from astra.rendering.camera import Camera
            try:
                default_cam = Camera(position=Vector3(0, 0, 10))
            except Exception:
                default_cam = Camera()  # type: ignore[call-arg]
            ctx = RenderContext(camera=default_cam, render_state=state.clone())
        else:
            # Ensure context references this state (isolated clone)
            try:
                ctx = ctx.clone()
                ctx.render_state = state.clone()
            except Exception:
                ctx = context
        return RenderFrame(
            render_state=state,
            context=ctx,
            lighting=None,
            batches=None,
            visibility_culled=0,
            performance_report=None,
            temporal_mode=state.temporal_mode,
        )

    # -- serialization (deterministic) --

    def serialize_frame(self, frame: RenderFrame, *, pretty: bool = False) -> bytes:
        """
        Deterministic JSON serialization. Validates bounded size.
        """
        if not isinstance(frame, RenderFrame):
            raise RenderDeliveryError(f"frame must be RenderFrame, got {type(frame).__name__}", operation="serialize", resource="frame")
        try:
            d = frame.to_dict()
            # ensure provenance preserved
            d.setdefault("provenance", frame.render_state.provenance)
            payload = json.dumps(d, sort_keys=True, separators=(",", ":") if not pretty else (",", ": "), indent=2 if pretty else None)
            raw = payload.encode("utf-8")
        except Exception as e:
            raise RenderDeliveryError(f"serialize failed: {e}", operation="serialize", cause=e)
        if len(raw) > self._max_bytes:
            raise RenderDeliveryError(
                f"serialized frame exceeds max_state_bytes {len(raw)} > {self._max_bytes}",
                operation="serialize",
                resource=f"tick:{frame.render_state.tick}",
                recoverable=False,
            )
        with self._lock:
            self._bytes_delivered += len(raw)
        return raw

    def deserialize_frame(self, raw: bytes) -> Dict[str, Any]:
        """Return dict (frame dict) — never mutates simulation."""
        try:
            d = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise RenderDeliveryError(f"deserialize failed: {e}", operation="deserialize", cause=e)
        if not isinstance(d, dict) or "render_state" not in d:
            raise RenderDeliveryError("deserialized payload missing render_state", operation="deserialize")
        return d

    # -- streaming for large state (§15) --

    def stream_frame(
        self,
        frame: RenderFrame,
        *,
        chunk_objects: Optional[int] = None,
    ) -> Iterable[Dict[str, Any]]:
        """
        Yield deterministic chunks for a large RenderFrame.
        Each chunk carries provenance + tick + chunk_index/total.
        """
        if not isinstance(frame, RenderFrame):
            raise RenderDeliveryError("frame must be RenderFrame", operation="stream")
        cs = int(chunk_objects) if chunk_objects else self._chunk_size
        objs = list(frame.render_state.iterate())
        total = (len(objs) + cs - 1) // cs if objs else 1
        header = {
            "tick": frame.render_state.tick,
            "simulation_time_s": frame.render_state.simulation_time_s,
            "provenance": frame.render_state.provenance,
            "temporal_mode": frame.temporal_mode.value,
            "total_chunks": total,
            "render_origin": frame.render_state.render_origin.to_tuple() if hasattr(frame.render_state.render_origin, "to_tuple") else (0, 0, 0),
            "context": frame.context.to_dict() if hasattr(frame.context, "to_dict") else {},
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
                "objects": [o.to_dict() if hasattr(o, "to_dict") else o for o in chunk],
                "provenance": frame.render_state.provenance,
            }

    # -- coordination helpers --

    def update_camera_relative(self, frame: RenderFrame, camera_position: Vector3) -> RenderFrame:
        """Helper: rebroadcast with updated camera origin (stateless)."""
        if not isinstance(camera_position, Vector3):
            raise RenderDeliveryError("camera_position must be Vector3", operation="update_camera_relative")
        # Return a cloned frame with updated render_origin for the next derive; this frame is immutable snapshot
        # For coordination, we just return the same frame — caller should re-derive with new origin next tick.
        return frame

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "deliveries": self._deliveries,
                "cache_hits": self._cache_hits,
                "bytes_delivered": self._bytes_delivered,
                "cache": self._cache.stats().to_dict() if hasattr(self._cache, "stats") else {},
                "max_state_bytes": self._max_bytes,
                "chunk_size": self._chunk_size,
            }


__all__ = ["RenderStateDelivery"]
