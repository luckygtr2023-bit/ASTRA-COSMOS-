# ASTRA COSMOS — Long-Term Cosmic Evolution Engine (Phase 21)

**Layer:** Evolution of structures and populations *within* the cosmological background.  
**Position:** `Universe Evolution` → `Galactic / LSS (Phase 20)` → **`Long-Term Cosmic Evolution (this package)`**

This package **never** computes the scale factor from scratch, never redefines galaxy types, never creates a second temporal engine, and never introduces a new coordinate system.  Where a required ASTRA dependency is absent the engine surfaces an explicit `EvolutionDependencyError` / `LimitationState` rather than fabricating data.

---

## 1. Architecture

```
Cosmic Time (Gyr, Temporal & Causality)
    ↓
Evolution Parameters (Scenario + Model)
    ↓
Physical / Population Models (ModelRegistry)
    ↓
Adaptive Time Advancement (TimestepController)
    ↓
Updated Cosmic State (EvolutionState)
    ↓
Events / Transitions (EvolutionEvent)
    ↓
New Cosmic State (history preserved)
```

- **Dependencies consumed via Protocols** (`astra.evolution.integration`):
  - PRESENT: `astra.core` (AuthorityContext, DeterministicRNG, EventBus, SimulationClock), `astra.mathematics`, `astra.celestial` (definitions), `astra.physics`, `astra.temporal`, `astra.blackhole`, `astra.spacetime`, `astra.world`, `astra.nbody`, `astra.orbital`, `astra.relativity`, `astra.motion`, `astra.ingestion`, `astra.destruction`, `astra.theoretical`.
  - PARTIAL: `astra.temporal.observation` (flat-spacetime only), `astra.celestial` (no evolution).
  - ABSENT: Universe Evolution / cosmology, Galactic/LSS (Phase 20), Observatory & Measurement.
  - Every ABSENT dependency is wrapped by an adapter in `astra.evolution.adapters` that raises `EvolutionDependencyError` on any use — never a silent stub.
- **Injection:** the `CosmicEvolutionEngine` receives providers via constructor; unspecified providers default to failing adapters so that callers discover missing capabilities by trying, not by importing a non-existent module.

---

## 2. Data Model

### EvolutionState
Immutable snapshot at a cosmic time:

```python
EvolutionState(
    object_id="galaxy-1",
    cosmic_time_gyr=5.0,
    phase="SPIRAL",                 # or STELLAR phase
    quantities={
        "stellar_mass_msun": Quantity(5e10, "Msun", Provenance.SIMULATED_DATA),
        "sfr_msun_per_yr":   Quantity(3.0,  "Msun/yr", Provenance.SIMULATED_DATA),
    },
    model_id="astra.evolution.galaxy.v1",
    provenance=Provenance.SIMULATED_DATA,   # overall snapshot provenance
    metadata={"morphology_probs": {...}, "regime": ...},
)
```

### EvolutionEvent
Immutable record of a transition:

```python
EvolutionEvent(
    event_id="evt-1",
    kind=EvolutionEventKind.GALAXY_MERGER,
    cosmic_time_gyr=7.2,
    source_object_ids=("galaxy-A", "galaxy-B"),
    resulting_object_ids=("galaxy-M"),
    physical_cause="major merger (mass ratio 1:2)",
    model_id="astra.evolution.galaxy.v1",
    provenance=Provenance.SIMULATED_DATA,
    causal_parent_event_id="evt-0",
)
```

### PopulationState / Histories
- `PopulationState`: reduced-order `(mass_function, age_distribution, remnant_fraction, metallicity)` for populations where per-star simulation is impractical (§2.7, §2.30).
- `StarFormationHistory`: `((t_gyr, SFR), ...)` with `ModelAssumption` on validity (§2.8).
- `MetallicityHistory`: `((t_gyr, Z), ...)`.

### Galaxy / Structure States
Lightweight wrappers `GalaxyState`, `ClusterState`, `CosmicWebState`, `VoidState` that add morphology probability distributions, `StructureRegime` (BOUND / EXPANDING_ASSOCIATION / DISSOLVING, §2.17) and AGN activity (§2.14).

---

