"""Observatory & Measurement exceptions."""

from __future__ import annotations

from astra.core.exceptions import AstraError


class ObservatoryError(AstraError):
    """Base observatory/measurement error."""


class InvalidObservatoryError(ObservatoryError, ValueError):
    pass


class InvalidInstrumentError(ObservatoryError, ValueError):
    pass


class InvalidDetectorError(ObservatoryError, ValueError):
    pass


class InvalidFilterError(ObservatoryError, ValueError):
    pass


class InvalidMeasurementError(ObservatoryError, ValueError):
    pass


class InvalidExposureError(ObservatoryError, ValueError):
    pass


class InvalidBandError(ObservatoryError, ValueError):
    pass


class UnsupportedWavelengthError(ObservatoryError, ValueError):
    pass


class TargetOutsideFOVError(ObservatoryError):
    pass


class DetectorSaturationError(ObservatoryError):
    pass


class CalibrationError(ObservatoryError, ValueError):
    pass


class HistoryUnavailableError(ObservatoryError):
    pass
