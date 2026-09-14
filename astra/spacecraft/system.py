"""SpacecraftSystem — deterministic propulsion + integration orchestration.

Responsibilities
----------------
- Maintain an ordered set of SpacecraftComponents on entities.
- Each step:
    1. Query gravity from a caller-supplied GravityProvider.
    2. Evaluate all currently-burning engines deterministically (in
       engine_specs order).
    3. Consume propellant accordingly.
    4. Accumulate net thrust force and net torque.
    5. Write acceleration / angular_acceleration into the MotionState.
    6. Hand off integration to the existing MotionSystem.

Boundaries respected
--------------------
- Motion owns integration. SpacecraftSystem does not integrate.
- Physics owns Force/Torque/Inertia primitives; this layer only
  accumulates and passes through.
- N-Body provides gravity; this layer never computes pairwise gravity.
- Authority is enforced at the top of every mutating method.
"""
from __future__ import annotations
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol, Tuple

from astra.core.entities import EntityManager, Query
from astra.core.threading import AuthorityContext
from astra.mathematics import Vector3
from astra.motion import MotionComponent, MotionSystem, validate_timestep
from astra.physics import PhysicsComponent
from astra.spacecraft.components import SpacecraftComponent
from astra.spacecraft.burns import FiniteBurn, ImpulsiveBurn
from astra.spacecraft.dynamics import evaluate_engines, EngineEvaluation
from astra.spacecraft.errors import InvalidBurnError, InvalidEngineError


class GravityProvider(Protocol):
    """Callable that returns the world-frame gravitational acceleration
    at a given position, for a given spacecraft mass, at the current time.

    Implementations may wrap an NBodySystem, a Physics GravitySource, or
    a custom source. They must be pure (no side effects).
    """
    def acceleration_at(self, position: Vector3, mass: float,
                        t: float) -> Vector3: ...


