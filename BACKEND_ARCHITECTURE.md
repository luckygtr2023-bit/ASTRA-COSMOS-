# ASTRA COSMOS — Backend & Runtime Integration Architecture

> **Scope:** Backend & Runtime layer (`astra.backend`) that integrates simulation, persistence,
> event, service, rendering, graphics, cache, data-access, diagnostics and lifecycle subsystems.
> Authoritative simulation remains `astra.core` + `astra.world` + `astra.celestial`.
> This document complements `RENDERING_ARCHITECTURE.md` and is the normative reference for
> `tests/test_backend.py`.

**Status:** Phase 5.3 — Implemented, 1684 tests passing (73 rendering + 76 backend + 1535 pre-existing)

---

## 1. Authority boundary (normative)

```
AUTHORITATIVE SIMULATION STATE         (astra.core.Engine, World, Celestial, Motion, Time)
        ↓  (pure read, never mutate)
RUNTIME SERVICES                        (astra.backend.runtime.BackendRuntime)
        ↓
RENDER / GRAPHICS STATE                 (RenderStateDelivery / GraphicsStateDelivery)
        ↓
VISUALIZATION / BLENDER BRIDGE          (future: graphics → blender bridge → MCP)
```

* Backend **never mutates** authoritative state. All derived data is cloned / serialized.
* Simulation-thread ownership enforced via `astra.core.threading.AuthorityContext` + `Security` layer (§11).
  `backend_operation("world.mutate")` raises `SecurityError` outside the sim thread / `AuthorityContext`;
  `render.*` / `graphics.*` reads are explicitly allowed concurrently.

---

## 2. Modules

| Module | File | Responsibility | Spec § |
|---|---|---|---|
| `exceptions` | `astra/backend/exceptions.py` | Explicit `BackendError` hierarchy with `subsystem / operation / resource / recoverable` | §16 |
| `config` | `astra/backend/config.py` | Unified, validated, versionable, deterministic `AstraBackendConfig` (core + rendering + graphics + runtime + cache + persistence + diagnostics + feature_flags) | §5 |
| `persistence` | `astra/backend/persistence.py` | Integration facade over `astra.core.persistence.PersistenceManager`; no second DB; world delegated, checkpoints / config / runtime snapshots as versioned JSON | §6 |
| `events` | `astra/backend/events.py` | Scoped `BackendEventHub` wrapping the single `EventBus`; explicit `SubscriptionHandle` lifecycle; no global duplication | §9 |
| `services` | `astra/backend/services.py` | Facade over `ServiceRegistry`; typed descriptors, dependency-ordered start, health | §7 |
| `cache` | `astra/backend/cache.py` | Bounded LRU `BoundedCache` + `CacheRegistry`; TTL, provenance, explicit invalidation | §16 |
| `render_delivery` | `astra/backend/render_delivery.py` | `RenderStateDelivery` — derives `RenderState` via `RenderPipeline`, bounded cache, deterministic serialize/stream | §8 |
| `graphics_delivery` | `astra/backend/graphics_delivery.py` | `GraphicsStateDelivery` — derives placeholder `GraphicsState` from `RenderState`; disabled degrades | §8, §3 |
| `data_access` | `astra/backend/data_access.py` | Explicit `DataAccessService` + `make_archive_handler` for catalog / world / entity reads; provenance preserving | §10 |
| `diagnostics` | `astra/backend/diagnostics.py` | Bounded `DiagnosticsCollector` + `HealthStatus` aggregation | §14 |
| `security` | `astra/backend/security.py` | Authority gating (`backend_operation`, `OperationClass`, `check_permission`) | §11 |
| `runtime` | `astra/backend/runtime.py` | `BackendRuntime` lifecycle orchestrator respecting `Engine` | §13 |
| `astra.backend` | `astra/backend/__init__.py` | Public re-export; stability surface for API/tooling | — |

---

## 3. Configuration (§5)

`AstraBackendConfig` (schema `BACKEND_SCHEMA_VERSION = 1`):

