# ASTRA CORE Contract v0.1.2

This document describes the ACTUAL implemented ASTRA CORE API.

## Engine

### Engine Lifecycle States

- `CREATED`: Engine initialized but not ready
- `READY`: Engine ready to run simulations  
- `RUNNING`: Engine actively simulating
- `PAUSED`: Engine paused (state preserved)
- `STOPPED`: Engine stopped
- `ERROR`: Engine encountered an error

### Engine API

```python
from astra.core.engine import Engine, EngineState
from astra.core.config import Config

config = Config()
engine = Engine(config)
engine.initialize()  # Transition to READY
engine.start()       # Transition to RUNNING
engine.step()        # Execute one tick
engine.pause()       # Pause simulation
engine.resume()      # Resume simulation
engine.stop()        # Stop simulation
engine.shutdown()    # Full shutdown
```

### Properties

- `clock`: SimulationClock instance
- `event_bus`: EventBus instance
- `rng`: DeterministicRNG instance
- `commands`: CommandDispatcher instance
- `scene`: Scene instance
- `persistence`: PersistenceManager instance
- `resources`: ResourceManager instance
- `recovery`: RecoveryManager instance
- `services`: ServiceRegistry instance

## Simulation Authority

Only the registered simulation thread may mutate authoritative state.

```python
from astra.core.threading import AuthorityContext

with AuthorityContext("operation_name"):
    # Authorized mutation here
    pass
```

Attempting to enter AuthorityContext from a non-simulation thread raises AuthorityError.

### AuthorityContext Methods

- `require_authority(operation: str)`: Raise if no authority
- `has_authority(operation: str) -> bool`: Check authority
- `get_current_token() -> AuthorityToken | None`: Get current token

## Commands

```python
from astra.core.commands import Command, CommandType, CommandStatus

cmd = Command(
    name="create_entity",
    type=CommandType.CREATE_ENTITY,
    data={"name": "test"},
    tick=0,
    sequence=0
)
```

### CommandDispatcher

- `queue_command(cmd)`: Queue for execution
- `execute_pending(tick)`: Execute pending commands
- `get_history()`: Get command history

## Events

```python
from astra.core.events import EventBus, Event, EventPriority

bus = EventBus()
bus.subscribe("event_name", handler, priority=EventPriority.NORMAL)
bus.publish_sync("event_name", tick, source="system", data={})
bus.unsubscribe("event_name", handler)
```

## RNG

```python
from astra.core.rng import DeterministicRNG

rng = DeterministicRNG(global_seed=42)
stream = rng.create_stream("subsystem")
value = stream.random()
state = rng.snapshot()
rng.restore(state)
```

### DeterministicRNG Methods

- `create_stream(name, seed)`: Create isolated stream
- `snapshot()`: Capture full RNG state
- `restore(state)`: Restore from snapshot
- `reset(seed)`: Reset with new seed

## Entities

```python
from astra.core.entities import EntityManager, Entity, Component

em = EntityManager()
entity = em.create_entity(name="test")
entity.add_component(Component("type", data={}))
entities = em.query_entities(enabled_only=True)
em.destroy_entity(entity.id)
```

### EntityManager Methods

- `create_entity(name, tags)`: Create entity
- `destroy_entity(id)`: Destroy entity
- `get_entity(id)`: Get entity or None
- `get_entity_or_raise(id)`: Get entity or raise
- `query_entities(enabled_only)`: Query entities
- `get_state_snapshot()`: Get serializable state
- `restore_from_snapshot(state)`: Restore state

## Coordinate Frames

```python
from astra.core.coords import CoordinateFrame, FrameRegistry, OriginRebaser

registry = FrameRegistry()
frame = CoordinateFrame(name="world", origin=(0,0,0))
registry.register_frame(frame)

rebaser = OriginRebaser(registry)
request = rebaser.request_rebase(new_origin=(1,2,3))
rebaser.execute_rebase(request, authorized=True)
```

### CoordinateFrame Properties

- `id`: Unique FrameID
- `name`: Frame name
- `origin`: (x, y, z) tuple
- `parent_id`: Parent frame ID or None

## Origin Rebase

```python
from astra.core.coords import OriginRebaseRequest

request = OriginRebaseRequest(
    new_origin=(1.0, 2.0, 3.0),
    reason="precision management"
)
```

Rebase requires proper authority and changes coordinate representation while preserving relative positions.

## Time

```python
from astra.core.time import SimulationClock, TimeMode

clock = SimulationClock(tick_duration=0.016, mode=TimeMode.INTERNAL_DETERMINISTIC)
clock.start()
tick = clock.advance()
time = clock.get_simulation_time()
clock.seek(target_tick)
clock.pause()
clock.resume()
clock.stop()
```

### TimeMode Values

- `INTERNAL_REALTIME`: Real-time simulation
- `INTERNAL_DETERMINISTIC`: Deterministic stepping
- `EXTERNAL_SYNC`: External timestamp synchronization

## Persistence

```python
from astra.core.persistence import PersistenceManager, Snapshot

pm = PersistenceManager(base_path="./snapshots")
snapshot = Snapshot(
    schema_version="1.0.0",
    engine_state={},
    simulation_time={},
    entities={},
    frames={},
    rng_state={},
    tick=0
)
path = pm.save(snapshot, "checkpoint")
loaded = pm.load("checkpoint")
```

### PersistenceManager Methods

- `save(snapshot, name)`: Atomic save with checksum
- `load(name)`: Load and verify
- `exists(name)`: Check existence
- `delete(name)`: Delete snapshot

## Resources

```python
from astra.core.resources import ResourceManager

rm = ResourceManager(max_handles=1000)
handle = rm.acquire("resource_type", resource)
rm.release(handle)
rm.get_ref_count(handle)
```

## Recovery

```python
from astra.core.recovery import RecoveryManager, RecoveryPolicy

rm = RecoveryManager(policy=RecoveryPolicy.FAIL_FAST)
rm.record_failure(failure_type, operation, tick, message)
rm.record_success(operation, tick)
```

### RecoveryPolicy Values

- `FAIL_FAST`: Stop on first failure
- `RETRY_STEP`: Retry failed step
- `DROP_EVENT`: Drop failing event and continue

## Services

```python
from astra.core.services import ServiceRegistry

registry = ServiceRegistry()
registry.register("name", service)
service = registry.get("name")
registry.unregister("name")
```

## Threading

### SimulationThread

```python
from astra.core.threading import SimulationThread

sim_thread = SimulationThread("ASTRA_Simulation")
sim_thread.start()
result = sim_thread.execute(lambda: computation())
sim_thread.stop()
```

### SimulationThreadRegistry

Singleton registry for authoritative thread identity.

```python
from astra.core.threading import get_simulation_thread_registry

registry = get_simulation_thread_registry()
registry.register_simulation_thread(thread_id)
registry.is_simulation_thread(thread_id)
registry.unregister_simulation_thread(thread_id)
```

## Exceptions

- `AstraError`: General ASTRA error
- `AuthorityError`: Authority violation
- `InvalidOperationError`: Invalid operation attempt
- `NotFoundError`: Resource not found

## Deterministic Guarantees

1. Same inputs produce same outputs
2. Replay produces identical results
3. RNG streams are isolated
4. Command ordering is preserved
5. Save/load continuation is deterministic

## Thread Safety Rules

1. Only simulation thread mutates authoritative state
2. Safe snapshot iteration (no yielding while holding locks)
3. Deadlock prevention via RLock usage
4. Authority verified per-operation

## Version Information

- Schema version: 1.0.0
- Core version: 0.1.2
