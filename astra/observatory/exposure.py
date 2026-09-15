"""Exposure handling — instantaneous vs time-integrated."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from astra.observatory.exceptions import InvalidExposureError

@dataclass(frozen=True)
class Exposure:
    """Single exposure.

    Attributes:
        start_time_s: coordinate start
        duration_s: integration time >0
        end_time_s: derived start+duration
        exposure_id: optional id
    """
    start_time_s: float
    duration_s: float
    exposure_id: str = ""

    def __post_init__(self):
        for name in ("start_time_s","duration_s"):
            v=getattr(self, name)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or math.isnan(v) or math.isinf(v):
                raise InvalidExposureError(f"{name} must be finite, got {v!r}")
        if self.start_time_s <0:
            raise InvalidExposureError("start_time_s must be >=0")
        if self.duration_s <=0 or self.duration_s>1e12:
            raise InvalidExposureError("duration_s must be >0 and reasonable")
        if self.exposure_id and not isinstance(self.exposure_id,str):
            raise InvalidExposureError("exposure_id must be str")

    @property
    def end_time_s(self) -> float:
        return self.start_time_s + self.duration_s

    @property
    def mid_time_s(self) -> float:
        return self.start_time_s + 0.5*self.duration_s

    def overlaps(self, other: "Exposure") -> bool:
        return not (self.end_time_s <= other.start_time_s or other.end_time_s <= self.start_time_s)

    def contains(self, t: float) -> bool:
        return self.start_time_s <= t <= self.end_time_s

    def to_dict(self) -> Dict:
        return {"start_time_s": self.start_time_s, "duration_s": self.duration_s, "exposure_id": self.exposure_id}
    @classmethod
    def from_dict(cls, d: Dict) -> "Exposure":
        return cls(d["start_time_s"], d["duration_s"], d.get("exposure_id",""))

@dataclass
class ExposureSequence:
    """Ordered sequence of exposures (e.g. survey cadence)."""

    exposures: List[Exposure] = field(default_factory=list)

    def add(self, exp: Exposure) -> None:
        if not isinstance(exp, Exposure):
            raise InvalidExposureError("must be Exposure")
        self.exposures.append(exp)
        self.exposures.sort(key=lambda e: e.start_time_s)

    def total_exposure(self) -> float:
        return sum(e.duration_s for e in self.exposures)

    def interval(self) -> Tuple[float,float] | None:
        if not self.exposures:
            return None
        return (self.exposures[0].start_time_s, self.exposures[-1].end_time_s)

    def to_dict(self) -> Dict:
        return {"exposures":[e.to_dict() for e in self.exposures]}
    @classmethod
    def from_dict(cls, d: Dict) -> "ExposureSequence":
        seq=cls()
        for ed in d.get("exposures",[]):
            seq.add(Exposure.from_dict(ed))
        return seq

__all__=["Exposure","ExposureSequence"]