* Sections: `core: Config`, `rendering: RenderingConfig`, `graphics: GraphicsConfig`, `runtime: RuntimeConfig`, `cache: CacheConfig`, `persistence: PersistenceBackendConfig`, `diagnostics: DiagnosticsConfig`, `feature_flags: Dict[str,bool]`, `schema_version`.
* **Validation:** finite numbers (`_require_finite`), positive budgets, allowed enums (`RecoveryPolicy`, `RenderQualityPreset`, `LogLevel`); unknown top-level keys warned in `CoreConfig`, wrong types raise `ConfigurationError`.
* **Deterministic:** `to_dict()` sorted, `to_json(sort_keys=True)`, stable `fingerprint()` (SHA-256/16). `from_dict` refuses unsupported `schema_version` (explicit migration required).
* **Load/save:** `save(path)` atomic (tmp → replace), `load(path)` validates. `validate()` checks `core` via `to_dict` roundtrip (core has no `validate()` method).
* **Pipeline mapping:** `to_pipeline_config() → PipelineConfig` (`global_bias = 1/lod_bias`, `max_visible_objects`, `max_memory_mb`, `max_distance_m`, quality map).

Example:
```python
cfg = AstraBackendConfig()                 # defaults
cfg.rendering.quality = RenderQualityPreset.HIGH
pipe = cfg.to_pipeline_config()            # pass to RenderPipeline
cfg.save("config/backend.json")
loaded = AstraBackendConfig.load("config/backend.json")
assert loaded.fingerprint() == cfg.fingerprint()
```

---

## 4. Persistence integration (§6)

`BackendPersistence(backend_root, persistence_manager?)`:

* **Delegates** `save_world_state / load_world_state` to the single `PersistenceManager` (`PERSISTENCE_INTEGRATION_ERROR` on failure). No competing SQLite DB.
* **Owns** only deterministic JSON checkpoints under `backend_root/checkpoints/<label>.json`:
  * `save_checkpoint(label, payload)` — label `str` without `/`, payload JSON-serializable (sorted keys).
  * `save_backend_config(cfg, label="active")` — validates `AstraBackendConfig`.
  * `save_render_config(pipeline_cfg)` — supports both `PipelineConfig` dataclass (via `dataclasses.asdict`) and dicts.
  * `save_runtime_snapshot(snapshot, tick)` — tick-bounded label.
* `list_checkpoints()` deterministic sorted; `load_*` returns `None` on missing (no swallow of corruption).
* Thread-safe via `RLock`; `stats()` reports `checkpoints` count and `backend_root` existence.

---

## 5. Event integration (§9)

`BackendEventHub(bus?, owner)`:

* Wraps the **single** `EventBus` passed from `Engine` (or an isolated bus for tests). `hub.bus is engine.event_bus` when engine supplied.
* `subscribe(event_names, handler, label, priority) → SubscriptionHandle` — `event_names` coerced (`str` or Enum `.value`), per-name `bus.subscribe(name, wrapped, priority)`. Wrapped handler counts `received/handler_errors` without swallowing.
* `publish(event_name, payload, tick, priority, source)` → `bus.publish_sync(name, tick, payload, priority, source)`.
* `publish_event(Event)` → `bus.publish(event)`.
* `unsubscribe(handle)` / `unsubscribe_all(prefix)` — ownership explicit; `active_subscriptions()` lists `types: sorted`.
* `stats()` — `published_via_hub / received_via_hub / handler_errors / bus: {history_size, failed_handlers, sequence}`.
* `shutdown()` unsubscribes all owned without shutting down the bus.

Event names are **strings** (`"engine_started"`, `"runtime_started"` etc.), compatible with `core` (`engine_initialized`, `engine_started`, `engine_paused`, `engine_stopped`).

---

## 6. Service integration (§7)

`BackendServiceRegistry(core_registry?)`:

* Wraps the single `ServiceRegistry`; no second registry.
* `BackendServiceDescriptor(name, dependencies, timeout_s, critical)` + `validate()` (circular/self-dep explicit).
* `register_service(instance, descriptor?, name?, dependencies?)` delegates to `core.register(name, instance, dependencies)` and tracks `descriptors`/`instances` for diagnostics.
* `start_service(name)`, `start_all_in_dependency_order() → List[str]` (Kahn topological check; circular → `ServiceError`), `stop_service`, `stop_all`, `clear`/`shutdown`.
* Health is `core` `started` flag (`HEALTHY`/`STOPPED`/`UNKNOWN`) aggregated in `health_summary()`, `recent_events(limit)`.

---

## 7. Cache — bounded, explicit, provenance-preserving (§16)

