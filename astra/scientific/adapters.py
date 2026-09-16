"""ASTRA Scientific — adapters for missing dependencies (§3.17, §1.4).

Each missing adapter raises ScientificError on attribute access; dunder
attributes are not intercepted so pytest collection works.
"""

from __future__ import annotations

from .errors import ScientificError


class _Missing:
    _name = "unknown"
    _detail = ""

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        raise ScientificError(
            f"dependency '{self._name}' unavailable; cannot access '{name}'"
            + (f" — {self._detail}" if self._detail else "")
        )

    def __call__(self, *args, **kwargs):
        raise ScientificError(f"dependency '{self._name}' unavailable; cannot call")


class MissingUnits(_Missing):
    _name = "mathematics.units"
    _detail = "No unit infrastructure found; validation via UnitProvider Protocol required."


class MissingObservation(_Missing):
    _name = "observation"
    _detail = "No observation layer available; use Temporal observation where present."


class MissingIngestion(_Missing):
    _name = "ingestion"
    _detail = "No ingestion pipeline available."


class MissingPhysics(_Missing):
    _name = "physics"


class MissingNBody(_Missing):
    _name = "nbody"


class MissingUniverse(_Missing):
    _name = "universe_evolution"


# Singletons for diagnostics
MISSING_UNITS = MissingUnits()
MISSING_OBS = MissingObservation()
MISSING_INGEST = MissingIngestion()
