"""Structural types."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple, Union

from .errors import GalacticNumericalError, GalacticValidationError
from .provenance import DerivedValue, ObservedValue, Provenance, SimulatedValue, UnknownValue

AnyValue = Union[ObservedValue, DerivedValue, SimulatedValue, UnknownValue]


def _finite(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise GalacticNumericalError(f"{name} must be numeric")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise GalacticNumericalError(f"{name} must be finite, got {fv}")
    return fv


@dataclass(frozen=True)
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "x", _finite("Vec3.x", self.x))
        object.__setattr__(self, "y", _finite("Vec3.y", self.y))
        object.__setattr__(self, "z", _finite("Vec3.z", self.z))

    def __add__(self, o): return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)
    def __sub__(self, o): return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)
    def __mul__(self, s): return Vec3(self.x * float(s), self.y * float(s), self.z * float(s))
    __rmul__ = __mul__
    def dot(self, o): return self.x * o.x + self.y * o.y + self.z * o.z
    def norm(self): return math.sqrt(self.dot(self))
    def magnitude(self): return self.norm()
    def to_tuple(self): return (self.x, self.y, self.z)
    def to_vector3(self):
        try:
            from astra.mathematics import Vector3
            return Vector3(self.x, self.y, self.z)
        except Exception:
            return self
    def is_finite(self): return math.isfinite(self.x) and math.isfinite(self.y) and math.isfinite(self.z)

    @classmethod
    def from_tuple(cls, t): return cls(float(t[0]), float(t[1]), float(t[2]))


class Frame(str, Enum):
    LOCAL = "LOCAL"
    WORLD = "WORLD"
    ICRS = "ICRS"
    GALACTIC = "GALACTIC"
    COMOVING = "COMOVING"
    OBSERVER = "OBSERVER"


class DistanceKind(str, Enum):
    PROPER = "PROPER"
    COMOVING = "COMOVING"
    LUMINOSITY = "LUMINOSITY"
    ANGULAR_DIAMETER = "ANGULAR_DIAMETER"
    REDSHIFT_DERIVED = "REDSHIFT_DERIVED"


@dataclass(frozen=True)
class CoordinateContext:
    """Carries frame + scale factor + epoch. Every distance call declares this."""
    frame: Frame
    scale_factor: float
    epoch_gyr: float
    reference_object_id: Optional[str] = None

    def __post_init__(self):
        _finite("scale_factor", self.scale_factor)
        _finite("epoch_gyr", self.epoch_gyr)
        if self.scale_factor <= 0.0:
            raise GalacticNumericalError("scale_factor must be > 0")
        if not isinstance(self.frame, Frame):
            raise GalacticValidationError(f"frame must be Frame, got {self.frame!r}")


class GalaxyType(str, Enum):
    SPIRAL = "SPIRAL"
    ELLIPTICAL = "ELLIPTICAL"
    LENTICULAR = "LENTICULAR"
    IRREGULAR = "IRREGULAR"
    DWARF = "DWARF"
    INTERACTING = "INTERACTING"
    MERGING = "MERGING"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Bulge:
    mass: AnyValue
    scale_radius_kpc: AnyValue
    profile: str = "deVaucouleurs"

    def __post_init__(self):
        if not isinstance(self.profile, str) or not self.profile:
            raise GalacticValidationError("profile must be non-empty string")


@dataclass(frozen=True)
class Disk:
    stellar_mass: AnyValue
    gas_mass: AnyValue
    scale_length_kpc: AnyValue
    thickness_kpc: AnyValue
    rotation_velocity_kms: AnyValue


@dataclass(frozen=True)
class Halo:
    mass: AnyValue
    characteristic_radius_kpc: AnyValue
    profile: str = "NFW"
    concentration: Optional[AnyValue] = None

    def __post_init__(self):
        if not isinstance(self.profile, str) or not self.profile:
            raise GalacticValidationError("profile must be non-empty string")


@dataclass(frozen=True)
class Galaxy:
    galaxy_id: str
    name: Optional[str]
    galaxy_type: GalaxyType
    position: Vec3
    coordinate_context: CoordinateContext
    bulge: Optional[Bulge] = None
    disk: Optional[Disk] = None
    halo: Optional[Halo] = None
    central_black_hole_ref: Optional[str] = None  # reference to existing black-hole object
    redshift: Optional[AnyValue] = None
    luminosity: Optional[AnyValue] = None
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.galaxy_id or not isinstance(self.galaxy_id, str):
            raise GalacticValidationError("galaxy_id required, non-empty string")
        if not isinstance(self.galaxy_type, GalaxyType):
            raise GalacticValidationError(f"galaxy_type must be GalaxyType, got {self.galaxy_type!r}")
        if not isinstance(self.position, Vec3):
            raise GalacticValidationError("position must be Vec3")
        if not isinstance(self.coordinate_context, CoordinateContext):
            raise GalacticValidationError("coordinate_context must be CoordinateContext")
        if not isinstance(self.provenance, Provenance):
            raise GalacticValidationError(f"provenance must be Provenance, got {self.provenance!r}")
        # black hole ref must be non-empty if present
        if self.central_black_hole_ref is not None and not self.central_black_hole_ref:
            raise GalacticValidationError("central_black_hole_ref must be non-empty if present")


@dataclass(frozen=True)
class GalaxyGroup:
    group_id: str
    member_galaxy_ids: Tuple[str, ...]
    center: Vec3
    coordinate_context: CoordinateContext
    total_mass: Optional[AnyValue] = None
    characteristic_radius_kpc: Optional[AnyValue] = None
    velocity_dispersion_kms: Optional[AnyValue] = None
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.group_id or not isinstance(self.group_id, str):
            raise GalacticValidationError("group_id required")
        if not isinstance(self.member_galaxy_ids, tuple):
            raise GalacticValidationError("member_galaxy_ids must be tuple")
        for gid in self.member_galaxy_ids:
            if not isinstance(gid, str) or not gid:
                raise GalacticValidationError(f"member galaxy id must be non-empty string, got {gid!r}")
        if not isinstance(self.center, Vec3):
            raise GalacticValidationError("center must be Vec3")
        if not isinstance(self.coordinate_context, CoordinateContext):
            raise GalacticValidationError("coordinate_context must be CoordinateContext")


@dataclass(frozen=True)
class GalaxyCluster:
    cluster_id: str
    member_group_ids: Tuple[str, ...]
    member_galaxy_ids: Tuple[str, ...]
    center: Vec3
    coordinate_context: CoordinateContext
    stellar_mass: Optional[AnyValue] = None
    gas_mass: Optional[AnyValue] = None
    dark_matter_mass: Optional[AnyValue] = None
    unknown_mass: Optional[AnyValue] = None
    characteristic_radius_kpc: Optional[AnyValue] = None
    velocity_dispersion_kms: Optional[AnyValue] = None
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.cluster_id or not isinstance(self.cluster_id, str):
            raise GalacticValidationError("cluster_id required")
        if not isinstance(self.member_galaxy_ids, tuple) or not isinstance(self.member_group_ids, tuple):
            raise GalacticValidationError("member lists must be tuples")
        if not isinstance(self.center, Vec3):
            raise GalacticValidationError("center must be Vec3")

    def total_mass_value(self) -> Optional[float]:
        """Explicit composition — sum known components if all present and numeric."""
        parts = [self.stellar_mass, self.gas_mass, self.dark_matter_mass]
        # unknown_mass is not summed; it represents missing
        if any(p is None or isinstance(p, UnknownValue) for p in parts):
            return None
        try:
            return sum(float(p.value) for p in parts if p is not None)  # type: ignore
        except Exception:
            return None


@dataclass(frozen=True)
class Supercluster:
    supercluster_id: str
    member_cluster_ids: Tuple[str, ...]
    member_group_ids: Tuple[str, ...]
    member_galaxy_ids: Tuple[str, ...]
    center: Vec3
    coordinate_context: CoordinateContext
    approximate_extent_mpc: Optional[AnyValue] = None
    gravitationally_bound: bool = False
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.supercluster_id or not isinstance(self.supercluster_id, str):
            raise GalacticValidationError("supercluster_id required")
        for attr in ("member_cluster_ids", "member_group_ids", "member_galaxy_ids"):
            v = getattr(self, attr)
            if not isinstance(v, tuple):
                raise GalacticValidationError(f"{attr} must be tuple")


class VoidBoundaryKind(str, Enum):
    SHELL = "SHELL"
    PARTITION = "PARTITION"
    VORONOI_CELL = "VORONOI_CELL"
    NONE = "NONE"


@dataclass(frozen=True)
class CosmicVoid:
    void_id: str
    center: Vec3
    coordinate_context: CoordinateContext
    characteristic_radius_mpc: AnyValue
    underdensity: AnyValue           # Δ = ρ/ρ̄ − 1, expected negative
    boundary_kind: VoidBoundaryKind = VoidBoundaryKind.NONE
    neighbor_structure_ids: Tuple[str, ...] = ()
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.void_id or not isinstance(self.void_id, str):
            raise GalacticValidationError("void_id required")
        if not isinstance(self.center, Vec3):
            raise GalacticValidationError("center must be Vec3")
        if not isinstance(self.characteristic_radius_mpc, (ObservedValue, DerivedValue, SimulatedValue, UnknownValue)):
            raise GalacticValidationError("characteristic_radius_mpc must be AnyValue")
        if not isinstance(self.underdensity, (ObservedValue, DerivedValue, SimulatedValue, UnknownValue)):
            raise GalacticValidationError("underdensity must be AnyValue")
        if not isinstance(self.boundary_kind, VoidBoundaryKind):
            raise GalacticValidationError(f"boundary_kind must be VoidBoundaryKind, got {self.boundary_kind!r}")
        # underdensity should be negative if known; but UnknownValue has no value
        if hasattr(self.underdensity, "value"):
            try:
                v = float(self.underdensity.value)  # type: ignore
                if v >= 0:
                    # not strictly error, but voids are underdense — allow but note
                    pass
            except Exception:
                pass


@dataclass(frozen=True)
class Filament:
    filament_id: str
    node_a_id: str
    node_b_id: str
    galaxy_ids: Tuple[str, ...] = ()
    group_ids: Tuple[str, ...] = ()
    length_mpc: Optional[AnyValue] = None
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.filament_id or not isinstance(self.filament_id, str):
            raise GalacticValidationError("filament_id required")
        if not self.node_a_id or not self.node_b_id:
            raise GalacticValidationError("node endpoints required")
        if self.node_a_id == self.node_b_id:
            raise GalacticValidationError("filament endpoints must differ")
        if not isinstance(self.galaxy_ids, tuple) or not isinstance(self.group_ids, tuple):
            raise GalacticValidationError("galaxy_ids/group_ids must be tuples")


@dataclass(frozen=True)
class Sheet:
    sheet_id: str
    member_filament_ids: Tuple[str, ...]
    characteristic_scale_mpc: Optional[AnyValue] = None
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.sheet_id or not isinstance(self.sheet_id, str):
            raise GalacticValidationError("sheet_id required")
        if not isinstance(self.member_filament_ids, tuple):
            raise GalacticValidationError("member_filament_ids must be tuple")


@dataclass(frozen=True)
class CosmicNode:
    node_id: str
    center: Vec3
    coordinate_context: CoordinateContext
    host_cluster_id: Optional[str] = None
    host_supercluster_id: Optional[str] = None
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.node_id or not isinstance(self.node_id, str):
            raise GalacticValidationError("node_id required")
        if not isinstance(self.center, Vec3):
            raise GalacticValidationError("center must be Vec3")
        if not isinstance(self.coordinate_context, CoordinateContext):
            raise GalacticValidationError("coordinate_context must be CoordinateContext")


@dataclass(frozen=True)
class CosmicWeb:
    web_id: str
    node_ids: Tuple[str, ...]
    filament_ids: Tuple[str, ...]
    sheet_ids: Tuple[str, ...]
    void_ids: Tuple[str, ...]
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not self.web_id or not isinstance(self.web_id, str):
            raise GalacticValidationError("web_id required")
        for attr in ("node_ids", "filament_ids", "sheet_ids", "void_ids"):
            v = getattr(self, attr)
            if not isinstance(v, tuple):
                raise GalacticValidationError(f"{attr} must be tuple")
            for item in v:
                if not isinstance(item, str) or not item:
                    raise GalacticValidationError(f"{attr} items must be non-empty strings, got {item!r}")


class HierarchyRelation(str, Enum):
    CONTAINS = "CONTAINS"
    GRAVITATIONALLY_BOUND = "GRAVITATIONALLY_BOUND"
    ASSOCIATED = "ASSOCIATED"
    OBSERVED_WITH = "OBSERVED_WITH"


@dataclass(frozen=True)
class HierarchyEdge:
    parent_id: str
    child_id: str
    relation: HierarchyRelation

    def __post_init__(self):
        if not self.parent_id or not self.child_id:
            raise GalacticValidationError("parent_id and child_id required")
        if not isinstance(self.relation, HierarchyRelation):
            raise GalacticValidationError(f"relation must be HierarchyRelation, got {self.relation!r}")
        if self.parent_id == self.child_id:
            raise GalacticValidationError("self-link forbidden")


@dataclass(frozen=True)
class DensitySample:
    """A single sample of large-scale matter distribution."""
    position: Vec3
    coordinate_context: CoordinateContext
    density_kg_m3: AnyValue
    overdensity: Optional[AnyValue] = None  # δ = ρ/ρ̄ -1
