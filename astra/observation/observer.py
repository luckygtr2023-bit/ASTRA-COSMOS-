"""Observer model — authoritative observer representation.

An Observer is an immutable value type describing where/who is observing.
It is NOT the observation result; it is the input. Observer-dependent
observations are therefore trivial: different Observer → different ObservedState.

Supports positions at arbitrary coordinates (planet, spacecraft, deep
space, near compact object, arbitrary simulation coordinates) and records
proper time when available.

No wall-clock, no RNG, no global state.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, Optional, Sequence, Tuple

from astra.observation.exceptions import InvalidObserverError, InvalidReferenceFrameError

# Allowed reference frames — reuse existing coordinate frames where possible,
# but keep a closed allowlist for validation.
_ALLOWED_FRAMES = {
    "inertial",
    "comoving",
    "observer_rest",
    "source_rest",
    "coordinate",
    "proper",
    "galactic",
    "icrs",
    "cartesian",
    "spherical",
}

# Valid orientation is a 3-vector direction; normalize checks are lenient
# (zero vector is invalid, non-finite is invalid).


def _finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidObserverError(f"{name} must be a real number, got {type(value).__name__}")
    v = float(value)
    if math.isnan(v) or math.isinf(v):
        raise InvalidObserverError(f"{name} cannot be NaN or Inf, got {value!r}")
    return v


def _check_vec3(value, name: str) -> Tuple[float, float, float]:
    if not isinstance(value, (list, tuple)):
        raise InvalidObserverError(f"{name} must be a 3-tuple/list, got {type(value).__name__}")
    if len(value) != 3:
        raise InvalidObserverError(f"{name} must be length 3, got {len(value)}")
    return tuple(_finite(v, f"{name}[{i}]") for i, v in enumerate(value))


def _check_identity(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidObserverError(f"{name} must be a non-empty string, got {value!r}")
    if len(value) > 256:
        raise InvalidObserverError(f"{name} too long (>256)")
    if ":" in value and name == "observer_id":
        # allow colons elsewhere but warn for observer_id simplicity
        pass
    return value.strip()


@dataclass(frozen=True)
class Observer:
    """Immutable observer specification.

    Attributes:
        observer_id: unique identity label (e.g. 'earth', 'jwst', 'probe-7')
        position: (x,y,z) metres in the declared reference_frame at the
                  observation time (instantaneous). For a moving observer,
                  supply the position at t_obs; its history can be stored
                  externally as a Worldline if needed.
        velocity: (vx,vy,vz) m/s in the same frame (default 0). Checked
                  against c via relativity lorentz_factor lazily in redshift.
        orientation: unit direction the observer is looking (default +x).
                     Not required to be normalized — normalized on demand.
        reference_frame: label of the coordinate frame. Must be in
                         _ALLOWED_FRAMES or a custom string starting with 'custom:'.
        observation_time_s: optional default observation time (s). Per-call
                            observation time overrides this.
        proper_time_s: optional observer proper time at observation_time_s
                       (if relativistic context, else None).
        field_of_view_deg: full conical FOV in degrees (0,180], default 60.
        metadata: free-form dict for instrument / site / spacecraft tags.
    """

    observer_id: str
    position: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    orientation: Tuple[float, float, float] = (1.0, 0.0, 0.0)
    reference_frame: str = "inertial"
    observation_time_s: Optional[float] = None
    proper_time_s: Optional[float] = None
    field_of_view_deg: float = 60.0
    metadata: Dict = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        oid = _check_identity(self.observer_id, "observer_id")
        object.__setattr__(self, "observer_id", oid)

        pos = _check_vec3(self.position, "position")
        vel = _check_vec3(self.velocity, "velocity")
        ori = _check_vec3(self.orientation, "orientation")

        # Orientation must be non-zero
        norm = math.sqrt(ori[0]*ori[0] + ori[1]*ori[1] + ori[2]*ori[2])
        if norm == 0.0:
            raise InvalidObserverError("orientation must be a non-zero vector")
        if math.isnan(norm) or math.isinf(norm):
            raise InvalidObserverError("orientation has non-finite norm")
        object.__setattr__(self, "position", pos)
        object.__setattr__(self, "velocity", vel)
        object.__setattr__(self, "orientation", ori)

        # reference_frame validation: allow custom: prefix for extensibility
        if not isinstance(self.reference_frame, str) or not self.reference_frame:
            raise InvalidReferenceFrameError("reference_frame must be a non-empty string")
        if self.reference_frame not in _ALLOWED_FRAMES and not self.reference_frame.startswith("custom:"):
            raise InvalidReferenceFrameError(
                f"unknown reference_frame {self.reference_frame!r}; "
                f"allowed {sorted(_ALLOWED_FRAMES)} or 'custom:<name>'"
            )
        # observation_time_s
        if self.observation_time_s is not None:
            t = _finite(self.observation_time_s, "observation_time_s")
            if t < 0.0:
                raise InvalidObserverError("observation_time_s must be >=0")
            object.__setattr__(self, "observation_time_s", float(t))
        if self.proper_time_s is not None:
            pt = _finite(self.proper_time_s, "proper_time_s")
            if pt < 0.0:
                raise InvalidObserverError("proper_time_s must be >=0")
            object.__setattr__(self, "proper_time_s", float(pt))
            if self.observation_time_s is not None and pt > self.observation_time_s * 2 + 1e6:
                # sanity: proper time should not wildly exceed coordinate time without strong field
                pass

        fov = _finite(self.field_of_view_deg, "field_of_view_deg")
        if not (0.0 < fov <= 180.0):
            raise InvalidObserverError("field_of_view_deg must be in (0,180]")
        object.__setattr__(self, "field_of_view_deg", float(fov))

        if not isinstance(self.metadata, dict):
            raise InvalidObserverError("metadata must be a dict")

    # -- derived ----------------------------------------------------------
    @property
    def speed_mps(self) -> float:
        vx, vy, vz = self.velocity
        return math.sqrt(vx*vx + vy*vy + vz*vz)

    @property
    def orientation_unit(self) -> Tuple[float, float, float]:
        x, y, z = self.orientation
        n = math.sqrt(x*x + y*y + z*z)
        return (x/n, y/n, z/n)

    # -- immutable updates ------------------------------------------------
    def at_position(self, position: Sequence[float]) -> "Observer":
        """Return a new Observer at a different position (same id)."""
        pos = _check_vec3(position, "position")
        return replace(self, position=pos)

    def at_time(self, observation_time_s: float) -> "Observer":
        t = _finite(observation_time_s, "observation_time_s")
        if t < 0:
            raise InvalidObserverError("observation_time_s must be >=0")
        return replace(self, observation_time_s=float(t))

    def with_velocity(self, velocity: Sequence[float]) -> "Observer":
        vel = _check_vec3(velocity, "velocity")
        return replace(self, velocity=vel)

    def with_orientation(self, orientation: Sequence[float]) -> "Observer":
        ori = _check_vec3(orientation, "orientation")
        n = math.sqrt(ori[0]*ori[0] + ori[1]*ori[1] + ori[2]*ori[2])
        if n == 0:
            raise InvalidObserverError("orientation must be non-zero")
        return replace(self, orientation=ori)

    # -- factories --------------------------------------------------------
    @classmethod
    def on_planet(cls, observer_id: str, planet_position: Sequence[float],
                  planet_velocity: Sequence[float] = (0, 0, 0),
                  **kwargs) -> "Observer":
        """Factory: observer anchored to a planetary surface (inherits planet motion)."""
        return cls(observer_id=observer_id, position=tuple(planet_position),
                   velocity=tuple(planet_velocity), **kwargs)

    @classmethod
    def in_spacecraft(cls, observer_id: str, sc_position: Sequence[float],
                      sc_velocity: Sequence[float], **kwargs) -> "Observer":
        """Factory: observer onboard a spacecraft."""
        return cls(observer_id=observer_id, position=tuple(sc_position),
                   velocity=tuple(sc_velocity), **kwargs)

    @classmethod
    def in_deep_space(cls, observer_id: str, position: Sequence[float],
                      velocity: Sequence[float] = (0, 0, 0), **kwargs) -> "Observer":
        return cls(observer_id=observer_id, position=tuple(position),
                   velocity=tuple(velocity), **kwargs)

    @classmethod
    def near_compact_object(cls, observer_id: str, position: Sequence[float],
                            velocity: Sequence[float] = (0, 0, 0),
                            reference_frame: str = "coordinate",
                            **kwargs) -> "Observer":
        """Factory: observer near a black hole / neutron star. Frame defaults to coordinate."""
        return cls(observer_id=observer_id, position=tuple(position),
                   velocity=tuple(velocity), reference_frame=reference_frame, **kwargs)

    # -- persistence ------------------------------------------------------
    def to_dict(self) -> Dict:
        return {
            "observer_id": self.observer_id,
            "position": list(self.position),
            "velocity": list(self.velocity),
            "orientation": list(self.orientation),
            "reference_frame": self.reference_frame,
            "observation_time_s": self.observation_time_s,
            "proper_time_s": self.proper_time_s,
            "field_of_view_deg": self.field_of_view_deg,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "Observer":
        return cls(
            observer_id=data["observer_id"],
            position=tuple(data.get("position", (0, 0, 0))),
            velocity=tuple(data.get("velocity", (0, 0, 0))),
            orientation=tuple(data.get("orientation", (1, 0, 0))),
            reference_frame=data.get("reference_frame", "inertial"),
            observation_time_s=data.get("observation_time_s"),
            proper_time_s=data.get("proper_time_s"),
            field_of_view_deg=data.get("field_of_view_deg", 60.0),
            metadata=dict(data.get("metadata", {})),
        )


__all__ = ["Observer", "_ALLOWED_FRAMES"]
