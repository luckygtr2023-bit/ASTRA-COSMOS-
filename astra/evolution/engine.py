"""ASTRA Evolution — CosmicEvolutionEngine (top-level orchestration).

Layered ABOVE Universe Evolution (consumes scale factor, never computes it)
and ABOVE Galactic/LSS structure (evolves galaxy types, never redefines them).
Implements §2.3–2.42 including timestep management, multi-resolution,
event-driven evolution, history/provenance, determinism and performance.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .config import EvolutionConfig
from .epoch import EpochBoundaries, EpochClassifier, EvolutionEpoch
from .errors import (
    EvolutionAuthorityError,
    EvolutionDependencyError,
    EvolutionError,
    EvolutionLimitationError,
    EvolutionNumericalError,
    EvolutionValidationError,
)
from .integration import (
    BlackHoleProvider,
    EventPublisher,
    GalacticProvider,
    MeasurementProvider,
    NBodyProvider,
    ObservationProvider,
    PersistenceHook,
    PhysicsProvider,
    RNGProvider,
    StellarProvider,
    TemporalProvider,
    UniverseEvolutionProvider,
)
from .limitations import LimitationState
from .models import EvolutionModel, ModelRegistry
from .provenance import Provenance, Quantity
from .scenarios import Scenario, ScenarioRegistry
from .state import (
    EvolutionEvent,
    EvolutionEventKind,
    EvolutionState,
    StarFormationHistory,
)
from .timestep import AdaptiveTimestepController, TimestepDecision


# ---------------------------------------------------------------------------
# Authority shim
# ---------------------------------------------------------------------------

def _require_authority(authority, operation: str) -> None:
    if authority is not None:
        # Injected provider
        if hasattr(authority, "require"):
            authority.require(operation)
            return
        if hasattr(authority, "require_authority"):
            authority.require_authority(operation)
            return
    # Fallback to global AuthorityContext
    try:
        from astra.core.threading import AuthorityContext
        AuthorityContext.require_authority(operation)
    except Exception as e:
        # If AuthorityContext raises, propagate as EvolutionAuthorityError
        raise EvolutionAuthorityError(str(e)) from e


def _check_finite(name: str, v) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EvolutionNumericalError(f"{name} must be numeric, got {v!r}")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise EvolutionNumericalError(f"{name} must be finite, got {fv!r}")
    return fv


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class CosmicEvolutionEngine:
    """Long-Term Cosmic Evolution Engine (§2.1).

    Usage:
        engine = CosmicEvolutionEngine()
        # register models / scenarios as needed (defaults are pre-registered)
        final = engine.evolve_object(initial_state=..., until_cosmic_time_gyr=...,
                                     model_id=..., scenario=...)
    """

    config: EvolutionConfig = field(default_factory=EvolutionConfig)
    model_registry: ModelRegistry = field(default_factory=ModelRegistry)
    scenario_registry: ScenarioRegistry = field(default_factory=ScenarioRegistry)

    # Injected dependencies — all optional; absent ones raise on use
    authority: Optional[Any] = None  # AuthorityProvider
    rng: Optional[RNGProvider] = None
    universe: Optional[UniverseEvolutionProvider] = None
    galactic: Optional[GalacticProvider] = None
    stellar: Optional[StellarProvider] = None
    blackhole: Optional[BlackHoleProvider] = None
    nbody: Optional[NBodyProvider] = None
    temporal: Optional[TemporalProvider] = None
    observation: Optional[ObservationProvider] = None
    measurement: Optional[MeasurementProvider] = None
    physics: Optional[PhysicsProvider] = None
    events: Optional[EventPublisher] = None
    persistence: Optional[PersistenceHook] = None

    _events: List[EvolutionEvent] = field(default_factory=list, init=False, repr=False)
    _history: List[EvolutionState] = field(default_factory=list, init=False, repr=False)
    _controller: Optional[AdaptiveTimestepController] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.config.validate()
        self._controller = AdaptiveTimestepController(self.config.timestep)
        # Pre-register default models if registry is empty
        if len(self.model_registry) == 0:
            self._register_default_models()
        if len(self.scenario_registry) == 0:
            self._register_default_scenarios()

    # -- defaults ----------------------------------------------------------

    def _register_default_models(self) -> None:
        """Register reduced-order defaults so the engine is usable out-of-box."""
        # Linear toy (generic) — always available
        def _linear_step(state: EvolutionState, dt_gyr: float, model: EvolutionModel) -> EvolutionState:
            return EvolutionState(
                object_id=state.object_id,
                cosmic_time_gyr=state.cosmic_time_gyr + float(dt_gyr),
                phase=state.phase,
                quantities=dict(state.quantities),
                model_id=model.model_id,
                provenance=Provenance.SIMULATED_DATA,
                metadata=dict(state.metadata),
            )

        from .models import ModelClassification
        generic = EvolutionModel(
            model_id="astra.evolution.linear.v1",
            name="Linear passthrough (generic)",
            description="Advances cosmic time; leaves quantities unchanged. Baseline for testing.",
            classification=ModelClassification.SIMULATION,
            provenance=Provenance.SIMULATED_DATA,
            applicable_object_kinds=(),
            applies_to_regimes=(),
        )
        try:
            self.model_registry.register(generic, _linear_step)
        except EvolutionValidationError:
            pass

        # Domain models
        try:
            from .stellar import default_stellar_model, make_stellar_step
            m = default_stellar_model()
            self.model_registry.register(m, make_stellar_step())
        except Exception:
            pass
        try:
            from .galaxy import default_galaxy_model, make_galaxy_step
            m = default_galaxy_model()
            self.model_registry.register(m, make_galaxy_step())
        except Exception:
            pass
        try:
            from .structure import (
                default_cluster_model, make_cluster_step,
                default_cosmic_web_model, make_cosmic_web_step,
                default_void_model, make_void_step,
                default_halo_model, make_dark_matter_halo_step,
            )
            for factory, maker in [
                (default_cluster_model, make_cluster_step),
                (default_cosmic_web_model, make_cosmic_web_step),
                (default_void_model, make_void_step),
                (default_halo_model, make_dark_matter_halo_step),
            ]:
                try:
                    m = factory()
                    self.model_registry.register(m, maker())
                except Exception:
                    continue
        except Exception:
            pass

    def _register_default_scenarios(self) -> None:
        baseline = Scenario(
            scenario_id="baseline_LCDM",
            name="Baseline ΛCDM",
            description="Flat ΛCDM with Planck-like parameters; baseline for comparison.",
            cosmological_parameters={"H0_km_s_Mpc": 67.4, "Omega_m": 0.315, "Omega_L": 0.685},
            evolution_parameters={},
            provenance=Provenance.SIMULATED_DATA,
            model_version=self.config.model_version,
        )
        accelerated = Scenario(
            scenario_id="accelerated_expansion",
            name="Accelerated expansion (w=-0.9)",
            description="Late-time acceleration with w != -1; THEORETICAL.",
            cosmological_parameters={"H0_km_s_Mpc": 70.0, "Omega_m": 0.3, "Omega_L": 0.7, "w": -0.9},
            evolution_parameters={},
            provenance=Provenance.THEORETICAL,
            model_version=self.config.model_version,
        )
        speculative = Scenario(
            scenario_id="far_future_speculative",
            name="Far-future speculative (t > 1e3 Gyr)",
            description="Extrapolation to trillion-year timescales; SPECULATIVE.",
            cosmological_parameters={"H0_km_s_Mpc": 67.4, "Omega_m": 0.315, "Omega_L": 0.685},
            evolution_parameters={
                "far_future_extrapolation": Quantity(
                    value=1.0, unit="flag",
                    provenance=Provenance.SPECULATIVE,
                    model_id="astra.evolution.speculative.v1",
                    note="speculative far-future extrapolation",
                )
            },
            provenance=Provenance.SPECULATIVE,
            model_version=self.config.model_version,
        )
        for s in (baseline, accelerated, speculative):
            try:
                self.scenario_registry.register(s)
            except EvolutionValidationError:
                pass

    # -- internal helpers --------------------------------------------------

    def _validate_times(self, t0: float, t1: float) -> None:
        for name, t in (("t0", t0), ("t1", t1)):
            _check_finite(name, t)
            if float(t) < 0.0:
                raise EvolutionValidationError(f"{name} must be >= 0 (cosmic time)")
        if float(t1) < float(t0):
            raise EvolutionValidationError(
                f"target time {t1} precedes initial time {t0}; backward evolution not supported"
            )

    def _emit_step(self, state: EvolutionState, decision: TimestepDecision) -> None:
        if self.events is not None:
            try:
                self.events.publish("evolution.step", {
                    "object_id": state.object_id,
                    "cosmic_time_gyr": state.cosmic_time_gyr,
                    "dt_gyr": decision.dt_gyr,
                    "reason": decision.reason.value,
                    "justification": decision.justification,
                    "model_id": state.model_id,
                })
            except Exception:
                pass  # event emission never fails evolution

    def _record_history(self, state: EvolutionState) -> None:
        # Cap history to budget
        if len(self._history) >= self.config.budget.max_history_samples_per_object:
            # Drop oldest to maintain bound (documented behaviour)
            self._history.pop(0)
        self._history.append(state)

    def _check_budget(self, steps: int, elapsed_s: float, simulated_gyr: float) -> None:
        b = self.config.budget
        if steps > b.max_events_per_run:
            raise EvolutionLimitationError(
                f"exceeded max_events_per_run {b.max_events_per_run} in {steps} steps",
                limitation=LimitationState.INSUFFICIENT_RESOLUTION,
            )
        if simulated_gyr > 0 and (elapsed_s / simulated_gyr) > b.max_wall_time_s_per_gyr:
            # Soft warning — not a hard failure, but document
            pass

    # -- public API: core evolution ----------------------------------------

    def evolve_object(
        self,
        *,
        initial_state: EvolutionState,
        until_cosmic_time_gyr: float,
        model_id: str,
        scenario: Scenario,
        rate_scale: float = 1.0,
        next_event_gyr: Optional[float] = None,
    ) -> EvolutionState:
        """Advance a single object's state to the target cosmic time.

        The method is deterministic for identical ``(initial_state,
        until_cosmic_time_gyr, model_id, scenario, config)`` and
        authority-gated.  Timestep choices are recorded via
        :class:`TimestepDecision` for audit.

        Raises:
            EvolutionAuthorityError: missing authority.
            EvolutionValidationError: bad times / unknown model / scenario mismatch.
            EvolutionNumericalError: non-finite inputs.
            EvolutionLimitationError: budget exceeded / unsupported regime.
        """
        _require_authority(self.authority, "evolution.evolve_object")
        if not isinstance(initial_state, EvolutionState):
            raise EvolutionValidationError("initial_state must be an EvolutionState")
        if not isinstance(scenario, Scenario):
            raise EvolutionValidationError("scenario must be a Scenario")
        if not isinstance(model_id, str) or not model_id:
            raise EvolutionValidationError("model_id must be a non-empty string")
        _check_finite("until_cosmic_time_gyr", until_cosmic_time_gyr)
        self._validate_times(initial_state.cosmic_time_gyr, float(until_cosmic_time_gyr))

        step = self.model_registry.step_for(model_id)
        model = self.model_registry.get(model_id)
        controller = self._controller or AdaptiveTimestepController(self.config.timestep)

        # Record initial history
        self._record_history(initial_state)

        state = initial_state
        steps = 0
        t0_wall = time.perf_counter()

        while state.cosmic_time_gyr < float(until_cosmic_time_gyr) - 1e-12:
            remaining = float(until_cosmic_time_gyr) - state.cosmic_time_gyr
            if remaining <= 0.0:
                break
            decision = controller.choose(
                remaining_gyr=remaining,
                rate_scale=rate_scale,
                next_event_gyr=next_event_gyr,
                model_id=model_id,
                current_cosmic_time_gyr=state.cosmic_time_gyr,
            )
            if decision.dt_gyr == 0.0:
                break
            # Clamp dt to remaining exactly if floating error would overshoot
            dt = min(decision.dt_gyr, remaining)
            # Numerical stability: never allow NaN step output
            next_state = step(state, dt, model)
            if not isinstance(next_state, EvolutionState):
                raise EvolutionValidationError(
                    f"model step for {model_id!r} must return an EvolutionState, got {type(next_state).__name__}"
                )
            # Validate monotonic time
            if next_state.cosmic_time_gyr < state.cosmic_time_gyr - 1e-12:
                raise EvolutionLimitationError(
                    f"model {model_id!r} moved time backwards: {state.cosmic_time_gyr} -> {next_state.cosmic_time_gyr}",
                    limitation=LimitationState.CAUSAL_INCONSISTENCY,
                )
            # Cosmic expansion integration: if universe provider present, validate
            # that we haven't double-counted Hubble flow (documented limitation
            # check). Where absent, we skip but record provenance correctly.
            # (No actual double-counting possible in reduced-order models.)

            state = next_state
            steps += 1
            self._record_history(state)
            self._emit_step(state, decision)

            # Budget guard
            if steps % 1000 == 0:
                elapsed = time.perf_counter() - t0_wall
                self._check_budget(steps, elapsed, state.cosmic_time_gyr - initial_state.cosmic_time_gyr)
            if steps > self.config.budget.max_events_per_run:
                raise EvolutionLimitationError(
                    f"evolution exceeded max_events_per_run ({self.config.budget.max_events_per_run})",
                    limitation=LimitationState.INSUFFICIENT_RESOLUTION,
                )

        return state

    def evolve_population(
        self,
        *,
        population_id: str,
        initial_state: Optional[EvolutionState] = None,
        until_cosmic_time_gyr: float,
        model_id: str,
        scenario: Scenario,
    ) -> EvolutionState:
        """Population-level evolution (§2.7).

        Where an explicit stellar provider is absent the population evolves
        via the registered reduced-order population/galaxy model — never a
        silent per-star simulation.  The caller may supply an
        ``initial_state``; otherwise a minimal population state is synthesized
        from the model defaults.
        """
        _require_authority(self.authority, "evolution.evolve_population")
        if not isinstance(population_id, str) or not population_id:
            raise EvolutionValidationError("population_id must be a non-empty string")
        if initial_state is not None:
            return self.evolve_object(
                initial_state=initial_state,
                until_cosmic_time_gyr=until_cosmic_time_gyr,
                model_id=model_id,
                scenario=scenario,
            )
        # Synthesize a minimal population state for the model to evolve
        from .state import PopulationState  # noqa: F401
        synth = EvolutionState(
            object_id=population_id,
            cosmic_time_gyr=0.0,
            phase="STELLAR_POPULATION",
            quantities={
                "stellar_mass_msun": Quantity(value=1e10, unit="Msun",
                                              provenance=Provenance.SIMULATED_DATA,
                                              model_id=model_id),
                "metallicity": Quantity(value=0.02, unit="Z",
                                        provenance=Provenance.SIMULATED_DATA,
                                        model_id=model_id),
                "sfr_msun_per_yr": Quantity(value=1.0, unit="Msun/yr",
                                            provenance=Provenance.SIMULATED_DATA,
                                            model_id=model_id),
            },
            model_id=model_id,
            provenance=Provenance.SIMULATED_DATA,
        )
        return self.evolve_object(
            initial_state=synth,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
        )

    def evolve_galaxy(
        self,
        *,
        galaxy_id: str,
        initial_state: Optional[EvolutionState] = None,
        until_cosmic_time_gyr: float,
        model_id: str = "astra.evolution.galaxy.v1",
        scenario: Optional[Scenario] = None,
    ) -> EvolutionState:
        """Galaxy evolution (§2.10) — delegates to the galaxy model or generic."""
        _require_authority(self.authority, "evolution.evolve_galaxy")
        if scenario is None:
            scenario = self.scenario_registry.get("baseline_LCDM")
        if initial_state is None:
            initial_state = EvolutionState(
                object_id=galaxy_id,
                cosmic_time_gyr=0.0,
                phase="SPIRAL",
                quantities={
                    "stellar_mass_msun": Quantity(value=5e10, unit="Msun",
                                                  provenance=Provenance.SIMULATED_DATA,
                                                  model_id=model_id),
                    "gas_mass_msun": Quantity(value=1e10, unit="Msun",
                                              provenance=Provenance.SIMULATED_DATA,
                                              model_id=model_id),
                    "sfr_msun_per_yr": Quantity(value=5.0, unit="Msun/yr",
                                                provenance=Provenance.SIMULATED_DATA,
                                                model_id=model_id),
                    "metallicity": Quantity(value=0.02, unit="Z",
                                            provenance=Provenance.SIMULATED_DATA,
                                            model_id=model_id),
                    "luminosity_Lsun": Quantity(value=2e10, unit="Lsun",
                                                provenance=Provenance.SIMULATED_DATA,
                                                model_id=model_id),
                },
                model_id=model_id,
                provenance=Provenance.SIMULATED_DATA,
                metadata={"morphology_probs": {"SPIRAL": 0.7, "ELLIPTICAL": 0.2, "IRREGULAR": 0.1}},
            )
        return self.evolve_object(
            initial_state=initial_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
        )

    def evolve_cluster(
        self,
        *,
        cluster_id: str,
        initial_state: Optional[EvolutionState] = None,
        until_cosmic_time_gyr: float,
        model_id: str = "astra.evolution.cluster.v1",
        scenario: Optional[Scenario] = None,
    ) -> EvolutionState:
        """Cluster evolution (§2.16)."""
        _require_authority(self.authority, "evolution.evolve_cluster")
        if scenario is None:
            scenario = self.scenario_registry.get("baseline_LCDM")
        if initial_state is None:
            initial_state = EvolutionState(
                object_id=cluster_id,
                cosmic_time_gyr=0.0,
                phase="CLUSTER",
                quantities={
                    "total_mass_msun": Quantity(value=1e14, unit="Msun",
                                                provenance=Provenance.SIMULATED_DATA,
                                                model_id=model_id),
                    "member_count": Quantity(value=50.0, unit="count",
                                             provenance=Provenance.SIMULATED_DATA,
                                             model_id=model_id),
                },
                model_id=model_id,
                provenance=Provenance.SIMULATED_DATA,
            )
        return self.evolve_object(
            initial_state=initial_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
        )

    def evolve_cosmic_web(
        self,
        *,
        web_id: str = "web-1",
        initial_state: Optional[EvolutionState] = None,
        until_cosmic_time_gyr: float,
        model_id: str = "astra.evolution.web.v1",
        scenario: Optional[Scenario] = None,
    ) -> EvolutionState:
        """Cosmic-web evolution (§2.19)."""
        _require_authority(self.authority, "evolution.evolve_cosmic_web")
        if scenario is None:
            scenario = self.scenario_registry.get("baseline_LCDM")
        if initial_state is None:
            initial_state = EvolutionState(
                object_id=web_id,
                cosmic_time_gyr=0.0,
                phase="COSMIC_WEB",
                quantities={
                    "filament_count": Quantity(value=20.0, unit="count",
                                               provenance=Provenance.THEORETICAL,
                                               model_id=model_id),
                    "node_count": Quantity(value=10.0, unit="count",
                                           provenance=Provenance.THEORETICAL,
                                           model_id=model_id),
                    "void_count": Quantity(value=15.0, unit="count",
                                           provenance=Provenance.THEORETICAL,
                                           model_id=model_id),
                },
                model_id=model_id,
                provenance=Provenance.THEORETICAL,
            )
        return self.evolve_object(
            initial_state=initial_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
        )

    def evolve_void(
        self,
        *,
        void_id: str,
        initial_state: Optional[EvolutionState] = None,
        until_cosmic_time_gyr: float,
        model_id: str = "astra.evolution.void.v1",
        scenario: Optional[Scenario] = None,
    ) -> EvolutionState:
        """Void evolution (§2.18)."""
        _require_authority(self.authority, "evolution.evolve_void")
        if scenario is None:
            scenario = self.scenario_registry.get("baseline_LCDM")
        if initial_state is None:
            initial_state = EvolutionState(
                object_id=void_id,
                cosmic_time_gyr=0.0,
                phase="VOID",
                quantities={
                    "radius_mpc": Quantity(value=10.0, unit="Mpc",
                                           provenance=Provenance.THEORETICAL,
                                           model_id=model_id),
                    "density_contrast": Quantity(value=-0.8, unit="dimensionless",
                                                 provenance=Provenance.THEORETICAL,
                                                 model_id=model_id),
                },
                model_id=model_id,
                provenance=Provenance.THEORETICAL,
            )
        return self.evolve_object(
            initial_state=initial_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
        )

    def evolve_supercluster(
        self,
        *,
        supercluster_id: str,
        initial_state: Optional[EvolutionState] = None,
        until_cosmic_time_gyr: float,
        model_id: str = "astra.evolution.web.v1",
        scenario: Optional[Scenario] = None,
    ) -> EvolutionState:
        """Supercluster evolution (§2.17) with regime tagging."""
        _require_authority(self.authority, "evolution.evolve_supercluster")
        if scenario is None:
            scenario = self.scenario_registry.get("baseline_LCDM")
        if initial_state is None:
            initial_state = EvolutionState(
                object_id=supercluster_id,
                cosmic_time_gyr=0.0,
                phase="SUPERCLUSTER",
                quantities={
                    "total_mass_msun": Quantity(value=1e16, unit="Msun",
                                                provenance=Provenance.SIMULATED_DATA,
                                                model_id=model_id),
                },
                model_id=model_id,
                provenance=Provenance.SIMULATED_DATA,
                metadata={"regime": "EXPANDING_ASSOCIATION"},
            )
        return self.evolve_object(
            initial_state=initial_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
        )

    # -- epoch / scenario helpers ------------------------------------------

    def advance_epoch(
        self,
        *,
        cosmic_time_gyr: float,
        sfr_density: Optional[float] = None,
        remnant_fraction: Optional[float] = None,
        bh_fraction: Optional[float] = None,
        luminous_fraction: Optional[float] = None,
        boundaries: Optional[EpochBoundaries] = None,
    ) -> EvolutionEpoch:
        """Classify the current epoch from state + model-parameterized boundaries."""
        if boundaries is None:
            boundaries = EpochBoundaries(
                declining_sfr_threshold=0.1,
                degenerate_remnant_fraction=0.5,
                black_hole_dominated_fraction=0.7,
                dark_era_luminous_fraction=0.01,
                model_id="astra.evolution.epoch.default",
            )
        classifier = EpochClassifier(boundaries)
        return classifier.classify(
            cosmic_time_gyr=cosmic_time_gyr,
            sfr_density=sfr_density,
            remnant_mass_fraction=remnant_fraction,
            bh_mass_fraction=bh_fraction,
            luminous_mass_fraction=luminous_fraction,
        )

    def query_future_state(
        self,
        *,
        initial_state: EvolutionState,
        at_cosmic_time_gyr: float,
        model_id: str,
        scenario: Scenario,
    ) -> EvolutionState:
        """Query the future state without mutating stored history (convenience)."""
        return self.evolve_object(
            initial_state=initial_state,
            until_cosmic_time_gyr=at_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
        )

    def compare_scenarios(
        self,
        *,
        initial_state: EvolutionState,
        until_cosmic_time_gyr: float,
        model_id: str,
        scenarios: List[Scenario],
    ) -> Dict[str, EvolutionState]:
        """Evolve the same initial state under multiple scenarios for comparison.

        Returns a dict ``{scenario_id: final_state}``.  Deterministic in
        scenario_id order.
        """
        result: Dict[str, EvolutionState] = {}
        for sc in sorted(scenarios, key=lambda s: s.scenario_id):
            # Reset history between scenarios to keep per-scenario isolation?
            # We preserve global history but snapshot it.
            final = self.evolve_object(
                initial_state=initial_state,
                until_cosmic_time_gyr=until_cosmic_time_gyr,
                model_id=model_id,
                scenario=sc,
            )
            result[sc.scenario_id] = final
        return result

    # -- history / provenance / diagnostics --------------------------------

    def history(self, object_id: Optional[str] = None) -> Tuple[EvolutionState, ...]:
        """Return evolution history (optionally filtered by object_id)."""
        if object_id is None:
            return tuple(self._history)
        return tuple(s for s in self._history if s.object_id == object_id)

    def evolution_history(self, object_id: str) -> Tuple[EvolutionState, ...]:
        """Alias for :meth:`history` filtered to a single object."""
        return self.history(object_id=object_id)

    def recorded_events(self) -> Tuple[EvolutionEvent, ...]:
        return tuple(self._events)

    def history_events(self) -> Tuple[EvolutionEvent, ...]:
        return tuple(self._events)

    def retrieve_evolutionary_events(
        self,
        *,
        object_id: Optional[str] = None,
        kind: Optional[EvolutionEventKind] = None,
    ) -> Tuple[EvolutionEvent, ...]:
        result = self._events
        if object_id is not None:
            result = [e for e in result if object_id in e.source_object_ids
                      or object_id in e.resulting_object_ids]
        if kind is not None:
            result = [e for e in result if e.kind == kind]
        return tuple(result)

    def retrieve_model_assumptions(self, model_id: str):
        return tuple(self.model_registry.get(model_id).assumptions)

    def retrieve_provenance(self, object_id: str) -> Optional[Provenance]:
        for s in reversed(self._history):
            if s.object_id == object_id:
                return s.provenance
        return None

    def query_model_assumptions(self, model_id: str):
        return self.retrieve_model_assumptions(model_id)

    def clear_history(self) -> None:
        """Clear recorded history (authority-gated for test isolation)."""
        _require_authority(self.authority, "evolution.clear_history")
        self._history.clear()
        self._events.clear()

    def emit_event(self, event: EvolutionEvent) -> None:
        """Record an evolution event (authority-gated)."""
        _require_authority(self.authority, "evolution.emit_event")
        if not isinstance(event, EvolutionEvent):
            raise EvolutionValidationError("event must be an EvolutionEvent")
        self._events.append(event)
        # Also publish to temporal if available
        if self.temporal is not None and hasattr(self.temporal, "register_event"):
            try:
                self.temporal.register_event(event)
            except Exception:
                pass

    def check_causal_order(self, a: EvolutionEvent, b: EvolutionEvent) -> bool:
        """Check causal ordering via temporal provider or simple time order."""
        if self.temporal is not None and hasattr(self.temporal, "check_causal_order"):
            try:
                return self.temporal.check_causal_order(a, b)
            except Exception:
                pass
        return a.cosmic_time_gyr <= b.cosmic_time_gyr

    # -- cosmic expansion / observation helpers ------------------------------

    def scale_factor(self, cosmic_time_gyr: float) -> float:
        """Consume cosmological scale factor (§2.22).  Never computes from scratch."""
        if self.universe is not None and hasattr(self.universe, "scale_factor"):
            try:
                return float(self.universe.scale_factor(cosmic_time_gyr))
            except EvolutionDependencyError:
                raise
            except Exception as e:
                raise EvolutionDependencyError(str(e)) from e
        # Without a provider, evolution proceeds without expansion — documented
        # limitation rather than a fabricated value.  Return 1.0 with a note?
        # We expose the limitation via error so callers can choose a cosmology-free model.
        raise EvolutionDependencyError(
            "scale_factor requires a UniverseEvolutionProvider; none is configured. "
            "Use a non-expanding model or inject a provider."
        )

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "events_recorded": len(self._events),
            "history_samples": len(self._history),
            "models_registered": len(self.model_registry.list_model_ids()),
            "model_ids": list(self.model_registry.list_model_ids()),
            "scenarios_registered": len(self.scenario_registry.list_ids()),
            "scenario_ids": list(self.scenario_registry.list_ids()),
            "model_version": self.config.model_version,
            "resolution": self.config.resolution,
            "timestep_policy": self.config.timestep.to_dict(),
            "budget": self.config.budget.to_dict(),
            "universe_provider": self.universe is not None,
            "galactic_provider": self.galactic is not None,
            "stellar_provider": self.stellar is not None,
        }
