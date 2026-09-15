"""
ASTRA Backend — diagnostics and health (§14).

Aggregates:
  - Event hub stats
  - Cache stats
  - Service health
  - Runtime lifecycle counters
  - Persistence stats
  - Rendering delivery metrics

No hidden background threads here; runtime orchestrator drives heartbeat.
Thread-safe, bounded log.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class DiagnosticsEntry:
    timestamp_monotonic: float
    level: str  # DEBUG/INFO/WARNING/ERROR
    subsystem: str
    operation: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class DiagnosticsCollector:
    def __init__(self, max_entries: int = 10000):
        self._max = max(1, int(max_entries))
        self._entries: List[DiagnosticsEntry] = []
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = {}
        self._health: Dict[str, HealthStatus] = {}
        self._started = time.monotonic()

    def log(self, level: str, subsystem: str, operation: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        entry = DiagnosticsEntry(
            timestamp_monotonic=time.monotonic(),
            level=level,
            subsystem=subsystem,
            operation=operation,
            message=message,
            details=details or {},
        )
        with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max:
                self._entries = self._entries[-self._max :]
            self._counters[f"{subsystem}.{operation}"] = self._counters.get(f"{subsystem}.{operation}", 0) + 1

    def debug(self, subsystem: str, operation: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.log("DEBUG", subsystem, operation, message, details)

    def info(self, subsystem: str, operation: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.log("INFO", subsystem, operation, message, details)

    def warning(self, subsystem: str, operation: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.log("WARNING", subsystem, operation, message, details)

    def error(self, subsystem: str, operation: str, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.log("ERROR", subsystem, operation, message, details)

    def set_health(self, subsystem: str, status: HealthStatus) -> None:
        with self._lock:
            self._health[subsystem] = status

    def get_health(self, subsystem: Optional[str] = None) -> Dict[str, str]:
        with self._lock:
            if subsystem:
                s = self._health.get(subsystem, HealthStatus.UNKNOWN)
                return {subsystem: s.value}
            return {k: v.value for k, v in self._health.items()}

    def overall_health(self) -> HealthStatus:
        with self._lock:
            if not self._health:
                return HealthStatus.UNKNOWN
            if any(v == HealthStatus.UNHEALTHY for v in self._health.values()):
                return HealthStatus.UNHEALTHY
            if any(v == HealthStatus.DEGRADED for v in self._health.values()):
                return HealthStatus.DEGRADED
            if all(v == HealthStatus.HEALTHY for v in self._health.values()):
                return HealthStatus.HEALTHY
            return HealthStatus.UNKNOWN

    def recent(self, limit: int = 100, level: Optional[str] = None, subsystem: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            entries = list(self._entries)
        if level:
            entries = [e for e in entries if e.level == level]
        if subsystem:
            entries = [e for e in entries if e.subsystem == subsystem]
        # newest first
        entries = entries[-limit:]
        return [
            {
                "ts": e.timestamp_monotonic,
                "level": e.level,
                "subsystem": e.subsystem,
                "operation": e.operation,
                "message": e.message,
                "details": e.details,
            }
            for e in entries
        ]

    def counters(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def uptime_s(self) -> float:
        return time.monotonic() - self._started

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            n = len(self._entries)
            counters = dict(self._counters)
            health = {k: v.value for k, v in self._health.items()}
        return {
            "uptime_s": self.uptime_s(),
            "entries": n,
            "counters": counters,
            "health": health,
            "overall": self.overall_health().value,
        }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._counters.clear()


__all__ = ["HealthStatus", "DiagnosticsEntry", "DiagnosticsCollector"]
