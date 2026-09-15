# Phase 21 — Long-Term Cosmic Evolution Engine

Status: **implemented and verified** on branch `arena/01a0a53a-astra-cosmos`.
This package evolves cosmic objects coherently from Myr timescales to a
trillion years (1e3 Gyr) as a thin, honest layer ABOVE the existing ASTRA
COSMOS systems — it replaces none of them, duplicates no authority, and
refuses loudly (with a typed `LimitationState`) whenever it would have to
guess.

Companion document: `docs/evolution/DEPENDENCY_MATRIX.md` (row-by-row
reconciliation between the phase specification and the actual repository,
verified by reading the real modules).

Package statistics (verified): 18 modules + `__init__.py`, ~5.6k lines,
92 exported public symbols, 178 test functions in `tests/evolution/`
(198 with parametrization expansion), all passing, full repository
regression 1732 passed.

---

## 1. Purpose and Scope

Phase 21 answers one question coherently: *given objects created by the
rest of ASTRA COSMOS, what happens to them over cosmic time — a million
years, a billion years, a trillion years?*

It provides, and only provides:

- **long-horizon state evolution** for five object kinds — single stars,
  stellar populations (conveyor belt), one-zone galaxies, galaxy clusters
  (member aggregates), and the cosmic web (regime bookkeeping);
- **a model registry** of explicitly-classified, explicitly-bounded
  reduced-order models with per-model validity horizons;
- **scenario bookkeeping** (alternative cosmological/evolutionary
  parameterizations) with deterministic comparison;
- **an adaptive timestep controller** with explicit, recorded decisions;
- **epoch classification** (STELLIFEROUS, DECLINING, DEGENERATE,
  BLACK_HOLE_DOMINATED, DARK_ERA, UNKNOWN) as a pure function of state +
  configuration;
- **a causal event ledger** with ordered, parent-linked, serializable
  events;
- **provenance-preserving persistence** round-trips;
- **integration adapters** for the core systems that exist and explicit
  refusals (`Missing*` adapters) for the systems that do not.

It deliberately does **not** do (non-scope, enforced by the architecture):

- background cosmology (no scale factor, no FLRW, no Hubble rate) — that
  is Universe Evolution's authority, which is ABSENT from the repository,
  so every expansion-dependent feature *refuses* with
  `EvolutionDependencyError` until a provider is injected;
- galaxy/cluster/web STRUCTURE creation, orbital dynamics, N-body,
  dynamics, or velocities (there is no `VelocityDecomposition` in the repo
  to reuse and Phase 21 computes none, so Hubble flow cannot be
  double-counted);
- observation, light propagation, or measurement — astra.temporal and the
  (absent) Observatory keep those authorities; Phase 21 produces
  simulation states whose provenance is SIMULATED / THEORETICAL /
  SPECULATIVE, never REAL_DATA;
- rendering, graphics, VFX, ingestion, travel.

## 2. Layering and Non-Duplication

Phase 21 sits at the top of the dependency stack and consumes, never
re-implements:

```
astra.evolution            (this phase: long-term reduced-order evolution)
    ▲ consumes
astra.core                 authority gate, event bus, persistence, RNG, IDs
astra.mathematics          validation, numerical conventions, tolerances
astra.celestial            taxonomy: phases, remnant kinds, DataProvenance
astra.temporal             SI-second time semantics, causal ordering
astra.destruction          structural template (protocols + adapters)
```

The single-authority rules are respected exactly: coordinates (core),
physics (physics), N-body (nbody), relativity, spacetime, cosmology
(Universe Evolution — absent, so refused), observation (temporal +
Observation provider), ingestion, travel, galactic structure (Phase 20 —
absent, so reduced-order state containers with the GalacticProvider
Protocol reserved for it), rendering (none). There is exactly one
temporal engine (astra.temporal) — `timebase.py` only converts Gyr to SI
seconds; there is exactly one merger recorder (this package's caller-
recorded event API — Phase 20/21 bookkeeping, not dynamics); black-hole
GEOMETRY stays in astra.blackhole — Phase 21 tracks only population-level
BH mass growth as its own quantity.

## 3. Package Layout

