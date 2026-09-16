"""ASTRA Core coordinate frame and origin rebasing system."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import threading

from astra.core.ids import FrameId
from astra.core.logging import get_logger
from astra.core.exceptions import FrameError, AuthorityError
from astra.core.threading import AuthorityContext, get_simulation_thread_registry


@dataclass
class CoordinateFrame:
    """A coordinate frame in the simulation."""

    id: FrameId
    name: str
    parent_id: Optional[str] = None
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    children: List[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        name: str,
        parent_id: Optional[str] = None,
        origin: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> "CoordinateFrame":
        """Create a new coordinate frame."""
        frame_id = FrameId.from_name(name)
        return cls(id=frame_id, name=name, parent_id=parent_id, origin=origin)


@dataclass
class OriginRebaseRequest:
    """Request to rebase the simulation origin."""

    new_origin: Tuple[float, float, float]
    frame_id: Optional[str] = None
    reason: str = ""
    tick_requested: int = 0

    @classmethod
    def create(
        cls,
        new_origin: Tuple[float, float, float],
        frame_id: Optional[str] = None,
        reason: str = "",
        tick: int = 0,
    ) -> "OriginRebaseRequest":
        """Create a new rebase request."""
        return cls(
            new_origin=new_origin,
            frame_id=frame_id,
            reason=reason,
            tick_requested=tick,
        )


@dataclass
class RebaseResult:
    """Result of an origin rebase operation."""

    success: bool
    old_origin: Tuple[float, float, float]
    new_origin: Tuple[float, float, float]
    offset: Tuple[float, float, float]
    affected_frames: List[str] = field(default_factory=list)
    error: Optional[str] = None


class OriginRebaser:
    """Handles origin rebasing operations."""

    def __init__(self):
        self._pending_request: Optional[OriginRebaseRequest] = None
        self._current_origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._rebase_history: List[RebaseResult] = []
        self._lock = threading.Lock()
        self._logger = get_logger("origin_rebaser")
        self._registry = get_simulation_thread_registry()

    def _require_authority_if_needed(self, operation: str):
        if self._registry.is_registered() and not self._registry.is_simulation_thread():
            raise AuthorityError(
                f"Operation '{operation}' requires simulation thread",
                operation=operation,
                context={
                    "current_thread_id": threading.current_thread().ident,
                    "registered_thread_id": self._registry.get_simulation_thread_id(),
                },
            )

    def request_rebase(
        self,
        new_origin: Tuple[float, float, float],
        frame_id: Optional[str] = None,
        reason: str = "",
        tick: int = 0,
    ) -> OriginRebaseRequest:
        """Request an origin rebase (does not execute immediately)."""
        request = OriginRebaseRequest.create(
            new_origin=new_origin,
            frame_id=frame_id,
            reason=reason,
            tick=tick,
        )
        with self._lock:
            self._pending_request = request
            self._logger.info(f"Origin rebase requested: {new_origin}, reason: {reason}")
        return request

    def get_pending_request(self) -> Optional[OriginRebaseRequest]:
        """Get the pending rebase request, if any."""
        with self._lock:
            return self._pending_request

    def execute_rebase(
        self,
        frames: Dict[str, CoordinateFrame],
        authority_check: bool = True,
    ) -> RebaseResult:
        """Execute a pending rebase request.
        
        Args:
            frames: Dictionary of all coordinate frames
            authority_check: If True, verify authority before executing
            
        Returns:
            RebaseResult with success/failure information
        """
        if authority_check:
            AuthorityContext.require_authority("origin_rebase")

        with self._lock:
            request = self._pending_request
            if request is None:
                return RebaseResult(
                    success=False,
                    old_origin=self._current_origin,
                    new_origin=self._current_origin,
                    offset=(0.0, 0.0, 0.0),
                    error="No pending rebase request",
                )

            old_origin = self._current_origin
            new_origin = request.new_origin

            # Calculate offset: new_origin - old_origin
            offset = tuple(n - o for n, o in zip(new_origin, old_origin))

            # Update all frames to preserve physical positions.
            # Physical position = old_origin + frame.origin (in old representation)
            # After rebase, new representation should be: frame_new = frame_old - offset
            # So that physical position preserved: new_origin + frame_new = old_origin + frame_old
            affected_frames = []
            for frame_id, frame in frames.items():
                if request.frame_id is None or frame_id == request.frame_id:
                    # Correct logic: subtract offset to preserve physical position
                    frame.origin = tuple(o - off for o, off in zip(frame.origin, offset))
                    affected_frames.append(frame_id)

            # Update current origin
            self._current_origin = new_origin
            self._pending_request = None

            result = RebaseResult(
                success=True,
                old_origin=old_origin,
                new_origin=new_origin,
                offset=offset,
                affected_frames=affected_frames,
            )
            self._rebase_history.append(result)
            self._logger.info(f"Origin rebase executed: {old_origin} -> {new_origin}")
            return result

    def cancel_request(self):
        """Cancel the pending rebase request."""
        with self._lock:
            self._pending_request = None
            self._logger.debug("Origin rebase request cancelled")

    def get_current_origin(self) -> Tuple[float, float, float]:
        """Get the current origin."""
        with self._lock:
            return self._current_origin

    def set_origin(self, origin: Tuple[float, float, float], require_authority: bool = False):
        """Set the origin directly (use with caution)."""
        if require_authority:
            AuthorityContext.require_authority("origin_rebase.set_origin")
        else:
            self._require_authority_if_needed("origin_rebase.set_origin")
        with self._lock:
            self._current_origin = origin

    def get_rebase_history(self) -> List[RebaseResult]:
        """Get the history of rebase operations."""
        with self._lock:
            return self._rebase_history.copy()

    def clear_history(self):
        """Clear rebase history."""
        with self._lock:
            self._rebase_history.clear()


class FrameRegistry:
    """Registry for coordinate frames."""

    def __init__(self):
        self._frames: Dict[str, CoordinateFrame] = {}
        self._lock = threading.RLock()
        self._logger = get_logger("frame_registry")
        self._registry = get_simulation_thread_registry()

    def _require_authority_if_needed(self, operation: str):
        if self._registry.is_registered() and not self._registry.is_simulation_thread():
            raise AuthorityError(
                f"Operation '{operation}' requires simulation thread",
                operation=operation,
                context={
                    "current_thread_id": threading.current_thread().ident,
                    "registered_thread_id": self._registry.get_simulation_thread_id(),
                },
            )

    def register(self, frame: CoordinateFrame, require_authority: bool = False):
        """Register a coordinate frame."""
        if require_authority:
            AuthorityContext.require_authority("frame.register")
        else:
            self._require_authority_if_needed("frame.register")
        with self._lock:
            if frame.id.value in self._frames:
                raise FrameError(
                    f"Frame already exists: {frame.id.value}",
                    frame_id=frame.id.value,
                    operation="register",
                )
            self._frames[frame.id.value] = frame

            # Update parent-child relationships
            if frame.parent_id and frame.parent_id in self._frames:
                parent = self._frames[frame.parent_id]
                parent.children.append(frame.id.value)

            self._logger.debug(f"Registered frame: {frame.name}")

    def unregister(self, frame_id: str, require_authority: bool = False):
        """Unregister a coordinate frame."""
        if require_authority:
            AuthorityContext.require_authority("frame.unregister")
        else:
            self._require_authority_if_needed("frame.unregister")
        with self._lock:
            if frame_id not in self._frames:
                raise FrameError(
                    f"Frame not found: {frame_id}",
                    frame_id=frame_id,
                    operation="unregister",
                )

            frame = self._frames[frame_id]

            # Remove from parent's children
            if frame.parent_id and frame.parent_id in self._frames:
                parent = self._frames[frame.parent_id]
                if frame_id in parent.children:
                    parent.children.remove(frame_id)

            del self._frames[frame_id]
            self._logger.debug(f"Unregistered frame: {frame_id}")

    def get_frame(self, frame_id: str) -> Optional[CoordinateFrame]:
        """Get a frame by ID."""
        return self._frames.get(frame_id)

    def get_frame_or_raise(self, frame_id: str) -> CoordinateFrame:
        """Get a frame by ID or raise an error."""
        frame = self._frames.get(frame_id)
        if frame is None:
            raise FrameError(
                f"Frame not found: {frame_id}",
                frame_id=frame_id,
                operation="get",
            )
        return frame

    def get_all_frames(self) -> Dict[str, CoordinateFrame]:
        """Get all registered frames."""
        with self._lock:
            return dict(self._frames)

    def get_root_frames(self) -> List[CoordinateFrame]:
        """Get all root frames (frames without parents)."""
        with self._lock:
            return [f for f in self._frames.values() if f.parent_id is None]

    def transform_point(
        self,
        point: Tuple[float, float, float],
        from_frame: str,
        to_frame: str,
    ) -> Tuple[float, float, float]:
        """Transform a point from one frame to another.
        
        This is a basic implementation. Complex hierarchies may require
        more sophisticated transformation logic.
        """
        with self._lock:
            if from_frame not in self._frames:
                raise FrameError(f"Source frame not found: {from_frame}", from_frame, "transform")
            if to_frame not in self._frames:
                raise FrameError(f"Target frame not found: {to_frame}", to_frame, "transform")

            src = self._frames[from_frame]
            dst = self._frames[to_frame]

            # Simple translation (no rotation/scaling in CORE)
            # Transform to world first, then to target
            world_point = tuple(p + o for p, o in zip(point, src.origin))
            local_point = tuple(w - o for w, o in zip(world_point, dst.origin))

            return local_point

    def clear(self, require_authority: bool = False):
        """Clear all frames."""
        if require_authority:
            AuthorityContext.require_authority("frame.clear")
        else:
            self._require_authority_if_needed("frame.clear")
        with self._lock:
            self._frames.clear()
            self._logger.debug("Cleared all frames")
