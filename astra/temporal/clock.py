"""ASTRA Temporal - deterministic temporal clock.

Contract: simulation time advances ONLY through explicit simulation
inputs. There is no wall-clock read, no sleep-based pacing, no global
mutable temporal state, and no RNG in this module.

Authority: this is the ONE mutable object in the temporal layer; its
mutating operation (advance / reset) is gated by the repository's real
authority mechanism, ``astra.core.threading.AuthorityContext.require_``
``authority("temporal.advance")``, mirroring ``astra.motion.MotionSystem``
exactly (including the ``require_authority`` escape hatch for tests).

Relationship to ``astra.core.time.SimulationClock``: the core clock owns
tick accounting for the engine loop. This clock owns the TEMPORAL LAYER
accumulators (coordinate time, proper time via per-tick rates) used by
relativistic subsystems; it composes with core (reading nothing from the
wall clock) but does not replace or modify it.
"""

from __future__ import annotations

import math

from astra.core.threading import AuthorityContext
from astra.temporal.exceptions import InvalidTemporalStateError
from astra.temporal.state import TemporalState


class TemporalClock:
    """Explicit-advance deterministic clock with proper-time accumulation.

    advances of coordinate time may carry a proper-time rate
    (dtau/dt, e.g. 1/gamma or sqrt(1 - r_s/r)); proper time accumulates
    at that rate. Deterministic: identical call sequences produce
    bit-identical accumulators.
    """

    def __init__(self, observer: str = "simulation",
                 simulation_time_s: float = 0.0,
                 coordinate_time_s: float = 0.0,
                 proper_time_s: float = 0.0):
        if not isinstance(observer, str) or not observer:
            raise InvalidTemporalStateError("observer must be a non-empty string label")
        self._observer = observer
        self._simulation_time_s = float(simulation_time_s)
        self._coordinate_time_s = float(coordinate_time_s)
        self._proper_time_s = float(proper_time_s)
        self._rate = 1.0  # dtau/dt for subsequent advances
        for name, v in (("simulation_time_s", simulation_time_s),
                        ("coordinate_time_s", coordinate_time_s),
                        ("proper_time_s", proper_time_s)):
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or math.isnan(float(v)) or math.isinf(float(v)) or float(v) < 0.0:
                raise InvalidTemporalStateError(f"{name} must be finite >= 0, got {v!r}")

    # -- reads -------------------------------------------------------------
    @property
    def observer(self) -> str:
        return self._observer

    @property
    def simulation_time_s(self) -> float:
        return self._simulation_time_s

    @property
    def coordinate_time_s(self) -> float:
        return self._coordinate_time_s

    @property
    def proper_time_s(self) -> float:
        return self._proper_time_s

    @property
    def rate(self) -> float:
        return self._rate

    def to_state(self) -> TemporalState:
        """Immutable snapshot of the current temporal state."""
        return TemporalState(
            simulation_time_s=self._simulation_time_s,
            coordinate_time_s=self._coordinate_time_s,
            proper_time_s=self._proper_time_s,
            observer=self._observer,
            rate=self._rate,
        )

    # -- explicit, authoritative mutation -----------------------------------
    def set_rate(self, rate: float, require_authority: bool = True) -> None:
        """Set the proper-time rate dtau/dt applied to future advances.

        Must be finite and > 0 (a clock cannot tick at zero or negative
        proper rate in this layer).
        """
        if require_authority:
            AuthorityContext.require_authority("temporal.set_rate")
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) \
                or math.isnan(float(rate)) or math.isinf(float(rate)) or float(rate) <= 0.0:
            raise InvalidTemporalStateError(f"rate must be finite and > 0, got {rate!r}")
        self._rate = float(rate)

    def advance(self, dt_s: float, require_authority: bool = True) -> TemporalState:
        """Advance all accumulators by an explicit, finite, non-negative dt.

        simulation/coordinate time increase by dt; proper time increases by
        dt * rate. Returns the resulting TemporalState snapshot.
        """
        if require_authority:
            AuthorityContext.require_authority("temporal.advance")
        if isinstance(dt_s, bool) or not isinstance(dt_s, (int, float)) \
                or math.isnan(float(dt_s)) or math.isinf(float(dt_s)) or float(dt_s) < 0.0:
            raise InvalidTemporalStateError(f"dt_s must be finite >= 0, got {dt_s!r}")
        dt = float(dt_s)
        self._simulation_time_s += dt
        self._coordinate_time_s += dt
        self._proper_time_s += dt * self._rate
        return self.to_state()

    def reset(self, simulation_time_s: float = 0.0, coordinate_time_s: float = 0.0,
              proper_time_s: float = 0.0, require_authority: bool = True) -> None:
        """Reset accumulators to explicit values (deterministic restarts)."""
        if require_authority:
            AuthorityContext.require_authority("temporal.reset")
        for name, v in (("simulation_time_s", simulation_time_s),
                        ("coordinate_time_s", coordinate_time_s),
                        ("proper_time_s", proper_time_s)):
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or math.isnan(float(v)) or math.isinf(float(v)) or float(v) < 0.0:
                raise InvalidTemporalStateError(f"{name} must be finite >= 0, got {v!r}")
        self._simulation_time_s = float(simulation_time_s)
        self._coordinate_time_s = float(coordinate_time_s)
        self._proper_time_s = float(proper_time_s)
        self._rate = 1.0
