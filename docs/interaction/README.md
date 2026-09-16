# ASTRA COSMOS — Interaction & Exploration Engine (Phase 23)

**Layer:** Player/operator interface to the simulation — validates, delegates, records.  
**Position:** `Data / Engines (Core, World, Celestial, Spacecraft, Temporal, Theoretical, Scientific)` → **`Interaction & Exploration (this package)`** → `Provenance / History / Discovery`

Interaction is **not** a game abstraction that bypasses physics. Every movement, observation, travel, or temporal operation is delegated to the authoritative subsystem that owns that physics.

Forbidden APIs (`grep -rn` must find zero definitions in `astra/interaction`):
```
teleport_to_planet, instant_travel, ignore_physics, set_position_directly,
fake_discovery, instant_time_jump, bypass_causality
```

---

## 1. Exploration Model

```python
from astra.interaction import ExplorerIdentity, ExplorationState, NavigationContext, ScaleLevel
from astra.scientific import Classification

explorer = ExplorerIdentity(explorer_id="player-1", display_name="Operator A",
                            classification=Classification.SIMULATED_DATA)
state = ExplorationState(
    explorer=explorer,
    tick=42,
    simulation_time_s=1_000_000.0,
    proper_time_s=999_900.0,
    navigation=NavigationContext(scale=ScaleLevel.STELLAR_SYSTEM, frame_id="frame_world", origin_hint=(0,0,0)),
    active_target_id="star-1",
    active_spacecraft_id="ent-sc-1",
    classification=Classification.SIMULATED_DATA,
)
state.to_dict()  # serializable, deterministic, provenance-aware
```

Fields are **references** to authoritative state (entity id, frame id, world node id), never copies of physics vectors. `ExplorationState` is mutable for live use but exposes `to_dict`/`from_dict` for persistence and replay.

---

## 2. Interaction System

All player actions are explicit `InteractionAction` events, not scattered UI callbacks:

```python
from astra.interaction import InteractionAction, InteractionType

act = InteractionAction(
    action_id="ia-000001",
    type=InteractionType.OBSERVE,      # INSPECT | OBSERVE | MEASURE | APPROACH | DEPART | ENTER | LEAVE
    tick=10,                            # SELECT | TRACK | FOLLOW | INITIATE_TRAVEL | PAUSE | RESUME
    target_id="t-star-1",               # CHANGE_PERSPECTIVE | CHANGE_FRAME | SPACECRAFT_COMMAND
    parameters={"instrument": "spectrometer"},  # WORLD_INTERACT | EXPERIMENT | RECORD_DISCOVERY | NAVIGATE | SET_SCALE
    frame_id="frame_world",
    classification=Classification.SIMULATED_DATA,
)
```

`InteractionResult` is structured: `{success, error_code, error_message, data, classification, warnings}` — never silent.

Available `InteractionType` (20 values): `INSPECT, OBSERVE, MEASURE, APPROACH, DEPART, ENTER, LEAVE, SELECT, TRACK, FOLLOW_TRAJECTORY, INITIATE_TRAVEL, PAUSE, RESUME, CHANGE_PERSPECTIVE, CHANGE_FRAME, SPACECRAFT_COMMAND, WORLD_INTERACT, EXPERIMENT, RECORD_DISCOVERY, NAVIGATE, SET_SCALE`.

---

## 3. Player Control

```python
from astra.interaction import ControlInput, ThrottleCommand, TrajectoryControl, OrientationCommand, CameraControl

ctrl = ControlInput(
    throttle=ThrottleCommand(throttle=0.7, duration_s=10.0, engine_id="eng-main"),
    trajectory=TrajectoryControl(delta_v=(100,0,0), frame_id="world"),
    orientation=OrientationCommand(yaw_rad=0.05),
    camera=CameraControl(position_offset=(10,0,0), fov_deg=70),
)
translator = ControlTranslator(spacecraft_provider=spacecraft_system, motion_provider=motion_system)
cmds = translator.translate("ent-sc-1", ctrl, tick=10)
# -> {"entity_id": "ent-sc-1", "commands": [{"type": "throttle", ...}, ...]}
# Caller must submit via CommandDispatcher / SpacecraftSystem; translator never mutates physics directly.
```

