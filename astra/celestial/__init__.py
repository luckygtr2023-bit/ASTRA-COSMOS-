"""ASTRA Celestial layer.

Dependency direction:
    CORE -> ... -> SPACETIME -> THEORETICAL -> TEMPORAL -> CELESTIAL

Astronomical DOMAIN ARCHITECTURE: immutable definitions of celestial
objects (identity, taxonomy, physical/photometric properties) with strict
provenance tracking. This layer computes NO physics:

    - state          : astra.motion (current), astra.temporal (history)
    - dynamics       : astra.physics / astra.nbody
    - orbits         : astra.orbital
    - BH geometry    : astra.blackhole (delegated by BlackHoleObject)
    - barycenters    : astra.nbody.barycenter

DATA HONESTY CONTRACTS
    - Unknown quantities are None (Optional), never 0.0 placeholders.
    - Physics pipelines read via require_mass_kg()/require_radius_m(),
      which raise IncompletePhysicalDataError on unknown data - a specific,
      explicit failure instead of a fabricated value.
    - Every property block carries a DataProvenance tag (REAL / DERIVED /
      SIMULATED / THEORETICAL / SPECULATIVE).
    - No astronomical datasets are embedded, downloaded, or faked in this
      layer; aliases are receptacles for a future ingestion pipeline.

HIERARCHY: parent-child structure is a strict DAG (CyclicHierarchyError);
mass aggregation fails honestly rather than returning partial sums.

Determinism: identities derive ids deterministically (sha256 of the
canonical name); no RNG anywhere.
"""
from astra.celestial.exceptions import (
    CelestialError,
    InvalidPropertyError,
    IncompletePhysicalDataError,
    CyclicHierarchyError,
    DuplicateNodeError,
)
from astra.celestial.provenance import (
    DataProvenance,
    ScientificConfidence,
    ProvenanceTag,
    DEFAULT_CONFIDENCE,
)
from astra.celestial.identity import CelestialIdentity, ensure_distinct
from astra.celestial.classification import (
    ObjectCategory,
    SpectralType,
    LuminosityClass,
    HOST_CATEGORIES,
)
from astra.celestial.properties import CelestialProperties
from astra.celestial.hierarchy import HierarchyNode
from astra.celestial.objects import (
    CelestialObject,
    Star,
    BinarySystem,
    WhiteDwarf,
    NeutronStar,
    Pulsar,
    Planet,
    DwarfPlanet,
    Moon,
    Exoplanet,
    Asteroid,
    Comet,
    Nebula,
    Galaxy,
    StarCluster,
    Quasar,
    AGN,
    BlackHoleObject,
)
from astra.celestial import api
from astra.celestial.api import (
    create_identity,
    create_properties,
    create_star,
    create_planet,
    create_black_hole_object,
    build_hierarchy,
    get_category,
)

__all__ = [
    # exceptions
    "CelestialError", "InvalidPropertyError", "IncompletePhysicalDataError",
    "CyclicHierarchyError", "DuplicateNodeError",
    # provenance
    "DataProvenance", "ScientificConfidence", "ProvenanceTag",
    "DEFAULT_CONFIDENCE",
    # identity / taxonomy
    "CelestialIdentity", "ensure_distinct", "ObjectCategory", "SpectralType",
    "LuminosityClass", "HOST_CATEGORIES",
    # properties & hierarchy
    "CelestialProperties", "HierarchyNode",
    # domain objects
    "CelestialObject", "Star", "BinarySystem", "WhiteDwarf", "NeutronStar",
    "Pulsar", "Planet", "DwarfPlanet", "Moon", "Exoplanet", "Asteroid",
    "Comet", "Nebula", "Galaxy", "StarCluster", "Quasar", "AGN",
    "BlackHoleObject",
    # facade
    "api", "create_identity", "create_properties", "create_star",
    "create_planet", "create_black_hole_object", "build_hierarchy",
    "get_category",
]
