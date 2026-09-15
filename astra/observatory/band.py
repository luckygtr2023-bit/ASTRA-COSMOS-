"""Wavelength / spectral bands.

Provides deterministic conversions and band identification.

Units: wavelength in metres, frequency in Hz, energy in J.
C is exact. Uses Planck constant where needed (for energy).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from astra.relativity.core import SPEED_OF_LIGHT as C
from astra.observatory.exceptions import InvalidBandError, UnsupportedWavelengthError

PLANCK_H = 6.62607015e-34  # J s, exact
# Common bands (approximate, scientific but not calibrated)
BAND_RANGES = {
    "radio": (1e-1, 1e4),           # 0.1 m to 10 km
    "microwave": (1e-3, 1e-1),       # 1 mm to 10 cm
    "infrared": (7e-7, 1e-3),        # 700 nm to 1 mm
    "visible": (3.8e-7, 7.5e-7),     # 380-750 nm
    "ultraviolet": (1e-8, 3.8e-7),   # 10-380 nm
    "x-ray": (1e-11, 1e-8),          # 0.01-10 nm
    "gamma-ray": (1e-14, 1e-11),     # <0.01 nm
}

# Ordered list for identification (shortest first)
_BAND_ORDER = ["gamma-ray", "x-ray", "ultraviolet", "visible", "infrared", "microwave", "radio"]

class SpectralBand(str, Enum):
    RADIO = "radio"
    MICROWAVE = "microwave"
    INFRARED = "infrared"
    VISIBLE = "visible"
    ULTRAVIOLET = "ultraviolet"
    X_RAY = "x-ray"
    GAMMA_RAY = "gamma-ray"

@dataclass(frozen=True)
class WavelengthRange:
    """Inclusive wavelength interval in metres."""
    min_m: float
    max_m: float

    def __post_init__(self):
        if not isinstance(self.min_m, (int, float)) or not isinstance(self.max_m, (int, float)):
            raise InvalidBandError("wavelength bounds must be numbers")
        if math.isnan(self.min_m) or math.isinf(self.min_m) or math.isnan(self.max_m) or math.isinf(self.max_m):
            raise InvalidBandError("wavelength bounds must be finite")
        if self.min_m <=0 or self.max_m <=0:
            raise InvalidBandError("wavelength bounds must be >0")
        if self.min_m > self.max_m:
            raise InvalidBandError(f"min {self.min_m} > max {self.max_m}")

    def contains(self, wavelength_m: float) -> bool:
        if not isinstance(wavelength_m, (int,float)) or math.isnan(wavelength_m) or math.isinf(wavelength_m):
            return False
        return self.min_m <= wavelength_m <= self.max_m

    def bandwidth(self) -> float:
        return self.max_m - self.min_m

    def central_wavelength(self) -> float:
        return 0.5*(self.min_m+self.max_m)

    def to_frequency_range(self) -> tuple[float,float]:
        # f = c / lambda, so min lambda -> max f
        return (C/self.max_m, C/self.min_m)

    def to_dict(self) -> dict:
        return {"min_m": self.min_m, "max_m": self.max_m}
    @classmethod
    def from_dict(cls, d: dict) -> "WavelengthRange":
        return cls(d["min_m"], d["max_m"])

def wavelength_to_frequency(wavelength_m: float) -> float:
    if not isinstance(wavelength_m, (int,float)) or wavelength_m<=0 or math.isnan(wavelength_m) or math.isinf(wavelength_m):
        raise UnsupportedWavelengthError(f"invalid wavelength {wavelength_m!r}")
    return C / float(wavelength_m)

def frequency_to_wavelength(frequency_hz: float) -> float:
    if not isinstance(frequency_hz, (int,float)) or frequency_hz<=0 or math.isnan(frequency_hz) or math.isinf(frequency_hz):
        raise UnsupportedWavelengthError(f"invalid frequency {frequency_hz!r}")
    return C / float(frequency_hz)

def wavelength_to_energy(wavelength_m: float) -> float:
    # E = h c / lambda
    if not isinstance(wavelength_m, (int,float)) or wavelength_m<=0 or math.isnan(wavelength_m) or math.isinf(wavelength_m):
        raise UnsupportedWavelengthError(f"invalid wavelength {wavelength_m!r}")
    return PLANCK_H * C / float(wavelength_m)

def identify_band(wavelength_m: float) -> SpectralBand | None:
    if not isinstance(wavelength_m, (int,float)) or wavelength_m<=0 or math.isnan(wavelength_m) or math.isinf(wavelength_m):
        raise UnsupportedWavelengthError(f"invalid wavelength {wavelength_m!r}")
    for name in _BAND_ORDER:
        lo, hi = BAND_RANGES[name]
        # BAND_RANGES uses (shortest? Let's treat as min=max correctly: visible is 380-750nm so min 3.8e-7 max 7.5e-7
        # For radio we stored (0.1, 1e4) correct min<max, but for order we check containment
        mn, mx = (lo, hi) if lo<hi else (hi, lo)
        if mn <= wavelength_m <= mx:
            # map to enum: need to handle hyphen
            for band in SpectralBand:
                if band.value==name:
                    return band
    return None

def band_range(band: SpectralBand | str) -> WavelengthRange:
    if isinstance(band, SpectralBand):
        name=band.value
    else:
        name=str(band)
        if name not in BAND_RANGES:
            raise InvalidBandError(f"unknown band {band!r}")
    lo, hi = BAND_RANGES[name]
    mn, mx = (lo, hi) if lo<hi else (hi, lo)
    return WavelengthRange(mn, mx)

__all__=["SpectralBand","WavelengthRange","wavelength_to_frequency","frequency_to_wavelength","wavelength_to_energy","identify_band","band_range","BAND_RANGES","PLANCK_H"]
