"""Simulation time state — authoritative temporal state for persistence.

Uses existing Core state contracts where possible; adds evolution-specific fields.

Distinguishes:
  simulation_time  – deterministic engine clock (SI seconds, never wall)
  coordinate_time  – chart coordinate (SI)
  proper_time      – invariant along worldline (SI)
  observation_time – lookback (emission) time, never mutated by simulation advancement
  wall_time        – external driver, never authoritative
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional

from astra.core.time import TimeMode

from .exceptions import InvalidTimestampError


def _validate_finite_nonneg(value: Any, name: str, allow_zero: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidTimestampError(f"{name} must be a number, got {type(value).__name__}", operation="validate_time")
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        raise InvalidTimestampError(f"{name} cannot be NaN/Inf, got {value!r}", operation="validate_time")
    if v < 0.0 or (v == 0.0 and not allow_zero):
        raise InvalidTimestampError(f"{name} must be {'>=0' if allow_zero else '>0'}, got {v!r}", operation="validate_time")
    # overflow guard: beyond 1e18 seconds (~3e10 years) is considered out of supported range for single-step
    if v > 1e18:
        raise InvalidTimestampError(f"{name} overflow beyond supported range (1e18s), got {v!r}", operation="validate_time")
    return v


@dataclass(frozen=True)
class SimulationTimeState:
    """Immutable snapshot of simulation temporal state."""

    simulation_time_s: float
    coordinate_time_s: float
    proper_time_s: float
    elapsed_s: float
    tick: int
    tick_duration_s: float
    rate: float
    mode: str
    is_paused: bool
    is_running: bool
    start_time_s: float
    observer: str = "simulation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_time_s": self.simulation_time_s,
            "coordinate_time_s": self.coordinate_time_s,
            "proper_time_s": self.proper_time_s,
            "elapsed_s": self.elapsed_s,
            "tick": self.tick,
            "tick_duration_s": self.tick_duration_s,
            "rate": self.rate,
            "mode": self.mode,
            "is_paused": self.is_paused,
            "is_running": self.is_running,
            "start_time_s": self.start_time_s,
            "observer": self.observer,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationTimeState":
        return cls(
            simulation_time_s=_validate_finite_nonneg(data.get("simulation_time_s", 0.0), "simulation_time_s"),
            coordinate_time_s=_validate_finite_nonneg(data.get("coordinate_time_s", 0.0), "coordinate_time_s"),
            proper_time_s=_validate_finite_nonneg(data.get("proper_time_s", 0.0), "proper_time_s"),
            elapsed_s=_validate_finite_nonneg(data.get("elapsed_s", 0.0), "elapsed_s"),
            tick=int(data.get("tick", 0)),
            tick_duration_s=_validate_finite_nonneg(data.get("tick_duration_s", 1.0/60.0), "tick_duration_s", allow_zero=False),
            rate=_validate_finite_nonneg(data.get("rate", 1.0), "rate", allow_zero=False),
            mode=str(data.get("mode", TimeMode.INTERNAL_DETERMINISTIC.value)),
            is_paused=bool(data.get("is_paused", False)),
            is_running=bool(data.get("is_running", False)),
            start_time_s=_validate_finite_nonneg(data.get("start_time_s", 0.0), "start_time_s"),
            observer=str(data.get("observer", "simulation")),
        )
