# PHASE 21 — DEPENDENCY RECONCILIATION MATRIX (verified 2026-09-15)

Verified against the actual repository at commit f6f88425e3337c07555dd89f92d008470a253797
(branch arena/01a0a53a-astra-cosmos). Every row was checked by reading the real
module files, not by trusting the handoff document.

| #  | Spec claims exists                      | Actual module path (verified)                                   | Actual public API (verified, subset used)                                                                                     | Status   | Phase 21 uses it for |
|----|-----------------------------------------|------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|----------|----------------------|
| 1  | Core Architecture                       | astra.core (engine, events, rng, threading, persistence, ids)    | AuthorityContext.require_authority, EventBus.publish, RNGStream.next_float, PersistenceManager/Snapshot, Event/EventId          | PRESENT  | authority gate, event publishing, deterministic RNG, snapshot persistence |
| 2  | Mathematics                             | astra.mathematics (validation, numerical, constants, statistics) | require_finite, require_non_negative, require_positive, require_in_range, DEFAULT_RTOL/ATOL                                    | PRESENT  | input validation, numerical conventions |
| 3  | Coordinates / Spatial                   | astra.core.coords, astra.world.spatial                           | CoordinateFrame, OriginRebaser; World.index_object                                                                             | PRESENT  | NOT extended: Phase 21 introduces no new coordinate system (see limitation L6) |
| 4  | Motion                                  | astra.motion                                                     | MotionSystem, MotionState, integrators                                                                                         | PRESENT  | not consumed (no kinematics in Phase 21) |
| 5  | Physics                                 | astra.physics                                                    | constants (G, tolerances), energy, momentum                                                                                    | PRESENT  | conventions only; no forces computed |
| 6  | Orbital Mechanics                       | astra.orbital                                                    | elements, propagation, maneuvers                                                                                               | PRESENT  | not consumed |
| 7  | N-Body Dynamics                         | astra.nbody                                                      | NBodySystem, NBodyBody, gravity                                                                                                | PRESENT  | not consumed (no cluster N-body bodies exist in-repo; see L2) |
| 8  | Spacecraft Physics                      | astra.spacecraft                                                 | engines, rocket, dynamics                                                                                                      | PRESENT  | not consumed |
| 9  | Relativity                              | astra.relativity                                                 | SPEED_OF_LIGHT, lorentz_factor, four-vectors                                                                                   | PRESENT  | referenced for SI second/c conventions via temporal interop |
| 10 | Black-Hole Physics                      | astra.blackhole                                                  | create_black_hole, BlackHoleState, get_schwarzschild_boundaries                                                                | PRESENT  | referenced: BH geometry stays in astra.blackhole; Phase 21 tracks population-level BH mass growth as its own reduced-order state |
| 11 | Spacetime Physics                       | astra.spacetime                                                  | MetricField, geodesics, causality                                                                                              | PRESENT  | not consumed |
| 12 | Temporal & Causality                    | astra.temporal                                                   | TemporalState (5 time quantities, SI s), TemporalClock, causal ordering, observation/lookback                                   | PRESENT  | time semantics interop (Gyr<->s), causal ordering conventions; no new time engine |
| 13 | Real Astronomical Data Ingestion        | astra.ingestion                                                  | pipeline, database, query, validation                                                                                          | PRESENT  | provenance flows through the canonical astra.celestial.provenance taxonomy; no ingestion call needed |
| 14 | World / Scene                           | astra.world                                                      | World, hierarchy, spatial                                                                                                      | PRESENT  | not consumed |
| 15 | Destruction & Impact                    | astra.destruction                                                | DestructionSystem, integration protocols + adapters pattern                                                                    | PRESENT  | structural template for protocols/adapters/errors/persistence |
| 16 | Universe Evolution                      | (none found; repo-wide search: no scale factor / FLRW engine)    | -                                                                                                                              | ABSENT   | UniverseEvolutionProvider Protocol + MissingUniverseEvolution adapter; Phase 21 NEVER computes the background itself |
| 17 | Observation & Cosmic History            | astra.temporal.observation (lookback/ObservedState for worldlines)| ObservedState, observe semantics                                                                                              | PARTIAL  | ObservationProvider Protocol; finite-light-propagation semantics preserved by never bypassing astra.temporal.observation; no cosmological observation layer exists (see L4) |
| 18 | Observatory & Measurement               | (none found)                                                     | -                                                                                                                              | ABSENT   | MeasurementProvider Protocol + MissingMeasurement adapter |
| 19 | Extreme Spacetime & Travel              | astra.theoretical                                                | ScientificClassification, warp/wormhole/whitehole metrics, energy conditions                                                   | PRESENT  | not consumed by Phase 21 |
| 20 | Galactic / Large-Scale Structure (P20)  | (none found; no galaxy/cluster/web objects anywhere in repo)     | -                                                                                                                              | ABSENT   | GalacticProvider Protocol + MissingGalactic adapter; galaxy/cluster/web states live in Phase 21's own explicitly-tagged evolution-state containers (see L2); no VelocityDecomposition exists to reuse, and Phase 21 computes no velocities, so Hubble flow cannot be double-counted |
| 21 | Celestial / Stellar                     | astra.celestial                                                  | CelestialObject/Star, ObjectCategory (incl. WHITE_DWARF, NEUTRON_STAR, BLACK_HOLE, GALAXY, AGN), CelestialProperties.metallicity, DataProvenance | PARTIAL  | taxonomy alignment for lifecycle phases and remnant kinds; stars are immutable definitions, so lifecycle STATE lives in Phase 21; no stellar-evolution physics exists in-repo (see L3) |

## Consequences for the design

- L1 (Universe Evolution ABSENT): scale factor, Hubble rate, lookback time are
  ONLY available through the injected UniverseEvolutionProvider. Without it,
  every expansion-dependent feature refuses explicitly with
  EvolutionDependencyError. Phase 21 contains no FLRW mathematics.
- L2 (Phase 20 ABSENT): no Galaxy/Cluster/Supercluster/CosmicWeb objects exist.
  Phase 21 therefore defines reduced-order STATE containers (EvolutionState with
  documented quantity keys) for these kinds, tagged SIMULATED_DATA, and exposes
  the GalacticProvider Protocol so a future Phase 20 can be bound in without
  touching the engine.
- L3 (no stellar astrophysics layer): lifecycle transitions use documented
  reduced-order models (power-law mass-lifetime, mass-luminosity, configurable
  remnant thresholds) registered in the model registry with explicit
  ModelAssumption entries, uncertainties, and DERIVED_MODEL classification.
- L4 (Observation PARTIAL): lookback exists for recorded worldlines only;
  observation of evolution states requires the ObservationProvider.
- L5 (no Observatory & Measurement): MeasurementProvider Protocol only.
- L6 (coordinates): Phase 21 evolves no positions at all; all evolution is in
  mass/energy/population/structure space, so no coordinate authority is touched
  and none is duplicated.

Authority, events, RNG, and persistence are bound to the REAL core systems via
adapters (astra.evolution.adapters), following the astra.destruction pattern.
