"""Instrument abstraction — shared base plus telescope/spectrometer/photometer/astrometric.

Keeps theoretical vs effective resolution distinguishable.
Uses existing mathematics conventions, no second physics engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, Optional, Tuple

from astra.observatory.band import SpectralBand, WavelengthRange, BAND_RANGES
from astra.observatory.detector import Detector
from astra.observatory.filter import Filter
from astra.observatory.exceptions import InvalidInstrumentError

class InstrumentType(str, Enum):
    OPTICAL_TELESCOPE = "optical_telescope"
    RADIO_TELESCOPE = "radio_telescope"
    INFRARED = "infrared"
    ULTRAVIOLET = "ultraviolet"
    X_RAY = "x-ray"
    GAMMA_RAY = "gamma-ray"
    SPECTROMETER = "spectrometer"
    PHOTOMETER = "photometer"
    ASTROMETRIC = "astrometric"
    GENERIC_DETECTOR = "generic_detector"

def _finite(v, name: str) -> float:
    if isinstance(v,bool) or not isinstance(v,(int,float)) or math.isnan(v) or math.isinf(v):
        raise InvalidInstrumentError(f"{name} must be finite, got {v!r}")
    return float(v)

def _check_range(r: WavelengthRange, name: str) -> WavelengthRange:
    if not isinstance(r, WavelengthRange):
        raise InvalidInstrumentError(f"{name} must be WavelengthRange")
    return r

@dataclass(frozen=True)
class Instrument:
    """Generic instrument base.

    Attributes:
        instrument_id: unique
        instrument_type: enum
        aperture_m: primary aperture diameter (>0 for telescopes, else 0)
        focal_length_m: >0 if applicable, else 0
        field_of_view_deg: full cone
        wavelength_range: response interval
        detector: Detector instance
        filter: optional Filter
        throughput: 0-1 (optics)
        angular_resolution_arcsec: optional effective resolution override (if not provided, diffraction limit is theoretical)
        spectral_resolution: lambda/delta_lambda for spectrometers (0 means not applicable)
    """
    instrument_id: str
    instrument_type: InstrumentType = InstrumentType.GENERIC_DETECTOR
    aperture_m: float = 0.0
    focal_length_m: float = 0.0
    field_of_view_deg: float = 10.0
    wavelength_range: WavelengthRange = field(default_factory=lambda: WavelengthRange(3.8e-7, 7.5e-7))
    detector: Detector = field(default_factory=lambda: Detector("default"))
    filter: Optional[Filter] = None
    throughput: float = 0.8
    angular_resolution_arcsec: Optional[float] = None
    spectral_resolution: float = 0.0  # R = lambda/dlambda
    metadata: Dict = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        if not isinstance(self.instrument_id, str) or not self.instrument_id.strip():
            raise InvalidInstrumentError("instrument_id must be non-empty")
        if not isinstance(self.instrument_type, InstrumentType):
            raise InvalidInstrumentError("instrument_type must be InstrumentType")
        # aperture
        ap=_finite(self.aperture_m, "aperture_m")
        if ap <0:
            raise InvalidInstrumentError("aperture_m must be >=0")
        object.__setattr__(self, "aperture_m", float(ap))
        fl=_finite(self.focal_length_m, "focal_length_m")
        if fl<0:
            raise InvalidInstrumentError("focal_length_m must be >=0")
        object.__setattr__(self, "focal_length_m", float(fl))
        # FOV
        fov=_finite(self.field_of_view_deg, "field_of_view_deg")
        if not (0 < fov <= 180):
            raise InvalidInstrumentError("field_of_view_deg must be in (0,180]")
        object.__setattr__(self, "field_of_view_deg", float(fov))
        _check_range(self.wavelength_range, "wavelength_range")
        if not isinstance(self.detector, Detector):
            raise InvalidInstrumentError("detector must be Detector")
        if self.filter is not None and not isinstance(self.filter, Filter):
            raise InvalidInstrumentError("filter must be Filter or None")
        thr=_finite(self.throughput, "throughput")
        if not (0 < thr <=1):
            raise InvalidInstrumentError("throughput must be in (0,1]")
        object.__setattr__(self, "throughput", float(thr))
        if self.angular_resolution_arcsec is not None:
            v=_finite(self.angular_resolution_arcsec, "angular_resolution_arcsec")
            if v<=0:
                raise InvalidInstrumentError("angular_resolution_arcsec must be >0")
            object.__setattr__(self, "angular_resolution_arcsec", float(v))
        sr=_finite(self.spectral_resolution, "spectral_resolution")
        if sr<0:
            raise InvalidInstrumentError("spectral_resolution must be >=0")
        object.__setattr__(self, "spectral_resolution", float(sr))
        if not isinstance(self.metadata, dict):
            raise InvalidInstrumentError("metadata must be dict")

    # -- derived -------------------------------------------------------
    @property
    def focal_ratio(self) -> Optional[float]:
        if self.aperture_m==0 or self.focal_length_m==0:
            return None
        return self.focal_length_m / self.aperture_m

    @property
    def collecting_area_m2(self) -> float:
        if self.aperture_m<=0:
            return 0.0
        r=self.aperture_m/2
        return math.pi * r * r

    def theoretical_resolution_rad(self, wavelength_m: Optional[float]=None) -> Optional[float]:
        """Diffraction limit 1.22*lambda/D (radians). None if no aperture."""
        if self.aperture_m<=0:
            return None
        lam = wavelength_m if wavelength_m is not None else self.wavelength_range.central_wavelength()
        if lam<=0:
            return None
        return 1.22 * lam / self.aperture_m

    def theoretical_resolution_arcsec(self, wavelength_m: Optional[float]=None) -> Optional[float]:
        rad=self.theoretical_resolution_rad(wavelength_m)
        if rad is None:
            return None
        return rad * (180/math.pi) * 3600

    def effective_resolution_arcsec(self, wavelength_m: Optional[float]=None) -> Optional[float]:
        """Effective = max(theoretical, configured). Keeps distinguishable."""
        theor=self.theoretical_resolution_arcsec(wavelength_m)
        if theor is None:
            return self.angular_resolution_arcsec
        if self.angular_resolution_arcsec is None:
            return theor
        return max(theor, self.angular_resolution_arcsec)

    def supports_wavelength(self, wavelength_m: float) -> bool:
        if wavelength_m is None:
            return False
        return self.wavelength_range.contains(wavelength_m) and (self.filter.contains(wavelength_m) if self.filter else True)

    def field_radius_deg(self) -> float:
        return self.field_of_view_deg / 2.0

    # -- updates -------------------------------------------------------
    def with_filter(self, filt: Optional[Filter]) -> "Instrument":
        if filt is not None and not isinstance(filt, Filter):
            raise InvalidInstrumentError("filter must be Filter")
        return replace(self, filter=filt)

    def with_detector(self, det: Detector) -> "Instrument":
        if not isinstance(det, Detector):
            raise InvalidInstrumentError("detector must be Detector")
        return replace(self, detector=det)

    def to_dict(self) -> Dict:
        return {
            "instrument_id": self.instrument_id,
            "instrument_type": self.instrument_type.value,
            "aperture_m": self.aperture_m,
            "focal_length_m": self.focal_length_m,
            "field_of_view_deg": self.field_of_view_deg,
            "wavelength_range": self.wavelength_range.to_dict(),
            "detector": self.detector.to_dict(),
            "filter": self.filter.to_dict() if self.filter else None,
            "throughput": self.throughput,
            "angular_resolution_arcsec": self.angular_resolution_arcsec,
            "spectral_resolution": self.spectral_resolution,
            "metadata": dict(self.metadata),
        }
    @classmethod
    def from_dict(cls, d: Dict) -> "Instrument":
        from astra.observatory.filter import Filter as F
        filt = F.from_dict(d["filter"]) if d.get("filter") else None
        return cls(
            instrument_id=d["instrument_id"],
            instrument_type=InstrumentType(d.get("instrument_type", "generic_detector")),
            aperture_m=d.get("aperture_m",0),
            focal_length_m=d.get("focal_length_m",0),
            field_of_view_deg=d.get("field_of_view_deg",10),
            wavelength_range=WavelengthRange.from_dict(d["wavelength_range"]),
            detector=Detector.from_dict(d["detector"]),
            filter=filt,
            throughput=d.get("throughput",0.8),
            angular_resolution_arcsec=d.get("angular_resolution_arcsec"),
            spectral_resolution=d.get("spectral_resolution",0),
            metadata=dict(d.get("metadata",{})),
        )

# Convenience factories for required types

def optical_telescope(instrument_id: str, aperture_m: float, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.OPTICAL_TELESCOPE, aperture_m=aperture_m, wavelength_range=WavelengthRange(3.8e-7,7.5e-7), **kw)

def radio_telescope(instrument_id: str, aperture_m: float, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.RADIO_TELESCOPE, aperture_m=aperture_m, wavelength_range=WavelengthRange(1e-2,1e2), **kw)

def infrared_instrument(instrument_id: str, aperture_m: float, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.INFRARED, aperture_m=aperture_m, wavelength_range=WavelengthRange(7.5e-7,1e-3), **kw)

def ultraviolet_instrument(instrument_id: str, aperture_m: float, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.ULTRAVIOLET, aperture_m=aperture_m, wavelength_range=WavelengthRange(1e-8,3.8e-7), **kw)

def xray_instrument(instrument_id: str, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.X_RAY, aperture_m=kw.pop("aperture_m",0.5), wavelength_range=WavelengthRange(1e-11,1e-8), **kw)

def gamma_ray_instrument(instrument_id: str, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.GAMMA_RAY, aperture_m=kw.pop("aperture_m",0.3), wavelength_range=WavelengthRange(1e-14,1e-11), **kw)

def spectrometer(instrument_id: str, spectral_resolution: float, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.SPECTROMETER, spectral_resolution=spectral_resolution, **kw)

def photometer(instrument_id: str, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.PHOTOMETER, **kw)

def astrometric_instrument(instrument_id: str, aperture_m: float, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.ASTROMETRIC, aperture_m=aperture_m, **kw)

def generic_detector(instrument_id: str, **kw) -> Instrument:
    return Instrument(instrument_id, InstrumentType.GENERIC_DETECTOR, **kw)

__all__=[
    "Instrument","InstrumentType",
    "optical_telescope","radio_telescope","infrared_instrument","ultraviolet_instrument","xray_instrument","gamma_ray_instrument","spectrometer","photometer","astrometric_instrument","generic_detector"
]