Forbidden: direct `set_position_directly` or `ignore_physics`. All commands go through `SpacecraftSystem.start_finite_burn` / `apply_impulsive` / `MotionSystem`.

---

## 4. Navigation (Hierarchical, No Second Coordinate System)

Scales (§8):

```
LOCAL_ENVIRONMENT → PLANETARY_SYSTEM → STELLAR_SYSTEM → GALACTIC_REGION → GALAXY
→ GALAXY_GROUP → CLUSTER → SUPERCLUSTER → COSMIC_WEB → LARGE_SCALE_UNIVERSE
```

```python
from astra.interaction import NavigationService, NavigationRequest, ScaleLevel
from astra.core.coords import FrameRegistry, OriginRebaser
from astra.world import World

nav = NavigationService(frame_registry=frame_registry, world=world, origin_rebaser=rebaser)
req = NavigationRequest(
    request_id="nav-001",
    from_scale=ScaleLevel.PLANETARY_SYSTEM,
    to_scale=ScaleLevel.STELLAR_SYSTEM,
    target_reference="star-1",  # authoritative id
    frame_id="frame_world",
)
result = nav.execute(req)  # resolves via World SceneGraph / Hierarchy / SpatialIndex
# result.world_position, result.rebase_applied, result.steps
# Origin rebase (representation change, not teleport) is applied only for large jumps (≥3 scale steps)
```

Uses `FrameRegistry`, `OriginRebaser`, `WorldHierarchy`, `SceneGraph`, `SpatialIndex` — never introduces global float coordinates.

---

## 5. Travel Integration (Delegated)

```python
from astra.interaction import TravelRequest, TravelMethod, TravelConstraints, DelegatingTravelService
from astra.scientific import Classification

travel = DelegatingTravelService(provider=authoritative_travel_engine)  # wraps Theoretical + Spacetime + Temporal
req = TravelRequest(
    request_id="travel-001",
    method=TravelMethod.WORMHOLE,  # CONVENTIONAL_RELATIVISTIC | STRONG_GRAVITY_TRAJECTORY | WORMHOLE | WARP | TEMPORAL_DISPLACEMENT | SPECULATIVE
    target_id="wormhole-throat-1",
    classification=Classification.SPECULATIVE,  # wormhole requires HYPOTHETICAL/SPECULATIVE
    constraints=TravelConstraints(requires_energy_j=1e20, requires_stability=0.8, causal=True),
)
result = travel.initiate(req)  # validates classification, never strengthens, delegates physics
# result.proper_time_s, coordinate_time_s, energy_j, stability, causal_status, warnings
```

No travel physics is implemented here. `DelegatingTravelService` validates `ClassificationOrder` (speculative methods require weaker classification) and delegates `can_travel`/`initiate` to the injected `TravelProvider`. `NullTravelProvider` fails explicitly when no engine is injected.

Respects: proper time / coordinate time / observer time / reference frames / causal status / energy / stability / classification.

---

## 6. Observation & Discovery (Finite Light)

```python
from astra.interaction import ObservationContext, ObservationService, Discovery
from astra.spacetime.events import Worldline, SpacetimeEvent
from astra.temporal.observation import observe as temporal_observe

obs_svc = ObservationService(observation_provider=temporal_observe)  # finite flat-spacetime null propagation
ctx = ObservationContext(observer_id="player", observer_position=(3e8,0,0), observation_time_s=12.0, instrument="telescope")
# history must be a Worldline with ≥2 samples; emission before first sample raises TemporalHistoryUnavailableError (no fabrication)
discovery = obs_svc.observe("star-1", ctx, history=worldline)
# discovery.lookback_time_s, discovery.emission_time_s(), discovery.coordinates (emission event), discovery.measurement_data
# observed state is distinct from current simulation state (lookback preserved)
```

