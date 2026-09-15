"""ASTRA Rendering - destruction / impact visual boundary.

Consumes authoritative destruction outputs (astra.destruction) without
re-implementing physics. Exposes visual states INTACT..DESTROYED plus
fragments / ejecta / debris as RenderObjects for the renderer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from astra.mathematics import Vector3, Quaternion

from astra.rendering.exceptions import RenderStateError
from astra.rendering.render_state import RenderObject, MaterialRef
from astra.rendering.types import DamageVisualState, RenderObjectKind


# Map destruction DamageState -> visual DamageVisualState (same names but independent enum for rendering)
def _map_damage_state(destruction_state) -> DamageVisualState:
    """Map astra.destruction.damage.DamageState to rendering DamageVisualState."""
    name = getattr(destruction_state, "value", str(destruction_state))
    try:
        return DamageVisualState(name)
    except ValueError:
        # fallback by ordering
        order = {"INTACT": 0, "DAMAGED": 1, "FRACTURED": 2, "FRAGMENTED": 3, "DESTROYED": 4}
        n = name.upper() if isinstance(name, str) else "INTACT"
        return DamageVisualState(n) if n in order else DamageVisualState.INTACT


@dataclass
class FragmentVisual:
    """Visual representation of a fragment (derived)."""

    fragment_id: str
    parent_id: str
    mass_kg: float
    position: Vector3
    velocity: Optional[Vector3] = None
    radius_m: float = 1.0
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="fragment_default", kind="fragment_placeholder"))

    def to_render_object(self, render_origin: Optional[Vector3] = None) -> RenderObject:
        pos = self.position - render_origin if render_origin is not None else Vector3(self.position.x, self.position.y, self.position.z)
        return RenderObject(
            id=self.fragment_id,
            name=f"Fragment {self.fragment_id}",
            kind=RenderObjectKind.FRAGMENT,
            category="FRAGMENT",
            position=pos,
            bounding_radius_m=float(self.radius_m),
            material=self.material,
            damage_state=DamageVisualState.FRAGMENTED,
            metadata={"mass_kg": self.mass_kg, "parent_id": self.parent_id, "velocity": self.velocity.to_tuple() if self.velocity else None},
            source_ref=self.parent_id,
        )


@dataclass
class EjectaVisual:
    ejecta_id: str
    impact_id: str
    source_id: str
    mass_kg: float
    position: Vector3
    velocity: Vector3
    kinetic_energy_j: float = 0.0
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="ejecta_default", kind="ejecta_placeholder"))

    def to_render_object(self, render_origin: Optional[Vector3] = None) -> RenderObject:
        pos = self.position - render_origin if render_origin is not None else Vector3(self.position.x, self.position.y, self.position.z)
        # Ejecta are tiny point-like; use small radius hint
        radius = max(0.1, min(10.0, (self.mass_kg / 1000.0) ** (1.0/3.0))) if self.mass_kg > 0 else 0.5
        return RenderObject(
            id=self.ejecta_id,
            name=f"Ejecta {self.ejecta_id}",
            kind=RenderObjectKind.EJECTA,
            category="EJECTA",
            position=pos,
            bounding_radius_m=float(radius),
            material=self.material,
            damage_state=DamageVisualState.FRAGMENTED,
            metadata={
                "mass_kg": self.mass_kg,
                "kinetic_energy_j": self.kinetic_energy_j,
                "source_id": self.source_id,
                "impact_id": self.impact_id,
                "velocity": self.velocity.to_tuple(),
            },
            source_ref=self.source_id,
        )


@dataclass
class DebrisVisual:
    debris_id: str
    origin_impact_id: str
    mass_kg: float
    position: Vector3
    velocity: Vector3
    is_ejecta: bool = False
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="debris_default", kind="debris_placeholder"))

    def to_render_object(self, render_origin: Optional[Vector3] = None) -> RenderObject:
        pos = self.position - render_origin if render_origin is not None else Vector3(self.position.x, self.position.y, self.position.z)
        radius = max(0.2, min(50.0, (self.mass_kg / 2000.0) ** (1.0/3.0))) if self.mass_kg > 0 else 1.0
        return RenderObject(
            id=self.debris_id,
            name=f"Debris {self.debris_id}",
            kind=RenderObjectKind.DEBRIS,
            category="DEBRIS",
            position=pos,
            bounding_radius_m=float(radius),
            material=self.material,
            metadata={"mass_kg": self.mass_kg, "origin_impact_id": self.origin_impact_id, "is_ejecta": self.is_ejecta},
            source_ref=self.origin_impact_id,
        )


@dataclass
class DestructionVisualState:
    """Aggregate visual state for a destroyed/damaged object."""

    object_id: str
    damage_state: DamageVisualState = DamageVisualState.INTACT
    fragments: Tuple[FragmentVisual, ...] = field(default_factory=tuple)
    ejecta: Tuple[EjectaVisual, ...] = field(default_factory=tuple)
    debris: Tuple[DebrisVisual, ...] = field(default_factory=tuple)
    impact_id: Optional[str] = None
    # For rendering: should the original object still be visible?
    # INTACT/DAMAGED: yes, FRACTURED: yes with cracks, FRAGMENTED/DESTROYED: original hidden, fragments shown
    original_visible: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.object_id, str) or not self.object_id:
            raise RenderStateError("DestructionVisualState.object_id must be non-empty string")
        if not isinstance(self.damage_state, DamageVisualState):
            raise RenderStateError(f"damage_state must be DamageVisualState, got {self.damage_state!r}")
        if self.damage_state in (DamageVisualState.FRAGMENTED, DamageVisualState.DESTROYED):
            self.original_visible = False
        elif self.damage_state == DamageVisualState.FRACTURED:
            self.original_visible = True

    def to_render_objects(self, render_origin: Optional[Vector3] = None) -> List[RenderObject]:
        out: List[RenderObject] = []
        for frag in self.fragments:
            out.append(frag.to_render_object(render_origin))
        for ej in self.ejecta:
            out.append(ej.to_render_object(render_origin))
        for db in self.debris:
            out.append(db.to_render_object(render_origin))
        return out

    def summary(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "damage_state": self.damage_state.value,
            "fragment_count": len(self.fragments),
            "ejecta_count": len(self.ejecta),
            "debris_count": len(self.debris),
            "original_visible": self.original_visible,
            "impact_id": self.impact_id,
        }


def destruction_result_to_visual(
    impact_result,
    render_origin: Optional[Vector3] = None,
) -> DestructionVisualState:
    """Convert an authoritative ImpactResult to a visual state.

    Consumes fragments/ejecta/debris lists without recomputing physics.
    """
    # Duck-type ImpactResult: expect .target_state_after, .fragments/.ejecta/.debris/.event
    try:
        target_after = getattr(impact_result, "target_state_after", None)
        visual_damage = _map_damage_state(target_after) if target_after is not None else DamageVisualState.INTACT

        # Extract object_id / impact_id
        event = getattr(impact_result, "event", None)
        target_id = getattr(event, "target_id", "unknown") if event is not None else getattr(impact_result, "target_id", "unknown")
        impact_id = getattr(event, "impact_id", None) if event is not None else getattr(impact_result, "impact_id", None)

        fragments: List[FragmentVisual] = []
        for frag_state in getattr(impact_result, "fragments", ()):
            # FragmentState has fragment_id, parent_id, mass_kg, position, velocity
            try:
                fid = getattr(frag_state, "fragment_id", str(id(frag_state)))
                parent = getattr(frag_state, "parent_id", target_id)
                mass = float(getattr(frag_state, "mass_kg", 1.0))
                pos = getattr(frag_state, "position", Vector3(0, 0, 0))
                vel = getattr(frag_state, "velocity", None)
                if not isinstance(pos, Vector3):
                    # try to convert from tuple
                    pos = Vector3(float(pos[0]), float(pos[1]), float(pos[2])) if pos is not None else Vector3(0, 0, 0)
                if vel is not None and not isinstance(vel, Vector3):
                    try:
                        vel = Vector3(float(vel[0]), float(vel[1]), float(vel[2]))
                    except Exception:
                        vel = None
                fragments.append(FragmentVisual(fragment_id=str(fid), parent_id=str(parent), mass_kg=float(mass), position=pos, velocity=vel))
            except Exception:
                continue

        ejecta: List[EjectaVisual] = []
        for ej_state in getattr(impact_result, "ejecta", ()):
            try:
                eid = getattr(ej_state, "ejecta_id", str(id(ej_state)))
                src = getattr(ej_state, "source_id", target_id)
                mass = float(getattr(ej_state, "mass_kg", 0.1))
                pos = getattr(ej_state, "position", Vector3(0, 0, 0))
                vel = getattr(ej_state, "velocity", Vector3(0, 0, 0))
                ke = float(getattr(ej_state, "kinetic_energy_j", 0.0))
                if not isinstance(pos, Vector3):
                    pos = Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
                if not isinstance(vel, Vector3):
                    vel = Vector3(float(vel[0]), float(vel[1]), float(vel[2]))
                ejecta.append(EjectaVisual(ejecta_id=str(eid), impact_id=str(impact_id) if impact_id else "unknown", source_id=str(src), mass_kg=mass, position=pos, velocity=vel, kinetic_energy_j=ke))
            except Exception:
                continue

        debris: List[DebrisVisual] = []
        for db_state in getattr(impact_result, "debris", ()):
            try:
                did = getattr(db_state, "debris_id", str(id(db_state)))
                mass = float(getattr(db_state, "mass_kg", 1.0))
                pos = getattr(db_state, "position", Vector3(0, 0, 0))
                vel = getattr(db_state, "velocity", Vector3(0, 0, 0))
                is_ej = bool(getattr(db_state, "is_ejecta", False))
                if not isinstance(pos, Vector3):
                    pos = Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
                if not isinstance(vel, Vector3):
                    vel = Vector3(float(vel[0]), float(vel[1]), float(vel[2]))
                debris.append(DebrisVisual(debris_id=str(did), origin_impact_id=str(impact_id) if impact_id else str(did), mass_kg=mass, position=pos, velocity=vel, is_ejecta=is_ej))
            except Exception:
                continue

        return DestructionVisualState(
            object_id=str(target_id),
            damage_state=visual_damage,
            fragments=tuple(fragments),
            ejecta=tuple(ejecta),
            debris=tuple(debris),
            impact_id=str(impact_id) if impact_id is not None else None,
        )
    except Exception as e:
        raise RenderStateError(f"failed to convert destruction result to visual: {e}") from e


def apply_destruction_visual_to_object(
    render_obj: RenderObject,
    visual_state: DestructionVisualState,
) -> RenderObject:
    """Enrich a RenderObject with destruction visual info (does not mutate original)."""
    if not isinstance(render_obj, RenderObject):
        raise RenderStateError("render_obj must be RenderObject")
    if not isinstance(visual_state, DestructionVisualState):
        raise RenderStateError("visual_state must be DestructionVisualState")
    cloned = render_obj.clone()
    cloned.damage_state = visual_state.damage_state
    cloned.fragment_ids = tuple(f.fragment_id for f in visual_state.fragments)
    cloned.ejecta_ids = tuple(e.ejecta_id for e in visual_state.ejecta)
    # Hide original if fragmented/destroyed
    if not visual_state.original_visible:
        cloned.visible = False
        cloned.visibility = cloned.visibility  # keep as is? but rendering will hide via damage_state? We set visible false
    cloned.metadata = dict(cloned.metadata)
    cloned.metadata.update({
        "damage_state": visual_state.damage_state.value,
        "impact_id": visual_state.impact_id,
        "fragment_count": len(visual_state.fragments),
    })
    return cloned
