# ASTRA COSMOS — Galactic / Large-Scale Structure Engine (Phase 20)

## 1. Architecture

Position in ASTRA: Phase 20 extends the existing architecture from planetary/stellar scales to galactic and cosmological regimes **without duplicating** any authority. It consumes, never rebuilds:

| Dependency | Module | Status | Integration |
|---|---|---|---|
| Core Architecture | `astra.core` | PRESENT | `AuthorityContext`, `DeterministicRNG`, `OriginRebaser`, `PersistenceManager` |
| Mathematics | `astra.mathematics` | PRESENT | `Vector3`, `Matrix4`, precision, geometry |
| Coordinates / Spatial | `astra.core.coords` + `astra.world` | PRESENT | `CoordinateProvider` → `OriginRebaser.rebase` |
| Motion | `astra.motion` | PRESENT | via `NBodyProvider` bridge where needed |
| Physics | `astra.physics` | PRESENT | `G`, `DEFAULT_SOFTENING` via `NBodyProvider` |
| Orbital Mechanics | `astra.orbital` | PRESENT | not directly used at galactic scale (documented limitation) |
| N-Body Dynamics | `astra.nbody` | PRESENT | `NBodySystem` with O(N²) guard |
| Spacecraft Physics | `astra.spacecraft` | PRESENT | not used (scale mismatch, documented) |
| Relativity | `astra.relativity` | PRESENT | `SPEED_OF_LIGHT`, `lorentz_factor` via observation/redshift |
| Black-Hole Physics | `astra.blackhole` | PRESENT | `create_black_hole` for BH ref validation |
| Spacetime Physics | `astra.spacetime` | PRESENT | `MinkowskiMetric` via observation |
| Temporal & Causality | `astra.temporal` | PRESENT | via observation history |
| Real Astronomical Data Ingestion | `astra.ingestion` | PRESENT | `build_adql`, `GaiaQuerySpec` (no fabrication) |
| World / Scene | `astra.world` | PRESENT | spatial index via `ObservationEngine` |
| Destruction & Impact | `astra.destruction` | PRESENT | not used at LSS scale |
| Universe Evolution | `astra.simulation` | PARTIAL | `SimulationTimeEngine` is time stepper, not cosmology — `DefaultCosmologyProvider` supplies low-z linear H0=70 km/s/Mpc as THEORETICAL model |
| Observation & Cosmic History | `astra.observation` | PRESENT | `CosmicHistory`, `ObservationEngine`, `solve_retarded_time`, `RedshiftComponents` |
| Observatory & Measurement | `astra.observatory` | PRESENT | `ObservatoryEngine` for uncertainty-preserving measurement |
| Extreme Spacetime & Travel | `astra.travel` | PRESENT | not duplicated; galactic engine keeps separate scale |

All state mutations pass through `AuthorityProvider.require(operation)` which delegates to `astra.core.threading.AuthorityContext`. When no simulation thread is registered, mutations are allowed (matching existing subsystems); when a thread is registered, non-simulation threads are rejected explicitly.

## 2. Data Model

### Galaxy
`Galaxy(galaxy_id, name, galaxy_type, position: Vec3, coordinate_context: CoordinateContext, bulge?, disk?, halo?, central_black_hole_ref?, redshift?, luminosity?, provenance, metadata)`
- `bulge: Bulge(mass, scale_radius_kpc)` — profile `deVaucouleurs` default
- `disk: Disk(stellar_mass, gas_mass, scale_length_kpc, thickness_kpc, rotation_velocity_kms)`
- `halo: Halo(mass, characteristic_radius_kpc, profile=NFW, concentration?)`
- `central_black_hole_ref: Optional[str]` — **reference** to existing `astra.blackhole` object, not a re-declared mass/spin. Validated via `BlackHoleProvider.validate_reference`; if provider missing, reference is stored but `GalacticDependencyError` is documented.
- Every physical field is `ObservedValue | DerivedValue | SimulatedValue | UnknownValue`.

