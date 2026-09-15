"""Filter / bandpass abstraction."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict

from astra.observatory.band import WavelengthRange
from astra.observatory.exceptions import InvalidFilterError

@dataclass(frozen=True)
class Filter:
    """Simple bandpass filter.

    Attributes:
        filter_id: unique id (e.g. 'V', 'J', 'Lyman-alpha')
        wavelength_range: passband in metres
        transmission: peak transmission 0-1 (simplified, flat within band)
        bandwidth: derived
        description: free text
    """
    filter_id: str
    wavelength_range: WavelengthRange
    transmission: float = 1.0
    description: str = ""

    def __post_init__(self):
        if not isinstance(self.filter_id, str) or not self.filter_id.strip():
            raise InvalidFilterError("filter_id must be non-empty string")
        if not isinstance(self.wavelength_range, WavelengthRange):
            raise InvalidFilterError("wavelength_range must be WavelengthRange")
        if not isinstance(self.transmission, (int,float)) or math.isnan(self.transmission) or math.isinf(self.transmission) or not (0 < self.transmission <=1):
            raise InvalidFilterError("transmission must be in (0,1]")

    def contains(self, wavelength_m: float) -> bool:
        return self.wavelength_range.contains(wavelength_m)

    def effective_transmission(self, wavelength_m: float) -> float:
        """Flat transmission inside band, 0 outside (simplified)."""
        return float(self.transmission) if self.contains(wavelength_m) else 0.0

    def to_dict(self) -> Dict:
        return {"filter_id": self.filter_id, "wavelength_range": self.wavelength_range.to_dict(), "transmission": self.transmission, "description": self.description}
    @classmethod
    def from_dict(cls, d: Dict) -> "Filter":
        return cls(d["filter_id"], WavelengthRange.from_dict(d["wavelength_range"]), d.get("transmission",1.0), d.get("description",""))

# Common astronomical filters (central, simplified)
COMMON_FILTERS: Dict[str, Filter] = {
    "U": Filter("U", WavelengthRange(3.2e-7, 3.9e-7), 0.8, "Johnson U"),
    "B": Filter("B", WavelengthRange(3.9e-7, 4.9e-7), 0.85, "Johnson B"),
    "V": Filter("V", WavelengthRange(4.95e-7, 5.95e-7), 0.9, "Johnson V"),
    "R": Filter("R", WavelengthRange(5.8e-7, 7.2e-7), 0.85, "Cousins R"),
    "I": Filter("I", WavelengthRange(7.2e-7, 9e-7), 0.8, "Cousins I"),
    "J": Filter("J", WavelengthRange(1.1e-6, 1.4e-6), 0.75, "IR J"),
    "H": Filter("H", WavelengthRange(1.5e-6, 1.8e-6), 0.75, "IR H"),
    "K": Filter("K", WavelengthRange(2.0e-6, 2.4e-6), 0.7, "IR K"),
    "radio_L": Filter("radio_L", WavelengthRange(0.15, 0.25), 0.6, "Radio L-band"),
    "xray_soft": Filter("xray_soft", WavelengthRange(1e-9, 3e-9), 0.5, "Soft X-ray"),
    "gamma": Filter("gamma", WavelengthRange(1e-12, 1e-11), 0.3, "Gamma"),
}

__all__=["Filter","COMMON_FILTERS"]