## 3. Provenance Model

```
REAL_DATA        → direct observation / catalog value
DERIVED_DATA     → deterministic derivation from REAL_DATA
SIMULATED_DATA   → simulation with real input boundaries
THEORETICAL      → prediction of a well-established theoretical model
HYPOTHETICAL     → prediction of a plausible but unconfirmed model
SPECULATIVE      → far-future extrapolation beyond validated regimes
```

- Every `Quantity` carries `value + unit + provenance + uncertainty + model_id`.
- Every `EvolutionState` and `EvolutionEvent` carries a top-level `Provenance`.
- Far-future outputs (`t > ~50 Gyr` or `SPECULATIVE` scenarios) are **always** tagged `THEORETICAL` / `HYPOTHETICAL` / `SPECULATIVE`, never `REAL_DATA` (§2.39, §2.26).
- Where the celestial layer defines `DataProvenance` (`REAL_DATA`, `DERIVED_DATA`, `SIMULATED_DATA`, `THEORETICAL_MODEL`, `SPECULATIVE_MODEL`), a mapping helper `Quantity.to_data_provenance()` maps `HYPOTHETICAL → SPECULATIVE_MODEL` explicitly.
- Enforcement: model metadata declares its output provenance; the engine never promotes a `SPECULATIVE` scenario to `SIMULATED_DATA`.

---

## 4. Epoch Model

Epochs are **derived from the current simulated state + configured model**, not hard-coded (§2.5 enhanced).

```python
boundaries = EpochBoundaries(
    declining_sfr_threshold=0.1,       # Msun/yr/Mpc^3
    degenerate_remnant_fraction=0.5,  # remnant mass fraction
    black_hole_dominated_fraction=0.7,
    dark_era_luminous_fraction=0.01,
    model_id="my-cosmology",
)
classifier = EpochClassifier(boundaries)
epoch = classifier.classify(
    cosmic_time_gyr=13.8,
    sfr_density=0.015,
    remnant_mass_fraction=0.6,
    bh_mass_fraction=0.05,
    luminous_mass_fraction=0.02,
)
# → EvolutionEpoch.DEGENERATE (or UNKNOWN if SFR/remnant is None)
```

Two scenarios with different cosmological parameters register different `EpochBoundaries`; the classifier is a pure function `f(boundaries, state) → epoch`.

---

## 5. Model Registry

```python
from astra.evolution import ModelRegistry, EvolutionModel, ModelClassification, Provenance

registry = ModelRegistry()
registry.register(
    EvolutionModel(
        model_id="my.galaxy.v1",
        name="My galaxy model",
        description="Reduced-order; no hydro",
        classification=ModelClassification.SIMULATION,
        provenance=Provenance.SIMULATED_DATA,
        parameters={"tau": Quantity(5.0, "Gyr", Provenance.SIMULATED_DATA)},
        assumptions=(
            ModelAssumption(
                statement="Exponential SFH tau=5 Gyr",
                valid_regime="0 < t < 13 Gyr",
                outside_behaviour="hold constant, tag HYPOTHETICAL",
                uncertainty=0.5,
            ),
        ),
        applicable_object_kinds=("GALAXY",),
        applies_to_regimes=("STELLIFEROUS",),
    ),
    step_callable,
)

# Deterministic query — no trial-and-error (§2.37 enhanced)
candidates = registry.query(object_kind="GALAXY", regime="STELLIFEROUS")
# → tuple sorted by model_id, reproducible
```

The top-level `CosmicEvolutionEngine` pre-registers seven reduced-order models:

| model_id | kind | provenance |
|---|---|---|
| `astra.evolution.linear.v1` | generic | SIMULATED_DATA |
| `astra.evolution.stellar.v1` | STAR | SIMULATED_DATA |
| `astra.evolution.galaxy.v1` | GALAXY | SIMULATED_DATA |
| `astra.evolution.cluster.v1` | CLUSTER | SIMULATED_DATA |
| `astra.evolution.web.v1` | COSMIC_WEB | THEORETICAL |
| `astra.evolution.void.v1` | VOID | THEORETICAL |
| `astra.evolution.halo.v1` | HALO | SIMULATED_DATA |