| Module | Contents |
|---|---|
| `quantity.py` | `Quantity` (frozen value+unit+`DataProvenance`+uncertainty+model_id+note) |
| `state.py` | `EvolutionState`, `ObjectKind`, `LifecyclePhase`, `RemnantKind`, `MorphologyClass`, `AGNActivityState`, `PopulationState`, `StarFormationHistory`, `MetallicityHistory`, factories `make_*_state` |
| `models.py` | `EvolutionModel`, `ModelClassification`, `ModelRegistry`, `StepFn`/`RateScale` protocols |
| `builtins.py` | five built-in models + factories + `BuiltinModelParams` |
| `registry re-exports` | `ModelRegistry`, `register_builtin_models`, `STELLAR_MODEL_ID`, `POPULATION_MODEL_ID`, `GALAXY_MODEL_ID`, `CLUSTER_MODEL_ID`, `WEB_MODEL_ID` |
| `scenarios.py` | `Scenario`, `ScenarioRegistry`, `EpochBoundaries` (parameterization, never hard-coded) |
| `timestep.py` | `TimestepPolicy`, `TimestepDecision`, `TimestepReason`, `AdaptiveTimestepController` |
| `config.py` | `EvolutionConfig` (timestep policy, performance budget, resolution, rtol/atol, model_version) |
| `epoch.py` | `EpochClassifier`, `EpochInputs`, `EvolutionEpoch`, `EpochBoundaries` re-export |
| `events.py` | `EvolutionEvent`, `EvolutionEventKind`, `EvolutionLedger` |
| `ledger.py` | ledger implementation, history sampling, decimation accounting |
| `limitations.py` | `LimitationState` enum (every failure maps to one) |
| `errors.py` | typed hierarchy rooted at `EvolutionError` |
| `provenance.py` | `ProjectionClass` (NONE/PREDICTED/…/SPECULATIVE), `ScientificConfidence`, `ProvenanceTag` |
| `persistence.py` | JSON round-trips for every data type |
| `adapters.py` | `Missing*` fail-closed adapters for ABSENT systems |
| `integration.py` | REAL core adapters: `CoreAuthorityProvider`, `CoreEventPublisherAdapter`, `CorePersistenceHookAdapter`, `DictPersistenceHook`, provider Protocols |
| `engine.py` | `CosmicEvolutionEngine` + outcome/summary/advance/compare/projection types |
| `timebase.py` | Gyr ↔ SI seconds (Julian year = 31557600 s exactly); no time engine |

## 4. The Five Built-in Models

All parameters live in `BuiltinModelParams` (validated on construction)
and are surfaced as model parameter `Quantity`s so scenarios can override
them; NOTHING astronomical is hard-coded inside steps.

1. **`stellar.single_star_lifecycle.v1`** — analytic single-star conveyor:
   t_MS = t_ms_sun_gyr · M^-2.5, L ∝ M^3.5; phases FORMATION →
   MAIN_SEQUENCE → POST_MAIN_SEQUENCE → REMNANT with smooth logistic
   transitions inside `post_ms_fraction` of t_MS; remnant kind by initial
   mass (≥ m_bh_threshold → stellar BH at 0.3·M, ≥ m_ns_threshold → NS at
   1.4 Msun, else WD at 0.6 Msun); validated against the canonical
   1 Msun lifetimes (t_MS = 10 Gyr, transitions at 10.0/11.0 Gyr). This is
   a classification-grade approximation, SIMULATED_DATA, max_valid 1e6 Gyr.
2. **`population.conveyor.v1`** — Kroupa-style IMF (0.08–100 Msun over 24
   log bins, fixed purely mathematical shape fractions), cohort conveyor
   with per-bin death windows, gas bookkeeping (requested-SFR driver held
   in metadata; actual SFR gas-limited), recycling-fed residual star
   formation, metallicity enrichment from returning ejecta, cohort
   coarsening under `max_cohorts_per_bin` (counted, reported), SFH/MZH
   histories, `PopulationState` summary view.
3. **`galaxy.one_zone.v1`** — closed-box one-zone: gas → stars
   (`gas_depletion_time_gyr`), inflow (optional, scenario-controlled),
   stellar deaths return gas + lock remnants, metallicity enrichment,
   SMBH growth by Eddington-limited-by-policy fuel fraction with an
   explicit hysteresis state machine (INACTIVE → LOW → ACTIVE → HIGH and
   back, thresholds in parameters), quasi-static morphology distribution
   drifting with gas fraction (SPIRAL/LENTICULAR/ELLIPTICAL
   probabilities, explicitly labeled qualitative).
