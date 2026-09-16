"""ASTRA Temporal - observation vs actual state, lookback.

Contract: separation of ACTUAL and OBSERVED state is explicit and
enforced by types. An observation NEVER mutates the actual state; it
returns an immutable :class:`ObservedState` describing the emission event
that the observer literally sees at observation time.

Propagation model (this phase): flat-spacetime null propagation between
the observer position and the object's recorded trajectory,

    t_obs - t_emit = |x_observer - x(t_emit)| / c,

solved by deterministic bisection on the recorded history bracket.
Metric-curved propagation paths (gravitational lensing delays, Shapiro
delay) are OUT OF SCOPE and deliberately not approximated.

Honesty policy: emission times earlier than the first recorded sample
raise ``TemporalHistoryUnavailableError``. This layer NEVER fabricates,
extrapolates, or invents astronomical history - interpolation strictly
between recorded samples only (linear, deterministic, documented).

Units: seconds, metres, c exact. Deterministic pure functions.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple

from astra.relativity.core import SPEED_OF_LIGHT
from astra.spacetime.events import CHART_CARTESIAN, SpacetimeEvent, Worldline
from astra.temporal.exceptions import (
    InvalidTemporalStateError,
    InvalidWorldlineError,
    TemporalHistoryUnavailableError,
)

# Bisection depth for the retarded-time equation. 80 halvings of any
# bracket exceed double precision: fully deterministic convergence.
_BISECTION_ITERATIONS: int = 80


@dataclass(frozen=True)
class ObservedState:
    """The state an observer literally SEES, plus its provenance.

    actual_state_at_observation: the object's real state at t_obs (never
    mutated by observation). emission_event: where/when the received light
    left the object. lookback_time_s: t_obs - t_emit (>= 0).
    """

    observation_time_s: float
    emission_time_s: float
    lookback_time_s: float
    emission_event: SpacetimeEvent
    actual_state_at_observation: SpacetimeEvent
    observer: str

    def to_dict(self) -> Dict:
        return {
            "observation_time_s": self.observation_time_s,
            "emission_time_s": self.emission_time_s,
            "lookback_time_s": self.lookback_time_s,
            "emission_event": self.emission_event.to_dict(),
            "actual_state_at_observation": self.actual_state_at_observation.to_dict(),
            "observer": self.observer,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ObservedState":
        return cls(
            observation_time_s=data["observation_time_s"],
            emission_time_s=data["emission_time_s"],
            lookback_time_s=data["lookback_time_s"],
            emission_event=SpacetimeEvent.from_dict(data["emission_event"]),
            actual_state_at_observation=SpacetimeEvent.from_dict(
                data["actual_state_at_observation"]),
            observer=data["observer"],
        )


def _check_time(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or math.isnan(float(value)) or math.isinf(float(value)) or float(value) < 0.0:
        raise InvalidTemporalStateError(f"{name} must be finite >= 0, got {value!r}")
    return float(value)


def _cartesian_worldline(history: Worldline) -> Worldline:
    """Accept cartesian worldlines; convert spherical ones (reuse path)."""
    if not isinstance(history, Worldline):
        raise InvalidWorldlineError("history must be an astra.spacetime.Worldline")
    if len(history.samples) < 2:
        raise InvalidWorldlineError("history needs >= 2 recorded samples")
    if all(e.chart == CHART_CARTESIAN for e in history.events):
        return history
    from astra.spacetime.events import cartesian_to_spherical  # noqa: F401
    from astra.spacetime.events import spherical_to_cartesian
    converted = []
    for p, e in history.samples:
        if e.chart == CHART_CARTESIAN:
            converted.append((p, e))
        else:
            x, y, z = spherical_to_cartesian(e.x, e.y, e.z)
            converted.append((p, SpacetimeEvent(e.ct_m, x, y, z, CHART_CARTESIAN)))
    return Worldline(tuple(converted))


def _interpolate(history: Worldline, t_emit: float) -> SpacetimeEvent:
    """Linear interpolation strictly BETWEEN recorded samples (t in s).

    The worldline parameter IS coordinate time for recorded histories.
    Exact sample hits return the recorded event unchanged.
    """
    params = history.parameters
    events = history.events
    for p, e in zip(params, events):
        if p == t_emit:
            return e
    lo = max(i for i in range(len(params)) if params[i] <= t_emit)
    t0, t1 = params[lo], params[lo + 1]
    e0, e1 = events[lo], events[lo + 1]
    w = (t_emit - t0) / (t1 - t0)
    return SpacetimeEvent(
        e0.ct_m + w * (e1.ct_m - e0.ct_m),
        e0.x + w * (e1.x - e0.x),
        e0.y + w * (e1.y - e0.y),
        e0.z + w * (e1.z - e0.z),
        CHART_CARTESIAN,
    )


def _event_at(history: Worldline, t_emit: float) -> SpacetimeEvent:
    params = history.parameters
    if t_emit < params[0] - 1e-12 * max(1.0, params[0]):
        raise TemporalHistoryUnavailableError(
            f"emission time {t_emit!r} s precedes the first recorded sample "
            f"{params[0]!r} s: refusing to fabricate history"
        )
    if t_emit > params[-1] + 1e-12 * max(1.0, params[-1]):
        raise TemporalHistoryUnavailableError(
            f"emission time {t_emit!r} s exceeds the last recorded sample "
            f"{params[-1]!r} s: refusing to extrapolate history"
        )
    return _interpolate(history, min(max(t_emit, params[0]), params[-1]))


def observe(
    history: Worldline,
    observer_position: Sequence[float],
    observation_time_s: float,
    observer: str = "observer",
) -> ObservedState:
    """Observe a recorded object from a static observer position.

    Solves the light-propagation retardation on the recorded history:

        g(t) = observation_time - t - |x_obs - x(t)| / c   (decreasing in t
        for |v| < c), g(t_obs) = -dist(t_obs)/c <= 0. If g(t_first) < 0 the
        emission is unrecorded -> TemporalHistoryUnavailableError.

    Returns an immutable ObservedState. The actual state at t_obs is
    included for contrast and is NOT modified by this call.
    """
    t_obs = _check_time(observation_time_s, "observation_time_s")
    if len(observer_position) != 3:
        raise InvalidTemporalStateError("observer_position must be an (x, y, z) triple")
    xo = tuple(float(v) for v in observer_position)
    if any(math.isnan(v) or math.isinf(v) for v in xo):
        raise InvalidTemporalStateError("observer_position contains non-finite components")
    if not isinstance(observer, str) or not observer:
        raise InvalidTemporalStateError("observer must be a non-empty string label")

    hist = _cartesian_worldline(history)
    params = hist.parameters
    events = hist.events

    def range_delay(t: float) -> float:
        e = _event_at(hist, t)
        dx = e.x - xo[0]
        dy = e.y - xo[1]
        dz = e.z - xo[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz) / SPEED_OF_LIGHT

    # Bracket check BEFORE solving: honesty precedes numerics.
    first = params[0]
    if t_obs - first - range_delay(first) < 0.0 and first < t_obs:
        raise TemporalHistoryUnavailableError(
            f"light emitted at the first recorded sample ({first!r} s) has not "
            f"reached the observer by {t_obs!r} s: required history is unavailable"
        )

    # g(t) = t_obs - t - delay(t); g(t_obs) = -delay(t_obs) <= 0.
    hi = min(t_obs, params[-1])
    if hi < t_obs:
        raise TemporalHistoryUnavailableError(
            f"observation at {t_obs!r} s needs emission states up to that time; "
            f"history ends at {params[-1]!r} s"
        )
    lo = first
    if lo > t_obs:
        raise TemporalHistoryUnavailableError(
            f"observation time {t_obs!r} s precedes all recorded history "
            f"(starts {lo!r} s)"
        )
    g_lo = t_obs - lo - range_delay(lo)
    if g_lo < 0.0:
        raise TemporalHistoryUnavailableError(
            "no recorded emission in this history could have reached the "
            "observer by the observation time: history unavailable"
        )
    # Deterministic bisection on [lo, hi] with g(lo) >= 0 >= g(hi).
    for _ in range(_BISECTION_ITERATIONS):
        mid = 0.5 * (lo + hi)
        if t_obs - mid - range_delay(mid) >= 0.0:
            lo = mid
        else:
            hi = mid
    t_emit = 0.5 * (lo + hi)

    emission = _event_at(hist, t_emit)
    actual = _event_at(hist, t_obs) if t_obs <= params[-1] else None
    if actual is None:
        raise TemporalHistoryUnavailableError(
            f"actual state at {t_obs!r} s is not recorded; refusing to invent it"
        )
    return ObservedState(
        observation_time_s=t_obs,
        emission_time_s=t_emit,
        lookback_time_s=t_obs - t_emit,
        emission_event=emission,
        actual_state_at_observation=actual,
        observer=observer,
    )


def lookback_time(observer_position: Sequence[float], emission_position: Sequence[float],
                  observation_time_s: float, emission_time_s: float) -> float:
    """Light-travel delay for a given emission/observation geometry (s).

    Simple geometric form: |x_obs - x_emit| / c with explicit finiteness
    validation; emission must not follow observation.
    """
    t_obs = _check_time(observation_time_s, "observation_time_s")
    t_emit = _check_time(emission_time_s, "emission_time_s")
    if len(observer_position) != 3 or len(emission_position) != 3:
        raise InvalidTemporalStateError("positions must be (x, y, z) triples")
    d = tuple(o - e for o, e in zip(observer_position, emission_position))
    if any(math.isnan(v) or math.isinf(v) for v in d):
        raise InvalidTemporalStateError("positions contain non-finite components")
    if t_emit > t_obs:
        raise InvalidTemporalStateError(
            f"emission ({t_emit!r} s) cannot follow observation ({t_obs!r} s)"
        )
    dist = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
    return dist / SPEED_OF_LIGHT
