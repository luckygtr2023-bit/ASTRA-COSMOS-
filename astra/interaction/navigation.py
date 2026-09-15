"""ASTRA Interaction — navigation across hierarchical coordinate architecture.

Uses existing FrameRegistry / OriginRebaser / WorldHierarchy / SpatialIndex.
Never introduces a second coordinate system; never teleports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Any
import math

from .scale import ScaleLevel, scale_transition_steps
from .errors import NavigationError


def _fin(name, v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
        raise NavigationError(f"{name} must be finite, got {v!r}")
    return float(v)


@dataclass(frozen=True)
class NavigationRequest:
    request_id: str
    from_scale: ScaleLevel
    to_scale: ScaleLevel
    target_reference: Optional[str] = None  # authoritative id of destination
    frame_id: Optional[str] = None
    position: Optional[Tuple[float, float, float]] = None
    via_provenance: bool = False

    def __post_init__(self):
        if not isinstance(self.request_id, str) or not self.request_id:
            raise NavigationError("request_id must be non-empty string")
        if not isinstance(self.from_scale, ScaleLevel) or not isinstance(self.to_scale, ScaleLevel):
            raise NavigationError("scales must be ScaleLevel")
        if self.target_reference is not None and not isinstance(self.target_reference, str):
            raise NavigationError("target_reference must be str or None")
        if self.position is not None:
            if len(self.position) != 3:
                raise NavigationError("position must be 3-tuple")
            for i, v in enumerate(self.position):
                _fin(f"position[{i}]", v)
            object.__setattr__(self, "position", tuple(float(x) for x in self.position))

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "from_scale": self.from_scale.value,
            "to_scale": self.to_scale.value,
            "target_reference": self.target_reference,
            "frame_id": self.frame_id,
            "position": list(self.position) if self.position else None,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "NavigationRequest":
        return cls(
            request_id=d["request_id"],
            from_scale=ScaleLevel(d["from_scale"]),
            to_scale=ScaleLevel(d["to_scale"]),
            target_reference=d.get("target_reference"),
            frame_id=d.get("frame_id"),
            position=tuple(d["position"]) if d.get("position") else None,
        )


@dataclass(frozen=True)
class NavigationResult:
    request_id: str
    success: bool
    from_scale: ScaleLevel
    to_scale: ScaleLevel
    frame_id: Optional[str] = None
    world_position: Optional[Tuple[float, float, float]] = None
    rebase_applied: bool = False
    steps: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "success": self.success,
            "from_scale": self.from_scale.value,
            "to_scale": self.to_scale.value,
            "frame_id": self.frame_id,
            "world_position": list(self.world_position) if self.world_position else None,
            "rebase_applied": self.rebase_applied,
            "steps": self.steps,
            "error": self.error,
        }


class NavigationService:
    """Navigation that delegates to authoritative spatial systems.

    Providers (injected):
      - frame_registry: FrameRegistry
      - world: World (hierarchy/scene_graph/spatial)
      - origin_rebaser: OriginRebaser
    """

    def __init__(self, frame_registry=None, world=None, origin_rebaser=None):
        self._frames = frame_registry
        self._world = world
        self._rebaser = origin_rebaser

    def validate(self, req: NavigationRequest) -> None:
        # Scale transition is always valid structurally; semantic validation delegates
        if req.target_reference is not None and self._world is None:
            # still valid; we just warn later but not fail — require world for real resolve
            pass
        if req.frame_id is not None and self._frames is not None:
            if self._frames.get_frame(req.frame_id) is None:
                raise NavigationError(f"frame not found: {req.frame_id!r}")

    def execute(self, req: NavigationRequest, require_authority: bool = False) -> NavigationResult:
        """Deterministic navigation — no teleport.

        Real movement must be driven by physics/motion; this call only
        validates the request, resolves the target via World/Frame, and
        optionally rebases origin for precision. It returns the TARGET
        placement, not an instant move.
        """
        self.validate(req)
        steps = scale_transition_steps(req.from_scale, req.to_scale)

        # Resolve target position via world if available; otherwise use hint
        world_pos = req.position
        frame_id = req.frame_id

        if req.target_reference is not None and self._world is not None:
            # Try scene graph / hierarchy / spatial index — in order, no duplication
            # All via authoritative references
            try:
                node = self._world.get_scene_node(req.target_reference)
                if node is None:
                    # try hierarchy node
                    hnode = self._world.get_hierarchy_node(req.target_reference)
                    if hnode is not None:
                        # use scene position if available via world_position
                        try:
                            world_pos = self._world.get_world_position(hnode.id)
                        except Exception:
                            pass
                else:
                    world_pos = self._world.get_world_position(node.id)
                    frame_id = frame_id or getattr(node, "parent_id", None)
            except Exception as e:
                # Structured failure, not silent
                return NavigationResult(
                    request_id=req.request_id,
                    success=False,
                    from_scale=req.from_scale,
                    to_scale=req.to_scale,
                    frame_id=frame_id,
                    error=f"target resolution failed: {e}",
                    steps=steps,
                )
            # Also try spatial index position hint if still None
            if world_pos is None:
                try:
                    # SpatialIndex is inside world; use public query if available
                    idx = getattr(self._world, "_spatial_index", None)
                    if idx is not None:
                        objs = getattr(idx, "_objects", {})
                        if req.target_reference in objs:
                            world_pos = tuple(objs[req.target_reference])
                except Exception:
                    pass

        # If still no world_pos and no target_reference, use origin_hint or fail explicitly
        if world_pos is None and req.target_reference is not None:
            # target without resolvable position is invalid (no teleport to unknown)
            return NavigationResult(
                request_id=req.request_id,
                success=False,
                from_scale=req.from_scale,
                to_scale=req.to_scale,
                frame_id=frame_id,
                error=f"target {req.target_reference!r} has no resolvable position",
                steps=steps,
            )

        # Origin rebasing for large scale transitions (preserve relative positions)
        rebase_applied = False
        if world_pos is not None and self._rebaser is not None and steps >= 3:
            # For coarse scale jumps, rebase origin to target for precision
            # This is the ONLY allowed coordinate mutation and it preserves physics
            try:
                if require_authority:
                    from astra.core.threading import AuthorityContext
                    AuthorityContext.require_authority("navigation.rebase")
                # Request then execute via rebaser if frames supplied
                # We do not silently teleport; rebasing only changes representation
                pending = self._rebaser.request_rebase(world_pos, frame_id=frame_id, reason=f"navigation {req.request_id}")
                # Execution requires frames map; delegate if available
                if self._frames is not None:
                    frames = self._frames.get_all_frames()
                    result = self._rebaser.execute_rebase(frames, authority_check=False)
                    rebase_applied = result.success
                else:
                    # Just record request; no execution without frame map
                    rebase_applied = False
            except Exception:
                rebase_applied = False

        return NavigationResult(
            request_id=req.request_id,
            success=True,
            from_scale=req.from_scale,
            to_scale=req.to_scale,
            frame_id=frame_id,
            world_position=world_pos,
            rebase_applied=rebase_applied,
            steps=steps,
        )
