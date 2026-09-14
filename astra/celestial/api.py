"""ASTRA Celestial - authoritative facade API.

Contract: external subsystems build celestial definitions through THIS
module only. Dependency direction (no reverse edges):

    ... -> SPACETIME -> THEORETICAL -> TEMPORAL -> CELESTIAL

Definitions are immutable; dynamics/state remain with the owning
subsystems (motion/nbody/temporal). No datasets are embedded or fetched.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from astra.celestial.classification import (
    HOST_CATEGORIES,
    LuminosityClass,
    ObjectCategory,
    SpectralType,
)
from astra.celestial.hierarchy import HierarchyNode
from astra.celestial.identity import CelestialIdentity, ensure_distinct
from astra.celestial.objects import (
    AGN,
    Asteroid,
    BinarySystem,
    BlackHoleObject,
    Comet,
    DwarfPlanet,
    Exoplanet,
    Galaxy,
    Moon,
    Nebula,
    NeutronStar,
    Planet,
    Pulsar,
    Quasar,
    Star,
    StarCluster,
    WhiteDwarf,
)
from astra.celestial.properties import CelestialProperties
from astra.celestial.provenance import (
    DataProvenance,
    ProvenanceTag,
    ScientificConfidence,
)


def create_identity(canonical_name: str,
                    aliases: Sequence[Tuple[str, str]] = ()) -> CelestialIdentity:
    """Deterministic celestial identity (no RNG)."""
    return CelestialIdentity(canonical_name, tuple(aliases))


def create_properties(provenance: DataProvenance = DataProvenance.SIMULATED_DATA,
                      source_label: str = "astra", **fields) -> CelestialProperties:
    """Validated, immutable property block with strict unknown semantics."""
    return CelestialProperties(provenance=ProvenanceTag(provenance, source_label),
                               **fields)


def create_star(identity: CelestialIdentity, properties: CelestialProperties,
                spectral_type: SpectralType = SpectralType.UNKNOWN,
                luminosity_class: LuminosityClass = LuminosityClass.DWARF) -> Star:
    return Star(identity, properties, ObjectCategory.STAR, spectral_type,
                luminosity_class)


def create_planet(identity: CelestialIdentity, properties: CelestialProperties,
                  kind: ObjectCategory = ObjectCategory.PLANET) -> Planet:
    """Planet-family factory: PLANET, DWARF_PLANET, MOON, EXOPLANET."""
    if kind not in (ObjectCategory.PLANET, ObjectCategory.DWARF_PLANET,
                    ObjectCategory.MOON, ObjectCategory.EXOPLANET):
        raise TypeError(f"{kind!r} is not a planetary category")
    cls = {
        ObjectCategory.PLANET: Planet,
        ObjectCategory.DWARF_PLANET: DwarfPlanet,
        ObjectCategory.MOON: Moon,
        ObjectCategory.EXOPLANET: Exoplanet,
    }[kind]
    return cls(identity, properties, kind)


def create_black_hole_object(identity: CelestialIdentity,
                             properties: CelestialProperties,
                             spin_param: float = 0.0) -> BlackHoleObject:
    """Black-hole definition; geometry delegates to astra.blackhole."""
    return BlackHoleObject(identity, properties, ObjectCategory.BLACK_HOLE,
                           spin_param)


def build_hierarchy(root_identity: CelestialIdentity,
                    properties: Optional[CelestialProperties] = None
                    ) -> HierarchyNode:
    """Create a hierarchy root node."""
    node = HierarchyNode(root_identity)
    if properties is not None:
        node.attach_properties(properties)
    return node


def get_category(obj: CelestialObject) -> ObjectCategory:
    return obj.category


__all__ = [
    "create_identity", "create_properties", "create_star", "create_planet",
    "create_black_hole_object", "build_hierarchy", "get_category",
    "ensure_distinct",
    # re-exports
    "CelestialIdentity", "CelestialProperties", "ProvenanceTag",
    "DataProvenance", "ScientificConfidence", "HierarchyNode",
    "ObjectCategory", "SpectralType", "LuminosityClass", "HOST_CATEGORIES",
    "Star", "BinarySystem", "WhiteDwarf", "NeutronStar", "Pulsar",
    "Planet", "DwarfPlanet", "Moon", "Exoplanet", "Asteroid", "Comet",
    "Nebula", "Galaxy", "StarCluster", "Quasar", "AGN", "BlackHoleObject",
]