A measurement adds `instrument` to the context and is recorded as `MEASUREMENT_PERFORMED` in history.

Discoveries carry: `object/event identity, observation context, observer state, simulation time, observation time, coordinates/frame, measurement data, provenance, classification, uncertainty, source/model`.

Never fabricates: `ObservationService.observe` raises `ObservationError` when history/provider missing instead of inventing a distant state.

---

## 7. Finite Light Propagation Invariant

- Uses `astra.temporal.observation.observe` (`t_obs - t_emit = |x_obs - x(t_emit)|/c`, bisection, deterministic).
- Honesty: emission before first recorded sample or beyond last sample → `TemporalHistoryUnavailableError` (no extrapolation).
- `Discovery.lookback_time_s` is preserved; `Discovery.to_dict` stores it explicitly.

---

## 8. Exploration History

```python
from astra.interaction import ExplorationHistory, HistoryEventKind

history = ExplorationHistory()
history.emit(HistoryEventKind.LOCATION_VISITED, tick=10, sim_s=100.0, target_id="planet-1")
history.emit(HistoryEventKind.DISCOVERY_MADE, tick=12, sim_s=120.0, target_id="star-1", data={"mag": 10})
history.all()  # deterministic sorted by (tick, event_id)
history.for_kind(HistoryEventKind.DISCOVERY_MADE)
history.for_target("planet-1")
```

History is append-only, deterministic, serializable (`to_dict`/`from_dict`), provenance-aware, and stores references not copies. Compatible with future persistence (`full_snapshot`).

---

## 9. Exploration State Machine

```python
from astra.interaction import ExplorationStateMachine, ExplorationStateType

fsm = ExplorationStateMachine(ExplorationStateType.IDLE)
fsm.transition(ExplorationStateType.NAVIGATING)
fsm.transition(ExplorationStateType.ARRIVING)
fsm.transition(ExplorationStateType.EXPLORING)
# invalid: IN_TRANSIT -> OBSERVING without ARRIVING
fsm = ExplorationStateMachine(ExplorationStateType.IN_TRANSIT)
fsm.transition(ExplorationStateType.OBSERVING)  # raises StateTransitionError
```

States: `IDLE, NAVIGATING, APPROACHING, OBSERVING, MEASURING, TRAVELLING, IN_TRANSIT, ARRIVING, EXPLORING, INTERACTING, TRACKING, PAUSED, FAILED, COMPLETED`.

All transitions are explicit; `StateTransitionError` on invalid, never silent repair. `PAUSED` requires `RESUME` before other actions.

---

## 10. Targeting & Object Selection

```python
from astra.interaction import TargetKind, Target, TargetRegistry

reg = TargetRegistry()
reg.register(Target(target_id="t-planet", kind=TargetKind.PLANET, authoritative_id="planet-1", position_hint=(0,0,0), classification=Classification.REAL_DATA))
reg.register(Target(target_id="t-bh", kind=TargetKind.BLACK_HOLE, authoritative_id="bh-1", position_hint=(1e9,0,0)))
reg.query_by_kind(TargetKind.PLANET)
reg.nearby(center=(0,0,0), radius=1e6, limit=10)  # range query, deterministic by distance then id
```

Kinds: `PLANET, MOON, STAR, ASTEROID, COMET, SPACECRAFT, BLACK_HOLE, GALAXY, CLUSTER, COSMIC_WEB_STRUCTURE, PHENOMENON, OBSERVATION_TARGET, SIMULATION_REGION, CELESTIAL_OBJECT, WORLD_NODE, SCENE_NODE, ENTITY`.

Targets reference authoritative ids (celestial, world, entity) — no duplicate celestial DB. `TargetRegistry` is a lazy index/cache; `nearby` is O(n) over cached hints, not a full universe load.

---

## 11. Multi-Scale Integrity

