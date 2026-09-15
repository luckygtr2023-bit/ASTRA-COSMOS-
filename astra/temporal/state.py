"""ASTRA Temporal - explicit temporal state.

Contract: separate, explicit representations for the five ASTRA time
quantities (simulation time, coordinate time, proper time, observer
reference, temporal rate) plus elapsed intervals.

Conventions (documented once):
    - All times are SECONDS (SI). Proper/coordinate/simulation times are
      non-negative and finite; rates are finite and positive.
    - simulation_time_s: the deterministic engine clock (advanced only by
      explicit simulation inputs - never a wall clock).
    - coordinate_time_s: time coordinate of the active chart.
    - proper_time_s: invariant time accumulated along a worldline.
    - observer: immutable label of the reference context (free-form string
      per house convention; no hidden global observer state).
    - rate: dtau/dt_coordinate (dimensionless); 1.0 for inertial observers
      in flat spacetime.

Mutation policy: TemporalState/TemporalInterval are frozen value objects;
the only mutable temporal authority is astra.temporal.clock.TemporalClock,
gated by the REAL ASTRA authority mechanism
(astra.core.threading.AuthorityContext). No wall-clock, no RNG, no global
mutable state anywhere in this layer.

Persistence: plain primitives via to_dict / from_dict (repository
convention); schema carries units implicitly by documented field names
(_s suffix) and validates on load.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

from astra.temporal.exceptions import InvalidTemporalStateError


def _positive_finite(value, name: str, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTemporalStateError(
            f"{name} must be a real number, got {type(value).__name__}"
        )
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        raise InvalidTemporalStateError(f"{name} cannot be NaN or Infinite, got {value!r}")
    if v < 0.0 or (v == 0.0 and not allow_zero):
        raise InvalidTemporalStateError(f"{name} must be >= 0, got {v!r}")
    return v


@dataclass(frozen=True)
class TemporalState:
    """Immutable, explicit temporal state of a simulated object/observer."""

    simulation_time_s: float
    coordinate_time_s: float
    proper_time_s: float
    observer: str
    rate: float = 1.0  # dtau / dt_coordinate, dimensionless

    def __post_init__(self):
        object.__setattr__(self, "simulation_time_s",
                           _positive_finite(self.simulation_time_s, "simulation_time_s"))
        object.__setattr__(self, "coordinate_time_s",
                           _positive_finite(self.coordinate_time_s, "coordinate_time_s"))
        object.__setattr__(self, "proper_time_s",
                           _positive_finite(self.proper_time_s, "proper_time_s"))
        object.__setattr__(self, "rate",
                           _positive_finite(self.rate, "rate", allow_zero=False))
        if not isinstance(self.observer, str) or not self.observer:
            raise InvalidTemporalStateError("observer must be a non-empty string label")

    def elapsed_since(self, earlier: "TemporalState") -> "TemporalInterval":
        """Elapsed interval from an earlier state to this state."""
        if not isinstance(earlier, TemporalState):
            raise InvalidTemporalStateError("elapsed_since requires a TemporalState")
        return TemporalInterval(
            simulation_delta_s=self.simulation_time_s - earlier.simulation_time_s,
            coordinate_delta_s=self.coordinate_time_s - earlier.coordinate_time_s,
            proper_delta_s=self.proper_time_s - earlier.proper_time_s,
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "simulation_time_s": self.simulation_time_s,
            "coordinate_time_s": self.coordinate_time_s,
            "proper_time_s": self.proper_time_s,
            "observer": self.observer,
            "rate": self.rate,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TemporalState":
        return cls(
            simulation_time_s=data["simulation_time_s"],
            coordinate_time_s=data["coordinate_time_s"],
            proper_time_s=data["proper_time_s"],
            observer=data["observer"],
            rate=data.get("rate", 1.0),
        )


@dataclass(frozen=True)
class TemporalInterval:
    """Elapsed temporal interval across the explicit time quantities.

    Deltas may be negative when comparing unordered states; validation
    only enforces finiteness. All values in seconds.
    """

    simulation_delta_s: float
    coordinate_delta_s: float
    proper_delta_s: float

    def __post_init__(self):
        for name in ("simulation_delta_s", "coordinate_delta_s", "proper_delta_s"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) \
                    or math.isnan(float(v)) or math.isinf(float(v)):
                raise InvalidTemporalStateError(f"{name} must be finite, got {v!r}")

    @property
    def total_seconds(self) -> float:
        """The coordinate-time magnitude of the interval (s)."""
        return self.coordinate_delta_s

    def to_dict(self) -> Dict[str, float]:
        return {
            "simulation_delta_s": self.simulation_delta_s,
            "coordinate_delta_s": self.coordinate_delta_s,
            "proper_delta_s": self.proper_delta_s,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TemporalInterval":
        return cls(
            simulation_delta_s=data["simulation_delta_s"],
            coordinate_delta_s=data["coordinate_delta_s"],
            proper_delta_s=data["proper_delta_s"],
        )
