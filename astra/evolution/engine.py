"""ASTRA COSMOS — Phase 21: CosmicEvolutionEngine.

Top-level orchestration of the Long-Term Cosmic Evolution Engine. The
engine sits ABOVE Universe Evolution (which owns the cosmological
background — ABSENT from this repository, consumed only through the
injected ``UniverseEvolutionProvider``) and above Galactic / Large-Scale
Structure (ABSENT — structure states live here as explicitly tagged
evolution-layer containers until a Phase 20 binds in). It NEVER computes
the scale factor, NEVER re-derives expansion, and introduces no new
coordinate, time, N-body, or observation authority.

What the engine DOES
--------------------
- advances EvolutionStates through registered models with explicit,
  justified adaptive timesteps (TimestepDecision records);
- detects lifecycle/activity/structure transitions and records them as
  causally chained EvolutionEvents (append-only ledger, causal validation);
- classifies cosmic epochs from state + configured boundaries;
- projects future states (explicit ProjectionClass, never presented as
  observation), compares scenarios, aggregates cluster members, advances
  whole cosmic epochs;
- gates EVERY mutation through the injected AuthorityProvider
  (fail-closed: no provider -> refusal);
- enforces the configured PerformanceBudget and resolution ladder.

What the engine DOES NOT DO
---------------------------
- no cosmological background mathematics (Universe Evolution's role);
- no stellar/galaxy INTERNAL physics beyond the registered reduced-order
  models (geometry stays in astra.blackhole, kinematics in motion/nbody,
  light propagation in astra.temporal.observation);
- no silent substitution, no silent clamping, no fabricated data.

Determinism: no wall-clock reads, no global RNG; the built-in models are
closed-form. Two identical calls produce bit-identical results.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from astra.celestial.provenance import DataProvenance

from .adapters import DictPersistenceHook  # noqa: F401  (re-export convenience)
from .builtins import (
    BuiltinModelParams,
    EXPANSION_INPUT_KEY,
    GALAXY_MODEL_ID,
    CLUSTER_MODEL_ID,
    POPULATION_MODEL_ID,
    STELLAR_MODEL_ID,
    WEB_MODEL_ID,
    register_builtin_models,
)
from .config import EvolutionConfig
from .epoch import (
    EpochClassifier,
    EpochInputs,
    EvolutionEpoch,
    epoch_inputs_from_state,
)
from .errors import (
    EvolutionAuthorityError,
    EvolutionDependencyError,
    EvolutionLimitationError,
    EvolutionNumericalError,
    EvolutionValidationError,
)
from .events import EvolutionEvent, EvolutionEventKind
from .integration import (
    AuthorityProvider,
    BlackHoleProvider,
    EventPublisher,
    GalacticProvider,
    MeasurementProvider,
    NBodyProvider,
    ObservationProvider,
    PersistenceHook,
    RNGProvider,
    StellarProvider,
    TemporalProvider,
    UniverseEvolutionProvider,
)
from .ledger import EvolutionLedger
from .limitations import LimitationState
from .models import ModelRegistry
from .models import EvolutionModel
from .provenance import ProjectionClass
from .quantity import Quantity, require_finite_number
from .scenarios import Scenario, ScenarioRegistry
from .state import (
    KIND_CLUSTER,
    KIND_COSMIC_WEB,
    KIND_GALAXY,
    KIND_POPULATION,
    KIND_STAR,
    KIND_STRUCTURE,
    EvolutionState,
    StructureRegime,
    kind_rank,
    resolution_rank,
)
from .timestep import AdaptiveTimestepController, TimestepDecision

# Authority operations (each mutation names exactly what it mutates).
OP_EVOLVE = "evolution.evolve"
OP_PROJECT = "evolution.project"
OP_RECORD_EVENT = "evolution.record_event"
OP_RECORD_MERGER = "evolution.record_merger"
OP_RESTORE = "evolution.restore_ledger"

_PROJECTION_PROVENANCES = (
    DataProvenance.SIMULATED_DATA,
    DataProvenance.THEORETICAL_MODEL,
    DataProvenance.SPECULATIVE_MODEL,
)


@dataclass(frozen=True)
class EvolutionOutcome:
    """Result of one evolution run. Everything the run produced is here;
    the ledger additionally retains it for history queries."""

    initial_state: EvolutionState
    final_state: EvolutionState
    events: Tuple[EvolutionEvent, ...]
    timesteps: Tuple[TimestepDecision, ...]
    epochs: Tuple[Tuple[float, str], ...]
    scenario_id: str
    model_id: str

    @property
    def final_epoch(self) -> str:
        return self.epochs[-1][1] if self.epochs else EvolutionEpoch.UNKNOWN.value


@dataclass(frozen=True)
class ClusterEvolutionOutcome:
    """Result of a cluster run: the cluster outcome plus per-member runs."""

    cluster: EvolutionOutcome
    members: Tuple[Tuple[str, EvolutionOutcome], ...]

    def member_final_state(self, member_id: str) -> EvolutionState:
        for mid, outcome in self.members:
            if mid == member_id:
                return outcome.final_state
        raise EvolutionValidationError(f"member {member_id} not part of this cluster run")


@dataclass(frozen=True)
class EpochAdvanceReport:
    """Result of advancing a set of objects to a common cosmic time."""

    outcomes: Tuple[Tuple[str, EvolutionOutcome], ...]
    ensemble_epoch_before: str
    ensemble_epoch_after: str
    events: Tuple[EvolutionEvent, ...]


@dataclass(frozen=True)
class ScenarioComparison:
    """Side-by-side projection under two scenarios. Both outcomes are
    SIMULATED projections under DIFFERENT ASSUMPTIONS — their differences
    are model deltas, never observational statements."""

    scenario_a_id: str
    scenario_b_id: str
    outcome_a: EvolutionOutcome
    outcome_b: EvolutionOutcome
    quantity_deltas: Tuple[Tuple[str, float, float, float], ...]
    note: str


def _ensemble_epoch_inputs(states: Sequence[EvolutionState]) -> EpochInputs:
    """Aggregate epoch inputs across states (sums of the documented
    mass-bookkeeping keys; fractions recomputed from the sums)."""
    live = gas = remnants = bh = sfr = 0.0
    have_any = False
    have_sfr = False
    for state in states:
        for key in ("live_stellar_mass_msun", "stellar_mass_msun"):
            q = state.quantities.get(key)
            if q is not None:
                live += q.value
                have_any = True
        q = state.quantities.get("gas_mass_msun")
        if q is not None:
            gas += q.value
            have_any = True
        for key in ("remnant_wd_msun", "remnant_ns_msun", "remnant_bh_msun", "remnant_mass_msun"):
            q = state.quantities.get(key)
            if q is not None:
                remnants += q.value
                have_any = True
        q = state.quantities.get("remnant_bh_msun")
        if q is not None:
            bh += q.value
        q = state.quantities.get("sfr_msun_yr")
        if q is not None:
            sfr += q.value
            have_sfr = True
    if not have_any:
        return EpochInputs()
    total = gas + live + remnants
    # SFR absent from every state is NOT SFR zero (honesty rule): only
    # states that actually carry an SFR quantity contribute information.
    if not have_sfr or live <= 0.0:
        sfr_specific = None
    else:
        sfr_specific = (sfr * 1.0e9) / live
    return EpochInputs(
        specific_sfr_per_gyr=sfr_specific,
        remnant_mass_fraction=(remnants / total) if total > 0.0 else None,
        bh_mass_fraction=(bh / total) if total > 0.0 else None,
        luminous_mass_fraction=(live / total) if total > 0.0 else None,
    )


class CosmicEvolutionEngine:
    """Long-term cosmic evolution engine (see module docstring)."""

    def __init__(
        self,
        config: Optional[EvolutionConfig] = None,
        model_registry: Optional[ModelRegistry] = None,
        scenario_registry: Optional[ScenarioRegistry] = None,
        authority: Optional[AuthorityProvider] = None,
        rng: Optional[RNGProvider] = None,
        universe: Optional[UniverseEvolutionProvider] = None,
        galactic: Optional[GalacticProvider] = None,
        stellar: Optional[StellarProvider] = None,
        blackhole: Optional[BlackHoleProvider] = None,
        nbody: Optional[NBodyProvider] = None,
        temporal: Optional[TemporalProvider] = None,
        observation: Optional[ObservationProvider] = None,
        measurement: Optional[MeasurementProvider] = None,
        events: Optional[EventPublisher] = None,
        persistence: Optional[PersistenceHook] = None,
        register_builtins: bool = True,
        builtin_params: Optional[BuiltinModelParams] = None,
    ) -> None:
        self.config = config or EvolutionConfig()
        self.config.validate()
        self.model_registry = model_registry or ModelRegistry()
        self.scenario_registry = scenario_registry or ScenarioRegistry()
        self.authority = authority
        self.rng = rng
        self.universe = universe
        self.galactic = galactic
        self.stellar = stellar
        self.blackhole = blackhole
        self.nbody = nbody
        self.temporal = temporal
        self.observation = observation
        self.measurement = measurement
        self.events = events
        self.persistence = persistence
        if register_builtins and STELLAR_MODEL_ID not in self.model_registry.list_model_ids():
            register_builtin_models(self.model_registry, builtin_params)
        self._ledger = EvolutionLedger()
        self._event_counter = 0
        self._objects_evolved = 0

    # ------------------------------------------------------------ public API
    def evolve_object(
        self,
        *,
        initial_state: EvolutionState,
        until_cosmic_time_gyr: float,
        model_id: str,
        scenario: Scenario,
        scheduled_events: Sequence[EvolutionEvent] = (),
    ) -> EvolutionOutcome:
        """Advance one object's state to the target cosmic time (spec 2.41)."""
        return self._run(
            initial_state=initial_state,
            until=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
            scheduled_events=scheduled_events,
            record=True,
            op=OP_EVOLVE,
        )

    def evolve_population(
        self,
        *,
        population_state: EvolutionState,
        until_cosmic_time_gyr: float,
        scenario: Scenario,
        model_id: str = POPULATION_MODEL_ID,
        scheduled_events: Sequence[EvolutionEvent] = (),
    ) -> EvolutionOutcome:
        """Population-level evolution (spec 2.7)."""
        return self.evolve_object(
            initial_state=population_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
            scheduled_events=scheduled_events,
        )

    def evolve_galaxy(
        self,
        *,
        galaxy_state: EvolutionState,
        until_cosmic_time_gyr: float,
        scenario: Scenario,
        model_id: str = GALAXY_MODEL_ID,
        scheduled_events: Sequence[EvolutionEvent] = (),
    ) -> EvolutionOutcome:
        """Galaxy-level evolution (spec 2.10)."""
        return self.evolve_object(
            initial_state=galaxy_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
            scheduled_events=scheduled_events,
        )

    def evolve_cluster(
        self,
        *,
        cluster_state: EvolutionState,
        member_states: Sequence[EvolutionState],
        until_cosmic_time_gyr: float,
        scenario: Scenario,
        galaxy_model_id: str = GALAXY_MODEL_ID,
        cluster_model_id: str = CLUSTER_MODEL_ID,
        scheduled_events: Sequence[EvolutionEvent] = (),
    ) -> ClusterEvolutionOutcome:
        """Evolve every member galaxy (deterministic id order), then the
        cluster aggregate; member totals are folded into the cluster state
        (spec 2.16). Members must be GALAXY states whose ids are listed in
        the cluster's metadata."""
        listed = set(cluster_state.metadata.get("member_ids", []))
        for member in member_states:
            if member.object_kind != KIND_GALAXY:
                raise EvolutionLimitationError(
                    LimitationState.INCOMPATIBLE_MODEL,
                    f"cluster member {member.object_id} is a {member.object_kind}, "
                    f"expected {KIND_GALAXY}",
                )
            if listed and member.object_id not in listed:
                raise EvolutionValidationError(
                    f"member {member.object_id} is not listed in cluster metadata"
                )
        members = sorted(member_states, key=lambda s: s.object_id)
        member_outcomes: list = []
        for member in members:
            outcome = self.evolve_object(
                initial_state=member,
                until_cosmic_time_gyr=until_cosmic_time_gyr,
                model_id=galaxy_model_id,
                scenario=scenario,
                scheduled_events=scheduled_events,
            )
            member_outcomes.append((member.object_id, outcome))
        cluster_outcome = self.evolve_object(
            initial_state=self._aggregate_cluster(cluster_state, [o.final_state for _, o in member_outcomes]),
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=cluster_model_id,
            scenario=scenario,
            scheduled_events=scheduled_events,
        )
        return ClusterEvolutionOutcome(
            cluster=cluster_outcome,
            members=tuple(member_outcomes),
        )

    def evolve_cosmic_web(
        self,
        *,
        web_state: EvolutionState,
        until_cosmic_time_gyr: float,
        scenario: Scenario,
        model_id: str = WEB_MODEL_ID,
        expansion_ratio_fn=None,
        scheduled_events: Sequence[EvolutionEvent] = (),
    ) -> EvolutionOutcome:
        """Cosmic-web evolution (spec 2.19). The per-step scale-factor ratio
        comes ONLY from the injected UniverseEvolutionProvider or the
        supplied ``expansion_ratio_fn(t_gyr, dt_gyr) -> ratio`` — Phase 21
        never computes expansion."""
        if expansion_ratio_fn is None and self.universe is None:
            raise EvolutionDependencyError(
                "evolve_cosmic_web requires an expansion input: inject a "
                "UniverseEvolutionProvider or supply expansion_ratio_fn "
                "(no Universe Evolution system exists in this repository and "
                "Phase 21 will not compute expansion itself)"
            )
        if expansion_ratio_fn is not None and not callable(expansion_ratio_fn):
            raise EvolutionValidationError("expansion_ratio_fn must be callable(t, dt)")
        if expansion_ratio_fn is None and self.universe is not None:
            provider = self.universe

            def expansion_ratio_fn(t_gyr: float, dt_gyr: float) -> float:
                """Scale-factor ratio CONSUMED from the injected provider at
                both endpoints (Phase 21 computes no cosmology itself)."""
                a0 = provider.scale_factor(t_gyr)
                a1 = provider.scale_factor(t_gyr + dt_gyr)
                return a1 / a0
        return self._run(
            initial_state=web_state,
            until=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
            scheduled_events=scheduled_events,
            record=True,
            op=OP_EVOLVE,
            expansion_ratio_fn=expansion_ratio_fn,
        )

    def advance_cosmic_epoch(
        self,
        *,
        states: Sequence[EvolutionState],
        until_cosmic_time_gyr: float,
        scenario: Scenario,
        model_for_kind: Mapping[str, str],
    ) -> EpochAdvanceReport:
        """Advance a whole cosmic state (many objects) to a common cosmic
        time (spec 2.41 'advance cosmic epoch'), reporting the ensemble
        epoch before/after (spec 2.5)."""
        classifier = self._classifier_for(scenario)
        before_inputs = _ensemble_epoch_inputs(states)
        epoch_before = classifier.classify_inputs(before_inputs).value
        outcomes: list = []
        events: list = []
        for state in sorted(states, key=lambda s: (s.object_id,)):
            model_id = model_for_kind.get(state.object_kind)
            if model_id is None:
                raise EvolutionValidationError(
                    f"no model configured for object kind {state.object_kind}"
                )
            outcome = self.evolve_object(
                initial_state=state,
                until_cosmic_time_gyr=until_cosmic_time_gyr,
                model_id=model_id,
                scenario=scenario,
            )
            outcomes.append((state.object_id, outcome))
            events.extend(outcome.events)
        after_inputs = _ensemble_epoch_inputs([o.final_state for _, o in outcomes])
        epoch_after = classifier.classify_inputs(after_inputs).value
        if epoch_before != epoch_after and epoch_after != EvolutionEpoch.UNKNOWN.value:
            event = self._new_event(
                kind=EvolutionEventKind.EPOCH_TRANSITION,
                cosmic_time_gyr=until_cosmic_time_gyr,
                source_object_ids=tuple(s.object_id for s in states),
                resulting_object_ids=(),
                physical_cause=(
                    f"ensemble epoch {epoch_before} -> {epoch_after} under scenario "
                    f"{scenario.scenario_id} (state-derived classification)"
                ),
                model_id="astra.evolution.epoch_classifier",
                provenance=DataProvenance.SIMULATED_DATA,
                causal_parent_event_id=None,
                metadata={"from": epoch_before, "to": epoch_after},
            )
            events.append(event)
        return EpochAdvanceReport(
            outcomes=tuple(outcomes),
            ensemble_epoch_before=epoch_before,
            ensemble_epoch_after=epoch_after,
            events=tuple(events),
        )

    def project_future_state(
        self,
        *,
        initial_state: EvolutionState,
        until_cosmic_time_gyr: float,
        model_id: str,
        scenario: Scenario,
        scheduled_events: Sequence[EvolutionEvent] = (),
    ) -> EvolutionOutcome:
        """Non-mutating future-state query (spec 2.41 'query future state'):
        runs the same evolution on an isolated path and records nothing in
        the primary ledger. The outcome is a PROJECTION under the
        scenario's ProjectionClass — never an observation."""
        return self._run(
            initial_state=initial_state,
            until=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario,
            scheduled_events=scheduled_events,
            record=False,
            op=OP_PROJECT,
        )

    def compare_scenarios(
        self,
        *,
        initial_state: EvolutionState,
        until_cosmic_time_gyr: float,
        model_id: str,
        scenario_a: Scenario,
        scenario_b: Scenario,
    ) -> ScenarioComparison:
        """Evolve the same initial state under two scenarios and report
        per-quantity deltas (spec 2.41 'compare scenarios')."""
        outcome_a = self.project_future_state(
            initial_state=initial_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario_a,
        )
        outcome_b = self.project_future_state(
            initial_state=initial_state,
            until_cosmic_time_gyr=until_cosmic_time_gyr,
            model_id=model_id,
            scenario=scenario_b,
        )
        deltas: list = []
        for key in sorted(set(outcome_a.final_state.quantities) & set(outcome_b.final_state.quantities)):
            va = outcome_a.final_state.quantities[key].value
            vb = outcome_b.final_state.quantities[key].value
            deltas.append((key, va, vb, vb - va))
        return ScenarioComparison(
            scenario_a_id=scenario_a.scenario_id,
            scenario_b_id=scenario_b.scenario_id,
            outcome_a=outcome_a,
            outcome_b=outcome_b,
            quantity_deltas=tuple(deltas),
            note=(
                "Both outcomes are SIMULATED projections under different scenario "
                "assumptions; deltas are model sensitivities, not observational "
                "uncertainties."
            ),
        )

    def record_event(self, event: EvolutionEvent) -> EvolutionEvent:
        """Record a caller-authored evolutionary event (spec 2.27) with an
        engine-assigned causal link when none is supplied."""
        self._require_authority(OP_RECORD_EVENT)
        if not isinstance(event, EvolutionEvent):
            raise EvolutionValidationError("record_event requires an EvolutionEvent")
        parent = event.causal_parent_event_id or self._ledger.last_event_id_for(
            event.source_object_ids[0] if event.source_object_ids else ""
        )
        stamped = event if parent == event.causal_parent_event_id else replace(
            event, causal_parent_event_id=parent
        )
        self._ledger.record_event(stamped)
        self._publish(stamped)
        return stamped

    def record_galaxy_merger(
        self,
        *,
        progenitor_a: EvolutionState,
        progenitor_b: EvolutionState,
        resulting: EvolutionState,
        cosmic_time_gyr: float,
        physical_cause: str,
        model_id: str = GALAXY_MODEL_ID,
    ) -> EvolutionEvent:
        """Record a galaxy-merger event explicitly (spec 2.11). Phase 21
        does NOT predict mergers autonomously (no Phase 20 orbits exist);
        callers with dynamics record them here — identity and history are
        preserved via progenitor references."""
        self._require_authority(OP_RECORD_MERGER)
        for name, state in (("progenitor_a", progenitor_a), ("progenitor_b", progenitor_b)):
            if not isinstance(state, EvolutionState):
                raise EvolutionValidationError(f"{name} must be an EvolutionState")
            if state.object_kind != KIND_GALAXY:
                raise EvolutionLimitationError(
                    LimitationState.INCOMPATIBLE_MODEL,
                    f"{name} is a {state.object_kind}, expected {KIND_GALAXY}",
                )
        if resulting.object_kind != KIND_GALAXY:
            raise EvolutionLimitationError(
                LimitationState.INCOMPATIBLE_MODEL,
                f"resulting object is a {resulting.object_kind}, expected {KIND_GALAXY}",
            )
        t = require_finite_number(cosmic_time_gyr, "cosmic_time_gyr")
        parent = self._ledger.last_event_id_for(progenitor_a.object_id)
        event = self._new_event(
            kind=EvolutionEventKind.GALAXY_MERGER,
            cosmic_time_gyr=t,
            source_object_ids=(progenitor_a.object_id, progenitor_b.object_id),
            resulting_object_ids=(resulting.object_id,),
            physical_cause=physical_cause,
            model_id=model_id,
            provenance=DataProvenance.SIMULATED_DATA,
            causal_parent_event_id=parent,
            metadata={
                "progenitor_stellar_mass_msun": [
                    progenitor_a.quantity_value("stellar_mass_msun", 0.0),
                    progenitor_b.quantity_value("stellar_mass_msun", 0.0),
                ],
                "resulting_stellar_mass_msun": resulting.quantity_value("stellar_mass_msun", 0.0),
                "note": "merger timing/mass redistribution supplied by the caller",
            },
        )
        return event

    def record_black_hole_merger(
        self,
        *,
        bh_mass_a_msun: float,
        bh_mass_b_msun: float,
        host_galaxy_id: str,
        cosmic_time_gyr: float,
        physical_cause: str,
        model_id: str = GALAXY_MODEL_ID,
    ) -> EvolutionEvent:
        """Record a black-hole merger ASSOCIATION with a host galaxy
        (spec 2.11/2.9 bookkeeping). The merged MASS is the sum of the two
        input masses; radiated mass loss and ringdown physics belong to the
        black-hole/relativity layers and are explicitly not modeled here."""
        self._require_authority(OP_RECORD_MERGER)
        a = require_finite_number(bh_mass_a_msun, "bh_mass_a_msun")
        b = require_finite_number(bh_mass_b_msun, "bh_mass_b_msun")
        if a <= 0.0 or b <= 0.0:
            raise EvolutionValidationError("black-hole masses must be > 0")
        t = require_finite_number(cosmic_time_gyr, "cosmic_time_gyr")
        parent = self._ledger.last_event_id_for(host_galaxy_id)
        event = self._new_event(
            kind=EvolutionEventKind.BLACK_HOLE_MERGER,
            cosmic_time_gyr=t,
            source_object_ids=(host_galaxy_id,),
            resulting_object_ids=(host_galaxy_id,),
            physical_cause=physical_cause,
            model_id=model_id,
            provenance=DataProvenance.SIMULATED_DATA,
            causal_parent_event_id=parent,
            metadata={
                "bh_mass_a_msun": a,
                "bh_mass_b_msun": b,
                "combined_mass_msun": a + b,
                "note": (
                    "summed mass; gravitational-wave energy loss/ringdown not "
                    "modeled (unsupported process, documented limitation)"
                ),
            },
        )
        return event

    def record_structure_regime(
        self,
        *,
        state: EvolutionState,
        structure_id: str,
        binding_energy_ratio: float,
        cosmic_time_gyr: float,
    ) -> EvolutionEvent:
        """Classify and record a structure's expansion regime from
        caller-supplied dynamics (spec 2.17)."""
        from .builtins import classify_structure_regime

        self._require_authority(OP_RECORD_EVENT)
        regime = classify_structure_regime(binding_energy_ratio=binding_energy_ratio)
        t = require_finite_number(cosmic_time_gyr, "cosmic_time_gyr")
        parent = self._ledger.last_event_id_for(structure_id)
        previous = None
        structures = state.metadata.get("structures", {})
        if isinstance(structures, dict) and structure_id in structures:
            previous = structures[structure_id].get("regime")
        event = self._new_event(
            kind=EvolutionEventKind.COSMIC_STRUCTURE_TRANSITION,
            cosmic_time_gyr=t,
            source_object_ids=(state.object_id,),
            resulting_object_ids=(structure_id,),
            physical_cause=(
                f"structure regime {previous or 'UNRECORDED'} -> {regime.value} from "
                f"binding_energy_ratio={binding_energy_ratio:.6g} supplied by the caller"
            ),
            model_id=state.model_id,
            provenance=DataProvenance.SIMULATED_DATA,
            causal_parent_event_id=parent,
            metadata={"from": previous, "to": regime.value, "binding_energy_ratio": binding_energy_ratio},
        )
        return event

    # -------------------------------------------------------------- history
    def history(self) -> Tuple[EvolutionEvent, ...]:
        """All recorded evolutionary events, in execution order."""
        return self._ledger.events()

    def events_for(self, object_id: str) -> Tuple[EvolutionEvent, ...]:
        return self._ledger.events_for(object_id)

    def object_history(self, object_id: str) -> Tuple[EvolutionState, ...]:
        """Recorded state samples for one object (spec 2.41)."""
        return self._ledger.history(object_id)

    def validate_history(self) -> Tuple[int, int]:
        """Full causal sweep of the ledger. Returns (events, chain_edges)."""
        return self._ledger.validate()

    def epoch_of(self, state: EvolutionState, scenario: Optional[Scenario] = None) -> str:
        """State-derived epoch label for one state."""
        classifier = self._classifier_for(scenario)
        return classifier.classify(state).value

    def model_assumptions(self, model_id: str) -> Dict[str, Any]:
        """Registered assumptions/limitations for one model (spec 2.41)."""
        model = self.model_registry.get(model_id)
        return {
            "model_id": model.model_id,
            "classification": model.classification.value,
            "provenance": model.provenance.value,
            "assumptions": [a.statement for a in model.assumptions],
            "limitations": list(model.limitations),
            "max_valid_cosmic_time_gyr": model.max_valid_cosmic_time_gyr,
        }

    @staticmethod
    def provenance_summary(state: EvolutionState) -> Dict[str, int]:
        """Count of quantities by provenance for one state."""
        counts: Dict[str, int] = {}
        for q in state.quantities.values():
            counts[q.provenance.value] = counts.get(q.provenance.value, 0) + 1
        counts["state:" + state.provenance.value] = counts.get("state:" + state.provenance.value, 0) + 1
        return dict(sorted(counts.items()))

    def diagnostics(self) -> Dict[str, Any]:
        return {
            "events_recorded": len(self._ledger.events()),
            "objects_evolved": self._objects_evolved,
            "steps_taken": self._ledger.steps,
            "models_registered": len(self.model_registry.list_model_ids()),
            "scenarios_registered": len(self.scenario_registry.list_ids()),
            "history_decimations": self._ledger.decimations(),
            "model_version": self.config.model_version,
            "resolution": self.config.resolution,
            "budget": self.config.budget.to_dict(),
        }

    # ------------------------------------------------------------ persistence
    def save(self, key: str) -> None:
        """Persist engine state through the injected PersistenceHook."""
        self._require_authority(OP_RECORD_EVENT)
        if self.persistence is None:
            raise EvolutionDependencyError(
                "no PersistenceHook injected; inject adapters.CorePersistenceHookAdapter "
                "or DictPersistenceHook to save"
            )
        payload = {
            "config": self.config.to_dict(),
            "ledger": self._ledger.to_dict(),
            "event_counter": self._event_counter,
            "objects_evolved": self._objects_evolved,
            "scenarios": [self.scenario_registry.get(sid).to_dict() for sid in self.scenario_registry.list_ids()],
            "models": [
                self.model_registry.get(mid).to_dict() for mid in self.model_registry.list_model_ids()
            ],
        }
        self.persistence.save(key, payload)

    def restore_ledger(self, payload: Mapping[str, Any]) -> None:
        """Restore the ledger (models/scenarios must be re-registered by
        the caller; steps are code and never travel through snapshots)."""
        self._require_authority(OP_RESTORE)
        ledger = EvolutionLedger()
        ledger.load_dict(dict(payload["ledger"]))
        self._ledger = ledger
        self._event_counter = int(payload.get("event_counter", 0))
        self._objects_evolved = int(payload.get("objects_evolved", 0))

    # ------------------------------------------------------------- internals
    def _require_authority(self, operation: str) -> None:
        if self.authority is None:
            raise EvolutionAuthorityError(
                f"no AuthorityProvider configured; cannot perform {operation}",
                operation=operation,
            )
        self.authority.require(operation)

    def _classifier_for(self, scenario: Optional[Scenario]) -> EpochClassifier:
        boundaries = self.config.epoch_boundaries
        if scenario is not None and scenario.epoch_boundaries is not None:
            boundaries = scenario.epoch_boundaries
        return EpochClassifier(boundaries)

    def _register_scenario(self, scenario: Scenario) -> Scenario:
        if not isinstance(scenario, Scenario):
            raise EvolutionValidationError("scenario must be a Scenario")
        if self.scenario_registry.has(scenario.scenario_id):
            known = self.scenario_registry.get(scenario.scenario_id)
            if known != scenario:
                raise EvolutionValidationError(
                    f"scenario {scenario.scenario_id} already registered with a "
                    "different definition; use a new id"
                )
        else:
            self.scenario_registry.register(scenario)
        return scenario

    def _effective_model(self, model: EvolutionModel, scenario: Scenario) -> EvolutionModel:
        """Apply scenario evolution-parameter overrides by name (documented
        mechanism for scenario-dependent model behavior)."""
        if not scenario.evolution_parameters:
            return model
        unknown = set(scenario.evolution_parameters) - set(model.parameters)
        if unknown:
            raise EvolutionValidationError(
                f"scenario {scenario.scenario_id} overrides unknown parameters "
                f"{sorted(unknown)} for model {model.model_id}"
            )
        merged = dict(model.parameters)
        merged.update(scenario.evolution_parameters)
        return replace(model, parameters=merged)

    def _new_event(
        self,
        *,
        kind: EvolutionEventKind,
        cosmic_time_gyr: float,
        source_object_ids: Tuple[str, ...],
        resulting_object_ids: Tuple[str, ...],
        physical_cause: str,
        model_id: str,
        provenance: DataProvenance,
        causal_parent_event_id: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
        ledger: Optional[EvolutionLedger] = None,
        publish: bool = True,
    ) -> EvolutionEvent:
        self._event_counter += 1
        event = EvolutionEvent(
            event_id=f"evo-evt-{self._event_counter:08d}",
            kind=kind,
            cosmic_time_gyr=cosmic_time_gyr,
            source_object_ids=tuple(source_object_ids),
            resulting_object_ids=tuple(resulting_object_ids),
            physical_cause=physical_cause,
            model_id=model_id,
            provenance=provenance,
            causal_parent_event_id=causal_parent_event_id,
            metadata=dict(metadata or {}),
        )
        (ledger or self._ledger).record_event(event)
        if publish:
            self._publish(event)
        return event

    def _publish(self, event: EvolutionEvent) -> None:
        if self.events is not None:
            self.events.publish("evolution.event", event.to_dict())

    def _check_budgets(self) -> None:
        budget = self.config.budget
        if self._objects_evolved >= budget.max_objects_evolved:
            raise EvolutionLimitationError(
                LimitationState.BUDGET_EXCEEDED,
                f"max_objects_evolved ({budget.max_objects_evolved}) reached",
            )

    def _resolve_scheduled(
        self,
        scheduled_events: Sequence[EvolutionEvent],
        t0: float,
        until: float,
    ) -> Tuple[EvolutionEvent, ...]:
        events = list(scheduled_events)
        for event in events:
            if not isinstance(event, EvolutionEvent):
                raise EvolutionValidationError("scheduled events must be EvolutionEvent records")
            t = event.cosmic_time_gyr
            if not (t0 < t <= until):
                raise EvolutionValidationError(
                    f"scheduled event {event.event_id} at {t} lies outside ({t0}, {until}]"
                )
            if event.provenance not in _PROJECTION_PROVENANCES:
                raise EvolutionValidationError(
                    f"scheduled event {event.event_id} claims provenance "
                    f"{event.provenance.value}; future events are projections "
                    "(SIMULATED_DATA / THEORETICAL_MODEL / SPECULATIVE_MODEL), "
                    "never observations"
                )
        return tuple(sorted(events, key=lambda e: (e.cosmic_time_gyr, e.event_id)))

    def _run(
        self,
        *,
        initial_state: EvolutionState,
        until: float,
        model_id: str,
        scenario: Scenario,
        scheduled_events: Sequence[EvolutionEvent],
        record: bool,
        op: str,
        expansion_ratio_fn=None,
    ) -> EvolutionOutcome:
        self._require_authority(op)
        self._check_budgets()
        t0 = initial_state.cosmic_time_gyr
        until_v = require_finite_number(until, "until_cosmic_time_gyr")
        if until_v < t0:
            raise EvolutionValidationError(
                f"target time {until_v} precedes initial time {t0}; backward "
                "evolution is not supported"
            )
        model = self.model_registry.get(model_id)
        if initial_state.object_kind not in model.applicable_object_kinds:
            raise EvolutionLimitationError(
                LimitationState.INCOMPATIBLE_MODEL,
                f"model {model_id} applies to {model.applicable_object_kinds}, "
                f"not to {initial_state.object_kind}",
            )
        if resolution_rank(self.config.resolution) < kind_rank(initial_state.object_kind):
            raise EvolutionLimitationError(
                LimitationState.INSUFFICIENT_RESOLUTION,
                f"configured resolution '{self.config.resolution}' cannot evolve a "
                f"{initial_state.object_kind} object; raise EvolutionConfig.resolution "
                "to trade performance for resolution explicitly",
            )
        scenario = self._register_scenario(scenario)
        effective = self._effective_model(model, scenario)
        self._check_validity(effective, scenario, t0, until_v)

        controller = AdaptiveTimestepController(self.config.timestep)
        classifier = self._classifier_for(scenario)
        pending = self._resolve_scheduled(scheduled_events, t0, until_v)

        # Projections run on a scratch ledger: outcomes carry their events,
        # but the primary ledger and the event bus stay untouched.
        if record:
            ledger = self._ledger
            publish = True
        else:
            ledger = EvolutionLedger()
            publish = False

        state = initial_state
        run_events: list = []
        timesteps: list = []
        epochs: list = []
        last_epoch: Optional[str] = None
        parent_id: Optional[str] = None
        if record:
            parent_id = self._ledger.last_event_id_for(initial_state.object_id)
            if parent_id is not None:
                parent_event = next(
                    e for e in self._ledger.events() if e.event_id == parent_id
                )
                fork_tolerance = self.config.rtol * max(1.0, abs(t0)) + self.config.atol
                if parent_event.cosmic_time_gyr > t0 + fork_tolerance:
                    raise EvolutionValidationError(
                        f"the ledger already records {initial_state.object_id} history "
                        f"up to t={parent_event.cosmic_time_gyr} Gyr; evolving from t0={t0} "
                        "would fork the recorded causal timeline. Use "
                        "project_future_state for counterfactual runs (they are not "
                        "recorded), a fresh object_id for a new lineage, or continue "
                        "from the recorded state."
                    )
        initial_inputs = epoch_inputs_from_state(state)
        if not initial_inputs.is_empty():
            last_epoch = classifier.classify_inputs(initial_inputs).value
            epochs.append((t0, last_epoch))

        if record:
            self._objects_evolved += 1
            self._ledger.record_sample(state, self.config.budget)

        steps = 0
        budget = self.config.budget
        pending_index = 0
        while state.cosmic_time_gyr < until_v:
            steps += 1
            if steps > budget.max_steps_per_object:
                raise EvolutionLimitationError(
                    LimitationState.BUDGET_EXCEEDED,
                    f"max_steps_per_object ({budget.max_steps_per_object}) exceeded; "
                    "check the timestep policy for degenerate settings",
                )
            now = state.cosmic_time_gyr
            next_event_time: Optional[float] = None
            while pending_index < len(pending) and pending[pending_index].cosmic_time_gyr <= now:
                # Defensive: a due event at loop start (cannot normally occur
                # because steps land exactly on boundaries) is recorded now.
                scheduled = pending[pending_index]
                pending_index += 1
                recorded = scheduled
                if recorded.causal_parent_event_id is None and parent_id is not None:
                    recorded = replace(recorded, causal_parent_event_id=parent_id)
                ledger.record_event(recorded)
                if publish:
                    self._publish(recorded)
                run_events.append(recorded)
                parent_id = recorded.event_id
            if pending_index < len(pending):
                next_event_time = pending[pending_index].cosmic_time_gyr

            rate_scale = 0.0
            if effective.rate_scale is not None:
                rate_scale = effective.rate_scale(state, effective)
                rate_scale = require_finite_number(rate_scale, "model rate_scale")
                if rate_scale < 0.0:
                    raise EvolutionValidationError(
                        f"model {model_id} returned a negative rate_scale"
                    )
            decision = controller.choose(
                now_gyr=now,
                remaining_gyr=until_v - now,
                rate_scale=rate_scale,
                next_event_time_gyr=next_event_time,
                model_id=model_id,
            )
            if decision.dt_gyr <= 0.0:
                raise EvolutionLimitationError(
                    LimitationState.INVALID_TIMESTEP,
                    f"controller produced a non-positive step ({decision.dt_gyr})",
                )

            working = state
            if expansion_ratio_fn is not None:
                ratio = expansion_ratio_fn(now, decision.dt_gyr)
                ratio = require_finite_number(ratio, "expansion_ratio_fn result")
                if ratio <= 0.0:
                    raise EvolutionLimitationError(
                        LimitationState.INVALID_COSMOLOGY,
                        f"expansion scale-factor ratio must be > 0, got {ratio}",
                    )
                metadata = dict(working.metadata)
                metadata[EXPANSION_INPUT_KEY] = ratio
                working = replace(working, metadata=metadata)

            prev_state = working
            new_state = self.model_registry.step_for(model_id)(working, decision.dt_gyr, effective)
            if not isinstance(new_state, EvolutionState):
                raise EvolutionValidationError(
                    f"model {model_id} step returned {type(new_state).__name__}, "
                    "expected an EvolutionState"
                )
            expected = now + decision.dt_gyr
            drift = abs(new_state.cosmic_time_gyr - expected)
            tolerance = self.config.rtol * max(1.0, abs(expected)) + self.config.atol
            if new_state.cosmic_time_gyr <= now or drift > tolerance:
                raise EvolutionLimitationError(
                    LimitationState.NUMERICAL_INSTABILITY,
                    f"model {model_id} time bookkeeping violated: t {now} -> "
                    f"{new_state.cosmic_time_gyr}, expected {expected}",
                )
            # Stamp bookkeeping honestly: which model produced each
            # quantity, and which projection depth this scenario carries.
            stamped = {}
            for k, q in new_state.quantities.items():
                if q.model_id is None:
                    q = replace(q, model_id=model_id)
                stamped[k] = q
            new_state = replace(new_state, quantities=stamped)
            # Bounded rolling series for the canonical history extractors
            # (StarFormationHistory / MetallicityHistory); decimated in
            # place when the cap is exceeded, mirroring ledger decimation.
            series_meta = dict(new_state.metadata)
            for _key in ("sfr_msun_yr", "metallicity_z"):
                _q = stamped.get(_key)
                if _q is None:
                    continue
                _name = "history_" + _key
                _series = list(series_meta.get(_name) or ())
                _series.append((new_state.cosmic_time_gyr, _q.value))
                if len(_series) > 2 * 2048:
                    _series = _series[::2]
                series_meta[_name] = tuple(_series)
            new_state = replace(new_state, metadata=series_meta)
            if scenario.projection_class is not ProjectionClass.NONE:
                new_state = replace(new_state, projection_class=scenario.projection_class)
            state = new_state
            timesteps.append(decision)

            parent_id = self._detect_transitions(
                prev=prev_state, new=state, model_id=model_id,
                run_events=run_events, parent_id=parent_id,
                ledger=ledger, publish=publish,
            )

            label = classifier.classify(state)
            if label is not EvolutionEpoch.UNKNOWN and label.value != last_epoch:
                epochs.append((state.cosmic_time_gyr, label.value))
                event = self._new_event(
                    kind=EvolutionEventKind.EPOCH_TRANSITION,
                    cosmic_time_gyr=state.cosmic_time_gyr,
                    source_object_ids=(state.object_id,),
                    resulting_object_ids=(),
                    physical_cause=(
                        f"epoch {last_epoch} -> {label.value} (state-derived "
                        f"classification against configured boundaries)"
                    ),
                    model_id=state.model_id,
                    provenance=DataProvenance.SIMULATED_DATA,
                    causal_parent_event_id=parent_id,
                    metadata={"from": last_epoch, "to": label.value},
                    ledger=ledger,
                    publish=publish,
                )
                run_events.append(event)
                parent_id = event.event_id
                last_epoch = label.value

            while pending_index < len(pending) and (
                state.cosmic_time_gyr >= pending[pending_index].cosmic_time_gyr
            ):
                scheduled = pending[pending_index]
                pending_index += 1
                recorded = scheduled
                if recorded.causal_parent_event_id is None and parent_id is not None:
                    recorded = replace(recorded, causal_parent_event_id=parent_id)
                ledger.record_event(recorded)
                if publish:
                    self._publish(recorded)
                run_events.append(recorded)
                parent_id = recorded.event_id

            if record:
                self._ledger.record_sample(state, self.config.budget)

        if record:
            self._ledger.record_sample(state, self.config.budget)
        return EvolutionOutcome(
            initial_state=initial_state,
            final_state=state,
            events=tuple(run_events),
            timesteps=tuple(timesteps),
            epochs=tuple(epochs),
            scenario_id=scenario.scenario_id,
            model_id=model_id,
        )

    def _check_validity(
        self, model: EvolutionModel, scenario: Scenario, t0: float, t1: float
    ) -> None:
        horizon = model.max_valid_cosmic_time_gyr
        if horizon is None:
            return
        if t1 <= horizon and t0 <= horizon:
            return
        detail = (
            f"model {model.model_id} declares validity to {horizon} Gyr; requested "
            f"evolution reaches {max(t0, t1)} Gyr"
        )
        if t0 > horizon:
            raise EvolutionLimitationError(LimitationState.UNSUPPORTED_TIMESCALE, detail)
        if scenario.projection_class is ProjectionClass.MODEL_PROJECTED:
            raise EvolutionLimitationError(
                LimitationState.OUTSIDE_VALID_RANGE,
                detail + "; re-classify the scenario as HYPOTHETICAL or SPECULATIVE "
                "and register a correspondingly classified model to explore beyond "
                "this horizon",
            )
        raise EvolutionLimitationError(
            LimitationState.UNSUPPORTED_TIMESCALE,
            detail + "; no registered model computes this range — register a "
            "HYPOTHETICAL/SPECULATIVE-classified model explicitly",
        )

    def _detect_transitions(
        self,
        *,
        prev: EvolutionState,
        new: EvolutionState,
        model_id: str,
        run_events: list,
        parent_id: Optional[str],
        ledger: EvolutionLedger,
        publish: bool,
    ) -> Optional[str]:
        """Compare consecutive states and record transition events. Returns
        the (possibly updated) causal chain tip for this object."""
        cause = new.metadata.get("transition_detail")
        kind: Optional[EvolutionEventKind] = None
        detail: Optional[str] = None

        if new.phase != prev.phase:
            if new.object_kind == KIND_STAR:
                kind = EvolutionEventKind.STELLAR_TRANSITION
            elif new.object_kind == KIND_POPULATION:
                kind = EvolutionEventKind.POPULATION_TRANSITION
            elif new.object_kind == KIND_GALAXY:
                kind = EvolutionEventKind.AGN_TRANSITION
            else:
                kind = EvolutionEventKind.COSMIC_STRUCTURE_TRANSITION
        else:
            # Same phase, but regime/dissolution metadata may still change.
            if new.object_kind in (KIND_CLUSTER, KIND_COSMIC_WEB, KIND_STRUCTURE):
                structures_prev = prev.metadata.get("structures", {})
                structures_new = new.metadata.get("structures", {})
                for sid in sorted(set(structures_new) - set(structures_prev)):
                    if structures_new[sid].get("dissolved"):
                        kind = EvolutionEventKind.COSMIC_STRUCTURE_TRANSITION
                        detail = structures_new[sid].get("transition_detail")
                        break
            prev_sfr = prev.quantity_value("sfr_msun_yr")
            new_sfr = new.quantity_value("sfr_msun_yr")
            if kind is None and prev_sfr is not None and new_sfr is not None:
                if prev_sfr > 0.0 and new_sfr == 0.0:
                    kind = EvolutionEventKind.STAR_FORMATION_TRANSITION
            if kind is None and new.object_kind == KIND_GALAXY:
                prev_morph = prev.metadata.get("morphology", {})
                new_morph = new.metadata.get("morphology", {})
                if prev_morph and new_morph:
                    from .state import MorphologyClass as _M

                    prev_top = max(prev_morph.items(), key=lambda kv: (kv[1], kv[0]))[0]
                    new_top = max(new_morph.items(), key=lambda kv: (kv[1], kv[0]))[0]
                    if prev_top != new_top and new_top in tuple(m.value for m in _M):
                        kind = EvolutionEventKind.MORPHOLOGY_TRANSITION
                        detail = f"dominant morphology {prev_top} -> {new_top} (distribution drift)"

        if kind is None:
            return parent_id

        event = self._new_event(
            kind=kind,
            cosmic_time_gyr=new.cosmic_time_gyr,
            source_object_ids=(new.object_id,),
            resulting_object_ids=(new.object_id,),
            physical_cause=str(detail or cause or (
                f"{prev.phase} -> {new.phase} under model {model_id}"
            )),
            model_id=model_id,
            provenance=new.provenance,
            causal_parent_event_id=parent_id,
            metadata={
                "from": prev.phase,
                "to": new.phase,
                **({"remnant_kind": new.metadata["remnant_kind"]}
                   if "remnant_kind" in new.metadata else {}),
                **({"transition_detail": detail} if detail else {}),
            },
            ledger=ledger,
            publish=publish,
        )
        run_events.append(event)
        parent_id = event.event_id

        if new.object_kind == KIND_STAR and new.phase == "REMNANT" and prev.phase != "REMNANT":
            death = self._new_event(
                kind=EvolutionEventKind.STELLAR_DEATH,
                cosmic_time_gyr=new.cosmic_time_gyr,
                source_object_ids=(new.object_id,),
                resulting_object_ids=(new.object_id,),
                physical_cause=str(new.metadata.get("transition_detail") or (
                    f"remnant formation ({new.metadata.get('remnant_kind', 'UNKNOWN')})"
                )),
                model_id=model_id,
                provenance=new.provenance,
                causal_parent_event_id=parent_id,
                metadata={
                    "from": prev.phase,
                    "to": new.phase,
                    **({"remnant_kind": new.metadata["remnant_kind"]}
                       if "remnant_kind" in new.metadata else {}),
                },
                ledger=ledger,
                publish=publish,
            )
            run_events.append(death)
            parent_id = death.event_id
        return parent_id

    def _aggregate_cluster(
        self, cluster_state: EvolutionState, member_finals: Sequence[EvolutionState]
    ) -> EvolutionState:
        """Fold member totals into the cluster state before its own step."""
        stellar = sum(s.quantity_value("stellar_mass_msun", 0.0) for s in member_finals)
        gas = sum(s.quantity_value("gas_mass_msun", 0.0) for s in member_finals)
        bh = sum(s.quantity_value("bh_mass_msun", 0.0) for s in member_finals)
        sfr = sum(s.quantity_value("sfr_msun_yr", 0.0) for s in member_finals)
        lum = sum(s.quantity_value("luminosity_lsun", 0.0) for s in member_finals)
        metal_weighted = 0.0
        if gas > 0.0:
            metal_weighted = sum(
                s.quantity_value("metallicity_z", 0.0) * s.quantity_value("gas_mass_msun", 0.0)
                for s in member_finals
            ) / gas
        updates = {
            "stellar_mass_msun": Quantity(value=stellar, unit="Msun", note="sum over members"),
            "gas_mass_msun": Quantity(value=gas, unit="Msun", note="sum over members"),
            "bh_mass_msun": Quantity(value=bh, unit="Msun", note="sum over members"),
            "sfr_msun_yr": Quantity(value=sfr, unit="Msun/yr", note="sum over members"),
            "luminosity_lsun": Quantity(value=lum, unit="Lsun", note="sum over members"),
            "metallicity_z": Quantity(
                value=metal_weighted, unit="dimensionless", note="gas-mass-weighted mean"
            ),
        }
        merged = dict(cluster_state.quantities)
        merged.update(updates)
        return replace(cluster_state, quantities=merged)
