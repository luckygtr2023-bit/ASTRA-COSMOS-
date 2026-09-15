"""Astronomical Observatory & Measurement Engine.

Pipeline:
  PHYSICAL STATE → COSMIC/HISTORICAL → LIGHT PROPAGATION → OBSERVATION EVENT → OBSERVATORY → INSTRUMENT → DETECTOR → MEASUREMENT → DATA PRODUCT

Reuses Observation & Cosmic History, Relativity, Spacetime, Celestial provenance, Coordinates.
Never mutates authoritative state.
"""

from __future__ import annotations

from astra.observatory.exceptions import (
    ObservatoryError,
    InvalidObservatoryError,
    InvalidInstrumentError,
    InvalidDetectorError,
    InvalidFilterError,
    InvalidMeasurementError,
    InvalidExposureError,
    InvalidBandError,
    UnsupportedWavelengthError,
    TargetOutsideFOVError,
    DetectorSaturationError,
    CalibrationError,
    HistoryUnavailableError,
)
from astra.observatory.observatory import Observatory, PlatformType, on_planetary_surface, in_orbit, on_spacecraft, in_deep_space
from astra.observatory.band import SpectralBand, WavelengthRange, wavelength_to_frequency, frequency_to_wavelength, wavelength_to_energy, identify_band, band_range, BAND_RANGES
from astra.observatory.filter import Filter, COMMON_FILTERS
from astra.observatory.detector import Detector, NoiseModel
from astra.observatory.exposure import Exposure, ExposureSequence
from astra.observatory.instrument import Instrument, InstrumentType, optical_telescope, radio_telescope, infrared_instrument, ultraviolet_instrument, xray_instrument, gamma_ray_instrument, spectrometer, photometer, astrometric_instrument, generic_detector
from astra.observatory.measurement import Uncertainty, Measurement, ImagingDataProduct, PhotometryDataProduct, AstrometryDataProduct, SpectroscopyDataProduct
from astra.observatory.calibration import CalibrationFrame, Calibrator
from astra.observatory.session import ObservationSession, SurveyField, SurveyPlan
from astra.observatory.engine import ObservatoryEngine, MAG_ZERO_FLUX

__all__ = [
    # exceptions
    "ObservatoryError", "InvalidObservatoryError", "InvalidInstrumentError", "InvalidDetectorError", "InvalidFilterError", "InvalidMeasurementError", "InvalidExposureError", "InvalidBandError", "UnsupportedWavelengthError", "TargetOutsideFOVError", "DetectorSaturationError", "CalibrationError", "HistoryUnavailableError",
    # observatory
    "Observatory", "PlatformType", "on_planetary_surface", "in_orbit", "on_spacecraft", "in_deep_space",
    # bands
    "SpectralBand", "WavelengthRange", "wavelength_to_frequency", "frequency_to_wavelength", "wavelength_to_energy", "identify_band", "band_range", "BAND_RANGES",
    # filter
    "Filter", "COMMON_FILTERS",
    # detector
    "Detector", "NoiseModel",
    # exposure
    "Exposure", "ExposureSequence",
    # instrument
    "Instrument", "InstrumentType", "optical_telescope", "radio_telescope", "infrared_instrument", "ultraviolet_instrument", "xray_instrument", "gamma_ray_instrument", "spectrometer", "photometer", "astrometric_instrument", "generic_detector",
    # measurement
    "Uncertainty", "Measurement", "ImagingDataProduct", "PhotometryDataProduct", "AstrometryDataProduct", "SpectroscopyDataProduct",
    # calibration
    "CalibrationFrame", "Calibrator",
    # session
    "ObservationSession", "SurveyField", "SurveyPlan",
    # engine
    "ObservatoryEngine", "MAG_ZERO_FLUX",
]

__version__="1.0.0"