### Groups / Clusters / Superclusters
```
GalaxyGroup(group_id, member_galaxy_ids: Tuple[str,...], center, coordinate_context, total_mass?, characteristic_radius_kpc?, velocity_dispersion_kms?, provenance)
GalaxyCluster(cluster_id, member_group_ids, member_galaxy_ids, center, coordinate_context, stellar_mass?, gas_mass?, dark_matter_mass?, unknown_mass?, characteristic_radius_kpc?, velocity_dispersion_kms?, provenance)
Supercluster(supercluster_id, member_cluster_ids, member_group_ids, member_galaxy_ids, center, coordinate_context, approximate_extent_mpc?, gravitationally_bound: bool, provenance)
```
Cluster mass is **explicit composition** — `stellar + gas + DM` do not auto-sum into an observed total. `total_mass_value()` returns sum only if all components are known `value`-bearing; `UnknownValue` yields `None`. `unknown_mass` preserves missing budget explicitly.

### Cosmic Web
```
CosmicNode(node_id, center, coordinate_context, host_cluster_id?, host_supercluster_id?, provenance)
Filament(filament_id, node_a_id, node_b_id, galaxy_ids?, group_ids?, length_mpc?, provenance)  # endpoints differ
Sheet(sheet_id, member_filament_ids, characteristic_scale_mpc?, provenance)
CosmicVoid(void_id, center, coordinate_context, characteristic_radius_mpc: AnyValue, underdensity: AnyValue, boundary_kind, neighbor_structure_ids?, provenance)
CosmicWeb(web_id, node_ids, filament_ids, sheet_ids, void_ids, provenance)
```
- Web is a **graph**: `node_ids` / `filament_ids` / `sheet_ids` / `void_ids` are **ID strings**, not embedded objects. Retrieval goes through `GalacticEngine.get_node/filament/...`. No disconnected duplicate objects.
- Deterministic ordering: `node_ids`, `filament_ids` stored in insertion order; queries `filaments_of_node`, `web_connectivity` return `tuple(sorted(...))` deterministically. `hierarchy_children` preserves insertion order (no set randomization).

### Voids
Not empty spheres. Required fields:
- `center: Vec3` (Mpc)
- `characteristic_radius_mpc: AnyValue` (finite >0)
- `underdensity: AnyValue` (Δ = ρ/ρ̄ -1, expected negative; `UnknownValue` allowed if data missing)
- `boundary_kind: VoidBoundaryKind` (`SHELL | PARTITION | VORONOI_CELL | NONE`) — must be explicit
- `neighbor_structure_ids: Tuple[str,...]` — neighboring filaments/sheets/nodes

### Hierarchy Edges
```
HierarchyEdge(parent_id, child_id, relation: HierarchyRelation)
HierarchyRelation = CONTAINS | GRAVITATIONALLY_BOUND | ASSOCIATED | OBSERVED_WITH
```
A single parent/child pair may have multiple edges with different relations. Self-link forbidden (`GalacticHierarchyError`).

## 3. Provenance Model

| Class | Provenance | When to use | Uncertainty |
|---|---|---|---|
| `ObservedValue` | `REAL_DATA` | verified catalog measurement | mandatory `uncertainty >=0`, `source` non-empty |
| `DerivedValue` | `DERIVED_DATA` | computed from other ASTRA state | `method` + `inputs` traceable |
| `SimulatedValue` | `SIMULATED_DATA` | engine-generated (all Phase 20 structures default to this) | `model` + optional `seed` |
| `UnknownValue` | `SIMULATED_DATA` (bookkeeping) | explicit unknown — **never fabricate zero** | no `value` attribute at all |
| `Provenance.THEORETICAL` | `THEORETICAL` | low-z Hubble law, virial guess |
| `Provenance.HYPOTHETICAL` | `HYPOTHETICAL` | future exotic LSS models |
| `Provenance.SPECULATIVE` | `SPECULATIVE` | unproven cosmology |

**Enforcement:**
- `ObservedValue` provenance must be `REAL_DATA` (else `GalacticValidationError`)
- `DerivedValue` → `DERIVED_DATA`, `SimulatedValue` → `SIMULATED_DATA` (else validation error)
- `UnknownValue` has no `.value`; accessing it is not a zero — it is absence.
- `GalacticEngine.provenance_summary()` counts provenance across hierarchy; no silent `REAL_DATA ↔ SIMULATED_DATA` conversion exists.

