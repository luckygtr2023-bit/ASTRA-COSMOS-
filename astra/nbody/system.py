"""NBodySystem — deterministic N-body state, integration, persistence.

Design
------
- Bodies stored in an ordered list; identity and iteration order are stable.
- No global RNG, no wall-clock, no unordered iteration.
- Acceleration caching: computes once per step.
- Authority: mutating operations (step, add_body, remove_body) require
  CORE simulation-thread authority via AuthorityContext.
- Standalone (not tied to CORE entities). Bridges to Motion/Physics via
  `from_motion_physics_entities` and `write_to_motion_physics_entities`.
"""
from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional

from astra.core.threading import AuthorityContext
from astra.mathematics import Vector3
from astra.physics.constants import GRAVITATIONAL_CONSTANT, DEFAULT_SOFTENING
from astra.nbody.bodies import NBodyBody
from astra.nbody.errors import DuplicateBodyError, InvalidBodyError
from astra.nbody.gravity import compute_accelerations
from astra.nbody.integration import velocity_verlet_step
from astra.nbody.diagnostics import (
    total_linear_momentum, total_energy, kinetic_energy,
    total_angular_momentum,
)
from astra.nbody.barycenter import (
    total_mass, center_of_mass, center_of_mass_velocity,
)


class NBodySystem:
    """Ordered collection of NBodyBody instances with a Velocity Verlet stepper."""

    def __init__(
        self,
        bodies: Optional[Iterable[NBodyBody]] = None,
        G: float = GRAVITATIONAL_CONSTANT,
        softening: float = DEFAULT_SOFTENING,
    ):
        self._bodies: List[NBodyBody] = list(bodies or [])
        self._G = float(G)
        self._softening = float(softening)
        self._accelerations: Optional[List[Vector3]] = None
        self._validate_unique_ids()

    # -- properties --

    @property
    def G(self) -> float:
        return self._G

    @property
    def softening(self) -> float:
        return self._softening

    @property
    def bodies(self) -> List[NBodyBody]:
        return list(self._bodies)

    def __len__(self) -> int:
        return len(self._bodies)

    # -- validation --

    def _validate_unique_ids(self) -> None:
        seen = set()
        for b in self._bodies:
            if b.id in seen:
                raise DuplicateBodyError(f"duplicate body id: {b.id!r}")
            seen.add(b.id)

    # -- mutation --

    def add_body(self, body: NBodyBody, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("nbody.add_body")
        if any(b.id == body.id for b in self._bodies):
            raise DuplicateBodyError(f"duplicate body id: {body.id!r}")
        self._bodies.append(body)
        self._accelerations = None

    def remove_body(self, body_id: str, require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("nbody.remove_body")
        for i, b in enumerate(self._bodies):
            if b.id == body_id:
                del self._bodies[i]
                self._accelerations = None
                return
        raise InvalidBodyError(f"body not found: {body_id!r}")

    def replace_bodies(self, bodies: Iterable[NBodyBody],
                       require_authority: bool = True) -> None:
        if require_authority:
            AuthorityContext.require_authority("nbody.replace_bodies")
        self._bodies = list(bodies)
        self._validate_unique_ids()
        self._accelerations = None

    # -- acceleration caching --

    def accelerations(self) -> List[Vector3]:
        if self._accelerations is None:
            self._accelerations = compute_accelerations(
                self._bodies, G=self._G, softening=self._softening
            )
        return list(self._accelerations)

    # -- step --

    def step(self, dt: float, require_authority: bool = True) -> None:
        """Advance the system by dt using velocity Verlet."""
        if require_authority:
            AuthorityContext.require_authority("nbody.step")
        new_bodies, new_accels = velocity_verlet_step(
            self._bodies, dt, G=self._G, softening=self._softening
        )
        self._bodies = new_bodies
        self._accelerations = new_accels

    # -- diagnostics --

    def total_mass(self) -> float:
        return total_mass(self._bodies)

    def center_of_mass(self) -> Vector3:
        return center_of_mass(self._bodies)

    def center_of_mass_velocity(self) -> Vector3:
        return center_of_mass_velocity(self._bodies)

    def total_linear_momentum(self) -> Vector3:
        return total_linear_momentum(self._bodies)

    def total_angular_momentum(self, about_origin: bool = True) -> Vector3:
        return total_angular_momentum(self._bodies, about_origin=about_origin)

    def kinetic_energy(self) -> float:
        return kinetic_energy(self._bodies)

    def total_energy(self) -> float:
        return total_energy(self._bodies, G=self._G, softening=self._softening)

    def is_finite(self) -> bool:
        for b in self._bodies:
            if not (b.position.is_finite() and b.velocity.is_finite()):
                return False
        return True

    # -- persistence --

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "G": self._G,
            "softening": self._softening,
            "bodies": [b.to_dict() for b in self._bodies],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NBodySystem":
        schema = d.get("schema_version", "1.0.0")
        if schema != "1.0.0":
            raise InvalidBodyError(f"unsupported schema_version: {schema!r}")
        if "bodies" not in d:
            raise InvalidBodyError("missing 'bodies' field")
        bodies = [NBodyBody.from_dict(bd) for bd in d["bodies"]]
        return cls(
            bodies=bodies,
            G=float(d.get("G", GRAVITATIONAL_CONSTANT)),
            softening=float(d.get("softening", DEFAULT_SOFTENING)),
        )

    # -- CORE entity bridge (Motion + Physics) --

    @classmethod
    def from_motion_physics_entities(
        cls,
        entity_manager,
        G: float = GRAVITATIONAL_CONSTANT,
        softening: float = DEFAULT_SOFTENING,
    ) -> "NBodySystem":
        """Build a system from entities that carry both MotionComponent and
        PhysicsComponent. Uses CORE's EntityManager iteration order.
        """
        from astra.motion.components import MotionComponent
        from astra.physics.components import PhysicsComponent
        bodies: List[NBodyBody] = []
        for entity in entity_manager.get_all_entities():
            mc = entity.get_component(MotionComponent)
            pc = entity.get_component(PhysicsComponent)
            if mc is None or pc is None:
                continue
            if pc.mass_properties.is_static:
                continue
            bodies.append(NBodyBody(
                id=entity.id.value,
                mass=pc.mass_properties.mass,
                position=mc.state.position,
                velocity=mc.state.velocity,
            ))
        return cls(bodies=bodies, G=G, softening=softening)

    def write_to_motion_physics_entities(
        self, entity_manager, require_authority: bool = True
    ) -> int:
        """Write each body's position/velocity into the matching MotionComponent.

        Requires authority (mutation of simulation state).
        """
        if require_authority:
            AuthorityContext.require_authority("nbody.write_to_entities")
        from astra.motion.components import MotionComponent
        updated = 0
        for b in self._bodies:
            entity = entity_manager.get_entity(b.id)
            if entity is None:
                continue
            mc = entity.get_component(MotionComponent)
            if mc is None:
                continue
            mc.state.position = b.position
            mc.state.velocity = b.velocity
            updated += 1
        return updated
