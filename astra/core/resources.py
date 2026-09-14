"""ASTRA Core resource management system."""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, Set, TypeVar, Generic
import threading
import weakref

from astra.core.logging import get_logger
from astra.core.exceptions import ResourceError
from astra.core.threading import AuthorityContext, get_simulation_thread_registry


T = TypeVar("T")


@dataclass
class ResourceInfo:
    """Information about a registered resource."""

    id: str
    name: str
    resource_type: str
    ref_count: int = 0
    acquired_by: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResourceHandle(Generic[T]):
    """A handle to a managed resource with reference counting."""

    def __init__(self, resource_id: str, manager: "ResourceManager"):
        self._resource_id = resource_id
        self._manager = weakref.ref(manager)
        self._valid = True
        self._logger = get_logger(f"resource.handle.{resource_id}")

    @property
    def resource_id(self) -> str:
        return self._resource_id

    @property
    def is_valid(self) -> bool:
        return self._valid

    def acquire(self, owner: str = "") -> T:
        """Acquire the resource for use."""
        if not self._valid:
            raise ResourceError(
                f"Cannot acquire invalid handle",
                resource_id=self._resource_id,
                operation="acquire",
            )

        manager = self._manager()
        if manager is None:
            raise ResourceError(
                f"Resource manager no longer exists",
                resource_id=self._resource_id,
                operation="acquire",
            )

        return manager._acquire_resource(self._resource_id, owner)

    def release(self, owner: str = ""):
        """Release the resource."""
        if not self._valid:
            raise ResourceError(
                f"Cannot release invalid handle",
                resource_id=self._resource_id,
                operation="release",
            )

        manager = self._manager()
        if manager is not None:
            manager._release_resource(self._resource_id, owner)

    def invalidate(self):
        """Invalidate this handle."""
        self._valid = False

    def __enter__(self) -> T:
        return self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class ResourceManager:
    """Manages resources with reference counting and lifecycle tracking."""

    def __init__(self, max_handles: int = 10000):
        self._resources: Dict[str, ResourceInfo] = {}
        self._actual_resources: Dict[str, Any] = {}
        self._max_handles = max_handles
        self._handle_counter = 0
        self._lock = threading.RLock()
        self._logger = get_logger("resource_manager")
        self._cleanup_interval = 100
        self._ticks_since_cleanup = 0
        self._registry = get_simulation_thread_registry()

    def _require_authority_if_needed(self, operation: str):
        # Enforce simulation thread identity if registry is active, similar to EntityManager
        if self._registry.is_registered() and not self._registry.is_simulation_thread():
            from astra.core.exceptions import AuthorityError
            import threading
            raise AuthorityError(
                f"Operation '{operation}' requires simulation thread",
                operation=operation,
                context={
                    "current_thread_id": threading.current_thread().ident,
                    "registered_thread_id": self._registry.get_simulation_thread_id(),
                },
            )

    def register(
        self,
        resource: Any,
        name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        require_authority: bool = False,
    ) -> ResourceHandle:
        """Register a new resource and return a handle."""
        if require_authority:
            AuthorityContext.require_authority("resource.register")
        else:
            self._require_authority_if_needed("resource.register")
        with self._lock:
            if len(self._resources) >= self._max_handles:
                raise ResourceError(
                    f"Maximum resource handles ({self._max_handles}) exceeded",
                    operation="register",
                )

            self._handle_counter += 1
            resource_id = f"resource_{self._handle_counter:08d}"

            info = ResourceInfo(
                id=resource_id,
                name=name or resource_id,
                resource_type=type(resource).__name__,
                metadata=metadata or {},
            )

            self._resources[resource_id] = info
            self._actual_resources[resource_id] = resource
            self._logger.debug(f"Registered resource: {resource_id} ({info.name})")

            return ResourceHandle(resource_id, self)

    def unregister(self, resource_id: str, force: bool = False, require_authority: bool = False):
        """Unregister a resource."""
        if require_authority:
            AuthorityContext.require_authority("resource.unregister")
        else:
            self._require_authority_if_needed("resource.unregister")
        with self._lock:
            if resource_id not in self._resources:
                raise ResourceError(
                    f"Resource not found: {resource_id}",
                    resource_id=resource_id,
                    operation="unregister",
                )

            info = self._resources[resource_id]
            if info.ref_count > 0 and not force:
                raise ResourceError(
                    f"Cannot unregister resource with active references (ref_count={info.ref_count})",
                    resource_id=resource_id,
                    operation="unregister",
                    context={"ref_count": info.ref_count},
                )

            del self._resources[resource_id]
            del self._actual_resources[resource_id]
            self._logger.debug(f"Unregistered resource: {resource_id}")

    def _acquire_resource(self, resource_id: str, owner: str = "") -> Any:
        """Internal method to acquire a resource."""
        with self._lock:
            if resource_id not in self._resources:
                raise ResourceError(
                    f"Resource not found: {resource_id}",
                    resource_id=resource_id,
                    operation="acquire",
                )

            info = self._resources[resource_id]
            info.ref_count += 1
            if owner:
                info.acquired_by.add(owner)

            self._logger.debug(
                f"Acquired resource: {resource_id} (ref_count={info.ref_count}, owner={owner})"
            )

            return self._actual_resources[resource_id]

    def _release_resource(self, resource_id: str, owner: str = ""):
        """Internal method to release a resource."""
        with self._lock:
            if resource_id not in self._resources:
                raise ResourceError(
                    f"Resource not found: {resource_id}",
                    resource_id=resource_id,
                    operation="release",
                )

            info = self._resources[resource_id]
            if info.ref_count <= 0:
                raise ResourceError(
                    f"Double release detected for resource: {resource_id}",
                    resource_id=resource_id,
                    operation="release",
                    context={"ref_count": info.ref_count},
                )

            info.ref_count -= 1
            if owner and owner in info.acquired_by:
                info.acquired_by.remove(owner)

            self._logger.debug(
                f"Released resource: {resource_id} (ref_count={info.ref_count})"
            )

    def get_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """Get information about a resource."""
        return self._resources.get(resource_id)

    def get_resource(self, resource_id: str) -> Optional[Any]:
        """Get the actual resource by ID."""
        return self._actual_resources.get(resource_id)

    def get_all_resources(self) -> Dict[str, ResourceInfo]:
        """Get all registered resources (read-only view)."""
        with self._lock:
            return dict(self._resources)

    def get_orphaned_resources(self) -> list:
        """Get resources with zero references."""
        with self._lock:
            return [
                info for info in self._resources.values()
                if info.ref_count == 0
            ]

    def cleanup_orphans(self):
        """Clean up orphaned resources (zero ref count)."""
        with self._lock:
            orphans = [
                rid for rid, info in self._resources.items()
                if info.ref_count == 0
            ]
            for rid in orphans:
                self._logger.debug(f"Cleaning up orphaned resource: {rid}")
                # Note: We don't automatically delete - caller must call unregister

    def tick(self):
        """Called each simulation tick for periodic cleanup."""
        self._ticks_since_cleanup += 1
        if self._ticks_since_cleanup >= self._cleanup_interval:
            self._ticks_since_cleanup = 0
            self.cleanup_orphans()

    def get_total_ref_count(self) -> int:
        """Get total reference count across all resources."""
        with self._lock:
            return sum(info.ref_count for info in self._resources.values())

    def get_stats(self) -> Dict[str, Any]:
        """Get resource management statistics."""
        with self._lock:
            return {
                "total_resources": len(self._resources),
                "total_references": sum(info.ref_count for info in self._resources.values()),
                "orphaned_resources": sum(1 for info in self._resources.values() if info.ref_count == 0),
                "max_handles": self._max_handles,
            }

    def clear(self, require_authority: bool = False):
        """Clear all resources (force unregister)."""
        if require_authority:
            AuthorityContext.require_authority("resource.clear")
        else:
            # Allow clear during engine reset even without explicit flag if on sim thread
            # Only enforce when registry active and not sim thread
            self._require_authority_if_needed("resource.clear")
        with self._lock:
            self._resources.clear()
            self._actual_resources.clear()
            self._handle_counter = 0
            self._logger.debug("Cleared all resources")
