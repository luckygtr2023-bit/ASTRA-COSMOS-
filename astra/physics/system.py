"""PhysicsSystem — deterministic force evaluation and Motion handoff.

Design
------
For each enabled entity that has both a MotionComponent and a
PhysicsComponent:

1. Evaluate every registered ForceSource in insertion order.
2. Sum forces and torques into a ForceAccumulator.
3. Compute acceleration a = F * inv_m (world frame).
4. Compute angular acceleration using Euler's equation in world frame:
       tau_total = I_world * alpha + omega x (I_world * omega)
   =>  alpha = I_world^-1 * (tau_total - omega x (I_world * omega))
5. Write a and alpha into the MotionState.
6. Hand off to MotionSystem.step(dt) which performs the integration.

Physics does NOT integrate. Motion does.
Physics does NOT own the state; Motion owns the state.

Authority
---------
`step` requires the CORE simulation-thread authority by default.
"""
from __future__ import annotations
from typing import Iterable, List, Optional, Tuple

from astra.core.entities import EntityManager, Query
from astra.core.threading import AuthorityContext
from astra.mathematics import Vector3
from astra.motion import MotionComponent, MotionSystem, validate_timestep
from astra.physics.components import PhysicsComponent
from astra.physics.forces import ForceAccumulator, ForceSource


class PhysicsSystem:
    """Orchestrates force evaluation and Motion handoff."""

    def __init__(
        self,
        entity_manager: EntityManager,
        motion_system: MotionSystem,
        force_sources: Optional[Iterable[ForceSource]] = None,
    ):
        self._em = entity_manager
        self._motion = motion_system
        self._sources: List[ForceSource] = list(force_sources or [])

    # -- source management --

    def add_source(self, source: ForceSource) -> None:
        self._sources.append(source)

    def remove_source(self, source: ForceSource) -> None:
        self._sources.remove(source)

    def clear_sources(self) -> None:
        self._sources.clear()

    @property
    def sources(self) -> Tuple[ForceSource, ...]:
        return tuple(self._sources)

    # -- iteration --

    def _iter_bodies(self) -> Iterable[Tuple[str, PhysicsComponent, MotionComponent]]:
        query = Query().with_component(PhysicsComponent).with_component(MotionComponent)
        for entity in self._em.query(query):
            pc = entity.get_component(PhysicsComponent)
            mc = entity.get_component(MotionComponent)
            if pc is None or mc is None:
                continue
            yield entity.id.value, pc, mc

    # -- force evaluation --

    def compute_forces(self, dt: float, require_authority: bool = True) -> int:
        """Evaluate all sources and write acceleration into MotionState.

        Returns the number of bodies updated.
        """
        validate_timestep(dt)
        if require_authority:
            AuthorityContext.require_authority("physics.compute_forces")

        updated = 0
        for _eid, pc, mc in self._iter_bodies():
            if not pc.enabled or not mc.enabled:
                continue
            mp = pc.mass_properties
            state = mc.state

            acc = ForceAccumulator()
            # Sources evaluated in insertion order (deterministic).
            for src in self._sources:
                applications = src.evaluate(
                    mass=mp.mass,
                    position=state.position,
                    orientation=state.orientation,
                    velocity=state.velocity,
                    angular_velocity=state.angular_velocity,
                    dt=dt,
                )
                for app in applications:
                    acc.add(app)

            # Linear acceleration: a = F * inv_m (static bodies: zero).
            state.acceleration = acc.net_force * mp.inverse_mass

            # Angular acceleration via Euler's equation in world frame.
            if mp.is_point_mass or mp.is_static:
                state.angular_acceleration = Vector3(0.0, 0.0, 0.0)
            else:
                I_world = mp.world_inertia(state.orientation)
                I_world_inv = mp.world_inverse_inertia(state.orientation)
                L = I_world.transform(state.angular_velocity)
                gyro = state.angular_velocity.cross(L)
                alpha = I_world_inv.transform(acc.net_torque - gyro)
                state.angular_acceleration = alpha

            updated += 1
        return updated

    # -- step --

    def step(self, dt: float, require_authority: bool = True) -> int:
        """Evaluate forces and integrate Motion. Returns bodies updated."""
        validate_timestep(dt)
        if require_authority:
            AuthorityContext.require_authority("physics.step")
            n = self.compute_forces(dt, require_authority=False)
            self._motion.step(dt, require_authority=False)
        else:
            n = self.compute_forces(dt, require_authority=False)
            self._motion.step(dt, require_authority=False)
        return n

    # -- snapshot --

    def snapshot(self) -> dict:
        out = {}
        for eid, pc, _mc in self._iter_bodies():
            out[eid] = pc.to_dict()
        return out

    def restore_from_snapshot(self, data: dict) -> int:
        restored = 0
        for eid, pdict in data.items():
            entity = self._em.get_entity(eid)
            if entity is None:
                continue
            pc = entity.get_component(PhysicsComponent)
            if pc is None:
                entity.add_component(PhysicsComponent.from_dict(pdict))
            else:
                new = PhysicsComponent.from_dict(pdict)
                pc.mass_properties = new.mass_properties
                pc.enabled = new.enabled
            restored += 1
        return restored