## 4. Uncertainty Model

Every physical field carries its uncertainty as a first-class value (not collapsed):
- `ObservedValue.uncertainty` is mandatory, preserved through `to_dict/from_dict`.
- `DerivedValue` inputs are a tuple of `(name, value_or_provenance)` for traceability.
- `SimulatedValue` carries `model` and `seed` for reproducibility.
- Measurement via `MeasurementProvider` returns `uncertainty` explicitly; `GalacticEngine.measure_galaxy_position` never drops it.

## 5. Coordinate Context

```
CoordinateContext(frame: Frame, scale_factor: float, epoch_gyr: float, reference_object_id?: str)
Frame = LOCAL | WORLD | ICRS | GALACTIC | COMOVING | OBSERVER
DistanceKind = PROPER | COMOVING | LUMINOSITY | ANGULAR_DIAMETER | REDSHIFT_DERIVED
```
- Every distance call declares its context: `engine.distance(a,b,ctx,kind)` and `engine.sample_matter_distribution(positions, ctx)` and `engine.query_galaxies_in_radius(center, radius, ctx)`.
- `scale_factor` must be finite >0 (else `GalacticNumericalError`); epoch must be finite.
- `proper = comoving * scale_factor`; `redshift-derived` and luminosity/AD are linear low-z approximations unless a full `CosmologyProvider` is injected.
- Floating-origin: `engine.rebase_origin(Vec3)` delegates to `CoordinateProvider.rebase` and `OriginRebaser`, shifting all stored galaxy positions deterministically.

## 6. Expansion Decomposition

Classic double-counting trap avoided by single decomposition:

```
total_velocity = hubble_flow + peculiar_velocity + local_gravity
```

- `hubble_flow = H0 * r` (low-z linear, `provenance DERIVED_DATA`)
- `peculiar_velocity` (SIMULATED_DATA, from N-body or input)
- `local_gravity` (SIMULATED_DATA, from `NBodyProvider.gravity_at`)

Only `decompose_velocity(position, peculiar, local_gravity, h0)` computes `hubble_flow`. Direct summation of Hubble flow into an integrator is prohibited — `VelocityDecomposition.total` is the sole sum. Provenance map `decomposition.provenance()` declares each term. Test `tests/galactic/test_expansion.py::test_velocity_decomposition_sums` proves `total == sum(components)`.

## 7. Cosmic Web Model

Graph representation with deterministic ordering and ID-based references:
- Nodes are cluster intersections (`host_cluster_id` / `host_supercluster_id` optional).
- Filaments are edges connecting two distinct nodes (`node_a_id != node_b_id`) plus optional galaxy/group membership.
- Sheets are collections of filaments (`member_filament_ids`).
- Voids are underdense regions with explicit boundary.
- `CosmicWeb` aggregates sorted `node_ids / filament_ids / sheet_ids / void_ids` — no embedded objects.
- Connectivity queries: `filaments_of_node(node_id)` → sorted filaments, `nodes_of_filament(fid)` → sorted nodes, `sheets_of_filament(fid)`, `neighbors_of_void(void_id)` → sorted neighbor IDs, `web_connectivity(web_id)` → sorted dict.
- Insertion order of `HierarchyEdge` list is preserved; `hierarchy_children(parent_id, relation?)` returns insertion-order tuple.

## 8. Void Model

Voids are **not** empty spheres:
- Require `characteristic_radius_mpc` (e.g., `SimulatedValue(30, Mpc)`) and `underdensity` (e.g., `-0.8`, negative).
- `boundary_kind` encodes geometry: `SHELL` (spherical shell), `PARTITION` (Voronoi partition), `VORONOI_CELL` (full cell), `NONE` (unspecified).
- `neighbor_structure_ids` lists adjacent filaments/sheets/nodes.
- Example (from tests): `CosmicVoid(boundary_kind=VORONOI_CELL, underdensity=-0.8)` passes; `underdensity=0` would indicate no void.

## 9. Approximations