4. **`cluster.member_aggregate.v1`** — aggregates member galaxies
   (engine folds members BEFORE the cluster step; mass =
   Σ members + accretion parameter; metallicity = gas-weighted member Z).
   Cluster physics (dynamics, relaxation, tides) is NOT modeled — regime
   metadata defaults to UNKNOWN, never "bound".
5. **`web.regime_evolution.v1`** — regime bookkeeping for the cosmic web:
   volume fractions drift hierarchically (voids grow, sheets → filaments
   → nodes), σ decays in DISSOLVING regimes only, proper sizes =
   comoving × Π(scale-factor ratios CONSUMED from the injected provider
   or caller function). Expansion is never computed here.

## 5. State, Quantities, and Provenance

`EvolutionState` = object_id, object_kind, cosmic_time_gyr (Gyr), phase,
frozen quantity map, model_id, scenario_id, `DataProvenance`,
`ProjectionClass`, JSON-safe metadata. Every quantity is a `Quantity`
carrying unit + `DataProvenance` + optional uncertainty + the model_id
that produced it (stamped by the engine). Engine outputs never carry
`REAL_DATA` or `DERIVED_DATA` — asserted by tests. States produced under
a scenario with a `ProjectionClass` are stamped with it (depth of the
projection), and events for projected runs carry projection-safe
provenance. Future states are SIMULATED/THEORETICAL/HYPOTHETICAL/
SPECULATIVE — never presented as observation — and the science-facing
summary (`ScenarioComparison.note`, cluster/web summaries, `sn_number_proxy`)
carries that disclaimer in its text.

## 6. Model Registry and Contracts

`EvolutionModel` = id, name, description, `ModelClassification`
(DERIVED_MODEL / SIMULATION / THEORETICAL / HYPOTHETICAL / SPECULATIVE),
`DataProvenance`, applicable object kinds, parameter `Quantity`s,
`max_valid_gyr` horizon, optional `rate_scale(state, model)` adaptive-
stepping callback. The registry validates on register (id uniqueness and
format, non-empty name/description, finite positive parameters, positive
max_valid), queries return **deterministically sorted** results, and the
engine only ever sees an *effective model* = registry copy with scenario
parameter overrides applied (unknown parameter names are rejected;
unit-bearing overrides are `Quantity`s). Step contract: `(state, dt,
model) → state'` with `state'.cosmic_time_gyr == state.cosmic_time_gyr +
dt` and kind/identity preserved — violations raise
`EvolutionValidationError` or map to `NUMERICAL_INSTABILITY`, never
corrupt the timeline silently.

## 7. Scenarios

`Scenario` = scenario_id, name, description, cosmological_parameters
(finite floats), evolution_parameters (`Quantity`s), provenance,
model_version, projection_class, epoch_boundaries, present_epoch_gyr.
`ScenarioRegistry` is deterministic (sorted `list_ids`), refuses
duplicate ids, and the engine auto-registers any scenario it is handed
(re-registering the SAME definition is idempotent; a conflicting
redefinition is an error). Comparisons (`compare_scenarios`) run both
scenarios through a scratch ledger (nothing is recorded to the main
ledger, nothing is published), then report per-quantity deltas in
deterministic order with an explicit "not observational" note.
`advance_cosmic_epoch` evolves a heterogeneous ensemble with per-kind
model mapping and reports the ensemble epoch before/after.

## 8. Adaptive Timestepping (Explicit Decisions)

Every step produces a `TimestepDecision` (dt_gyr, reason, justification,
requested_dt_gyr, clamped_to_remaining) — there is NO silent clamping
anywhere. Policy order: ceiling `max_dt_gyr` → rate-limited
`base_dt/rate_scale` (floored at `min_dt_gyr`, capped AT the ceiling;
decaying rates lengthen steps only up to max_dt — a regression test pins
this) → event-driven cap lands EXACTLY on scheduled boundaries →
explicit REMAINDER step when the tail is below the floor (sub-floor
integration is recorded as the limitation, never hidden by stretching a
step past the requested time) → NO_INTERVAL for zero. Non-finite inputs,
negative remaining time, events in the past, and scheduled events under a
policy with `allow_event_driven=False` all fail with
`EvolutionNumericalError`. `PerformanceBudget` (max steps/object, total
steps, history samples/object with counted decimation, wall-time
reference, memory reference) is enforced with `BUDGET_EXCEEDED`.

