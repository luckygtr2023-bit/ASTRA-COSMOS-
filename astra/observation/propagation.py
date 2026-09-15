"""Light propagation — finite-speed retarded-time solver.

Reuses astra.temporal.observation's flat-spacetime model:
  t_obs - t_emit = |x_obs - x(t_emit)| / c
solved by deterministic bisection. Extends it to:

* moving observer (worldline interpolated to t_obs)
* source worldline interpolation (linear between samples)
* honest history-unavailable errors (no extrapolation)
* vectorized distance, lookback, and path tracing helpers

Does NOT introduce curved-path propagation; metric-curved delays remain
out of scope and delegated to spacetime where applicable. Uses
astra.relativity.core.SPEED_OF_LIGHT as single source of truth.
"""

from __future__ import annotations

import math
from typing import Dict, Optional, Sequence, Tuple

from astra.relativity.core import SPEED_OF_LIGHT
from astra.spacetime.events import CHART_CARTESIAN, SpacetimeEvent, Worldline
from astra.temporal.exceptions import InvalidTemporalStateError, InvalidWorldlineError, TemporalHistoryUnavailableError

_BISECTION_ITERATIONS = 80

def _check_time(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or math.isnan(float(value)) or math.isinf(float(value)) or float(value) < 0:
        raise InvalidTemporalStateError(f"{name} must be finite >=0, got {value!r}")
    return float(value)

def _check_vec3(value, name: str) -> Tuple[float,float,float]:
    if not isinstance(value, (list, tuple)) or len(value)!=3:
        raise InvalidTemporalStateError(f"{name} must be (x,y,z) triple")
    out = tuple(float(v) for v in value)
    if any(math.isnan(v) or math.isinf(v) for v in out):
        raise InvalidTemporalStateError(f"{name} contains non-finite")
    return out

def _cartesian_worldline(history: Worldline) -> Worldline:
    if not isinstance(history, Worldline):
        raise InvalidWorldlineError("history must be Worldline")
    if len(history.samples) < 2:
        raise InvalidWorldlineError("history needs >=2 samples")
    if all(e.chart == CHART_CARTESIAN for e in history.events):
        return history
    from astra.spacetime.events import spherical_to_cartesian
    conv=[]
    for p,e in history.samples:
        if e.chart == CHART_CARTESIAN:
            conv.append((p,e))
        else:
            x,y,z = spherical_to_cartesian(e.x, e.y, e.z)
            conv.append((p, SpacetimeEvent(e.ct_m, x, y, z, CHART_CARTESIAN)))
    return Worldline(tuple(conv))

def _interpolate(history: Worldline, t: float) -> SpacetimeEvent:
    params=history.parameters
    events=history.events
    for p,e in zip(params, events):
        if p==t:
            return e
    lo = max(i for i in range(len(params)) if params[i]<=t)
    t0,t1=params[lo],params[lo+1]
    e0,e1=events[lo],events[lo+1]
    w=(t-t0)/(t1-t0) if t1!=t0 else 0.0
    return SpacetimeEvent(e0.ct_m + w*(e1.ct_m-e0.ct_m), e0.x+w*(e1.x-e0.x), e0.y+w*(e1.y-e0.y), e0.z+w*(e1.z-e0.z), CHART_CARTESIAN)

def _event_at(history: Worldline, t: float) -> SpacetimeEvent:
    params=history.parameters
    if t < params[0] - 1e-12*max(1.0, params[0]):
        raise TemporalHistoryUnavailableError(f"emission {t!r}s precedes first sample {params[0]!r}s")
    if t > params[-1] + 1e-12*max(1.0, params[-1]):
        raise TemporalHistoryUnavailableError(f"time {t!r}s exceeds last sample {params[-1]!r}s")
    return _interpolate(history, min(max(t, params[0]), params[-1]))

def _observer_position_at(observer, observation_time_s: float) -> Tuple[float,float,float]:
    """Extract observer position at t_obs.

    observer may be:
      - a tuple/list (x,y,z)
      - an Observer instance (has .position)
      - a Worldline (interpolated)
      - an object with attribute .position or .worldline
    """
    if isinstance(observer, Worldline):
        # worldline parameter is time; interpolate
        try:
            ev=_event_at(observer, observation_time_s)
            return (ev.x, ev.y, ev.z)
        except Exception:
            raise InvalidTemporalStateError("observer Worldline does not cover observation time")
    if isinstance(observer, (list, tuple)) and len(observer)==3 and all(isinstance(v,(int,float)) for v in observer):
        return _check_vec3(observer, "observer_position")
    # Observer object
    if hasattr(observer, "position"):
        pos = getattr(observer, "position")
        return _check_vec3(pos, "observer.position")
    if hasattr(observer, "observer_position"):
        pos = getattr(observer, "observer_position")
        return _check_vec3(pos, "observer.observer_position")
    # fallback: try to treat as dict with position
    if isinstance(observer, dict) and "position" in observer:
        return _check_vec3(observer["position"], "observer[position]")
    raise InvalidTemporalStateError(f"cannot extract observer position from {type(observer).__name__}")

def light_travel_time(distance_m: float) -> float:
    """Geometric light-travel time distance/c (s)."""
    if isinstance(distance_m, bool) or not isinstance(distance_m,(int,float)) or math.isnan(float(distance_m)) or math.isinf(float(distance_m)) or float(distance_m) <0:
        raise InvalidTemporalStateError(f"distance_m must be finite >=0, got {distance_m!r}")
    return float(distance_m) / SPEED_OF_LIGHT

def geometric_distance(observer_position: Sequence[float], emission_position: Sequence[float]) -> float:
    o=_check_vec3(observer_position, "observer_position")
    e=_check_vec3(emission_position, "emission_position")
    dx=o[0]-e[0]; dy=o[1]-e[1]; dz=o[2]-e[2]
    return math.sqrt(dx*dx+dy*dy+dz*dz)

def lookback_time_simple(observer_position: Sequence[float], emission_position: Sequence[float]) -> float:
    return geometric_distance(observer_position, emission_position)/SPEED_OF_LIGHT

def solve_retarded_time(
    source_history: Worldline,
    observer_position: Sequence[float],
    observation_time_s: float,
) -> Tuple[float, SpacetimeEvent, SpacetimeEvent]:
    """Solve retarded emission time for a static observer.

    Returns (t_emit, emission_event, actual_event_at_t_obs). Raises
    TemporalHistoryUnavailableError if history insufficient.

    Deterministic bisection identical to astra.temporal.observation.observe
    but exposed as a pure propagation primitive.
    """
    t_obs=_check_time(observation_time_s, "observation_time_s")
    xo=_check_vec3(observer_position, "observer_position")
    hist=_cartesian_worldline(source_history)
    params=hist.parameters

    def delay(t: float)->float:
        e=_event_at(hist, t)
        dx=e.x-xo[0]; dy=e.y-xo[1]; dz=e.z-xo[2]
        return math.sqrt(dx*dx+dy*dy+dz*dz)/SPEED_OF_LIGHT

    first=params[0]
    if t_obs - first - delay(first) <0 and first < t_obs:
        raise TemporalHistoryUnavailableError(f"light from first sample {first!r}s has not reached observer by {t_obs!r}s")
    hi=min(t_obs, params[-1])
    if hi < t_obs:
        raise TemporalHistoryUnavailableError(f"observation {t_obs!r}s needs history up to t_obs; history ends {params[-1]!r}s")
    lo=first
    if lo > t_obs:
        raise TemporalHistoryUnavailableError(f"t_obs {t_obs!r}s precedes history start {lo!r}s")
    g_lo=t_obs - lo - delay(lo)
    if g_lo <0:
        raise TemporalHistoryUnavailableError("no emission in history could have reached observer by t_obs")

    for _ in range(_BISECTION_ITERATIONS):
        mid=0.5*(lo+hi)
        if t_obs - mid - delay(mid) >=0:
            lo=mid
        else:
            hi=mid
    t_emit=0.5*(lo+hi)
    emission=_event_at(hist, t_emit)
    actual=_event_at(hist, t_obs)
    return t_emit, emission, actual

def solve_retarded_time_with_observer(
    source_history: Worldline,
    observer,
    observation_time_s: float,
) -> Tuple[float, SpacetimeEvent, SpacetimeEvent, Tuple[float,float,float]]:
    """Observer-aware retarded solver.

    observer may be a position tuple, Observer, or Worldline. Extracts its
    position at observation_time_s, then delegates to solve_retarded_time.

    Returns (t_emit, emission_event, actual_event, observer_position).
    """
    t_obs=_check_time(observation_time_s, "observation_time_s")
    xo=_observer_position_at(observer, t_obs)
    t_emit, emission, actual = solve_retarded_time(source_history, xo, t_obs)
    return t_emit, emission, actual, xo

def trace_light_path(
    emission_event: SpacetimeEvent,
    observer_position: Sequence[float],
    observation_time_s: float,
    steps: int = 16,
) -> Tuple[SpacetimeEvent, ...]:
    """Discrete null path sampling from emission to observer arrival.

    Linear in chart coordinates (flat-spacetime). Returns tuple of events
    along the path inclusive of endpoints. For metric-curved paths, callers
    should use spacetime geodesics instead (out of scope here).
    """
    if not isinstance(emission_event, SpacetimeEvent):
        raise InvalidTemporalStateError("emission_event must be SpacetimeEvent")
    xo=_check_vec3(observer_position, "observer_position")
    t_obs=_check_time(observation_time_s, "observation_time_s")
    if emission_event.time_sec > t_obs + 1e-12:
        raise InvalidTemporalStateError("emission cannot be after observation")
    if not (2 <= steps <= 1024):
        raise ValueError("steps must be 2..1024")
    t_emit = emission_event.time_sec
    # observer arrival event
    arrival = SpacetimeEvent.from_coordinates(t_obs, xo[0], xo[1], xo[2], CHART_CARTESIAN)
    out=[]
    for i in range(steps):
        w = i/(steps-1) if steps>1 else 0.0
        t = t_emit + w*(t_obs - t_emit)
        # linear spatial interpolation emission->observer
        x = emission_event.x + w*(xo[0] - emission_event.x)
        y = emission_event.y + w*(xo[1] - emission_event.y)
        z = emission_event.z + w*(xo[2] - emission_event.z)
        out.append(SpacetimeEvent.from_coordinates(t, x, y, z, CHART_CARTESIAN))
    return tuple(out)
