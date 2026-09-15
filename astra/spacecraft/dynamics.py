"""Engine dynamics: mass flow, thrust force, torque.

These are pure functions of engine + spacecraft state. They do not mutate
anything; SpacecraftSystem applies the results.

World-frame transforms
----------------------
Given body orientation q (Quaternion), the world-frame thrust direction is
    d_world = q.rotate(engine.thrust_direction_body)
The application point in world is
    p_world = com_world + q.rotate(engine.mount_offset_local)
Torque about the center of mass:
    tau_world = (p_world - com_world) x F_world
              = q.rotate(mount_offset_local) x F_world
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from astra.mathematics import Vector3, Quaternion
from astra.spacecraft.constants import G0
from astra.spacecraft.engines import Engine, EngineSpec
from astra.spacecraft.errors import InvalidEngineError


@dataclass(frozen=True)
class EngineEvaluation:
    """Per-engine evaluation result for one timestep."""
    engine_id: str
    thrust_force_world: Vector3
    torque_world: Vector3
    propellant_consumed: float
    burn_duration_used: float
    terminated: bool                # propellant exhausted this step


def engine_mass_flow(engine: Engine) -> float:
    """Full-throttle propellant mass flow (kg/s)."""
    return engine.mass_flow_rate


def engine_thrust_world(engine: Engine, orientation: Quaternion) -> Vector3:
    """World-frame thrust force at full throttle."""
    d_world = orientation.rotate(engine.thrust_direction_body)
    return d_world * engine.thrust_magnitude


def engine_torque_world(engine: Engine, orientation: Quaternion) -> Vector3:
    """World-frame torque from engine offset at full throttle."""
    r_world = orientation.rotate(engine.mount_offset_local)
    f_world = engine_thrust_world(engine, orientation)
    return r_world.cross(f_world)


def evaluate_engines(
    specs: Sequence[EngineSpec],
    orientation: Quaternion,
    propellant_available: float,
    dt: float,
) -> Tuple[List[EngineEvaluation], float]:
    """Evaluate all currently-burning, enabled engines for a timestep.

    Determinism: iterates `specs` in the given order (which the caller
    controls). Does not use dicts or sets internally.

    Behaviour:
    - Engines are processed in order.
    - Each burning engine consumes propellant at its full-throttle rate
      for min(dt, propellant_remaining / rate). If propellant runs out
      mid-step, the burn duration for that engine is truncated.
    - `terminated` is True on the step where the tank empties.
    - Returns (evaluations, propellant_used_total).

    `orientation` is the body-to-world rotation of the spacecraft.
    """
    if dt <= 0.0:
        raise InvalidEngineError(f"dt must be positive, got {dt!r}")
    if propellant_available < 0.0:
        raise InvalidEngineError(
            f"propellant_available must be non-negative, got {propellant_available!r}"
        )

    remaining = propellant_available
    results: List[EngineEvaluation] = []
    for spec in specs:
        eng = spec.engine
        if not (spec.enabled and spec.burning):
            continue
        if remaining <= 0.0:
            # Nothing left to consume; still report the intent so callers
            # can see the engine was skipped due to empty tank.
            results.append(EngineEvaluation(
                engine_id=eng.id,
                thrust_force_world=Vector3(0, 0, 0),
                torque_world=Vector3(0, 0, 0),
                propellant_consumed=0.0,
                burn_duration_used=0.0,
                terminated=True,
            ))
            continue

        rate = eng.mass_flow_rate
        if rate == 0.0:
            # Zero-thrust engine: no mass flow.
            f_world = engine_thrust_world(eng, orientation)
            t_world = engine_torque_world(eng, orientation)
            results.append(EngineEvaluation(
                engine_id=eng.id,
                thrust_force_world=f_world,
                torque_world=t_world,
                propellant_consumed=0.0,
                burn_duration_used=dt,
                terminated=False,
            ))
            continue

        max_time = remaining / rate
        used = min(dt, max_time)
        consumed = used * rate

        # Compute thrust with a per-engine override if the caller supplied one.
        # The override path is handled by the caller (see SpacecraftSystem);
        # here we use the engine's own direction.
        f_world = engine_thrust_world(eng, orientation)
        t_world = engine_torque_world(eng, orientation)

        remaining -= consumed
        if remaining < 0.0:
            remaining = 0.0

        results.append(EngineEvaluation(
            engine_id=eng.id,
            thrust_force_world=f_world,
            torque_world=t_world,
            propellant_consumed=consumed,
            burn_duration_used=used,
            terminated=(used < dt),
        ))

    used_total = propellant_available - remaining
    return results, used_total