`BoundedCache(max_entries, max_memory_bytes, default_ttl_s, name)`:

* **Bounded:** LRU eviction (`OrderedDict`, `move_to_end` on hit) on `max_entries` or `max_memory_bytes` (estimated via `sys.getsizeof` or explicit `size_bytes`).
* **TTL:** monotonic clock, lazy expiry on `get`; `is_expired(now)`.
* **Thread-safe:** `RLock`; `stats()` returns `hits/misses/evictions/expiries/invalidations/entries/estimated_memory_bytes/hit_rate`.
* **Explicit invalidation:** `invalidate(key)`, `invalidate_prefix(prefix)`, `invalidate_tags(set)`, `invalidate_provenance(provenance)`, `clear()`.
* **Provenance:** `CacheEntry(provenance, source_tick, tags, size_bytes)`; cache never re-labels authoritative data.
* **Cache-aside:** `get_or_compute(key, compute, ttl, provenance, source_tick, tags, size_bytes)` — `compute()` called only on miss outside lock.
* `CacheRegistry` scopes per-subsystem caches (`get_or_create(name, ...)`, `remove`, `clear_all`, `stats_summary`).

Delivery layers use bounded caches with `tags={"tick", "tick:<n>"}` and `provenance=...`, `source_tick=tick` for tick-aware invalidation. Large states (~`count*512B`) are cached but callers must **stream** when `serialize` exceeds `max_state_bytes`.

---

## 8. Render delivery (§8)

`RenderStateDelivery(pipeline?, cache?, max_state_bytes=16MiB, chunk_size=2000)`:

* `derive(tick, simulation_time_s, world_objects, render_origin, context?, provenance="simulated", use_cache=True) → RenderFrame`
  * Validates `tick >=0`, finite `simulation_time_s`, `world_objects: List[Dict]` bounded `≤200k`.
  * Cache key `render:tick:<t>:t<sim>:o<origin>:ctx<ctx_hash>:p<pipe_hash>:<prov>` (`ctx_hash` SHA-256 of `context.to_dict()`).
  * On miss, under `RLock`: if `context?.camera` present → `pipeline.build_frame(tick, sim_time, world_objects, camera=context.camera, quality=..., render_origin, temporal_mode)`; else `pipeline.build_render_state(...)` + `_frame_from_state` with default `Camera(position=(0,0,10))`. Provenance stamped. `est_bytes = count*512`.
* `serialize_frame(RenderFrame, pretty=False) → bytes` — `json(sort_keys=True)`, validates `len ≤ max_state_bytes`.
* `deserialize_frame(bytes) → dict` — never mutates simulation.
* `stream_frame(RenderFrame, chunk_objects?) → Iterable[Dict]` — header on first chunk (`tick, simulation_time_s, provenance, temporal_mode, total_chunks, render_origin, context`), per-chunk `provenance`.
* `invalidate_tick(tick)`, `invalidate_all()`, `update_camera_relative(frame, camera_position)` (stateless helper).
* Never holds authoritative handles; `world_objects` list not mutated.

---

## 9. Graphics delivery (§8, future bridge §3)

`GraphicsStateDelivery(cache?, enabled=True, max_state_bytes=16MiB, chunk_size=2000)`:

* Placeholders — no shader compilation, no `bpy`.
* `GraphicsObject` 1:1 `RenderObject` (`material_ref`, `shot_params`, `lod`, `visibility`, `provenance`, `tags`) via `from_render_object`.
* `GraphicsState(tick, simulation_time_s, graphics_origin, objects/order, provenance, max_objects=200k)`.
* `derive(RenderState, use_cache=True) → GraphicsState` — pure 1:1; if `enabled=False` sets `shader_params={placeholder:True, enabled:False}` so bridge can detect; cached `graphics:tick:<t>:o<hash>:p<prov>:en<int>`.
* `serialize(GraphicsState)`, `stream(GraphicsState)` mirroring render delivery; `invalidate_tick/all`, `cache` property, `set_enabled`, `stats()`.

Design satisfies `SIM → RENDER STATE → GRAPHICS STATE → VISUALIZATION` isolation and allows future `graphics → blender_bridge → MCP` without changing contracts.

---

## 10. Data access (§10)

`DataAccessService`:

