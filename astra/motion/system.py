"""MotionSystem — deterministic updater for MotionComponents.

Design
------
- Iterates entities returned by EntityManager.query (insertion order ->
  deterministic).
- Requires CORE authority by default (simulation thread only).
- No global RNG, no wall-clock; caller supplies dt (from SimulationClock).
- Snapshot/restore is exposed so a future engine integration layer can
  persist motion state without modifying CORE persistence.
"""
from __future__ import annotations
from typing import Dict, Any, Iterable, Optional, Tuple

from astra.core.entities import EntityManager, Query
from astra.core.threading import AuthorityContext
from astra.motion.components import MotionComponent
from astra.motion.integrators import Integrator, SemiImplicitEulerIntegrator
from astra.motion.state import validate_timestep


class MotionSystem:
    """Advances all MotionComponents owned by an EntityManager."""

    def __init__(self,
                 entity_manager: EntityManager,
                 integrator: Optional[Integrator] = None):
        self._em = entity_manager
        self._integrator: Integrator = integrator or SemiImplicitEulerIntegrator()

    @property
    def integrator(self) -> Integrator:
        return self._integrator

    def _iter_components(self) -> Iterable[Tuple[str, MotionComponent]]:
        query = Query().with_component(MotionComponent)
        for entity in self._em.query(query):
            comp = entity.get_component(MotionComponent)
            if comp is None:
                continue
            yield entity.id.value, comp

    def step(self, dt: float, require_authority: bool = True) -> int:
        """Advance every enabled MotionComponent by dt.

        Returns the number of components updated.
        """
        validate_timestep(dt)
        if require_authority:
            AuthorityContext.require_authority("motion.step")
        updated = 0
        for _eid, comp in self._iter_components():
            if not comp.enabled:
                continue
            new_state = self._integrator.step(comp.state, dt)
            new_state.validate()
            comp.state = new_state
            updated += 1
        return updated

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Return a serializable dict keyed by entity ID."""
        out: Dict[str, Dict[str, Any]] = {}
        for eid, comp in self._iter_components():
            out[eid] = comp.to_dict()
        return out

    def restore_from_snapshot(self, data: Dict[str, Dict[str, Any]]) -> int:
        """Restore component states keyed by entity ID.

        Entities must already exist. Existing MotionComponents are
        overwritten; missing entities are skipped.
        """
        restored = 0
        for eid, cdict in data.items():
            entity = self._em.get_entity(eid)
            if entity is None:
                continue
            comp = entity.get_component(MotionComponent)
            if comp is None:
                new_comp = MotionComponent.from_dict(cdict)
                entity.add_component(new_comp)
                restored += 1
            else:
                restored_comp = MotionComponent.from_dict(cdict)
                comp.state = restored_comp.state
                comp.enabled = restored_comp.enabled
                restored += 1
        return restored
