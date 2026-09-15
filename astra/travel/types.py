"""Core data types. Reconciled.

If the repository already defines authoritative Vector3, SpacetimeEvent,
Worldline, ProvenanceTag, we interoperate rather than duplicate.  The
scaffold Vec3/Worldline are kept for API compatibility but delegate to
astra.mathematics.Vector3 where possible.

Provenance merges celestial DataProvenance (REAL/DERIVED/SIMULATED) with
theoretical ScientificClassification (THEORETICAL/HYPOTHETICAL/SPECULATIVE)
into the 6-value travel provenance required by the spec.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from astra.mathematics import Vector3 as AstroVector3

from .errors import TravelNumericalError


def _finite(name: str, v: float) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise TravelNumericalError(f"{name} must be numeric")
    fv = float(v)
    if math.isnan(fv) or math.isinf(fv):
        raise TravelNumericalError(f"{name} must be finite, got {fv}")
    return fv


class Provenance(str, Enum):
    """Travel provenance — 6-value classification required by spec.

    Maps to DataProvenance / ScientificClassification for persistence:
      REAL_DATA      -> DataProvenance.REAL_DATA
      DERIVED_DATA   -> DataProvenance.DERIVED_DATA
      SIMULATED_DATA -> DataProvenance.SIMULATED_DATA
      THEORETICAL    -> DataProvenance.THEORETICAL_MODEL
      HYPOTHETICAL   -> DataProvenance.SPECULATIVE_MODEL (hypothetical)
      SPECULATIVE    -> DataProvenance.SPECULATIVE_MODEL
    """

    REAL_DATA = "REAL_DATA"
    DERIVED_DATA = "DERIVED_DATA"
    SIMULATED_DATA = "SIMULATED_DATA"
    THEORETICAL = "THEORETICAL"
    HYPOTHETICAL = "HYPOTHETICAL"
    SPECULATIVE = "SPECULATIVE"

    def to_data_provenance(self):
        from astra.celestial.provenance import DataProvenance

        mapping = {
            Provenance.REAL_DATA: DataProvenance.REAL_DATA,
            Provenance.DERIVED_DATA: DataProvenance.DERIVED_DATA,
            Provenance.SIMULATED_DATA: DataProvenance.SIMULATED_DATA,
            Provenance.THEORETICAL: DataProvenance.THEORETICAL_MODEL,
            Provenance.HYPOTHETICAL: DataProvenance.SPECULATIVE_MODEL,
            Provenance.SPECULATIVE: DataProvenance.SPECULATIVE_MODEL,
        }
        return mapping[self]

    def to_scientific_classification(self):
        from astra.theoretical.classification import ScientificClassification

        mapping = {
            Provenance.REAL_DATA: ScientificClassification.ESTABLISHED,
            Provenance.DERIVED_DATA: ScientificClassification.ESTABLISHED,
            Provenance.SIMULATED_DATA: ScientificClassification.ESTABLISHED,
            Provenance.THEORETICAL: ScientificClassification.THEORETICAL,
            Provenance.HYPOTHETICAL: ScientificClassification.SPECULATIVE,
            Provenance.SPECULATIVE: ScientificClassification.SPECULATIVE,
        }
        return mapping[self]


class Mechanism(str, Enum):
    RELATIVISTIC = "RELATIVISTIC"
    GRAVITATIONAL = "GRAVITATIONAL"
    WORMHOLE = "WORMHOLE"
    WHITE_HOLE = "WHITE_HOLE"
    WARP = "WARP"


class CausalStatus(str, Enum):
    CASUAL = "CASUAL"  # no causality concern
    TIMELIKE = "TIMELIKE"  # valid, subluminal
    LIGHTLIKE = "LIGHTLIKE"  # null
    SPACELIKE = "SPACELIKE"  # forbidden for matter
    CTC = "CTC"  # closed timelike curve
    CAUSALLY_INVALID = "CAUSALLY_INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Vec3:
    """Compatibility vector — API matches scaffold, delegates to Vector3.

    Supports norm() (alias for magnitude), dot, to_tuple, arithmetic,
    and finite validation.  Convertible to astra.mathematics.Vector3.
    """

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite("Vec3.x", self.x))
        object.__setattr__(self, "y", _finite("Vec3.y", self.y))
        object.__setattr__(self, "z", _finite("Vec3.z", self.z))

    def __add__(self, o: "Vec3") -> "Vec3":
        if isinstance(o, AstroVector3):
            o = Vec3(o.x, o.y, o.z)
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vec3") -> "Vec3":
        if isinstance(o, AstroVector3):
            o = Vec3(o.x, o.y, o.z)
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __neg__(self) -> "Vec3":
        return Vec3(-self.x, -self.y, -self.z)

    def __mul__(self, s: float) -> "Vec3":
        return Vec3(self.x * float(s), self.y * float(s), self.z * float(s))

    __rmul__ = __mul__

    def dot(self, o: "Vec3") -> float:
        if isinstance(o, AstroVector3):
            o = Vec3(o.x, o.y, o.z)
        return self.x * o.x + self.y * o.y + self.z * o.z

    def norm(self) -> float:
        return math.sqrt(self.dot(self))

    # alias for real API compatibility
    def magnitude(self) -> float:
        return self.norm()

    def magnitude_sq(self) -> float:
        return self.dot(self)

    def distance_to(self, o: "Vec3") -> float:
        return (self - o).norm()

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def to_vector3(self) -> AstroVector3:
        return AstroVector3(self.x, self.y, self.z)

    @classmethod
    def from_vector3(cls, v: AstroVector3) -> "Vec3":
        return cls(v.x, v.y, v.z)

    @classmethod
    def from_tuple(cls, t) -> "Vec3":
        return cls(float(t[0]), float(t[1]), float(t[2]))

    def is_finite(self) -> bool:
        return math.isfinite(self.x) and math.isfinite(self.y) and math.isfinite(self.z)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z


def _to_vec3(v) -> Vec3:
    """Coerce various vector representations to Vec3 deterministically."""
    if isinstance(v, Vec3):
        return v
    if isinstance(v, AstroVector3):
        return Vec3(v.x, v.y, v.z)
    if isinstance(v, (list, tuple)):
        if len(v) != 3:
            raise TravelNumericalError(f"vector must be 3-tuple, got {v!r}")
        return Vec3(float(v[0]), float(v[1]), float(v[2]))
    raise TravelNumericalError(f"cannot coerce {type(v).__name__} to Vec3")


@dataclass(frozen=True)
class WorldlineSample:
    """A single sample along a travel worldline."""

    coordinate_time_s: float
    proper_time_s: float
    position: Vec3
    observer_frame: str = "world"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _finite("coordinate_time_s", self.coordinate_time_s)
        _finite("proper_time_s", self.proper_time_s)
        if not isinstance(self.position, Vec3):
            # allow coercion on construction via object.__setattr__ hack
            object.__setattr__(self, "position", _to_vec3(self.position))
        if not isinstance(self.observer_frame, str) or not self.observer_frame:
            raise TravelNumericalError("observer_frame must be non-empty string")


@dataclass(frozen=True)
class Worldline:
    """Ordered sequence of samples. Travel-specific worldline.

    For causal classification the travel worldline is also convertible to
    astra.spacetime.Worldline via to_spacetime_worldline().
    """

    samples: Tuple[WorldlineSample, ...]
    parameterization: str = "proper_time"  # or "coordinate_time"
    provenance: Provenance = Provenance.SIMULATED_DATA

    def __post_init__(self) -> None:
        if not self.samples:
            raise TravelNumericalError("Worldline must have at least one sample")
        coerced = []
        for s in self.samples:
            if not isinstance(s, WorldlineSample):
                raise TravelNumericalError("Worldline samples must be WorldlineSample")
            coerced.append(s)
        object.__setattr__(self, "samples", tuple(coerced))
        if self.parameterization not in ("proper_time", "coordinate_time"):
            raise TravelNumericalError("parameterization must be proper_time or coordinate_time")

    def to_spacetime_worldline(self):
        """Convert to authoritative astra.spacetime.Worldline for metric/causal use."""
        from astra.spacetime.events import SpacetimeEvent, Worldline as STWorldline, CHART_CARTESIAN
        from astra.relativity.core import SPEED_OF_LIGHT

        st_samples = []
        for s in self.samples:
            ev = SpacetimeEvent(
                ct_m=s.coordinate_time_s * SPEED_OF_LIGHT,
                x=s.position.x,
                y=s.position.y,
                z=s.position.z,
                chart=CHART_CARTESIAN,
            )
            st_samples.append((s.proper_time_s, ev))
        return STWorldline(tuple(st_samples))

    def __len__(self) -> int:
        return len(self.samples)


@dataclass(frozen=True)
class TravelRequest:
    """Caller-supplied travel request."""

    request_id: str
    traveler_id: str
    departure_position: Vec3
    departure_velocity: Vec3
    departure_coordinate_time_s: float
    departure_reference_frame: str
    destination_position: Vec3
    destination_reference_frame: str
    mechanism: Mechanism
    config: Dict[str, Any] = field(default_factory=dict)
    requested_arrival_coordinate_time_s: Optional[float] = None
    provenance: Provenance = Provenance.SIMULATED_DATA

    def __post_init__(self) -> None:
        if not self.request_id or not isinstance(self.request_id, str):
            raise TravelNumericalError("request_id required")
        if not self.traveler_id or not isinstance(self.traveler_id, str):
            raise TravelNumericalError("traveler_id required")
        # coerce vectors
        object.__setattr__(self, "departure_position", _to_vec3(self.departure_position))
        object.__setattr__(self, "departure_velocity", _to_vec3(self.departure_velocity))
        object.__setattr__(self, "destination_position", _to_vec3(self.destination_position))
        _finite("departure_coordinate_time_s", self.departure_coordinate_time_s)
        if self.requested_arrival_coordinate_time_s is not None:
            _finite("requested_arrival_coordinate_time_s", self.requested_arrival_coordinate_time_s)
        if not isinstance(self.departure_reference_frame, str) or not self.departure_reference_frame:
            raise TravelNumericalError("departure_reference_frame must be non-empty string")
        if not isinstance(self.destination_reference_frame, str) or not self.destination_reference_frame:
            raise TravelNumericalError("destination_reference_frame must be non-empty string")
        if not isinstance(self.mechanism, Mechanism):
            # allow string coercion
            try:
                object.__setattr__(self, "mechanism", Mechanism(self.mechanism))
            except Exception:
                raise TravelNumericalError(f"mechanism must be Mechanism, got {self.mechanism!r}")
        if not isinstance(self.config, dict):
            raise TravelNumericalError("config must be dict")
        if not isinstance(self.provenance, Provenance):
            try:
                object.__setattr__(self, "provenance", Provenance(self.provenance))
            except Exception:
                raise TravelNumericalError(f"provenance must be Provenance, got {self.provenance!r}")


@dataclass(frozen=True)
class TravelEvent:
    """Immutable travel record."""

    travel_id: str
    traveler_id: str
    mechanism: Mechanism
    departure_position: Vec3
    departure_coordinate_time_s: float
    departure_reference_frame: str
    arrival_position: Vec3
    arrival_coordinate_time_s: float
    arrival_reference_frame: str
    proper_elapsed_time_s: float
    coordinate_elapsed_time_s: float
    observer_elapsed_time_s: float
    causal_status: CausalStatus
    worldline: Worldline
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.travel_id or not isinstance(self.travel_id, str):
            raise TravelNumericalError("travel_id required")
        if not self.traveler_id or not isinstance(self.traveler_id, str):
            raise TravelNumericalError("traveler_id required")
        object.__setattr__(self, "departure_position", _to_vec3(self.departure_position))
        object.__setattr__(self, "arrival_position", _to_vec3(self.arrival_position))
        _finite("departure_coordinate_time_s", self.departure_coordinate_time_s)
        _finite("arrival_coordinate_time_s", self.arrival_coordinate_time_s)
        _finite("proper_elapsed_time_s", self.proper_elapsed_time_s)
        _finite("coordinate_elapsed_time_s", self.coordinate_elapsed_time_s)
        _finite("observer_elapsed_time_s", self.observer_elapsed_time_s)
        # Allow arrival < departure only for wormhole CTC (Morris-Thorne-Yurtsever time shift)
        # where coordinate goes backward while proper advances — distinct diagnostic representation.
        if self.arrival_coordinate_time_s < self.departure_coordinate_time_s - 1e-12:
            if not (
                self.mechanism == Mechanism.WORMHOLE
                and self.causal_status in (CausalStatus.CTC, CausalStatus.CAUSALLY_INVALID)
                and self.provenance in (Provenance.HYPOTHETICAL, Provenance.SPECULATIVE)
            ):
                raise TravelNumericalError("arrival precedes departure (only wormhole CTC may be backward)")
            # For CTC, coordinate_elapsed may be negative — still finite, but we record magnitude in metadata
            # Ensure proper still advances forward (already finite >=0 checked)
            if self.proper_elapsed_time_s < -1e-12:
                raise TravelNumericalError("proper elapsed must be >=0 even for CTC")
        if not isinstance(self.worldline, Worldline):
            raise TravelNumericalError("worldline must be Worldline")
        if not isinstance(self.causal_status, CausalStatus):
            try:
                object.__setattr__(self, "causal_status", CausalStatus(self.causal_status))
            except Exception:
                raise TravelNumericalError(f"causal_status must be CausalStatus, got {self.causal_status!r}")


@dataclass(frozen=True)
class ArrivalState:
    """Explicit arrival state."""

    travel_id: str
    traveler_id: str
    position: Vec3
    velocity: Vec3
    orientation: Optional[Tuple[float, float, float, float]] = None
    proper_time_s: float = 0.0
    coordinate_time_s: float = 0.0
    reference_frame: str = "world"
    causal_status: CausalStatus = CausalStatus.UNKNOWN
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "position", _to_vec3(self.position))
        object.__setattr__(self, "velocity", _to_vec3(self.velocity))
        _finite("proper_time_s", self.proper_time_s)
        _finite("coordinate_time_s", self.coordinate_time_s)
        if self.orientation is not None:
            if not isinstance(self.orientation, (list, tuple)) or len(self.orientation) != 4:
                raise TravelNumericalError("orientation must be quaternion 4-tuple")
            for v in self.orientation:
                _finite("orientation component", v)


@dataclass(frozen=True)
class ObservationRecord:
    """Observation-side record of travel."""

    observation_id: str
    travel_id: str
    observer_id: str
    observer_frame: str
    observed_at_coordinate_time_s: float
    observed_event: str  # "departure" | "travel" | "arrival" | "signature"
    signal_delay_s: float
    provenance: Provenance = Provenance.SIMULATED_DATA
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.observation_id or not isinstance(self.observation_id, str):
            raise TravelNumericalError("observation_id required")
        _finite("observed_at_coordinate_time_s", self.observed_at_coordinate_time_s)
        _finite("signal_delay_s", self.signal_delay_s)
        if self.signal_delay_s < 0:
            raise TravelNumericalError("signal_delay_s must be >=0")
