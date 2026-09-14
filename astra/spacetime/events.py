"""ASTRA Spacetime - events, worldlines, coordinate charts.

Contract: immutable event value objects on the (-,+,+,+) signature with
x^mu = (ct, x, y, z) (metres), interop 1:1 with
``astra.relativity.four_vectors.FourVector``, and a Worldline: a
time-ordered, immutable sequence of events parameterized by proper time tau
(timelike) or an affine parameter lambda (null).

Serialization: plain Python primitives only (to_dict / from_dict); derived
quantities are never serialized.

Determinism: pure value types; no RNG, no wall-clock.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from astra.core.exceptions import AstraError
from astra.relativity.core import SPEED_OF_LIGHT
from astra.spacetime.exceptions import InvalidCoordinateError

# Coordinate charts used by ASTRA metrics.
CHART_CARTESIAN = "cartesian"        # (ct, x, y, z)
CHART_SPHERICAL = "spherical"        # (ct, r, theta, phi) BL-type


def _finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidCoordinateError(f"{name} must be a real number, got {type(value).__name__}")
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        raise InvalidCoordinateError(f"{name} cannot be NaN or Infinite, got {value!r}")
    return v


@dataclass(frozen=True)
class SpacetimeEvent:
    """An event: coordinates x^mu = (ct, x, y, z) in metres, plus chart label.

    ``ct_m`` is the time coordinate in metres of light travel (ct);
    ``chart`` records the coordinate chart the spatial triple lives in
    (CHART_CARTESIAN by default). Immutable.
    """

    ct_m: float
    x: float
    y: float
    z: float
    chart: str = CHART_CARTESIAN

    def __post_init__(self):
        object.__setattr__(self, "ct_m", _finite(self.ct_m, "ct_m"))
        object.__setattr__(self, "x", _finite(self.x, "x"))
        object.__setattr__(self, "y", _finite(self.y, "y"))
        object.__setattr__(self, "z", _finite(self.z, "z"))
        if self.chart not in (CHART_CARTESIAN, CHART_SPHERICAL):
            raise InvalidCoordinateError(f"Unknown chart {self.chart!r}")

    @classmethod
    def from_coordinates(cls, time_sec: float, x: float, y: float, z: float,
                         chart: str = CHART_CARTESIAN) -> "SpacetimeEvent":
        """Build an event from SI quantities: time in seconds, space in m."""
        t = _finite(time_sec, "time_sec")
        return cls(t * SPEED_OF_LIGHT, x, y, z, chart)

    @property
    def time_sec(self) -> float:
        return self.ct_m / SPEED_OF_LIGHT

    def coordinates(self) -> Tuple[float, float, float, float]:
        """Return (ct, x, y, z) as a plain tuple."""
        return (self.ct_m, self.x, self.y, self.z)

    def to_four_vector(self):
        """Interop 1:1 with astra.relativity.four_vectors.FourVector."""
        from astra.relativity.four_vectors import FourVector
        return FourVector(self.ct_m, self.x, self.y, self.z)

    @classmethod
    def from_four_vector(cls, fv, chart: str = CHART_CARTESIAN) -> "SpacetimeEvent":
        """Interop 1:1 from a relativity FourVector (t must be ct in m)."""
        return cls(fv.t, fv.x, fv.y, fv.z, chart)

    def to_dict(self) -> Dict[str, float]:
        """Canonical serialization: coordinates + chart label."""
        return {"ct_m": self.ct_m, "x": self.x, "y": self.y, "z": self.z,
                "chart": self.chart}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "SpacetimeEvent":
        return cls(data["ct_m"], data["x"], data["y"], data["z"],
                   data.get("chart", CHART_CARTESIAN))


@dataclass(frozen=True)
class Worldline:
    """Immutable, time-ordered sequence of (parameter, event) samples.

    The parameter is proper time tau (seconds) for timelike worldlines or an
    affine parameter lambda (1/m) for null ones. Monotonically increasing by
    construction.
    """

    samples: Tuple[Tuple[float, SpacetimeEvent], ...] = field(default=())

    def __post_init__(self):
        prev = None
        for param, event in self.samples:
            if not isinstance(event, SpacetimeEvent):
                raise InvalidCoordinateError("Worldline samples must hold SpacetimeEvent objects")
            if prev is not None and param <= prev:
                raise InvalidCoordinateError(
                    f"Worldline parameter must strictly increase: {param!r} <= {prev!r}"
                )
            prev = param
        object.__setattr__(self, "samples", tuple(self.samples))

    @property
    def events(self) -> Tuple[SpacetimeEvent, ...]:
        return tuple(e for _, e in self.samples)

    @property
    def parameters(self) -> Tuple[float, ...]:
        return tuple(p for p, _ in self.samples)

    def final_event(self) -> SpacetimeEvent:
        if not self.samples:
            raise InvalidCoordinateError("Worldline is empty")
        return self.samples[-1][1]

    def to_dict(self) -> Dict[str, List]:
        """Canonical serialization: parameter/event pairs as primitives."""
        return {"samples": [[p, e.to_dict()] for p, e in self.samples]}

    @classmethod
    def from_dict(cls, data: Dict) -> "Worldline":
        return cls(tuple(
            (p, SpacetimeEvent.from_dict(e)) for p, e in data["samples"]
        ))


def cartesian_to_spherical(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Convert cartesian spatial coordinates (m) to (r, theta, phi).

    theta in [0, pi], phi in (-pi, pi]. Raises InvalidCoordinateError at the
    origin (r = 0 is the physical singularity in spherical charts).
    """
    x, y, z = _finite(x, "x"), _finite(y, "y"), _finite(z, "z")
    r = math.sqrt(x * x + y * y + z * z)
    if r == 0.0:
        raise InvalidCoordinateError("Cannot convert the origin to spherical coordinates")
    theta = math.acos(max(-1.0, min(1.0, z / r)))
    phi = math.atan2(y, x)
    return (r, theta, phi)


def spherical_to_cartesian(r: float, theta: float, phi: float) -> Tuple[float, float, float]:
    """Convert (r, theta, phi) to cartesian spatial coordinates (m)."""
    r, theta, phi = _finite(r, "r"), _finite(theta, "theta"), _finite(phi, "phi")
    if r < 0.0:
        raise InvalidCoordinateError(f"Radius cannot be negative, got {r!r}")
    return (r * math.sin(theta) * math.cos(phi),
            r * math.sin(theta) * math.sin(phi),
            r * math.cos(theta))