Scale transitions preserve: `frame_id, world_id, simulation_time_s, proper_time_s, coordinate_time_s, provenance, classification`. No teleport: navigation only resolves the target and optionally rebases origin for precision; actual motion must be driven by `MotionSystem`/`NBodySystem`.

---

## 12. Scientific Mode Integration

Uses `astra.scientific.Classification` (single source):

```
REAL_DATA < DERIVED_DATA < SIMULATED_DATA < THEORETICAL < HYPOTHETICAL < SPECULATIVE
```

- Speculative wormhole/warp interactions carry `Classification.SPECULATIVE` and emit `WarningCode.SPECULATIVE_MODEL`.
- Discovery/Travel results never silently strengthen classification (`classify_combination` weakest-wins).
- Warnings are preserved in `WarningSink` and `InteractionResult.warnings`.

---

## 13. Player Safety — Structured Failures

Every invalid operation returns `InteractionResult(success=False, error_code, error_message)`; the engine may transition FSM to `FAILED` (explicit, not silent):

- `TargetError`: unknown/unavailable target
- `NavigationError`: invalid frame, unresolvable position
- `TravelError`: insufficient energy, unstable wormhole, classification mismatch, provider absent
- `ObservationError`: missing history, causality violation, instrument missing
- `ControlError`: non-finite delta-v, unknown entity
- `StateTransitionError`: illegal FSM transition
- `TemporalError`: pause/resume boundary violation

Never silently teleports, alters laws, or executes invalid commands.

---

## 14. Performance

- `TargetRegistry`: deterministic sorted `all()`, `nearby` with `limit`, no full DB scan beyond hints.
- `ExplorationHistory`: append O(1) with set-based duplicate check, `all()` sorted on demand; 10k events <0.2s, 10k targets <2s.
- `World` spatial queries delegate to `SpatialIndex`/`SceneGraph` (caller-supplied).
- Interaction layer is event-driven; no universe load on import.

---

## 15. Determinism

For identical `initial state + config + inputs + model config + time progression`, replay is bit-identical within numerical tolerances (sorted IDs, deterministic bisection in observation, deterministic RNG streams where used).

---

## 16. Architectural Rules Enforced

- No second physics/coordinate/observation/travel/rendering engine (verified by `grep -rn "class.*Physics" astra/interaction` → 0).
- All authoritative mutations go through `AuthorityContext` when providers are real engines; interaction layer itself never calls `AuthorityContext` unless injecting a real `SpacecraftSystem` with `require_authority=True`.
- Public APIs of `astra.core`, `astra.world`, `astra.temporal`, `astra.theoretical`, `astra.scientific` are preserved.

---

## 17. Persistence

```python
from astra.interaction import full_snapshot, full_snapshot_from_dict

snap = full_snapshot(state, history, target_registry, discovery_registry, fsm)
# snap = {"state": ..., "history": [...], "targets": [...], "discoveries": [...], "fsm": ..., "schema": "astra.interaction.v1"}
state2, history2, targets2, discs2, fsm2 = full_snapshot_from_dict(snap)
```

Deterministic, plain primitives, not the future player DB.

---

## 18. Testing

`tests/test_interaction.py` (48 tests) covers all items §21: commands, state transitions, navigation, targeting, exploration state, discovery, observation/measurement, travel, invalid actions, causality, temporal, serialization, deterministic replay, multi-scale, performance, provenance, scientific classification, and integration with World/Frame/Spacecraft/Temporal.

Run: `pytest tests/test_interaction.py -q` (48 passed) and full suite `pytest tests/ -q` (1660 passed).

---

## 19. Limitations (Non-Blocking)

- Travel delegation requires an injected `TravelProvider` that wraps `astra.theoretical` models; without it, `NullTravelProvider` correctly fails (ABSENT dependency, not a silent stub).
- Observation honesty relies on caller supplying a `Worldline` history with sufficient temporal coverage; without it, the layer correctly refuses to fabricate (raises `ObservationError`).
- Rendering/VFX/Backend integration is not reimplemented here; `ControlTranslator.camera` emits intent for the existing rendering layer to consume.
