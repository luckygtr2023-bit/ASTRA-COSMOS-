"""Measurements, uncertainties, data products."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from astra.celestial.provenance import DataProvenance, ProvenanceTag
from astra.observatory.exceptions import InvalidMeasurementError

@dataclass(frozen=True)
class Uncertainty:
    """Nominal + uncertainty + units."""
    value: float
    uncertainty: float
    unit: str = ""
    confidence: float = 0.68  # 1 sigma

    def __post_init__(self):
        if isinstance(self.value,bool) or not isinstance(self.value,(int,float)) or math.isnan(self.value) or math.isinf(self.value):
            raise InvalidMeasurementError(f"value must be finite, got {self.value!r}")
        if isinstance(self.uncertainty,bool) or not isinstance(self.uncertainty,(int,float)) or math.isnan(self.uncertainty) or math.isinf(self.uncertainty) or self.uncertainty<0:
            raise InvalidMeasurementError(f"uncertainty must be >=0 finite, got {self.uncertainty!r}")
        if not isinstance(self.unit,str):
            raise InvalidMeasurementError("unit must be str")
        if not (0 < self.confidence <=1):
            raise InvalidMeasurementError("confidence must be in (0,1]")
        object.__setattr__(self, "value", float(self.value))
        object.__setattr__(self, "uncertainty", float(self.uncertainty))

    def to_dict(self) -> Dict:
        return {"value": self.value, "uncertainty": self.uncertainty, "unit": self.unit, "confidence": self.confidence}
    @classmethod
    def from_dict(cls, d: Dict) -> "Uncertainty":
        return cls(d["value"], d["uncertainty"], d.get("unit",""), d.get("confidence",0.68))

    def __str__(self) -> str:
        # avoid false precision: format to 5 significant digits max
        return f"{self.value:.5g} ± {self.uncertainty:.2g} {self.unit}".strip()

@dataclass(frozen=True)
class Measurement:
    """Generic simulated measurement.

    Attributes:
        measurement_id: unique
        quantity: name (flux, magnitude, position, wavelength, etc.)
        value: nominal
        uncertainty: 1-sigma
        unit: string
        instrument_id, observatory_id, source_id
        timestamp_s: measurement time (mid exposure)
        exposure_s: integrated time
        band/filter: string id
        provenance: always SIMULATED_DATA for simulated telescope
        metadata: calibration, method etc.
    """
    measurement_id: str
    quantity: str
    value: float
    uncertainty: float
    unit: str
    instrument_id: str
    observatory_id: str
    source_id: str
    timestamp_s: float
    exposure_s: float = 0.0
    band: str = ""
    filter_id: str = ""
    provenance: ProvenanceTag = field(default_factory=lambda: ProvenanceTag(DataProvenance.SIMULATED_DATA, "astra.observatory"))
    metadata: Dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        if not isinstance(self.measurement_id,str) or not self.measurement_id:
            raise InvalidMeasurementError("measurement_id must be non-empty")
        if not isinstance(self.quantity,str) or not self.quantity:
            raise InvalidMeasurementError("quantity must be non-empty")
        for name in ("value","uncertainty","timestamp_s","exposure_s"):
            v=getattr(self, name)
            if isinstance(v,bool) or not isinstance(v,(int,float)) or math.isnan(v) or math.isinf(v):
                raise InvalidMeasurementError(f"{name} must be finite, got {v!r}")
        if self.uncertainty<0:
            raise InvalidMeasurementError("uncertainty must be >=0")
        if self.timestamp_s<0 or self.exposure_s<0:
            raise InvalidMeasurementError("timestamp/exposure must be >=0")
        if not isinstance(self.provenance, ProvenanceTag):
            raise InvalidMeasurementError("provenance must be ProvenanceTag")
        # simulated measurement must be SIMULATED_DATA (honesty)
        if self.provenance.provenance not in (DataProvenance.SIMULATED_DATA, DataProvenance.DERIVED_DATA, DataProvenance.THEORETICAL_MODEL, DataProvenance.SPECULATIVE_MODEL):
            # allow derived/theoretical/speculative for special cases, but not REAL_DATA
            if self.provenance.provenance == DataProvenance.REAL_DATA:
                raise InvalidMeasurementError("simulated measurement cannot be REAL_DATA")
        for field_name in ("instrument_id","observatory_id","source_id","unit","band","filter_id"):
            if not isinstance(getattr(self, field_name), str):
                raise InvalidMeasurementError(f"{field_name} must be str")

    @property
    def uncertainty_obj(self) -> Uncertainty:
        return Uncertainty(self.value, self.uncertainty, self.unit)

    @property
    def snr(self) -> float:
        if self.uncertainty==0:
            return math.inf if self.value!=0 else 0
        return abs(self.value)/self.uncertainty

    def to_dict(self) -> Dict:
        return {
            "measurement_id": self.measurement_id,
            "quantity": self.quantity,
            "value": self.value,
            "uncertainty": self.uncertainty,
            "unit": self.unit,
            "instrument_id": self.instrument_id,
            "observatory_id": self.observatory_id,
            "source_id": self.source_id,
            "timestamp_s": self.timestamp_s,
            "exposure_s": self.exposure_s,
            "band": self.band,
            "filter_id": self.filter_id,
            "provenance": {"provenance": self.provenance.provenance.value, "source_label": self.provenance.source_label},
            "metadata": dict(self.metadata),
        }
    @classmethod
    def from_dict(cls, d: Dict) -> "Measurement":
        prov=ProvenanceTag(DataProvenance(d["provenance"]["provenance"]), d["provenance"]["source_label"])
        return cls(
            measurement_id=d["measurement_id"], quantity=d["quantity"], value=d["value"], uncertainty=d["uncertainty"], unit=d["unit"],
            instrument_id=d["instrument_id"], observatory_id=d["observatory_id"], source_id=d["source_id"],
            timestamp_s=d["timestamp_s"], exposure_s=d.get("exposure_s",0), band=d.get("band",""), filter_id=d.get("filter_id",""),
            provenance=prov, metadata=dict(d.get("metadata",{}))
        )

# DataProducts aggregate measurements

@dataclass
class ImagingDataProduct:
    """Imaging metadata + measurements per pixel/grid (simplified)."""
    product_id: str
    observatory_id: str
    instrument_id: str
    filter_id: str
    exposure_s: float
    field_of_view_deg: float
    wavelength_m: float
    timestamp_s: float
    measurements: List[Measurement] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {"product_id": self.product_id, "observatory_id": self.observatory_id, "instrument_id": self.instrument_id, "filter_id": self.filter_id, "exposure_s": self.exposure_s, "field_of_view_deg": self.field_of_view_deg, "wavelength_m": self.wavelength_m, "timestamp_s": self.timestamp_s, "measurements":[m.to_dict() for m in self.measurements], "metadata": dict(self.metadata)}

@dataclass
class PhotometryDataProduct:
    product_id: str
    observatory_id: str
    instrument_id: str
    source_id: str
    timestamp_s: float
    flux: Measurement  # W/m2 or Jy
    magnitude: Optional[Measurement] = None  # mag
    band: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> Dict:
        return {"product_id": self.product_id, "observatory_id": self.observatory_id, "instrument_id": self.instrument_id, "source_id": self.source_id, "timestamp_s": self.timestamp_s, "flux": self.flux.to_dict(), "magnitude": self.magnitude.to_dict() if self.magnitude else None, "band": self.band, "metadata": dict(self.metadata)}

@dataclass
class AstrometryDataProduct:
    product_id: str
    observatory_id: str
    instrument_id: str
    source_id: str
    timestamp_s: float
    apparent_position: Tuple[float,float,float]  # x,y,z metres (observed)
    angular_position: Tuple[float,float]  # RA/Dec approx or azimuth/elev (radians)
    uncertainty_arcsec: float
    reference_frame: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> Dict:
        return {"product_id": self.product_id, "observatory_id": self.observatory_id, "instrument_id": self.instrument_id, "source_id": self.source_id, "timestamp_s": self.timestamp_s, "apparent_position": list(self.apparent_position), "angular_position": list(self.angular_position), "uncertainty_arcsec": self.uncertainty_arcsec, "reference_frame": self.reference_frame, "metadata": dict(self.metadata)}

@dataclass
class SpectroscopyDataProduct:
    product_id: str
    observatory_id: str
    instrument_id: str
    source_id: str
    timestamp_s: float
    wavelengths: List[float] # m
    intensities: List[float] # arbitrary (flux)
    uncertainties: List[float]
    redshift: Optional[float] = None
    resolution: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> Dict:
        return {"product_id": self.product_id, "observatory_id": self.observatory_id, "instrument_id": self.instrument_id, "source_id": self.source_id, "timestamp_s": self.timestamp_s, "wavelengths": list(self.wavelengths), "intensities": list(self.intensities), "uncertainties": list(self.uncertainties), "redshift": self.redshift, "resolution": self.resolution, "metadata": dict(self.metadata)}

__all__=["Uncertainty","Measurement","ImagingDataProduct","PhotometryDataProduct","AstrometryDataProduct","SpectroscopyDataProduct"]