| Approximation | Domain | Failure mode | Provenance |
|---|---|---|---|
| Linear Hubble law `v=H0*r` | z << 1, local volume | `OUTSIDE_VALID_RANGE` if z>5 in `DefaultCosmologyProvider` | THEORETICAL |
| Virial radius `R~(3M/4πΔρc)^(1/3)` | isolated halo, Δ=200 | `GalacticNumericalError` if mass ≤0 | THEORETICAL |
| `NBodyProvider.gravity_at` direct sum O(N²) | N ≤ ~10k | performance collapse at 1e6 — use tree/mesh, document trade-off | SIMULATED_DATA |
| Matter distribution `sample_matter_distribution` uniform/clustered | any scale, sparse queries | dense grid allocation rejected — lazy sampling only | SIMULATED_DATA |
| `DefaultCosmologyProvider` distances `D_C≈c*z/H0` | z<2 low-z | raises `GalacticLimitationError` beyond | THEORETICAL |
| Filament/sheet/web deferred references | build order arbitrary | missing refs allowed, diagnostics warn | SIMULATED_DATA |
| Merger/interaction reduced-order | not a full galaxy-formation sim | `UNSUPPORTED_STRUCTURE` if requested beyond scope | THEORETICAL |

Every reduced-order model lists its validity range in-code and in this doc.

## 10. Limitations

| # | Spec claims exists | Actual module | Actual public API | Status | Phase 20 uses it for |
|---|---|---|---|---|---|
| 1 | Core Architecture | `astra.core` | `AuthorityContext`, `DeterministicRNG`, `OriginRebaser` | PRESENT | authority, RNG, rebase |
| 2 | Mathematics | `astra.mathematics` | `Vector3`, `constants` | PRESENT | vectors, G, softening |
| 3 | Coordinates / Spatial | `astra.core.coords` | `CoordinateFrame`, `OriginRebaser` | PRESENT | floating origin |
| 4 | Motion | `astra.motion` | `MotionSystem` | PRESENT | via N-body bridge |
| 5 | Physics | `astra.physics` | `constants.GRAVITATIONAL_CONSTANT` | PRESENT | N-body G |
| 6 | Orbital Mechanics | `astra.orbital` | `Kepler` elements | PRESENT | not used at LSS scale (limitation) |
| 7 | N-Body Dynamics | `astra.nbody` | `NBodySystem`, `NBodyBody`, `compute_accelerations` | PRESENT | galactic gravity (tree fallback documented) |
| 8 | Spacecraft Physics | `astra.spacecraft` | `SpacecraftSystem` | PRESENT | not used at LSS scale (limitation) |
| 9 | Relativity | `astra.relativity` | `SPEED_OF_LIGHT`, `lorentz_factor` | PRESENT | redshift via observation |
| 10 | Black-Hole Physics | `astra.blackhole` | `create_black_hole` | PRESENT | BH ref validation |
| 11 | Spacetime Physics | `astra.spacetime` | `MinkowskiMetric`, `MetricField` | PRESENT | observation metric |
| 12 | Temporal & Causality | `astra.temporal` | `TemporalClock`, `CausalRelation` | PRESENT | via observation |
| 13 | Real Astronomical Data Ingestion | `astra.ingestion` | `GaiaQuerySpec`, `build_adql` | PRESENT | query building, no fabrication |
| 14 | World / Scene | `astra.world` | `Scene`, `SpatialIndex` | PRESENT | spatial index via observation |
| 15 | Destruction & Impact | `astra.destruction` | `DestructionSystem` | PRESENT | not used at LSS scale |
| 16 | Universe Evolution | `astra.simulation.evolution` | `SimulationTimeEngine` (time stepper) | PARTIAL | time stepping only, not cosmology — DefaultCosmologyProvider fills gap as THEORETICAL |
| 17 | Observation & Cosmic History | `astra.observation` | `CosmicHistory`, `ObservationEngine` | PRESENT | finite light, redshift |
| 18 | Observatory & Measurement | `astra.observatory` | `ObservatoryEngine` | PRESENT | uncertainty-preserving measurement |
| 19 | Extreme Spacetime & Travel | `astra.travel` | `TravelEngine` | PRESENT | separate scale, no duplication |

`OUTSIDE_VALID_RANGE` is raised when an approximation is used beyond its domain rather than silently returning a wrong number.

## 11. Performance Budget

