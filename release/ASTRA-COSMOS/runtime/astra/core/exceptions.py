"""ASTRA Core exceptions."""

from typing import Optional


class AstraError(Exception):
    """Base exception for all ASTRA errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AuthorityError(AstraError):
    """Raised when an unauthorized mutation is attempted."""

    def __init__(self, message: str, operation: str = "", context: Optional[dict] = None):
        super().__init__(message, {"operation": operation, **(context or {})})
        self.operation = operation
        self.context = context or {}


class ResourceError(AstraError):
    """Raised when a resource operation fails."""

    def __init__(
        self,
        message: str,
        resource_id: str = "",
        operation: str = "",
        context: Optional[dict] = None,
    ):
        super().__init__(
            message, {"resource_id": resource_id, "operation": operation, **(context or {})}
        )
        self.resource_id = resource_id
        self.operation = operation
        self.context = context or {}


class EntityError(AstraError):
    """Raised when an entity operation fails."""

    def __init__(self, message: str, entity_id: str = "", operation: str = ""):
        super().__init__(message, {"entity_id": entity_id, "operation": operation})
        self.entity_id = entity_id
        self.operation = operation


class CommandError(AstraError):
    """Raised when a command operation fails."""

    def __init__(self, message: str, command_id: str = "", tick: int = -1):
        super().__init__(message, {"command_id": command_id, "tick": tick})
        self.command_id = command_id
        self.tick = tick


class PersistenceError(AstraError):
    """Raised when a persistence operation fails."""

    def __init__(self, message: str, path: str = "", reason: str = ""):
        super().__init__(message, {"path": path, "reason": reason})
        self.path = path
        self.reason = reason


class TimeError(AstraError):
    """Raised when a time operation fails."""

    def __init__(self, message: str, operation: str = "", timestamp: float = 0.0):
        super().__init__(message, {"operation": operation, "timestamp": timestamp})
        self.operation = operation
        self.timestamp = timestamp


class FrameError(AstraError):
    """Raised when a coordinate frame operation fails."""

    def __init__(self, message: str, frame_id: str = "", operation: str = ""):
        super().__init__(message, {"frame_id": frame_id, "operation": operation})
        self.frame_id = frame_id
        self.operation = operation
