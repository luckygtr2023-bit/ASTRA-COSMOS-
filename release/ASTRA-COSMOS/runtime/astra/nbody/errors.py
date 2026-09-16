"""N-Body Mechanics exceptions, all deriving from astra.core.exceptions.AstraError."""
from astra.core.exceptions import AstraError


class NBodyError(AstraError):
    """Base N-Body error."""


class InvalidBodyError(NBodyError):
    """Raised when an NBodyBody is not a valid physical body."""


class InvalidMassError(NBodyError):
    """Raised when mass is not positive-finite (or +inf for test bodies)."""


class DuplicateBodyError(NBodyError):
    """Raised when two bodies share the same id."""


class NBodySingularityError(NBodyError):
    """Raised when pairwise evaluation encounters a true singularity
    (zero distance with zero softening)."""


class InvalidTimestepError(NBodyError):
    """Raised when dt is not positive-finite."""
