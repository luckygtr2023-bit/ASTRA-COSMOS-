"""ASTRA Rendering - temporal / observation rendering boundary.

Distinguishes CURRENT simulation state from OBSERVED / HISTORICAL visual
state. Does not confuse astronomical lookback with simulation time travel.

Uses astra.temporal.observation.ObservedState when available; otherwise
provides pure geometric lookback approximations for rendering.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from astra.mathematics import Vector3
from astra.rendering.exceptions import TemporalRenderError
from astra.rendering.render_state import RenderObject, RenderState
from astra.rendering.types import TemporalRenderMode


def _require_vector(v: Vector3, name: str) -> Vector3:
    if not isinstance(v, Vector3):
        raise TemporalRenderError(f"{name} must be Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise TemporalRenderError(f"{name} must be finite, got {v!r}")
    return v


# Speed of light exact (from relativity core if available)
try:
    from astra.relativity.core import SPEED_OF_LIGHT as C  # type: ignore
except Exception:
    C = 299792458.0


@dataclass(frozen=True)
class ObservedRenderRecord:
    """Visual record of an object as observed at a given time."""

    object_id: str
    observation_time_s: float
    emission_time_s: float
    lookback_time_s: float
    # Position as emitted (what observer sees) vs actual at observation
    emission_position: Vector3
    actual_position: Vector3
    observer_position: Vector3
    observer_id: str = "observer"

    def is_delayed(self) -> bool:
        return self.lookback_time_s > 1e-9

    def light_travel_distance_m(self) -> float:
        return self.lookback_time_s * C

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "observation_time_s": self.observation_time_s,
            "emission_time_s": self.emission_time_s,
            "lookback_time_s": self.lookback_time_s,
            "emission_position": self.emission_position.to_tuple(),
            "actual_position": self.actual_position.to_tuple(),
            "observer_position": self.observer_position.to_tuple(),
            "observer_id": self.observer_id,
        }


def compute_lookback(
    observer_position: Vector3,
    emission_position: Vector3,
    observation_time_s: float,
    emission_time_s: Optional[float] = None,
) -> float:
    """Geometric light travel time (distance / c). If emission_time not given, assume instantaneous geometry."""
    _require_vector(observer_position, "observer_position")
    _require_vector(emission_position, "emission_position")
    if not isinstance(observation_time_s, (int, float)) or isinstance(observation_time_s, bool):
        raise TemporalRenderError(f"observation_time_s must be numeric, got {type(observation_time_s).__name__}")
    obs_t = float(observation_time_s)
    if math.isnan(obs_t) or math.isinf(obs_t) or obs_t < 0:
        raise TemporalRenderError(f"observation_time_s must be finite >=0, got {observation_time_s!r}")
    # distance
    d = (observer_position - emission_position).magnitude()
    travel = d / C
    if emission_time_s is not None:
        if not isinstance(emission_time_s, (int, float)) or isinstance(emission_time_s, bool):
            raise TemporalRenderError("emission_time_s must be numeric")
        e = float(emission_time_s)
        if math.isnan(e) or math.isinf(e) or e < 0:
            raise TemporalRenderError(f"emission_time_s must be finite >=0, got {emission_time_s!r}")
        if e > obs_t + 1e-12:
            raise TemporalRenderError(f"emission_time {e} cannot be after observation {obs_t}")
        # consistency check? travel should approx obs - e for static? Use geometric as hint.
        return travel
    return travel


def observed_state_to_render_record(
    observed_state,  # astra.temporal.observation.ObservedState
    object_id: str,
    observer_position: Vector3,
) -> ObservedRenderRecord:
    """Convert an authoritative ObservedState to a rendering record."""
    try:
        obs_time = float(getattr(observed_state, "observation_time_s"))
        emit_time = float(getattr(observed_state, "emission_time_s"))
        lookback = float(getattr(observed_state, "lookback_time_s"))
        emission_event = getattr(observed_state, "emission_event")
        actual_event = getattr(observed_state, "actual_state_at_observation")
        observer = str(getattr(observed_state, "observer", "observer"))

        def _event_to_vec(ev) -> Vector3:
            # SpacetimeEvent has x,y,z (and ct) in cartesian chart
            x = float(getattr(ev, "x", 0.0))
            y = float(getattr(ev, "y", 0.0))
            z = float(getattr(ev, "z", 0.0))
            return Vector3(x, y, z)

        emit_pos = _event_to_vec(emission_event)
        actual_pos = _event_to_vec(actual_event)
        _require_vector(observer_position, "observer_position")
        return ObservedRenderRecord(
            object_id=object_id,
            observation_time_s=obs_time,
            emission_time_s=emit_time,
            lookback_time_s=lookback,
            emission_position=emit_pos,
            actual_position=actual_pos,
            observer_position=Vector3(observer_position.x, observer_position.y, observer_position.z),
            observer_id=observer,
        )
    except TemporalRenderError:
        raise
    except Exception as e:
        raise TemporalRenderError(f"failed to convert ObservedState: {e}") from e


def apply_observed_state_to_render_object(
    render_obj: RenderObject,
    record: ObservedRenderRecord,
    render_origin: Optional[Vector3] = None,
) -> RenderObject:
    """Return a new RenderObject positioned at emission (observed) location.

    Keeps original actual position in metadata for comparison/debug.
    """
    if not isinstance(render_obj, RenderObject):
        raise TemporalRenderError("render_obj must be RenderObject")
    if not isinstance(record, ObservedRenderRecord):
        raise TemporalRenderError("record must be ObservedRenderRecord")
    cloned = render_obj.clone()
    # Convert emission world position to render space
    world_emit = record.emission_position
    if render_origin is not None:
        _require_vector(render_origin, "render_origin")
        render_emit = world_emit - render_origin
    else:
        render_emit = Vector3(world_emit.x, world_emit.y, world_emit.z)
    cloned.position = render_emit
    cloned.temporal_mode = TemporalRenderMode.OBSERVED
    cloned.observation_time_s = record.observation_time_s
    cloned.emission_time_s = record.emission_time_s
    cloned.metadata = dict(cloned.metadata)
    cloned.metadata.update({
        "lookback_s": record.lookback_time_s,
        "actual_world_position": record.actual_position.to_tuple(),
        "emission_world_position": record.emission_position.to_tuple(),
        "observer_id": record.observer_id,
    })
    return cloned


def apply_temporal_mode_to_render_state(
    state: RenderState,
    mode: TemporalRenderMode,
    observer_position: Optional[Vector3] = None,
    observed_records: Optional[Dict[str, ObservedRenderRecord]] = None,
) -> RenderState:
    """Apply temporal mode to an entire RenderState (clone, do not mutate original)."""
    if not isinstance(state, RenderState):
        raise TemporalRenderError("state must be RenderState")
    if not isinstance(mode, TemporalRenderMode):
        raise TemporalRenderError(f"mode must be TemporalRenderMode, got {mode!r}")
    cloned = state.clone()
    cloned.temporal_mode = mode
    if mode == TemporalRenderMode.CURRENT:
        for oid in cloned.order:
            obj = cloned.objects[oid]
            obj.temporal_mode = TemporalRenderMode.CURRENT
            obj.observation_time_s = None
            obj.emission_time_s = None
        return cloned

    if mode in (TemporalRenderMode.OBSERVED, TemporalRenderMode.HISTORICAL):
        if observed_records is None:
            # Approximate: shift positions back along velocity if available? Without history, keep as is but mark mode.
            # For rendering, we at least mark them observed; positions are kept as derived current but hinted delayed.
            # Provide geometric lookback per object if observer_position supplied.
            for oid in cloned.order:
                obj = cloned.objects[oid]
                obj.temporal_mode = mode
                obj.observation_time_s = state.simulation_time_s
                if observer_position is not None:
                    # Approximate emission pos = current pos - velocity * travel?
                    # Without velocity, estimate lookback from distance.
                    world_pos = obj.position + state.render_origin  # reconstruct world
                    travel = (observer_position - world_pos).magnitude() / C
                    obj.emission_time_s = max(0.0, state.simulation_time_s - travel)
                    obj.metadata = dict(obj.metadata)
                    obj.metadata["approx_lookback_s"] = travel
                else:
                    obj.emission_time_s = None
            return cloned

        # Use supplied observed records (authoritative)
        for oid in list(cloned.order):
            obj = cloned.objects[oid]
            rec = observed_records.get(obj.source_ref or obj.id) or observed_records.get(oid)
            if rec is not None:
                # Replace with observed position
                new_obj = apply_observed_state_to_render_object(obj, rec, render_origin=cloned.render_origin)
                cloned.objects[oid] = new_obj
            else:
                obj.temporal_mode = mode
                obj.observation_time_s = state.simulation_time_s
    return cloned
