"""
ASTRA Backend & Runtime integration layer.

    SIM → AUTHORITATIVE STATE → RUNTIME SERVICES → RENDER/GRAPHICS STATE → VISUALIZATION

Never mutates authoritative simulation state.
All delivery (render/graphics) is derived, cached, and bounded.
"""

from astra.backend.exceptions import (
    BackendError,
    ConfigurationError,
    PersistenceIntegrationError,
    EventIntegrationError,
    CacheError,
    ServiceError,
    RuntimeError_,
    RenderDeliveryError,
    GraphicsDeliveryError,
    DataAccessError,
    SecurityError,
)
from astra.backend.config import (
    AstraBackendConfig,
    RenderingConfig,
    GraphicsConfig,
    RuntimeConfig,
    CacheConfig,
    PersistenceBackendConfig,
    DiagnosticsConfig,
    RenderQualityPreset,
    LogLevel,
    BACKEND_SCHEMA_VERSION,
)
from astra.backend.cache import BoundedCache, CacheRegistry, CacheEntry, CacheStats
from astra.backend.events import BackendEventHub, SubscriptionHandle
from astra.backend.persistence import BackendPersistence
from astra.backend.services import BackendServiceRegistry, BackendServiceName, BackendServiceDescriptor
from astra.backend.diagnostics import DiagnosticsCollector, HealthStatus
from astra.backend.security import (
    OperationClass,
    backend_operation,
    assert_authority,
    check_permission,
    is_simulation_thread,
)
from astra.backend.data_access import DataAccessService, DataSource, DataRequest, DataResponse, make_archive_handler
from astra.backend.render_delivery import RenderStateDelivery
from astra.backend.graphics_delivery import GraphicsStateDelivery, GraphicsState, GraphicsObject
from astra.backend.runtime import BackendRuntime, RuntimeState

__all__ = [
    # exceptions
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
    # config
    "AstraBackendConfig",
    "RenderingConfig",
    "GraphicsConfig",
    "RuntimeConfig",
    "CacheConfig",
    "PersistenceBackendConfig",
    "DiagnosticsConfig",
    "RenderQualityPreset",
    "LogLevel",
    "BACKEND_SCHEMA_VERSION",
    # cache
    "BoundedCache",
    "CacheRegistry",
    "CacheEntry",
    "CacheStats",
    # events
    "BackendEventHub",
    "SubscriptionHandle",
    # persistence
    "BackendPersistence",
    # services
    "BackendServiceRegistry",
    "BackendServiceName",
    "BackendServiceDescriptor",
    # diagnostics
    "DiagnosticsCollector",
    "HealthStatus",
    # security
    "OperationClass",
    "backend_operation",
    "assert_authority",
    "check_permission",
    "is_simulation_thread",
    # data
    "DataAccessService",
    "DataSource",
    "DataRequest",
    "DataResponse",
    "make_archive_handler",
    # delivery
    "RenderStateDelivery",
    "GraphicsStateDelivery",
    "GraphicsState",
    "GraphicsObject",
    # runtime
    "BackendRuntime",
    "RuntimeState",
]
