"""Detector & Noise models."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from astra.observatory.exceptions import InvalidDetectorError

@dataclass(frozen=True)
class Detector:
    """Generic detector abstraction.

    Attributes:
        detector_id: unique id
        quantum_efficiency: 0-1 (prob. photon → electron)
        read_noise_electrons: rms read noise per pixel/exposure
        dark_current_e_per_s: thermal dark per second per pixel
        saturation_electrons: full well
        dynamic_range: derived saturation/read_noise if not given
        pixel_scale_arcsec: optional plate scale for imaging
        gain: e-/ADU
        bias_level: baseline ADU
    """
    detector_id: str
    quantum_efficiency: float = 0.8
    read_noise_electrons: float = 5.0
    dark_current_e_per_s: float = 0.01
    saturation_electrons: float = 1e12
    pixel_scale_arcsec: Optional[float] = None
    gain: float = 1.0
    bias_level: float = 0.0

    def __post_init__(self):
        if not isinstance(self.detector_id, str) or not self.detector_id.strip():
            raise InvalidDetectorError("detector_id must be non-empty")
        for name in ("quantum_efficiency","read_noise_electrons","dark_current_e_per_s","saturation_electrons","gain"):
            v=getattr(self, name)
            if not isinstance(v,(int,float)) or math.isnan(v) or math.isinf(v):
                raise InvalidDetectorError(f"{name} must be finite, got {v!r}")
        if not (0 < self.quantum_efficiency <=1):
            raise InvalidDetectorError("quantum_efficiency must be in (0,1]")
        if self.read_noise_electrons <0 or self.dark_current_e_per_s<0 or self.saturation_electrons<=0 or self.gain<=0:
            raise InvalidDetectorError("detector noise/saturation/gain invalid")
        if self.pixel_scale_arcsec is not None:
            if not isinstance(self.pixel_scale_arcsec,(int,float)) or math.isnan(self.pixel_scale_arcsec) or math.isinf(self.pixel_scale_arcsec) or self.pixel_scale_arcsec<=0:
                raise InvalidDetectorError("pixel_scale_arcsec must be >0")

    @property
    def dynamic_range(self) -> float:
        if self.read_noise_electrons==0:
            return math.inf
        return self.saturation_electrons / self.read_noise_electrons

    def is_saturated(self, electrons: float) -> bool:
        return electrons >= self.saturation_electrons

    def to_dict(self) -> Dict:
        return {"detector_id": self.detector_id, "quantum_efficiency": self.quantum_efficiency, "read_noise_electrons": self.read_noise_electrons, "dark_current_e_per_s": self.dark_current_e_per_s, "saturation_electrons": self.saturation_electrons, "pixel_scale_arcsec": self.pixel_scale_arcsec, "gain": self.gain, "bias_level": self.bias_level}
    @classmethod
    def from_dict(cls, d: Dict) -> "Detector":
        return cls(**d)

@dataclass(frozen=True)
class NoiseModel:
    """Configurable measurement noise.

    Components are additive variances (electrons^2) where applicable.
    All are simulated, labeled simulated.
    """
    include_shot_noise: bool = True  # photon shot sqrt(N)
    include_read_noise: bool = True
    include_dark_noise: bool = True
    include_background: bool = True
    background_e_per_s: float = 0.5
    systematic_fraction: float = 0.01  # fractional systematic

    def __post_init__(self):
        if not isinstance(self.background_e_per_s,(int,float)) or math.isnan(self.background_e_per_s) or math.isinf(self.background_e_per_s) or self.background_e_per_s<0:
            raise InvalidDetectorError("background_e_per_s must be >=0")
        if not isinstance(self.systematic_fraction,(int,float)) or math.isnan(self.systematic_fraction) or math.isinf(self.systematic_fraction) or not (0 <= self.systematic_fraction <1):
            raise InvalidDetectorError("systematic_fraction must be in [0,1)")

    def total_noise(self, signal_electrons: float, exposure_s: float, detector: Detector) -> float:
        """Total rms noise electrons."""
        if signal_electrons<0 or exposure_s<0:
            return math.inf
        var=0.0
        if self.include_shot_noise:
            var += max(0.0, signal_electrons)  # Poisson variance = N
        if self.include_read_noise:
            var += detector.read_noise_electrons**2
        if self.include_dark_noise:
            var += detector.dark_current_e_per_s * exposure_s
        if self.include_background:
            var += self.background_e_per_s * exposure_s
        # systematic adds in quadrature as fraction of signal
        if self.systematic_fraction>0:
            var += (self.systematic_fraction * signal_electrons)**2
        return math.sqrt(var)

    def snr(self, signal_electrons: float, exposure_s: float, detector: Detector) -> float:
        n=self.total_noise(signal_electrons, exposure_s, detector)
        if n==0:
            return math.inf if signal_electrons>0 else 0
        return signal_electrons / n

    def to_dict(self) -> Dict:
        return {"include_shot_noise": self.include_shot_noise, "include_read_noise": self.include_read_noise, "include_dark_noise": self.include_dark_noise, "include_background": self.include_background, "background_e_per_s": self.background_e_per_s, "systematic_fraction": self.systematic_fraction}
    @classmethod
    def from_dict(cls, d: Dict) -> "NoiseModel":
        return cls(**d)

__all__=["Detector","NoiseModel"]