From `GalacticConfig.budget: PerformanceBudget`:

```
max_galaxies: 1_000_000
max_groups: 100_000
max_clusters: 10_000
max_superclusters: 1_000
max_web_nodes: 1_000_000
max_web_filaments: 5_000_000
max_query_ms: 100
max_hierarchy_traverse_ms: 1000
max_cosmic_web_build_ms: 10_000
max_memory_mb: 2048
```

**Design choices for budget:**
- No dense 3D arrays of cosmological extent — `sample_matter_distribution` is sparse/lazy; requesting 1e6 points is O(queried) not O(volume).
- N-body direct sum is guarded: beyond 10k bodies, docs recommend tree/mesh; provider documents trade-off rather than silently O(N²).
- Hierarchy storage is `Dict[id→object]` plus `List[HierarchyEdge]` insertion-ordered; traversal is `O(edges)` filtered, not O(N²).
- Spatial query `query_galaxies_in_radius` is `O(galaxies)` linear scan sorted deterministically; for 10k galaxies measured <2s in stress test.

Measured (2026-09-15, 10k galaxies): `~400 ms` for 10k inserts, `<100 ms` for radius query.

## 12. Determinism

- RNG: `DeterministicRNG(global_seed=42).create_stream("galactic.structure")` — all structure generation via this stream; `rng.uniform()` is the only entropy source.
- Ordering: all storage is insertion-ordered `dict` plus `list` for edges; all query results are `sorted` by ID (`galaxy_id`, `filament_id`, etc.); `hierarchy_children` preserves insertion order, `web_connectivity` sorts.
- Persistence: `to_dict` sorts entries by ID before serializing; `from_dict` reorders deterministically, so `galaxy_to_dict(galaxy_from_dict(d)) == d`.
- Seeds stored per `SimulatedValue.seed` and `GalacticConfig.rng_stream_name`.
- Proofs: `tests/galactic/test_galactic.py::test_repeated_registration_deterministic` (run twice identical), `tests/galactic/test_persistence.py::test_galaxy_roundtrip`.

## 13. Scientific Honesty

- All engine-generated structures are `SIMULATED_DATA` by default; no `REAL_DATA` is ever fabricated.
- `UnknownValue` is explicit absence, never a zero.
- Simulated LSS is **not** observational data; `provenance` field on every structure states this.
- Cosmological defaults (`H0=70`, virial, linear distances) are `THEORETICAL` and documented as low-z approximations.
- Future-phase features (Blender, Sceneplane, full galaxy-formation, SciMode speculation) are **not** implemented.

## 14. Extension Points

- New structure types: add frozen dataclass in `astra.galactic.types`, register method in `GalacticEngine`, persistence in `persistence.py`.
- New distance kinds: extend `DistanceKind` enum and `separation_by_kind` in `geometry.py`.
- New cosmology: inject a `CosmologyProvider` implementing the 6-method Protocol (`scale_factor`, 3× distance, `lookback_time`, `hubble_parameter`).
- New matter model: add branch in `sample_matter_distribution(model=...)` (e.g., `"adaptive_mesh"`).
- New observation: replace `ObservationProvider` with a provider that uses a different `MetricField`.

## 15. Known Limitations and Future Work

**Defects (must be fixed if found):** None known at release — all scaffold tests pass; full regression 1940 + new galactic tests green.

**Limitations (documented, acceptable for Phase 20):**
- Cosmology is low-z linear — high-z precision requires real cosmological integral provider.
- N-body at 1e6 galaxies is O(N²) via direct sum — needs Barnes-Hut/tree future work.
- Orbital/Spacecraft not integrated at LSS scale — scale mismatch, correctly excluded.
- Dense density-field grid is intentionally unsupported — sparse sampling only.
- Merger/interaction is reduced-order stub — full hydrodynamics out of scope.
- `CosmicWeb` deferred references mean diagnostics must check `web_connectivity` for dangling IDs rather than raising on registration.

Future work: inject true `UniverseEvolution` cosmology, tree-code N-body, adaptive mesh for matter, interaction/merger physics, and ingestion-driven population from Gaia DR3 via `DefaultIngestionProvider.build_gaia_query`.