## 9. Epochs

`EpochClassifier` is a pure function of `(EpochInputs, EpochBoundaries)`
with fixed precedence: DARK_ERA (stellar remnants gone) >
BLACK_HOLE_DOMINATED (BH fraction) > DEGENERATE (remnant fraction) >
sSFR threshold vs `declining_sfr_threshold` (STELLIFEROUS /
DECLINING_STAR_FORMATION) > UNKNOWN when inputs are insufficient.
Boundary values are **configuration** (`EpochBoundaries` — config or
scenario, never hard-coded; validated: finite, ordered). Classification
of aggregates uses the external SFR driver (metadata
`sfr_requested_msun_yr`) rather than the bursty instantaneous recycled
rate, so labels are stable. The engine emits `EPOCH_TRANSITION` events on
label changes (UNKNOWN ignored on entry) and refuses epochs it cannot
support honestly.

## 10. Events and the Causal Ledger

`EvolutionEvent` = id (`evo-evt-%08d`), kind, cosmic_time_gyr,
source/resulting object ids, physical_cause (free text, REQUIRED),
model_id, provenance (SIMULATED/THEORETICAL/SPECULATIVE only — REAL_DATA
rejected), causal_parent_event_id (auto-linked per object chain),
JSON-safe metadata. The ledger rejects duplicates, enforces per-object
causal ordering (`CAUSAL_INCONSISTENCY`), supports merge/decimate with
counted decimations, `validate()` → (n_events, n_edges), sorted queries
by object, and a fork guard: evolving a recorded object from a time that
would rewrite its recorded past raises `EvolutionValidationError`
(counterfactual runs belong in `project_future_state`, which uses a
scratch ledger and publishes nothing). Engine-emitted kinds include
STELLAR_TRANSITION, STELLAR_DEATH, POPULATION_TRANSITION, EPOCH_TRANSITION,
STAR_FORMATION_TRANSITION, AGN_TRANSITION, MORPHOLOGY_TRANSITION,
GALAXY_MERGER, BLACK_HOLE_MERGER, COSMIC_STRUCTURE_TRANSITION, CUSTOM.
Merger events are **caller-recorded** (the engine never moves objects):
galaxy mergers preserve identity (progenitors → new resulting object),
BH mergers record the SUM of masses and explicitly disclaim gravitational-
wave mass-loss precision.

## 11. Persistence

Everything is JSON round-trippable: `Quantity`, `EvolutionState`,
`EvolutionEvent`, `PopulationState`, `StarFormationHistory`,
`MetallicityHistory`, `Scenario`, `EvolutionConfig` (tuples↔lists;
non-JSON metadata rejected at save time, not discovered at load time;
`DataProvenance`/`ProjectionClass` restored as enums). `DictPersistenceHook`
and `CorePersistenceHookAdapter` (schema v1 over the REAL
astra.core.persistence) both work; loading into a non-empty ledger is
refused rather than silently merged.

## 12. Integration Adapters and Dependency Reconciliation

PRESENT systems are integrated for real (not mocked in the integration
tests): **Authority** — the engine requires authority
`"evolution.evolve"` per operation and `CoreAuthorityProvider` delegates
to the actual `astra.core.threading` registry + `AuthorityContext`
(denied outside, granted inside, denied after exit — tested against the
real gate); **Events** — `CoreEventPublisherAdapter` publishes each event
on the REAL `EventBus` (handler exceptions are collected, mirroring core
`publish` semantics); **Persistence** — `CorePersistenceHookAdapter`
persists snapshots through the REAL `PersistenceManager`.
ABSENT systems get Protocols plus fail-closed `Missing*` adapters that
raise `EvolutionDependencyError` naming the absent system:
`UniverseEvolutionProvider`/`GalacticProvider`/`MeasurementProvider`
(+ stellar/black-hole/observation/n-body/temporal hooks where the handoff
specified consumption). No module under `astra/evolution/` imports a
nonexistent module (grep-enforced, test-enforced). The full verified
matrix — including what each existing system was and was NOT used for —
is `docs/evolution/DEPENDENCY_MATRIX.md`.