* `register_handler(source: DataSource, handler: Callable[[DataRequest], DataResponse|List|Dict])`
* `DataRequest(source, query, limit=100, offset=0, provenance?, region?)` validated (`limit 1..10k`, `offset ≥0`, allowed `query` keys); `cache_key()`.
* `DataResponse(rows, total_hint?, provenance=DERIVED_DATA, source, truncated)` normalized from handler returns.
* `query(DataRequest) → DataResponse` — handler missing → `DataAccessError(recoverable=False)`; handler exception → `recoverable=True`.
* `stats()` → `handlers, query_count, error_count`.

`make_archive_handler(db_path)` — optional SQLite read-only passthrough for `stars_astrometry / confirmed_exoplanets / solar_system_bodies` with allowed filters + `region {ra_min, ra_max, dec_min, dec_max}` for stars, parametrized SQL (no injection), `data_classification=REAL_DATA`.

All results preserve `provenance` (`REAL_DATA` for archive).

---

## 11. Security & authority (§11)

`astra.backend.security`:

* `OperationClass` — `MUTATE_SIMULATION | MUTATE_BACKEND | READ_AUTHORITATIVE | READ_DERIVED`.
* `requires_authority(op)` — set `{"world.mutate", "engine.step", "engine.initialize", "persistence.save_world"}`.
* `classify_operation(op)` — explicit + prefix heuristics.
* `assert_authority(op)` — delegates to `AuthorityContext.require_authority`; wraps `AuthorityError → SecurityError(recoverable=False)`.
* `backend_operation(op, audit?)` context manager — classifies, checks, yields `{operation, class, thread_id, audit}`; used throughout runtime/diagnostics.
* `check_permission(op, thread_id?) → bool` — non-raising.
* `is_simulation_thread()` — delegates to `SimulationThreadRegistry`.

Guarantee: **render/graphics reads never require authority**; simulation mutations are impossible off the sim thread even via backend.

---

## 12. Diagnostics (§14)

`DiagnosticsCollector(max_entries=10000)`:

* `log(level, subsystem, operation, message, details?)` appends `DiagnosticsEntry(ts_monotonic, level, subsystem, operation, message, details)` bounded (`_max`, FIFO).
* Convenience `debug/info/warning/error(subsystem, operation, message, details?)`.
* `set_health(subsystem, HealthStatus)` / `get_health(subsystem?)` / `overall_health()` (`HEALTHY | DEGRADED | UNHEALTHY | UNKNOWN` — `UNHEALTHY` dominates).
* `recent(limit, level?, subsystem?)`, `counters()`, `uptime_s()`, `summary()`, `clear()`.

`BackendRuntime` wires diagnostics to lifecycle + recovery; `BackendEventHub` and `BoundedCache` emit stats aggregatable in `Runtime.health_summary()`.

---

## 13. Runtime & lifecycle (§13)

`BackendRuntime(engine?, config?, persistence?, event_hub?, diagnostics?, cache_registry?, render_delivery?, graphics_delivery?)`:

* **Constructs** with `AstraBackendConfig.clone()`, `BackendPersistence`, `BackendEventHub(bus=engine.event_bus if engine else isolated)`, `DiagnosticsCollector(max_entries=diagnostics.max_log_entries)`, `RecoveryManager(policy=config.runtime.recovery_policy, max_retry=...)`.
* States `RuntimeState: CREATED → INITIALIZED → RUNNING ⇄ PAUSED → STOPPED / FAILED`.
* `initialize(load_config_checkpoint?)` — `CREATED→INITIALIZED`, loads persisted config checkpoint if requested, `recovery.set_policy/max_retry`, `diag.set_health(RUNTIME, HEALTHY)`, guarded `backend_operation("runtime.initialize")`.
* `start()` — `INITIALIZED/PAUSED/STOPPED → RUNNING`, subscribes to `engine_started/engine_paused/engine_initialized`, `diag.info("runtime","start")`, publishes `runtime_started`.
* `pause()` — `RUNNING→PAUSED`; `resume()` — `PAUSED→RUNNING`; both guarded.
* `shutdown(clear_transient_caches=True)` — idempotent (`CREATED→STOPPED`), unsubscribes `runtime.*`, `caches.clear_all()`, `render_delivery.invalidate_all()`, `graphics_delivery.invalidate_all()`, `diag.info("runtime","shutdown")`, `HEALTH=UNKNOWN`.
* `recover(failure_type, operation, tick, message, context?) → bool` — `recovery.record_failure(...)`, invalidates render/graphics tick caches, `warning/error`, `health DEGRADED/UNHEALTHY`, `state FAILED` if no retry (FAIL_FAST).
* `on_tick_derived(tick, simulation_time_s, world_objects, **kwargs)` — `RUNNING` only; `render_delivery.derive(...)` + `graphics_delivery.derive(frame.render_state)`; on error `recover("render_derive", "runtime.on_tick_derived", ...)` and returns `render_error/should_retry`; on success `recovery.record_success`.
* `stats()` — `state/tick/uptime_s/deliveries/cache_hit_rate/health/recovery{policy, consecutive_failures, total_failures}`.
* `health_summary()` — merges `diagnostics`, `hub.stats`, `caches.stats_summary`, delivery stats.

