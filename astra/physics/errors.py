"""Physics-layer exceptions, all deriving from astra.core.exceptions.AstraError."""
from astra.core.exceptions import AstraError


class PhysicsError(AstraError):
    """Base Physics-layer error."""


class InvalidMassError(PhysicsError):
    """Raised when mass or inertia is not positive-finite."""


class InvalidForceError(PhysicsError):
    """Raised when a force is not finite."""


class InvalidTorqueError(PhysicsError):
    """Raised when a torque is not finite."""


class InvalidGravityError(PhysicsError):
    """Raised when a gravitational configuration is invalid."""


class InvalidContactError(PhysicsError):
    """Raised when a contact response is invalid."""
