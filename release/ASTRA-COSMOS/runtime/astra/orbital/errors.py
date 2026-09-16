"""Orbital Mechanics exceptions, all deriving from astra.core.exceptions.AstraError."""
from astra.core.exceptions import AstraError


class OrbitalError(AstraError):
    """Base Orbital Mechanics error."""


class DegenerateOrbitError(OrbitalError):
    """Raised when orbital elements or state are mathematically undefined
    (e.g. zero angular momentum, zero position, radial trajectory)."""


class InvalidOrbitError(OrbitalError):
    """Raised when an orbit is defined with non-finite or unphysical values."""


class KeplerConvergenceError(OrbitalError):
    """Raised when the Kepler equation solver fails to converge."""


class InvalidTransferError(OrbitalError):
    """Raised when a transfer configuration is invalid (radii, mu, etc.)."""
