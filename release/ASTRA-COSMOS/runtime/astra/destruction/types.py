"""Core immutable data types for Destruction & Impact.

Vector type
-----------
This package reuses the canonical ``astra.mathematics.Vector3`` instead of
defining a private vector. ``Vec3`` is kept as a local alias for readability.
Vector3 does NOT validate finiteness at construction (see astra.mathematics
docs), so finiteness is enforced at the package boundary:
``ImpactEvent.__post_init__`` validates every vector and scalar field.

Provenance
-----------
This package reuses ``astra.celestial.provenance.DataProvenance`` — the
repository's canonical provenance taxonomy — aliased here as ``Provenance``.
All impact outputs produced by this package are SIMULATED_DATA (or, for pure
recomputations by the caller, may be reclassified as DERIVED_DATA downstream).
This package never marks outputs REAL_DATA.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, Optional, Tuple

if TYPE_CHECKING:  # resolve forward references for static analysis only
    from .damage import DamageState

from astra.mathematics import Vector3

from .errors import NumericalError
from .provenance import DataProvenance

# Local aliases (documented as aliases, NOT new types).
Vec3 = Vector3
Provenance = DataProvenance


def _finite(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise NumericalError(f"{name} must be numeric, got {type(v).__name__}")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise NumericalError(f"{name} must be finite, got {fv}")
    return fv


def _vec_finite(name: str, v: Vector3) -> Vector3:
    if not isinstance(v, Vector3):
        raise NumericalError(f"{name} must be a Vector3, got {type(v).__name__}")
    if not v.is_finite():
        raise NumericalError(f"{name} must be finite, got {v!r}")
    return v


def _provenance(p: DataProvenance) -> DataProvenance:
    if not isinstance(p, DataProvenance):
        raise NumericalError(
            f"provenance must be a DataProvenance member, got {type(p).__name__}"
        )
    return p


@dataclass(frozen=True)
class ImpactGeometry:
    """Geometric description of an impact in the world frame.

    ``surface_normal`` is the outward unit normal of the target at the
    contact point; ``incoming_direction`` is the unit vector of the
    impactor's velocity relative to the target; ``incidence_angle_rad`` is
    the angle between ``-incoming_direction`` and the surface normal
    (0 = head-on, pi/2 = grazing).
    """

    contact_point: Vector3
    surface_normal: Vector3
    incoming_direction: Vector3
    incidence_angle_rad: float
    is_grazing: bool
    is_head_on: bool


@dataclass(frozen=True)
class ImpactEnergy:
    """Energy budget of an impact (SI, joules)."""

    kinetic_energy_j: float          # 1/2 * m_reduced * |v_rel|^2
    deposited_energy_j: float        # modelled energy transferred into target
    fragmentation_energy_j: float    # energy allocated to fracturing
    thermal_energy_j: float          # modelled thermal/other losses
    residual_kinetic_energy_j: float # kinetic energy remaining in products
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA


@dataclass(frozen=True)
class ImpactMomentum:
    """Momentum budget of an impact (kg m/s)."""

    relative_momentum_kg_m_s: Vector3
    transferred_momentum_kg_m_s: Vector3
    residual_momentum_kg_m_s: Vector3
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA


@dataclass(frozen=True)
class ImpactEvent:
    """Immutable description of a single impact, supplied by the caller.

    IDs must be caller-supplied and deterministic (no UUID generation inside
    this package). Position/velocity are world-frame Vector3.
    """

    impact_id: str
    impactor_id: str
    target_id: str
    sim_time_s: float
    impactor_mass_kg: float
    target_mass_kg: float
    impactor_position: Vector3
    target_position: Vector3
    impactor_velocity: Vector3
    target_velocity: Vector3
    impactor_radius_m: float = 0.0
    target_radius_m: float = 0.0
    reference_frame: str = "world"
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA
    metadata: Dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for f in ("impact_id", "impactor_id", "target_id"):
            if not isinstance(getattr(self, f), str):
                raise NumericalError(f"{f} must be a str")
        _finite("sim_time_s", self.sim_time_s)
        _finite("impactor_mass_kg", self.impactor_mass_kg)
        _finite("target_mass_kg", self.target_mass_kg)
        _finite("impactor_radius_m", self.impactor_radius_m)
        _finite("target_radius_m", self.target_radius_m)
        if self.impactor_radius_m < 0.0:
            raise NumericalError("impactor_radius_m must be >= 0")
        if self.target_radius_m < 0.0:
            raise NumericalError("target_radius_m must be >= 0")
        _vec_finite("impactor_position", self.impactor_position)
        _vec_finite("target_position", self.target_position)
        _vec_finite("impactor_velocity", self.impactor_velocity)
        _vec_finite("target_velocity", self.target_velocity)
        _provenance(self.provenance)
        if not isinstance(self.metadata, dict):
            raise NumericalError("metadata must be a dict")

    def relative_velocity(self) -> Vector3:
        return self.impactor_velocity - self.target_velocity

    def relative_speed(self) -> float:
        return self.relative_velocity().magnitude()

    def reduced_mass(self) -> float:
        m1, m2 = self.impactor_mass_kg, self.target_mass_kg
        if m1 + m2 <= 0.0:
            raise NumericalError("total mass must be positive")
        return (m1 * m2) / (m1 + m2)


@dataclass(frozen=True)
class FragmentState:
    """A deterministic fragment of a fractured target."""

    fragment_id: str
    parent_id: str
    impact_id: str
    mass_kg: float
    position: Vector3
    velocity: Vector3
    created_at_s: float
    material: Optional[str] = None
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA

    def __post_init__(self) -> None:
        _finite("mass_kg", self.mass_kg)
        _finite("created_at_s", self.created_at_s)
        _vec_finite("position", self.position)
        _vec_finite("velocity", self.velocity)
        _provenance(self.provenance)


@dataclass(frozen=True)
class EjectaState:
    """A single ejecta particle launched from the impact site."""

    ejecta_id: str
    impact_id: str
    source_id: str
    mass_kg: float
    position: Vector3
    velocity: Vector3
    kinetic_energy_j: float
    created_at_s: float
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA

    def __post_init__(self) -> None:
        _finite("mass_kg", self.mass_kg)
        _finite("kinetic_energy_j", self.kinetic_energy_j)
        _finite("created_at_s", self.created_at_s)
        _vec_finite("position", self.position)
        _vec_finite("velocity", self.velocity)
        _provenance(self.provenance)


@dataclass(frozen=True)
class DebrisState:
    """A persistent debris entity registered with entity/world systems."""

    debris_id: str
    origin_impact_id: str
    mass_kg: float
    position: Vector3
    velocity: Vector3
    created_at_s: float
    is_ejecta: bool = False
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA

    def __post_init__(self) -> None:
        _finite("mass_kg", self.mass_kg)
        _finite("created_at_s", self.created_at_s)
        _vec_finite("position", self.position)
        _vec_finite("velocity", self.velocity)
        _provenance(self.provenance)


@dataclass(frozen=True)
class SecondaryTarget:
    """A caller-supplied candidate body for secondary-impact scanning.

    Callers obtain these from their own authoritative sources (World spatial
    queries, NBody bodies, celestial registry) — this package never fabricates
    candidate bodies by itself.
    """

    body_id: str
    mass_kg: float
    position: Vector3
    velocity: Vector3
    radius_m: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.body_id, str) or not self.body_id:
            raise NumericalError("SecondaryTarget.body_id must be a non-empty str")
        if _finite("mass_kg", self.mass_kg) <= 0.0:
            raise NumericalError("SecondaryTarget.mass_kg must be > 0")
        _finite("radius_m", self.radius_m)
        if self.radius_m < 0.0:
            raise NumericalError("SecondaryTarget.radius_m must be >= 0")
        _vec_finite("position", self.position)
        _vec_finite("velocity", self.velocity)

    @classmethod
    def from_nbody_body(cls, body, radius_m: float = 0.0) -> "SecondaryTarget":
        """Adapt an ``astra.nbody.bodies.NBodyBody`` (duck-typed)."""
        return cls(
            body_id=body.id,
            mass_kg=body.mass,
            position=body.position,
            velocity=body.velocity,
            radius_m=radius_m,
        )


@dataclass(frozen=True)
class ImpactResult:
    """Immutable result of executing one impact."""

    event: ImpactEvent
    geometry: ImpactGeometry
    energy: ImpactEnergy
    momentum: ImpactMomentum
    target_state_before: "DamageState"
    target_state_after: "DamageState"
    fragments: Tuple[FragmentState, ...] = ()
    ejecta: Tuple[EjectaState, ...] = ()
    debris: Tuple[DebrisState, ...] = ()
    child_impacts: Tuple[ImpactEvent, ...] = ()
    rng_seed_used: int = 0
    model_version: str = "astra.destruction.v1"
    provenance: DataProvenance = DataProvenance.SIMULATED_DATA

    def to_tuple(self) -> Tuple:
        """Stable tuple form used by determinism tests."""
        return (
            self.event.impact_id,
            self.target_state_after.value,
            tuple(f.mass_kg for f in self.fragments),
            tuple(f.velocity.to_tuple() for f in self.fragments),
            self.energy.kinetic_energy_j,
        )