## 13. Resolution Ladder and Error Taxonomy

`EvolutionConfig.resolution` (individual < population < galaxy < cluster <
web) refuses to evolve an object kind FINER than the configured rung
(`INSUFFICIENT_RESOLUTION`) — users buy accuracy/resolution/performance
trade-offs explicitly. Every failure maps to `LimitationState`
(VALIDATION_ERROR, NUMERICAL_INSTABILITY, INSUFFICIENT_RESOLUTION,
UNSUPPORTED_TIMESCALE, OUTSIDE_VALID_RANGE, BUDGET_EXCEEDED,
CAUSAL_INCONSISTENCY, INCOMPATIBLE_MODEL, MISSING_REQUIRED_DATA,
DEPENDENCY_MISSING, INVALID_TIMESTEP, …) through the typed hierarchy
rooted at `EvolutionError`: `EvolutionValidationError`,
`EvolutionNumericalError` (also a `ValueError`),
`EvolutionDependencyError`, `EvolutionAuthorityError` (dual-typed with
the core `AuthorityError`), `EvolutionLimitationError`. No generic
`Exception` is ever raised; NaN/inf targets are rejected up front
(`EvolutionNumericalError`), backward time with
`EvolutionValidationError`.

## 14. Verification and Performance

- `tests/evolution/` — 178 test functions (198 items with
  parametrization), all passing; full repository regression
  **1732 passed** (baseline 1535 + 198 new) with zero pre-existing
  failures.
- **Import integrity**: all 18 modules import warning-free.
- **API listing**: `astra.evolution.__all__` = 92 symbols, every one
  resolvable, no duplicates, no unlisted public package members.
- **Grep sweeps**: no direct imports of absent systems; no
  `print(`/`breakpoint(`/`pdb` in the package; the only
  observation-language hits are explicit disclaimers.
- **Determinism**: double-run of representative star/population/galaxy/
  web scenarios is byte-identical (JSON, 330,927 bytes); interleaved runs
  do not cross-contaminate; event ids strictly sequential
  (`evo-evt-%08d`).
- **Stress**: a trillion-year (1e3 Gyr) population run completes in
  ~0.1 s wall in ~100 ceiling-limited steps; 20,000 populations × 10 Gyr
  ≈ 62 s; near-linear object scaling asserted; state payload bounded
  (< 1 MB) — no dense grids of cosmological extent are ever allocated.

## 15. Usage

```python
from astra.evolution import (
    CosmicEvolutionEngine, EvolutionConfig, Scenario,
    make_star_state, make_galaxy_state, CoreAuthorityProvider,
)
from astra.core.threading import AuthorityContext

engine = CosmicEvolutionEngine(                       # register_builtins=True
    config=EvolutionConfig(resolution="galaxy"),
    authority=CoreAuthorityProvider(),                # or any .require(op)
)
scenario = Scenario(
    scenario_id="baseline", name="Baseline", description="documented defaults",
    present_epoch_gyr=13.8,                           # configuration, not law
)

with AuthorityContext("evolution"):                   # real core authority gate
    star = make_star_state("sun-proxy", 0.0, 1.0)     # 1 Msun at t=0
    out = engine.evolve_object(
        initial_state=star, until_cosmic_time_gyr=15.0,
        model_id="stellar.single_star_lifecycle.v1", scenario=scenario,
    )
    print(out.final_state.phase)                      # REMNANT (white dwarf)
    print(out.epochs)                                 # ((0.0, UNKNOWN), (…, DARK_ERA))

galaxy = make_galaxy_state("g", 0.0, stellar_mass_msun=5e10,
                           gas_mass_msun=2e10, bh_mass_msun=1e7)
projection = engine.project_future_state(             # counterfactual: NOT recorded
    initial_state=galaxy, until_cosmic_time_gyr=300.0,
    model_id="galaxy.one_zone.v1", scenario=scenario,
)
```

Mergers, structure regimes, cluster aggregation, cosmic-web evolution
(with an injected `UniverseEvolutionProvider` or caller
`expansion_ratio_fn`), scenario comparison, persistence round-trips, and
the full error/limitation taxonomy are exercised end-to-end in
`tests/evolution/` — that directory doubles as the executable
specification.
