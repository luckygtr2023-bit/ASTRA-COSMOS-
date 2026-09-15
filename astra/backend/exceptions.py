"""
ASTRA Backend — explicit error boundaries.

Every failure identifies subsystem / operation / resource / recoverability.
No silent swallowing; no generic catch-all hiding corruption.
"""

from __future__ import annotations

from typing import Optional, Dict, Any

from astra.core.exceptions import AstraError


class BackendError(AstraError):
    """Base for all backend/runtime integration errors."""

    def __init__(
        self,
        message: str,
        *,
        subsystem: str = "backend",
        operation: str = "",
        resource: str = "",
        recoverable: bool = False,
        cause: Optional[BaseException] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, details or {})
        self.subsystem = subsystem
        self.operation = operation
        self.resource = resource
        self.recoverable = recoverable
        self.cause = cause
        # enrich details for diagnostics
        self.details.update(
            {
                "subsystem": subsystem,
                "operation": operation,
                "resource": resource,
                "recoverable": recoverable,
                "cause": str(cause) if cause else "",
            }
        )

    def __str__(self) -> str:
        return (
            f"[{self.subsystem}:{self.operation}] {self.message} "
            f"(resource={self.resource!r}, recoverable={self.recoverable})"
            + (f" cause={self.cause!r}" if self.cause else "")
        )


class ConfigurationError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "config")
        super().__init__(message, **kw)


class PersistenceIntegrationError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "persistence")
        super().__init__(message, **kw)


class EventIntegrationError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "events")
        super().__init__(message, **kw)


class CacheError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "cache")
        super().__init__(message, **kw)


class ServiceError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "services")
        super().__init__(message, **kw)


class RuntimeError_(BackendError):  # avoid shadowing builtin RuntimeError
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "runtime")
        super().__init__(message, **kw)


class RenderDeliveryError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "render_delivery")
        super().__init__(message, **kw)


class GraphicsDeliveryError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "graphics_delivery")
        super().__init__(message, **kw)


class DataAccessError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "data_access")
        super().__init__(message, **kw)


class SecurityError(BackendError):
    def __init__(self, message: str, **kw):
        kw.setdefault("subsystem", "security")
        super().__init__(message, **kw)


__all__ = [
    "BackendError",
    "ConfigurationError",
    "PersistenceIntegrationError",
    "EventIntegrationError",
    "CacheError",
    "ServiceError",
    "RuntimeError_",
    "RenderDeliveryError",
    "GraphicsDeliveryError",
    "DataAccessError",
    "SecurityError",
]
