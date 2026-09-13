"""ASTRA Core service registry."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Type, Callable, TypeVar
import threading

from astra.core.logging import get_logger
from astra.core.exceptions import AstraError


T = TypeVar("T")


@dataclass
class ServiceInfo:
    """Information about a registered service."""

    name: str
    service_type: str
    instance: Any
    dependencies: List[str] = field(default_factory=list)
    initialized: bool = False
    started: bool = False


class ServiceRegistry:
    """Registry for managing ASTRA services and their lifecycle."""

    def __init__(self):
        self._services: Dict[str, ServiceInfo] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._lock = threading.RLock()
        self._logger = get_logger("service_registry")

    def register(
        self,
        name: str,
        service: Any,
        dependencies: Optional[List[str]] = None,
    ):
        """Register a service instance."""
        with self._lock:
            if name in self._services:
                raise AstraError(f"Service already registered: {name}")

            info = ServiceInfo(
                name=name,
                service_type=type(service).__name__,
                instance=service,
                dependencies=dependencies or [],
                initialized=True,
                started=False,
            )

            self._services[name] = info
            self._logger.debug(f"Registered service: {name} ({info.service_type})")

    def register_factory(
        self,
        name: str,
        factory: Callable[[], Any],
        dependencies: Optional[List[str]] = None,
    ):
        """Register a service factory for lazy initialization."""
        with self._lock:
            if name in self._services or name in self._factories:
                raise AstraError(f"Service already registered: {name}")

            self._factories[name] = factory
            self._logger.debug(f"Registered service factory: {name}")

    def get(self, name: str) -> Optional[Any]:
        """Get a service by name."""
        with self._lock:
            # Check if already instantiated
            if name in self._services:
                return self._services[name].instance

            # Check if there's a factory
            if name in self._factories:
                factory = self._factories[name]
                try:
                    instance = factory()
                    # Register the instantiated service
                    self._services[name] = ServiceInfo(
                        name=name,
                        service_type=type(instance).__name__,
                        instance=instance,
                        initialized=True,
                        started=False,
                    )
                    del self._factories[name]
                    self._logger.debug(f"Lazily instantiated service: {name}")
                    return instance
                except Exception as e:
                    self._logger.error(f"Failed to instantiate service {name}: {e}")
                    return None

            return None

    def get_or_raise(self, name: str) -> Any:
        """Get a service by name or raise an error."""
        service = self.get(name)
        if service is None:
            raise AstraError(f"Service not found: {name}")
        return service

    def has_service(self, name: str) -> bool:
        """Check if a service is registered."""
        with self._lock:
            return name in self._services or name in self._factories

    def start_service(self, name: str):
        """Start a service (call its start method if available)."""
        with self._lock:
            if name not in self._services:
                raise AstraError(f"Service not found: {name}")

            info = self._services[name]
            if info.started:
                return

            instance = info.instance
            if hasattr(instance, "start") and callable(instance.start):
                instance.start()

            info.started = True
            self._logger.info(f"Started service: {name}")

    def stop_service(self, name: str):
        """Stop a service (call its stop method if available)."""
        with self._lock:
            if name not in self._services:
                raise AstraError(f"Service not found: {name}")

            info = self._services[name]
            if not info.started:
                return

            instance = info.instance
            if hasattr(instance, "stop") and callable(instance.stop):
                instance.stop()

            info.started = False
            self._logger.info(f"Stopped service: {name}")

    def start_all(self):
        """Start all registered services."""
        with self._lock:
            # Start services in dependency order
            started = set()
            for name, info in self._services.items():
                self._start_with_deps(name, started)

    def _start_with_deps(self, name: str, started: set):
        """Start a service after starting its dependencies."""
        if name in started:
            return

        info = self._services.get(name)
        if info is None:
            return

        # Start dependencies first
        for dep in info.dependencies:
            self._start_with_deps(dep, started)

        self.start_service(name)
        started.add(name)

    def stop_all(self):
        """Stop all registered services (reverse order)."""
        with self._lock:
            for name in reversed(list(self._services.keys())):
                self.stop_service(name)

    def unregister(self, name: str):
        """Unregister a service."""
        with self._lock:
            if name in self._services:
                # Stop first if running
                if self._services[name].started:
                    self.stop_service(name)
                del self._services[name]
                self._logger.debug(f"Unregistered service: {name}")

            if name in self._factories:
                del self._factories[name]

    def get_all_services(self) -> Dict[str, ServiceInfo]:
        """Get all registered services."""
        with self._lock:
            return dict(self._services)

    def get_service_names(self) -> List[str]:
        """Get list of all service names."""
        with self._lock:
            return list(self._services.keys())

    def clear(self):
        """Clear all services (stop and unregister)."""
        self.stop_all()
        with self._lock:
            self._services.clear()
            self._factories.clear()
            self._logger.debug("Cleared all services")
