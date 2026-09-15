"""Adapter layer — one adapter per missing ASTRA dependency.

Each adapter implements the Protocol in integration.py. If the real
module is present, use a direct pass-through adapter. If absent, use
the documented fallback (which raises GalacticDependencyError on use).

NEVER silently substitute a fallback for a real dependency.
"""
from __future__ import annotations

from typing import Any

from .errors import GalacticDependencyError


class _MissingDependency:
    """Base class for adapters that wrap a missing ASTRA module."""
    _module_name: str = "unknown"

    def __getattr__(self, name: str):
        raise GalacticDependencyError(
            f"dependency '{self._module_name}' is not available in this repository; "
            f"cannot call '{name}'"
        )


class MissingCosmology(_MissingDependency):
    _module_name = "universe_evolution"


class MissingCoordinates(_MissingDependency):
    _module_name = "coordinates"


class MissingNBody(_MissingDependency):
    _module_name = "nbody"


class MissingObservation(_MissingDependency):
    _module_name = "observation"


class MissingMeasurement(_MissingDependency):
    _module_name = "measurement"


class MissingIngestion(_MissingDependency):
    _module_name = "ingestion"


class MissingBlackHole(_MissingDependency):
    _module_name = "blackhole"
