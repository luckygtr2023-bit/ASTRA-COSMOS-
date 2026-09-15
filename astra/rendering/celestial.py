"""ASTRA Rendering - celestial rendering architecture.

Consumes existing ASTRA celestial definitions (astra.celestial) without
duplicating the celestial database. Provides renderer-independent
descriptors that a future Graphics/VFX layer and Blender bridge can consume.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from astra.mathematics import Vector3, Quaternion

from astra.celestial.classification import ObjectCategory, SpectralType, LuminosityClass
from astra.celestial.objects import CelestialObject
from astra.celestial.properties import CelestialProperties

from astra.rendering.exceptions import CelestialRenderError
from astra.rendering.render_state import RenderObject, MaterialRef
from astra.rendering.types import RenderObjectKind


# ---------------------------------------------------------------------------
# Mapping celestial category -> render kind
# ---------------------------------------------------------------------------

_CELESTIAL_TO_RENDER_KIND: Dict[ObjectCategory, RenderObjectKind] = {
    ObjectCategory.STAR: RenderObjectKind.STAR,
    ObjectCategory.WHITE_DWARF: RenderObjectKind.STAR,
    ObjectCategory.NEUTRON_STAR: RenderObjectKind.STAR,
    ObjectCategory.PULSAR: RenderObjectKind.STAR,
    ObjectCategory.BINARY_SYSTEM: RenderObjectKind.STAR,
    ObjectCategory.PLANET: RenderObjectKind.PLANET,
    ObjectCategory.DWARF_PLANET: RenderObjectKind.DWARF_PLANET,
    ObjectCategory.MOON: RenderObjectKind.MOON,
    ObjectCategory.EXOPLANET: RenderObjectKind.PLANET,
    ObjectCategory.ASTEROID: RenderObjectKind.ASTEROID,
    ObjectCategory.COMET: RenderObjectKind.COMET,
    ObjectCategory.NEBULA: RenderObjectKind.NEBULA,
    ObjectCategory.GALAXY: RenderObjectKind.GALAXY,
    ObjectCategory.STAR_CLUSTER: RenderObjectKind.STAR_CLUSTER,
    ObjectCategory.QUASAR: RenderObjectKind.GALAXY,
    ObjectCategory.AGN: RenderObjectKind.GALAXY,
    ObjectCategory.BLACK_HOLE: RenderObjectKind.BLACK_HOLE,
}


def celestial_kind_to_render_kind(cat: ObjectCategory) -> RenderObjectKind:
    return _CELESTIAL_TO_RENDER_KIND.get(cat, RenderObjectKind.UNKNOWN)


# ---------------------------------------------------------------------------
# Celestial render descriptor
# ---------------------------------------------------------------------------

@dataclass
class CelestialRenderDescriptor:
    """Renderer-independent visual description for a celestial object.

    References the authoritative CelestialObject id but carries only derived
    visual parameters (radius, color hint, spectral hint, material placeholder).
    No physics duplication.
    """

    object_id: str  # celestial identity canonical name
    name: str
    category: ObjectCategory
    render_kind: RenderObjectKind

    # Derived visual params (from CelestialProperties where available)
    radius_m: Optional[float] = None
    mass_kg: Optional[float] = None
    spectral_type: SpectralType = SpectralType.UNKNOWN
    luminosity_class: LuminosityClass = LuminosityClass.DWARF
    color_hint: Tuple[float, float, float] = (1.0, 1.0, 1.0)  # linear RGB
    absolute_magnitude: Optional[float] = None

    # Visual placeholders for future Graphics/VFX
    material: MaterialRef = field(default_factory=lambda: MaterialRef(id="celestial_default"))
    point_scale: float = 1.0  # for star/galaxy impostors
    texture_hint: Optional[str] = None

    # Hierarchy hint
    parent_id: Optional[str] = None
    children: Tuple[str, ...] = field(default_factory=tuple)

    # Provenance passthrough
    provenance: str = "simulated"
    source_label: str = "astra"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "object_id": self.object_id,
            "name": self.name,
            "category": self.category.value,
            "render_kind": self.render_kind.value,
            "radius_m": self.radius_m,
            "mass_kg": self.mass_kg,
            "spectral_type": self.spectral_type.value if hasattr(self.spectral_type, "value") else str(self.spectral_type),
            "color_hint": self.color_hint,
            "material": {"id": self.material.id, "kind": self.material.kind},
            "provenance": self.provenance,
        }


def _spectral_to_color(spectral: SpectralType) -> Tuple[float, float, float]:
    """Approximate color hint per spectral class (renderer placeholder)."""
    mapping = {
        SpectralType.O: (0.6, 0.7, 1.0),
        SpectralType.B: (0.7, 0.8, 1.0),
        SpectralType.A: (0.9, 0.9, 1.0),
        SpectralType.F: (1.0, 1.0, 0.9),
        SpectralType.G: (1.0, 0.95, 0.7),
        SpectralType.K: (1.0, 0.75, 0.4),
        SpectralType.M: (1.0, 0.5, 0.3),
        SpectralType.L: (0.9, 0.4, 0.2),
        SpectralType.T: (0.6, 0.3, 0.3),
        SpectralType.Y: (0.4, 0.3, 0.4),
        SpectralType.UNKNOWN: (1.0, 1.0, 1.0),
    }
    # SpectralType is an enum; fallback to UNKNOWN
    try:
        return mapping.get(spectral, (1.0, 1.0, 1.0))
    except Exception:
        return (1.0, 1.0, 1.0)


def describe_celestial(celestial_obj: CelestialObject, parent_id: Optional[str] = None) -> CelestialRenderDescriptor:
    """Create a render descriptor from an authoritative CelestialObject.

    Validates existence and extracts available physical parameters without
    fabricating missing data.
    """
    if not isinstance(celestial_obj, CelestialObject):
        raise CelestialRenderError(f"celestial_obj must be CelestialObject, got {type(celestial_obj).__name__}")

    identity = celestial_obj.identity
    props: CelestialProperties = celestial_obj.properties
    cat = celestial_obj.category
    kind = celestial_kind_to_render_kind(cat)

    # Extract radius/mass where available (may raise if unknown - treat as None)
    radius: Optional[float] = None
    mass: Optional[float] = None
    try:
        radius = float(props.require_radius_m())  # type: ignore
    except Exception:
        # try direct attribute access for optional fields
        try:
            v = getattr(props, "radius_m", None)
            if v is not None and not isinstance(v, bool):
                f = float(v)  # type: ignore
                if math.isfinite(f) and f > 0:
                    radius = f
        except Exception:
            pass
        # also check for None placeholder
        if radius is not None and (math.isnan(radius) or math.isinf(radius) or radius <= 0):
            radius = None

    try:
        mass = float(props.require_mass_kg())  # type: ignore
    except Exception:
        try:
            v = getattr(props, "mass_kg", None)
            if v is not None and not isinstance(v, bool):
                f = float(v)  # type: ignore
                if math.isfinite(f) and f > 0:
                    mass = f
        except Exception:
            pass
        if mass is not None and (math.isnan(mass) or math.isinf(mass) or mass <= 0):
            mass = None

    # Spectral / luminosity if star
    spectral = getattr(celestial_obj, "spectral_type", SpectralType.UNKNOWN)
    if not isinstance(spectral, SpectralType):
        spectral = SpectralType.UNKNOWN
    luminosity = getattr(celestial_obj, "luminosity_class", LuminosityClass.DWARF)
    if not isinstance(luminosity, LuminosityClass):
        luminosity = LuminosityClass.DWARF

    color = _spectral_to_color(spectral)

    # Provenance passthrough
    prov = "simulated"
    src_label = "astra"
    try:
        tag = getattr(props, "provenance", None)
        if tag is not None:
            # ProvenanceTag has .provenance and .source_label?
            prov_val = getattr(tag, "provenance", None)
            if prov_val is not None:
                # DataProvenance enum
                prov = str(getattr(prov_val, "value", prov_val))
            src = getattr(tag, "source_label", None)
            if isinstance(src, str) and src:
                src_label = src
    except Exception:
        pass

    # Material hint per category
    mat_id = f"celestial_{cat.value.lower()}"
    if kind == RenderObjectKind.STAR:
        mat_id = f"star_{spectral.value.lower()}" if hasattr(spectral, "value") else "star"
    elif kind == RenderObjectKind.GALAXY:
        mat_id = "galaxy_impostor"
    elif kind == RenderObjectKind.BLACK_HOLE:
        mat_id = "black_hole_horizon"

    return CelestialRenderDescriptor(
        object_id=identity.canonical_name if hasattr(identity, "canonical_name") else str(identity),
        name=getattr(identity, "canonical_name", str(identity)),
        category=cat,
        render_kind=kind,
        radius_m=radius,
        mass_kg=mass,
        spectral_type=spectral,
        luminosity_class=luminosity,
        color_hint=color,
        material=MaterialRef(id=mat_id, kind="celestial_placeholder"),
        provenance=prov,
        source_label=src_label,
        parent_id=parent_id,
    )


def celestial_to_render_object(
    celestial_obj: CelestialObject,
    world_position: Vector3,
    orientation: Quaternion | None = None,
    render_origin: Vector3 | None = None,
    scale: Vector3 | None = None,
) -> RenderObject:
    """Convert a celestial definition + world position to a RenderObject.

    Does NOT duplicate the celestial database; stores only a source_ref link.
    Position is converted to render space if render_origin supplied.
    """
    if not isinstance(world_position, Vector3):
        raise CelestialRenderError(f"world_position must be Vector3, got {type(world_position).__name__}")
    if not world_position.is_finite():
        raise CelestialRenderError(f"world_position must be finite, got {world_position!r}")
    desc = describe_celestial(celestial_obj)
    if render_origin is not None:
        if not isinstance(render_origin, Vector3):
            raise CelestialRenderError("render_origin must be Vector3")
        if not render_origin.is_finite():
            raise CelestialRenderError("render_origin must be finite")
        render_pos = world_position - render_origin
    else:
        render_pos = Vector3(world_position.x, world_position.y, world_position.z)

    if orientation is None:
        orientation = Quaternion.identity()
    if scale is None:
        scale = Vector3(1.0, 1.0, 1.0)

    # Radius for bounding sphere: use celestial radius if known else heuristic per kind
    radius_m = desc.radius_m
    if radius_m is None or not math.isfinite(radius_m) or radius_m <= 0:
        # Heuristic fallback for rendering; does not affect physics
        heuristics = {
            RenderObjectKind.STAR: 6.96e8,
            RenderObjectKind.PLANET: 6.371e6,
            RenderObjectKind.MOON: 1.7e6,
            RenderObjectKind.GALAXY: 5e20,
            RenderObjectKind.NEBULA: 1e18,
            RenderObjectKind.ASTEROID: 5e3,
            RenderObjectKind.COMET: 5e3,
            RenderObjectKind.BLACK_HOLE: 3e3,  # minimal horizon hint
        }
        radius_m = heuristics.get(desc.render_kind, 1.0)

    # Galaxy / nebula are emissive
    emissive = desc.render_kind in (RenderObjectKind.STAR, RenderObjectKind.GALAXY, RenderObjectKind.NEBULA, RenderObjectKind.STAR_CLUSTER)

    return RenderObject(
        id=f"celestial_{desc.object_id}",
        name=desc.name,
        kind=desc.render_kind,
        category=desc.category.value,
        position=render_pos,
        orientation=orientation,
        scale=scale,
        bounding_radius_m=float(radius_m),
        material=desc.material,
        provenance=desc.provenance,
        source_ref=desc.object_id,
        tags=(desc.category.value, desc.render_kind.value),
        metadata={
            "spectral_type": desc.spectral_type.value if hasattr(desc.spectral_type, "value") else str(desc.spectral_type),
            "color_hint": desc.color_hint,
            "texture_hint": desc.texture_hint,
        },
        receives_light=not emissive,
        emissive=emissive,
        casts_shadow=False,
    )
