"""Calibration architecture — extensible interfaces."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

from astra.observatory.exceptions import CalibrationError

@dataclass
class CalibrationFrame:
    """Generic calibration data."""
    calibration_id: str
    calibration_type: str  # bias, dark, flat, response, wavelength, photometric
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.calibration_id,str) or not self.calibration_id:
            raise CalibrationError("calibration_id must be non-empty")
        if not isinstance(self.calibration_type,str) or not self.calibration_type:
            raise CalibrationError("calibration_type must be non-empty")

    def to_dict(self) -> Dict:
        return {"calibration_id": self.calibration_id, "calibration_type": self.calibration_type, "data": dict(self.data), "metadata": dict(self.metadata)}
    @classmethod
    def from_dict(cls, d: Dict) -> "CalibrationFrame":
        return cls(d["calibration_id"], d["calibration_type"], dict(d.get("data",{})), dict(d.get("metadata",{})))

class Calibrator:
    """Applies calibration steps. Extensible — real data can be injected later."""

    def __init__(self):
        self._frames: Dict[str, CalibrationFrame] = {}

    def add(self, frame: CalibrationFrame) -> None:
        if not isinstance(frame, CalibrationFrame):
            raise CalibrationError("must be CalibrationFrame")
        self._frames[frame.calibration_id]=frame

    def get(self, calibration_id: str) -> Optional[CalibrationFrame]:
        return self._frames.get(calibration_id)

    def apply_bias_dark(self, raw_electrons: float, exposure_s: float, bias: float=0.0, dark_per_s: float=0.0) -> float:
        # simulated: subtract bias + dark*exposure, never negative
        if raw_electrons is None or math.isnan(raw_electrons) or math.isinf(raw_electrons):
            raise CalibrationError("raw_electrons must be finite")
        corrected = raw_electrons - bias - dark_per_s*exposure_s
        return max(0.0, corrected)

    def apply_flat(self, signal: float, flat_factor: float=1.0) -> float:
        if flat_factor<=0:
            raise CalibrationError("flat_factor must be >0")
        return signal / flat_factor

    def apply_photometric(self, flux: float, zeropoint: float=0.0) -> float:
        # simplistic: flux * 10^(zeropoint/2.5) ??? Keep linear for simulated
        return flux

    def calibrate_spectrum(self, wavelengths, intensities, response: Optional[Dict]=None):
        # placeholder: divide by response if provided
        if response is None:
            return intensities
        # assume response dict mapping wavelength -> factor
        out=[]
        for w,i in zip(wavelengths, intensities):
            factor=response.get(str(w),1.0)
            out.append(i/factor if factor!=0 else i)
        return out

__all__=["CalibrationFrame","Calibrator"]