---

## 6. Scenario Model

Scenarios are **configuration objects**, not hard-coded realities (§2.38):

```python
from astra.evolution import Scenario, Provenance, Quantity

baseline = Scenario(
    scenario_id="baseline_LCDM",
    name="Baseline ΛCDM",
    description="Planck-like flat ΛCDM",
    cosmological_parameters={"H0_km_s_Mpc": 67.4, "Omega_m": 0.315, "Omega_L": 0.685},
    evolution_parameters={},
    provenance=Provenance.SIMULATED_DATA,
    model_version="astra.evolution.v1",
)
```

Pre-registered scenarios: `baseline_LCDM` (SIMULATED_DATA), `accelerated_expansion` (THEORETICAL), `far_future_speculative` (SPECULATIVE).  `compare_scenarios` evolves the same initial state under multiple scenarios deterministically (sorted by `scenario_id`).

---

## 7. Timestep Policy

```python
from astra.evolution import TimestepPolicy, AdaptiveTimestepController

policy = TimestepPolicy(base_dt_gyr=0.01, min_dt_gyr=1e-6, max_dt_gyr=1.0)
ctrl = AdaptiveTimestepController(policy)
decision = ctrl.choose(
    remaining_gyr=0.5,
    rate_scale=2.0,               # faster evolution → smaller step
    next_event_gyr=0.25,           # never step past the event
    model_id="astra.evolution.galaxy.v1",
    current_cosmic_time_gyr=13.8,
)
print(decision.dt_gyr, decision.reason, decision.justification)
```

Guarantees (§2.31):

- `dt` ∈ `[min_dt, max_dt]` unless `remaining < min_dt` — then `dt = remaining` with `reason=CONFIGURED_MIN` and no silent clamp.
- Rate-limited: `base_dt / rate_scale` bounded to `[min, max]`.
- Event-driven when `allow_event_driven=True`.
- Every decision carries an explicit `reason` and `justification`; numerical shortcuts are never hidden.

---

## 8. Multi-Resolution

| resolution | description | when to use |
|---|---|---|
| `individual` | per-object (star, BH) | N ≤ 10⁴, need remnant detail |
| `population` | statistical moments (default) | stellar populations (§2.7) |
| `galaxy` | galaxy-integrated SFR, Z, L | galaxy evolution (§2.10) |
| `cluster` | cluster/group properties | cluster mergers (§2.16) |
| `web` | cosmic-web counts / regimes | large-scale (§2.19) |

Set via `EvolutionConfig(resolution="population")`.  The trade-off is explicit: finer resolution → more history samples, smaller timesteps, higher cost; coarser → population averages.  Budget enforcement via `PerformanceBudget`.

---

## 9. Approximations (every reduced-order model documents its domain)

| Model | approximation | domain | failure mode |
|---|---|---|---|
| stellar.v1 MS lifetime `10·M⁻²·⁵ Gyr` | power-law fit | 0.5–20 Msun | `OUTSIDE_VALID_RANGE` outside; uncertainty 0.3 |
| stellar.v1 remnant mapping | IFMR thresholds 8/25 Msun | 0.1–100 Msun | UNKNOWN remnant outside |
| galaxy.v1 SFR exp decline τ=5 Gyr | closed-box | t < 13 Gyr, Milky-Way-like | HYPOTHETICAL beyond |
| galaxy.v1 metal yield 0.02 | instantaneous recycling | Z < 0.05 | cap Z, mark OUTSIDE_VALID_RANGE |
| void.v1 spherical expansion 1%/Gyr | spherical symmetry | isolated void | THEORETICAL + regime flag |
| web.v1 filament coarsening | count-based | linear regime | freeze counts |
| halo.v1 smooth growth 2%/Gyr | abundance-matched | M>1e10 Msun, z<3 | UNSUPPORTED_STRUCTURE outside |

All carry `ModelAssumption` objects with `valid_regime` and `outside_behaviour`; violations raise `EvolutionLimitationError` with a `LimitationState`.

---

## 10. Limitations