Engine lifecycle is **respected**: runtime never drives `Engine` ticks; it reacts to engine events and is wired via caller's `on_tick_derived` hook.

---

## 14. Error handling (§16)

* All modules raise `BackendError(subsystem, operation, resource, recoverable, cause, details)` — `ConfigurationError`, `PersistenceIntegrationError`, `EventIntegrationError`, `CacheError`, `ServiceError`, `RuntimeError_`, `RenderDeliveryError`, `GraphicsDeliveryError`, `DataAccessError`, `SecurityError`.
* No `except: pass`; failures identify recoverability; handler errors are counted and (optionally) retried via `RecoveryManager`.
* Tests assert `subsystem/operation/resource/recoverable` presence.

---

## 15. Large-state & streaming (§15)

* Bounded counters: `world_objects ≤200k`, `RenderState.max_objects=200k`, `GraphicsState.max_objects=200k`, `max_state_bytes=16MiB`.
* `derive` estimates `est_bytes = count*512` but still caches (caller streams if serialize would exceed).
* `stream_frame/stream` yields `header (tick, simulation_time_s, provenance, temporal_mode, total_chunks, origin)` on first chunk, then per-chunk `objects: [to_dict()]` and `provenance`.
* `max_state_bytes` enforced on `serialize`; `render_delivery.derive` respects `max_visible_objects` via `PerformanceBudget` in the pipeline.

---

## 16. Determinism (§10, §16)

* Config fingerprint / JSON `sort_keys` guarantees byte-identical serialization for same inputs.
* `RenderStateDelivery` cache key includes pipeline fingerprint + context hash + tick; no wall-clock drift; `visual_seed` explicit in `RenderContext`.
* `RenderPipeline` is deterministic given deterministic `world_objects` order (insertion order preserved).
* Tests `TestDeterminism` assert same inputs → `serialize_frame` bytes identical, `visual_seed` explicit, world_objects order preserved.

---

## 17. Testing strategy (§17) — this phase

`tests/test_backend.py` (76 tests) + `tests/test_rendering.py` (73) + 1535 pre-existing = 1684 passing.

| Area | Test class | Covers |
|---|---|---|
| Config | `TestConfiguration` | defaults deterministic, validation finite, versionable, clone isolation, save/load, pipeline mapping |
| Persistence | `TestPersistenceIntegration` | delegation, checkpoints, backend config snapshot, render config snapshot, world delegation explicit error, runtime snapshot |
| Cache | `TestCache` | LRU eviction, memory bound, TTL, invalidation prefix/tags/provenance, clear/stats, get_or_compute, registry scoped, provenance, invalid keys, stale never stale |
| Events | `TestEventIntegration` | subscribe/publish lifecycle, multi-name, handler error counting, no duplication, unsubscribe prefix, publish_event, invalid subscribe, shutdown |
| Data | `TestDataAccess` | register/query, missing handler explicit, validation, list normalized, provenance, archive handler sqlite (+ region, pagination) |
| Services | `TestServices` | descriptor validation, dependency order, circular detection, get_instance |
| Diagnostics | `TestDiagnostics` | logging health counters, bounded log, summary |
| Security | `TestSecurity` | read allowed, mutate requires authority, backend mutation logged |
| Render | `TestRenderDelivery` | derive+cache_hit, serialize deterministic, streaming, large-state bounded+stream, never mutates, with context, invalid inputs |
| Graphics | `TestGraphicsDelivery` | derive from render, disabled degrades, cache+invalidate, streaming |
| Runtime | `TestRuntimeLifecycle` | initialize/start/pause/resume/shutdown, illegal transitions, on_tick requires running, recovery invalidates cache, shutdown clears transient, diagnostics integrated, config checkpoint load |
| Authority | `TestAuthorityIsolation` | render no authority, mutation requires authority, concurrent reads safe (5×20 threads) |
| Determinism | `TestDeterminism` | byte-identical serialize, visual_seed, order preserved |
| Errors | `TestErrorHandling` | subsystem/operation/recoverable, render delivery size guard, no silent swallow |
| Large state | `TestLargeState` | 5000 objects streamed, world_objects bounded |

