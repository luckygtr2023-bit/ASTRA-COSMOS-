"""Simulation time & evolution exceptions — explicit failure boundaries."""

from __future__ import annotations

from typing import Any, Dict, Optional


class SimulationTimeError(Exception):
    """Base for simulation time failures."""

    def __init__(self, message: str, *, subsystem: str = "simulation", operation: str = "", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.subsystem = subsystem
        self.operation = operation
        self.details = details or {}

    def __str__(self):
        return f"[{self.subsystem}:{self.operation}] {super().__str__()} {self.details}"


class InvalidTimestepError(SimulationTimeError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "clock")
        kw.setdefault("operation", "validate_timestep")
        super().__init__(message, **kw)


class InvalidRateError(SimulationTimeError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "rate")
        super().__init__(message, **kw)


class InvalidTimestampError(SimulationTimeError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "clock")
        super().__init__(message, **kw)


class SchedulerError(SimulationTimeError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "scheduler")
        super().__init__(message, **kw)


class EvolutionError(SimulationTimeError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "evolution")
        super().__init__(message, **kw)


class LargeJumpRejectedError(EvolutionError):
    def __init__(self, message: str, **kw):
        kw.setdefault("operation", "advance")
        super().__init__(message, **kw)


__all__ = [
    "SimulationTimeError",
    "InvalidTimestepError",
    "InvalidRateError",
    "InvalidTimestampError",
    "SchedulerError",
    "EvolutionError",
    "LargeJumpRejectedError",
]