class SpacecraftSystem:
    """Deterministic propulsion system."""

    def __init__(
        self,
        entity_manager: EntityManager,
        motion_system: MotionSystem,
        gravity_provider: Optional[GravityProvider] = None,
    ):
        self._em = entity_manager
        self._motion = motion_system
        self._gravity = gravity_provider

    # -- source management --

    def set_gravity_provider(self, provider: Optional[GravityProvider]) -> None:
        self._gravity = provider

    # -- iteration --

    def _iter_spacecraft(self) -> Iterable[
        Tuple[str, SpacecraftComponent, MotionComponent, Optional[PhysicsComponent]]
    ]:
        q = Query().with_component(SpacecraftComponent).with_component(MotionComponent)
        for entity in self._em.query(q):
            sc = entity.get_component(SpacecraftComponent)
            mc = entity.get_component(MotionComponent)
            pc = entity.get_component(PhysicsComponent)
            if sc is None or mc is None:
                continue
            yield entity.id.value, sc, mc, pc

    # -- burn management --

    def start_finite_burn(self, entity_id: str, burn: FiniteBurn,
                          require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("spacecraft.start_finite_burn")
        entity = self._em.get_entity(entity_id)
        if entity is None:
            raise InvalidBurnError(f"entity not found: {entity_id!r}")
        sc = entity.get_component(SpacecraftComponent)
        if sc is None:
            raise InvalidBurnError(f"entity has no SpacecraftComponent: {entity_id!r}")
        spec = sc.state.get_engine(burn.engine_id)
        if spec is None:
            raise InvalidBurnError(
                f"engine not found: {burn.engine_id!r} on entity {entity_id!r}"
            )
        if sc.state.active_burn_id is not None:
            raise InvalidBurnError(
                f"spacecraft already executing burn {sc.state.active_burn_id!r}"
            )
        if not spec.enabled:
            raise InvalidBurnError(f"engine {burn.engine_id!r} is disabled")
        spec.burning = True
        sc.state.active_burn_id = burn.id

    def cancel_burn(self, entity_id: str, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("spacecraft.cancel_burn")
        entity = self._em.get_entity(entity_id)
        if entity is None:
            return
        sc = entity.get_component(SpacecraftComponent)
        if sc is None:
            return
        for spec in sc.state.engine_specs:
            spec.burning = False
        sc.state.active_burn_id = None

    # -- impulsive maneuver --

    def apply_impulsive(self, entity_id: str, burn: ImpulsiveBurn,
                        require_authority: bool = True) -> None:
        """Apply an idealized instantaneous delta-v to the spacecraft velocity.

        The burn's delta_v is interpreted in the WORLD frame. Callers who
        want a prograde / radial / normal burn should compute the world-
        frame delta-v via the Orbital Mechanics layer first.
        """
        if require_authority:
            AuthorityContext.require_authority("spacecraft.apply_impulsive")
        entity = self._em.get_entity(entity_id)
        if entity is None:
            raise InvalidBurnError(f"entity not found: {entity_id!r}")
        mc = entity.get_component(MotionComponent)
        if mc is None:
            raise InvalidBurnError(
                f"entity has no MotionComponent: {entity_id!r}"
            )
        mc.state.velocity = mc.state.velocity + burn.delta_v

    # -- main step --

    def step(self, dt: float, require_authority: bool = True) -> int:
        """Advance all spacecraft by dt using the currently-active burns.

        Returns the number of spacecraft that were updated.
        """
        validate_timestep(dt)
        if require_authority:
            AuthorityContext.require_authority("spacecraft.step")

        updated = 0
        for _eid, sc, mc, pc in self._iter_spacecraft():
            if not sc.enabled:
                continue

            state = sc.state
            motion_state = mc.state

            # 1. Evaluate currently-burning engines, deterministic order.
            evaluations, propellant_used = evaluate_engines(
                state.engine_specs,
                motion_state.orientation,
                state.mass.propellant_mass,
                dt,
            )
            if propellant_used > 0.0:
                state.mass.consume(propellant_used)

            # 2. Accumulate net force and torque in world frame.
            net_force = Vector3(0.0, 0.0, 0.0)
            net_torque = Vector3(0.0, 0.0, 0.0)
            for ev in evaluations:
                net_force = net_force + ev.thrust_force_world
                net_torque = net_torque + ev.torque_world

            # 3. Gravity (if provided).
            gravity_acc = Vector3(0.0, 0.0, 0.0)
            if self._gravity is not None:
                gravity_acc = self._gravity.acceleration_at(
                    motion_state.position, state.mass.total_mass, motion_state.time
                )

            # 4. Thrust acceleration from net force and total mass.
            inv_m = state.mass.inverse_mass
            thrust_acc = net_force * inv_m

            # 5. Write accelerations into MotionState.
            motion_state.acceleration = gravity_acc + thrust_acc

            # 6. Angular acceleration from torque and inertia (if physics
            #    component provides inertia). Otherwise leave the previous
            #    angular acceleration untouched (point-mass behaviour).
            if pc is not None and not pc.mass_properties.is_point_mass:
                I_world_inv = pc.mass_properties.world_inverse_inertia(
                    motion_state.orientation
                )
                I_world = pc.mass_properties.world_inertia(
                    motion_state.orientation
                )
                L = I_world.transform(motion_state.angular_velocity)
                gyro = motion_state.angular_velocity.cross(L)
                motion_state.angular_acceleration = I_world_inv.transform(
                    net_torque - gyro
                )
            else:
                motion_state.angular_acceleration = Vector3(0.0, 0.0, 0.0)

            # 7. Terminate the burn if all fuel is gone.
            if state.mass.is_empty:
                for spec in state.engine_specs:
                    if spec.burning:
                        spec.burning = False
                state.active_burn_id = None

            updated += 1

        # 8. Hand integration off to Motion.
        self._motion.step(dt, require_authority=False)
        return updated

    # -- snapshot --

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        out = {}
        for eid, sc, _mc, _pc in self._iter_spacecraft():
            out[eid] = sc.to_dict()
        return out

    def restore_from_snapshot(self, data: Dict[str, Dict[str, Any]]) -> int:
        restored = 0
        for eid, sdict in data.items():
            entity = self._em.get_entity(eid)
            if entity is None:
                continue
            sc = entity.get_component(SpacecraftComponent)
            if sc is None:
                entity.add_component(SpacecraftComponent.from_dict(sdict))
            else:
                fresh = SpacecraftComponent.from_dict(sdict)
                sc.state = fresh.state
                sc.enabled = fresh.enabled
            restored += 1
        return restored