Also manual checks: `python -m pytest tests/test_authority.py tests/test_entities.py ...` still green (regression isolation).

---

## 18. Integration dependencies & file map

```
astra/
  core/                 (authoritative: Engine, PersistenceManager, EventBus, ServiceRegistry, RecoveryManager, threading.AuthorityContext)
  celestial/            (provenance: DataProvenance — REAL_DATA ...)
  mathematics/          (Vector3 / Quaternion — used for render positions)
  world/                (World — not mutated by backend; read via adapters)
  rendering/            (RenderPipeline, RenderState, RenderContext, Camera, FloatingOrigin, LOD, Culling, Performance — consumed by render_delivery)
  backend/              ← this phase
    exceptions.py
    config.py           depends: core.config.Config, core.recovery.RecoveryPolicy, rendering.PipelineConfig/LOD/Culling/Performance
    cache.py            (no external deps)
    events.py           depends: core.events.EventBus/Event/EventPriority
    persistence.py      depends: core.persistence.PersistenceManager
    services.py         depends: core.services.ServiceRegistry
    security.py         depends: core.threading.AuthorityContext/SimulationThreadRegistry, core.exceptions.AuthorityError
    diagnostics.py      (no external)
    data_access.py      depends: celestial.provenance.DataProvenance, optional sqlite ingestion DB
    render_delivery.py  depends: rendering.RenderPipeline/RenderState/RenderContext/Camera/types, cache.BoundedCache
    graphics_delivery.py depends: rendering.RenderState, cache.BoundedCache
    runtime.py          depends: core.Engine, recovery.RecoveryManager, persistence.BackendPersistence, events.BackendEventHub, cache.CacheRegistry, diagnostics.DiagnosticsCollector, security.backend_operation
  ingestion/            (read via data_access make_archive_handler)
```

**No Blender/MCP-Blender dependency.** `RenderFrame.to_dict()` / `GraphicsState.to_dict()` are the bridge-ready serialize points described in `RENDERING_ARCHITECTURE.md §18`; a future `astra.graphics`/`astra.blender_bridge` can consume them without importing `bpy`.

---

## 19. Known limits / future work (explicit, no silent debt)

* `astra.graphics` (MiMo materials/shaders/particles/post) intentionally not implemented — `GraphicsStateDelivery` is the placeholder contract.
* `mcp-blender` bridge not implemented — `BACKEND_ARCHITECTURE.md` designs for `SIM → RENDER/GRAPHICS STATE → GRAPHICS/VFX → BLENDER BRIDGE → BLENDER → MCP` via `to_dict` without coupling.
* `archive_db` handler is a minimal SQLite passthrough; production streaming of 10 M-row Gaia catalogs should use server-side TAP/paginated cursors (outside this phase).
* `Core Config.validate()` does not exist; backend validates via `to_dict` roundtrip + section validates.
* `ServiceRegistry` health is `started` boolean (core has no `ServiceHealth` enum); backend maps to `HEALTHY/STOPPED`.

---

## 20. Verification

```bash
python -m pytest tests/test_rendering.py tests/test_backend.py -q   # 149 passed
python -m pytest tests/ -q                                          # 1684 passed
python -c "import astra.backend; print(astra.backend.BACKEND_SCHEMA_VERSION)"  # 1
```

Commit: `feat(backend): implement GLM 5.3 backend & runtime integration (spec §5–§18)`

Refs: `ASTRA_CORE.txt`, `AUDIT_REPORT.md`, `RENDERING_ARCHITECTURE.md`, `astra/rendering/*`, `astra/core/*`.
