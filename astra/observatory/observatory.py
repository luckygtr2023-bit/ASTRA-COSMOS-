"""Observatory model — authoritative platform hosting instruments."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List

from astra.observatory.exceptions import InvalidObservatoryError
from astra.observation.observer import Observer, _ALLOWED_FRAMES
from astra.observatory.instrument import Instrument

class PlatformType(str):
    PLANETARY_SURFACE = "planetary_surface"
    ORBIT = "orbit"
    SPACECRAFT = "spacecraft"
    DEEP_SPACE = "deep_space"
    CUSTOM = "custom"

def _finite(v, name: str) -> float:
    if isinstance(v,bool) or not isinstance(v,(int,float)) or math.isnan(v) or math.isinf(v):
        raise InvalidObservatoryError(f"{name} must be finite, got {v!r}")
    return float(v)

def _vec3(v, name: str) -> Tuple[float,float,float]:
    if not isinstance(v,(list,tuple)) or len(v)!=3:
        raise InvalidObservatoryError(f"{name} must be 3-tuple")
    out=tuple(_finite(x, f"{name}[{i}]") for i,x in enumerate(v))
    return out

@dataclass(frozen=True)
class Observatory:
    """Immutable observatory specification.

    Attributes:
        observatory_id: unique id
        location: (x,y,z) metres in reference_frame at observing time
        orientation: pointing direction unit vector (e.g. boresight)
        reference_frame: allowed frame
        platform: PlatformType string
        observing_time_s: optional default time
        field_of_view_deg: observatory-wide FOV (overrides instrument if needed)
        instruments: tuple of mounted Instrument ids? Actually hold Instruments
        metadata: free-form environmental/config
    """
    observatory_id: str
    location: Tuple[float,float,float] = (0,0,0)
    orientation: Tuple[float,float,float] = (1,0,0)
    reference_frame: str = "inertial"
    platform: str = PlatformType.DEEP_SPACE
    observing_time_s: Optional[float] = None
    field_of_view_deg: float = 20.0
    instruments: Tuple[Instrument, ...] = ()
    metadata: Dict = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        if not isinstance(self.observatory_id, str) or not self.observatory_id.strip():
            raise InvalidObservatoryError("observatory_id must be non-empty")
        if len(self.observatory_id)>256:
            raise InvalidObservatoryError("observatory_id too long")
        loc=_vec3(self.location, "location")
        ori=_vec3(self.orientation, "orientation")
        n=math.sqrt(ori[0]*ori[0]+ori[1]*ori[1]+ori[2]*ori[2])
        if n==0 or math.isnan(n) or math.isinf(n):
            raise InvalidObservatoryError("orientation must be non-zero")
        object.__setattr__(self, "location", loc)
        object.__setattr__(self, "orientation", ori)
        if not isinstance(self.reference_frame,str) or not self.reference_frame:
            raise InvalidObservatoryError("reference_frame must be non-empty")
        if self.reference_frame not in _ALLOWED_FRAMES and not self.reference_frame.startswith("custom:"):
            raise InvalidObservatoryError(f"unknown reference_frame {self.reference_frame!r}")
        if self.platform not in (PlatformType.PLANETARY_SURFACE, PlatformType.ORBIT, PlatformType.SPACECRAFT, PlatformType.DEEP_SPACE, PlatformType.CUSTOM) and not self.platform.startswith("custom:"):
            raise InvalidObservatoryError(f"unknown platform {self.platform!r}")
        if self.observing_time_s is not None:
            t=_finite(self.observing_time_s, "observing_time_s")
            if t<0:
                raise InvalidObservatoryError("observing_time_s must be >=0")
            object.__setattr__(self, "observing_time_s", float(t))
        fov=_finite(self.field_of_view_deg, "field_of_view_deg")
        if not (0 < fov <=180):
            raise InvalidObservatoryError("field_of_view_deg must be in (0,180]")
        object.__setattr__(self, "field_of_view_deg", float(fov))
        if not isinstance(self.instruments, (list,tuple)):
            raise InvalidObservatoryError("instruments must be tuple/list")
        for inst in self.instruments:
            if not isinstance(inst, Instrument):
                raise InvalidObservatoryError("instruments must be Instrument")
        object.__setattr__(self, "instruments", tuple(self.instruments))
        if not isinstance(self.metadata, dict):
            raise InvalidObservatoryError("metadata must be dict")

    @property
    def orientation_unit(self) -> Tuple[float,float,float]:
        x,y,z=self.orientation
        n=math.sqrt(x*x+y*y+z*z)
        return (x/n,y/n,z/n)

    def to_observer(self, observer_id: Optional[str]=None, velocity: Tuple[float,float,float]=(0,0,0)) -> Observer:
        """Convert observatory location/orientation to an observation Observer."""
        return Observer(
            observer_id=observer_id or self.observatory_id,
            position=self.location,
            velocity=velocity,
            orientation=self.orientation,
            reference_frame=self.reference_frame,
            observation_time_s=self.observing_time_s,
            field_of_view_deg=self.field_of_view_deg,
            metadata=dict(self.metadata),
        )

    def has_instrument(self, instrument_id: str) -> bool:
        return any(inst.instrument_id==instrument_id for inst in self.instruments)

    def get_instrument(self, instrument_id: str) -> Optional[Instrument]:
        for inst in self.instruments:
            if inst.instrument_id==instrument_id:
                return inst
        return None

    def to_dict(self) -> Dict:
        return {
            "observatory_id": self.observatory_id,
            "location": list(self.location),
            "orientation": list(self.orientation),
            "reference_frame": self.reference_frame,
            "platform": self.platform,
            "observing_time_s": self.observing_time_s,
            "field_of_view_deg": self.field_of_view_deg,
            "instruments": [inst.to_dict() for inst in self.instruments],
            "metadata": dict(self.metadata),
        }
    @classmethod
    def from_dict(cls, d: Dict) -> "Observatory":
        from astra.observatory.instrument import Instrument as Inst
        insts=tuple(Inst.from_dict(x) for x in d.get("instruments",[]))
        return cls(
            observatory_id=d["observatory_id"],
            location=tuple(d.get("location",(0,0,0))),
            orientation=tuple(d.get("orientation",(1,0,0))),
            reference_frame=d.get("reference_frame","inertial"),
            platform=d.get("platform", PlatformType.DEEP_SPACE),
            observing_time_s=d.get("observing_time_s"),
            field_of_view_deg=d.get("field_of_view_deg",20),
            instruments=insts,
            metadata=dict(d.get("metadata",{})),
        )

# Factories for convenience
def on_planetary_surface(observatory_id: str, location: Tuple[float,float,float], **kw) -> Observatory:
    return Observatory(observatory_id, location=location, platform=PlatformType.PLANETARY_SURFACE, **kw)

def in_orbit(observatory_id: str, location: Tuple[float,float,float], **kw) -> Observatory:
    return Observatory(observatory_id, location=location, platform=PlatformType.ORBIT, **kw)

def on_spacecraft(observatory_id: str, location: Tuple[float,float,float], **kw) -> Observatory:
    return Observatory(observatory_id, location=location, platform=PlatformType.SPACECRAFT, **kw)

def in_deep_space(observatory_id: str, location: Tuple[float,float,float], **kw) -> Observatory:
    return Observatory(observatory_id, location=location, platform=PlatformType.DEEP_SPACE, **kw)

__all__=["Observatory","PlatformType","on_planetary_surface","in_orbit","on_spacecraft","in_deep_space"]
