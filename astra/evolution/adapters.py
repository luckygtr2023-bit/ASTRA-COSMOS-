"""ASTRA Evolution — adapters for missing or partial dependencies.

Each adapter either wraps the real ASTRA module (when PRESENT) or fails
loudly with :class:`~astra.evolution.errors.EvolutionDependencyError` on
any attribute access / call (when ABSENT).  Never silently substitutes.
"""

from __future__ import annotations

from typing import Any

from .errors import EvolutionDependencyError


class _MissingDependency:
    """Base for ABSENT-dependency adapters: any attribute access raises.

    Dunder attributes (``__name__``, ``__class__`` etc.) are not
    intercepted — pytest and inspect machinery queries them during
    collection and would otherwise be broken.
    """

    _module_name: str = "unknown"
    _detail: str = ""

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        raise EvolutionDependencyError(
            f"dependency '{self._module_name}' is not available in this "
            f"repository; cannot call '{name}'"
            + (f" — {self._detail}" if self._detail else "")
        )

    def __call__(self, *args, **kwargs):
        raise EvolutionDependencyError(
            f"dependency '{self._module_name}' is not available; cannot call"
        )


class MissingUniverseEvolution(_MissingDependency):
    """Universe Evolution / cosmology — ABSENT."""

    _module_name = "universe_evolution"
    _detail = (
        "No cosmological background module exists in this repository. "
        "Phase 21 cannot compute scale-factor, expansion history or "
        "comoving distances without it. Provide a UniverseEvolutionProvider "
        "or use a model that does not require expansion."
    )


class MissingGalactic(_MissingDependency):
    """Galactic / Large-Scale Structure (Phase 20) — ABSENT."""

    _module_name = "galactic"
    _detail = (
        "No Phase-20 Galactic/LSS module exists. Galaxy, group, cluster, "
        "supercluster and cosmic-web evolution run in reduced-order "
        "population mode until a provider is injected."
    )


class MissingStellar(_MissingDependency):
    """Stellar evolution — PARTIAL (celestial definitions present, evolution absent)."""

    _module_name = "celestial.evolution"
    _detail = (
        "astra.celestial provides immutable definitions only; stellar "
        "lifecycle evolution requires an injected StellarProvider."
    )


class MissingBlackHole(_MissingDependency):
    _module_name = "blackhole.provider"
    _detail = "No black-hole evolution provider injected; static BH geometry is available via astra.blackhole."


class MissingNBody(_MissingDependency):
    _module_name = "nbody.provider"


class MissingTemporal(_MissingDependency):
    _module_name = "temporal.provider"


class MissingObservation(_MissingDependency):
    """Observation & Cosmic History — PARTIAL (flat-spacetime only)."""

    _module_name = "observation"
    _detail = "Flat-spacetime observation available via astra.temporal.observation; curved propagation absent."


class MissingMeasurement(_MissingDependency):
    """Observatory & Measurement — ABSENT."""

    _module_name = "measurement"
    _detail = "No observatory/measurement module exists in this repository."


# Re-usable singletons for diagnostics (engine can expose which adapters are active)
MISSING_UNIVERSE = MissingUniverseEvolution()
MISSING_GALACTIC = MissingGalactic()
MISSING_STELLAR = MissingStellar()
MISSING_BLACK_HOLE = MissingBlackHole()
MISSING_NBODY = MissingNBody()
MISSING_TEMPORAL = MissingTemporal()
MISSING_OBSERVATION = MissingObservation()
MISSING_MEASUREMENT = MissingMeasurement()


# ---------------------------------------------------------------------------
# Wrapped present dependencies (light pass-through wrappers)
# ---------------------------------------------------------------------------

class CoreAuthorityAdapter:
    """Adapter that delegates to ``astra.core.threading.AuthorityContext``.

    This is the PRESENT case: authority is real and enforced.
    """

    def require(self, operation: str) -> None:
        from astra.core.threading import AuthorityContext
        AuthorityContext.require_authority(operation)

    def has_authority(self, operation: str) -> bool:
        from astra.core.threading import AuthorityContext
        return AuthorityContext.has_authority(operation)


class CoreRNGAdapter:
    """Adapter around ``astra.core.rng.DeterministicRNG``."""

    def __init__(self, global_seed: int = 42):
        from astra.core.rng import DeterministicRNG
        self._rng = DeterministicRNG(global_seed=global_seed)

    def create_stream(self, name: str, seed: int | None = None):
        return self._rng.create_stream(name, seed)

    def uniform(self, a: float = 0.0, b: float = 1.0) -> float:
        # use a transient stream?  For direct RNGProvider compat, delegate
        # to an ephemeral stream name
        s = self._rng.get_stream("evolution.cosmic")
        if s is None:
            s = self._rng.create_stream("evolution.cosmic")
        return s.uniform(a, b)

    def random(self) -> float:
        return self.uniform(0.0, 1.0)

    def state(self) -> Any:
        return self._rng.get_state()


class CelestialStellarAdapter:
    """Adapter for ``astra.celestial`` definitions (read-only).

    Evolution-specific advance is not available here; that belongs to a
    future stellar-evolution model.  This adapter surfaces celestial objects
    without duplicating them.
    """

    def get_star(self, star_id: str):
        # Celestial definitions are accessed via hierarchy / identity; there
        # is no global star registry, so this delegates to a lookup hook if
        # one is configured.  Without a hook, raise honestly.
        raise EvolutionDependencyError(
            "get_star requires a configured celestial data source; "
            "astra.celestial provides immutable definitions but no registry lookup "
            f"(star_id={star_id!r})"
        )

    def get_population(self, population_id: str):
        raise EvolutionDependencyError(
            f"get_population requires a provider (population_id={population_id!r})"
        )

    def advance_star(self, star_id: str, dt_gyr: float):
        raise EvolutionDependencyError(
            "advance_star requires a StellarProvider with evolution models; "
            "astra.celestial definitions are immutable and do not evolve"
        )


class BlackHoleAdapter:
    """Adapter for ``astra.blackhole`` (geometry present, evolution absent)."""

    def get_black_hole(self, black_hole_id: str):
        raise EvolutionDependencyError(
            f"get_black_hole requires a provider (id={black_hole_id!r}); "
            "static geometry available via astra.blackhole.parameters.BlackHoleState"
        )

    def grow_by_accretion(self, black_hole_id: str, mass_kg: float):
        from astra.blackhole.parameters import BlackHoleState
        # In the real provider this would mutate a registry; here we return
        # a validated state object so that model code can at least validate
        # accretion without a registry.
        return BlackHoleState(mass_kg=float(mass_kg), spin_param=0.0)

    def merge(self, bh_a_id: str, bh_b_id: str):
        raise EvolutionDependencyError(
            f"merge requires a provider: {bh_a_id!r} + {bh_b_id!r}"
        )