| # | Dependency | Status | Phase 21 behaviour |
|---|---|---|---|
| 1 | Core Architecture | PRESENT | direct use |
| 4 | Motion / temporal observation | PARTIAL | flat-spacetime only; curved propagation absent |
| 16 | Universe Evolution / cosmology | **ABSENT** | `scale_factor()` raises `EvolutionDependencyError`; non-expanding models still run |
| 20 | Galactic / LSS (Phase 20) | **ABSENT** | galaxy/cluster/web use reduced-order population models |
| 18 | Observatory & Measurement | **ABSENT** | `measurement` adapter raises; observation via `temporal.observation` only |
| 21 | Celestial stellar evolution | **PARTIAL** | definitions present; lifecycle via stellar.v1 |

When a required model is unavailable Phase 21 exposes `LimitationState.UNSUPPORTED_STRUCTURE` or `MISSING_REQUIRED_DATA` rather than inventing one.

---

## 11. Performance Budget

Declared in `PerformanceBudget` (and copied into `EvolutionConfig`):

```python
PerformanceBudget(
    max_objects_evolved=1_000_000,
    max_events_per_run=100_000,
    max_history_samples_per_object=1024,
    max_wall_time_s_per_gyr=5.0,
    max_memory_mb=2048,
)
```

Measured (on CI, Python 3.11, reduced-order models):

- 1 Gyr with `max_dt=1.0`: ~10 steps, < 10 ms
- 1 000 Gyr with `max_dt=10.0`: ~100 steps, < 10 ms
- History cap: drops oldest entry when `>1024` (documented).

Optimizations never change scientific meaning: population-level models, event-driven steps, caching and lazy evaluation are behind the same model identity and provenance.

---

## 12. Determinism

- No global RNG: callers inject a `DeterministicRNG` stream or use the engine's `rng` provider; the only randomness is via that stream.
- Seeds: `EvolutionConfig.rng_stream_name` + `scenario.model_version` are recorded in diagnostics; identical seeds + configs produce identical `TimestepDecision` sequences and final states.
- Ordering: `ModelRegistry.query` and `ScenarioRegistry.query` return results sorted by `model_id` / `scenario_id`; history is appended in consumption order; event comparison respects causal time ordering with nanosecond tie-breaking.
- Proof: `tests/evolution/test_determinism.py` runs the same evolution twice and asserts bitwise equality.

---

## 13. Scientific Honesty

- No astronomical datasets are embedded, downloaded or faked.  Aliases in `astra.celestial` receptacles and ingestion remains via `astra.ingestion`.
- No far-future prediction is ever tagged `REAL_DATA` or `DERIVED_DATA`.  Late-time outputs from `far_future_speculative` are `SPECULATIVE` and must be presented with their `ModelAssumption` and `Provenance`.
- No arbitrary future events are presented as facts: events require an explicit `physical_cause` and `model_id`.
- No topology-violating claims: Hubble flow is **not** double-counted — velocity decomposition reuses the existing Phase 20 concept (where absent, no flow is applied and the limitation is documented).

---

## 14. Extension Points

- **New model**: implement a `(state, dt, model) → state` callable, wrap with `EvolutionModel` metadata, and `registry.register(model, step)`.
- **New scenario**: build a `Scenario` with `cosmological_parameters` + `evolution_parameters` (as `Quantity` objects) and `registry.register(scenario)`.
- **New provider**: implement the Protocol in `integration.py` (e.g. `UniverseEvolutionProvider`) and pass to `CosmicEvolutionEngine(universe=my_provider)`.  Missing adapters self-document the gap.

---

## 15. Known Limitations and Future Work

**Defects (must fix before next phase):** none known; full regression passes.

**Documented limitations (acceptable):**

- Universe expansion not available without a provider — non-expanding evolution is correct but incomplete for precision cosmology.
- Phase 20 galactic structure absent — high-resolution hydro + feedback require a future provider.
- Curved light propagation absent — lookback via `temporal.observation` is flat-spacetime only.
- Chemical enrichment scalar Z — no yield-table distribution.
- Dark matter halo growth coarse-grained — no subhalo particle physics.

Future phases should inject `UniverseEvolutionProvider` and `GalacticProvider` when they become available; no engine rewrite is required (Protocol-based inversion).

