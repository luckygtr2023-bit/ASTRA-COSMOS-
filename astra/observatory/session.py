"""Observation session & survey abstractions."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from astra.observatory.observatory import Observatory
from astra.observatory.instrument import Instrument
from astra.observatory.exposure import Exposure, ExposureSequence
from astra.observatory.measurement import Measurement
from astra.observatory.exceptions import InvalidExposureError

@dataclass
class ObservationSession:
    """Reproducible observing session.

    Attributes:
        session_id: unique
        observatory: Observatory instance
        instrument: Instrument instance (must be mounted or compatible)
        target_id: source identifier
        start_time_s, end_time_s: session interval
        pointing: (x,y,z) direction or target position at start (unit vector will be derived)
        exposures: ExposureSequence
        measurements: generated Measurement list (populated after execution)
        metadata: free-form
        provenance: simulated etc.
    """
    session_id: str
    observatory: Observatory
    instrument: Instrument
    target_id: str
    start_time_s: float
    end_time_s: float
    pointing: Tuple[float,float,float] = (1,0,0)
    exposures: ExposureSequence = field(default_factory=ExposureSequence)
    measurements: List[Measurement] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.session_id,str) or not self.session_id:
            raise ValueError("session_id must be non-empty")
        if not isinstance(self.target_id,str) or not self.target_id:
            raise ValueError("target_id must be non-empty")
        if not isinstance(self.observatory, Observatory):
            raise ValueError("observatory must be Observatory")
        if not isinstance(self.instrument, Instrument):
            raise ValueError("instrument must be Instrument")
        for name in ("start_time_s","end_time_s"):
            v=getattr(self, name)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or math.isnan(v) or math.isinf(v) or v<0:
                raise ValueError(f"{name} must be finite >=0")
        if self.end_time_s < self.start_time_s:
            raise ValueError("end_time_s must be >= start_time_s")
        if not isinstance(self.pointing,(list,tuple)) or len(self.pointing)!=3:
            raise ValueError("pointing must be 3-tuple")
        n=math.sqrt(self.pointing[0]**2+self.pointing[1]**2+self.pointing[2]**2)
        if n==0 or math.isnan(n) or math.isinf(n):
            raise ValueError("pointing must be non-zero")
        if not isinstance(self.exposures, ExposureSequence):
            raise ValueError("exposures must be ExposureSequence")
        # exposures must lie within session interval
        for exp in self.exposures.exposures:
            if exp.start_time_s < self.start_time_s -1e-9 or exp.end_time_s > self.end_time_s +1e-9:
                raise InvalidExposureError(f"exposure {exp.exposure_id} outside session interval")

    def duration(self) -> float:
        return self.end_time_s - self.start_time_s

    def add_exposure(self, exp: Exposure) -> None:
        if exp.start_time_s < self.start_time_s or exp.end_time_s > self.end_time_s:
            raise InvalidExposureError("exposure outside session interval")
        self.exposures.add(exp)

    def add_measurement(self, meas: Measurement) -> None:
        if not isinstance(meas, Measurement):
            raise ValueError("must be Measurement")
        self.measurements.append(meas)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "observatory": self.observatory.to_dict(),
            "instrument": self.instrument.to_dict(),
            "target_id": self.target_id,
            "start_time_s": self.start_time_s,
            "end_time_s": self.end_time_s,
            "pointing": list(self.pointing),
            "exposures": self.exposures.to_dict(),
            "measurements": [m.to_dict() for m in self.measurements],
            "metadata": dict(self.metadata),
        }
    @classmethod
    def from_dict(cls, d: Dict) -> "ObservationSession":
        from astra.observatory.observatory import Observatory as Obs
        from astra.observatory.instrument import Instrument as Inst
        sess=cls(
            session_id=d["session_id"],
            observatory=Obs.from_dict(d["observatory"]),
            instrument=Inst.from_dict(d["instrument"]),
            target_id=d["target_id"],
            start_time_s=d["start_time_s"],
            end_time_s=d["end_time_s"],
            pointing=tuple(d.get("pointing",(1,0,0))),
            metadata=dict(d.get("metadata",{})),
        )
        for ed in d.get("exposures",{}).get("exposures",[]):
            sess.add_exposure(Exposure.from_dict(ed))
        for md in d.get("measurements",[]):
            sess.add_measurement(Measurement.from_dict(md))
        return sess

@dataclass
class SurveyField:
    """Sky region for survey."""
    field_id: str
    center: Tuple[float,float,float]  # direction or position
    radius_deg: float
    target_ids: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not isinstance(self.field_id,str) or not self.field_id:
            raise ValueError("field_id must be non-empty")
        if not isinstance(self.center,(list,tuple)) or len(self.center)!=3:
            raise ValueError("center must be 3-tuple")
        if not isinstance(self.radius_deg,(int,float)) or math.isnan(self.radius_deg) or math.isinf(self.radius_deg) or not (0 < self.radius_deg <=180):
            raise ValueError("radius_deg must be in (0,180]")

@dataclass
class SurveyPlan:
    """Repeated/batch observation plan."""
    survey_id: str
    observatory: Observatory
    instrument: Instrument
    fields: List[SurveyField] = field(default_factory=list)
    cadence_s: float = 3600.0
    total_duration_s: float = 86400.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.survey_id,str) or not self.survey_id:
            raise ValueError("survey_id must be non-empty")
        if not isinstance(self.observatory, Observatory):
            raise ValueError("observatory must be Observatory")
        if not isinstance(self.instrument, Instrument):
            raise ValueError("instrument must be Instrument")
        if self.cadence_s<=0 or self.total_duration_s<=0:
            raise ValueError("cadence and duration must be >0")

    def generate_sessions(self, start_time_s: float = 0.0) -> List[ObservationSession]:
        """Deterministically generate sessions per field/cadence (no global scan)."""
        sessions=[]
        t=start_time_s
        idx=0
        while t < start_time_s + self.total_duration_s:
            for f in self.fields:
                for tid in f.target_ids:
                    # pointing is field center for now
                    sess=ObservationSession(
                        session_id=f"{self.survey_id}_{idx}_{f.field_id}_{tid}",
                        observatory=self.observatory,
                        instrument=self.instrument,
                        target_id=tid,
                        start_time_s=t,
                        end_time_s=t+ self.cadence_s,
                        pointing=f.center,
                    )
                    # add single exposure of 0.5*cadence (fits within session)
                    dur=min(self.cadence_s*0.5, 1000)
                    sess.add_exposure(Exposure(t, dur, f"exp_{idx}"))
                    sessions.append(sess)
                    idx+=1
            t+=self.cadence_s
        return sessions

__all__=["ObservationSession","SurveyField","SurveyPlan"]
