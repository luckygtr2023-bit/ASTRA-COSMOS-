"""Spacecraft Physics exceptions, all deriving from astra.core.exceptions.AstraError."""
from astra.core.exceptions import AstraError


class SpacecraftError(AstraError):
    """Base Spacecraft Physics error."""


class InvalidMassError(SpacecraftError):
    """Raised when dry mass / propellant mass / total mass is invalid."""


class InvalidEngineError(SpacecraftError):
    """Raised when an engine spec is not physically valid."""


class InvalidBurnError(SpacecraftError):
    """Raised when a burn (finite or impulsive) is malformed."""


class PropellantExhaustedError(SpacecraftError):
    """Raised when a burn requests more propellant than remains."""


class InvalidRocketEquationError(SpacecraftError):
    """Raised when rocket-equation inputs are unphysical."""
