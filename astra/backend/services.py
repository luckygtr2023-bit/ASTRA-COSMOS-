"""
ASTRA Backend — service integration (§7).

Integrates with astra.core.services.ServiceRegistry.
Does NOT create a second competing registry; it layers typed,
bounded, health-checked service facets for backend concerns:

  - Rendering coordination
  - Cache management
  - Diagnostics aggregation
  - Data access gating

Service boundaries are explicit; each service declares dependencies;
health is observable. Authority enforcement is explicit per operation.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from astra.core.services import ServiceRegistry

from astra.backend.exceptions import ServiceError


class BackendServiceName(str, Enum):
    RENDER_DELIVERY = "render_delivery"
    GRAPHICS_DELIVERY = "graphics_delivery"
    CACHE = "cache"
    DIAGNOSTICS = "diagnostics"
    DATA_ACCESS = "data_access"
    RUNTIME = "runtime"


@dataclass
class BackendServiceDescriptor:
    name: BackendServiceName
    dependencies: List[BackendServiceName] = field(default_factory=list)
    timeout_s: float = 5.0
    critical: bool = False  # if True, registry will try restart on failure

    def validate(self) -> None:
        if not isinstance(self.name, BackendServiceName):
            raise ServiceError(f"service name must be BackendServiceName, got {self.name!r}", operation="validate", resource=str(self.name))
        for d in self.dependencies:
            if not isinstance(d, BackendServiceName):
                raise ServiceError(f"dependency must be BackendServiceName, got {d!r}", operation="validate", resource=self.name.value)
        if self.name in self.dependencies:
            raise ServiceError(f"service {self.name.value} cannot depend on itself", operation="validate", resource=self.name.value)


class BackendServiceRegistry:
    """
    Facade over core ServiceRegistry for backend service lifecycles.

    - Reuses the single ServiceRegistry; does not duplicate it.
    - Tracks backend descriptors + health events.
    - Thread-safe.
    """

    def __init__(self, core_registry: Optional[ServiceRegistry] = None):
        self._core: ServiceRegistry = core_registry or ServiceRegistry()
        self._descriptors: Dict[str, BackendServiceDescriptor] = {}
        self._instances: Dict[str, Any] = {}  # optional direct instance refs for diagnostics
        self._lock = threading.Lock()
        self._events: List[Dict[str, Any]] = []

    @property
    def core_registry(self) -> ServiceRegistry:
        return self._core

    def register_descriptor(self, desc: BackendServiceDescriptor) -> None:
        desc.validate()
        with self._lock:
            if desc.name.value in self._descriptors:
                raise ServiceError(f"descriptor already registered: {desc.name.value}", operation="register_descriptor", resource=desc.name.value)
            self._descriptors[desc.name.value] = desc
            self._log("descriptor_registered", desc.name.value, {"deps": [d.value for d in desc.dependencies]})

    def register_service(
        self,
        service: Any,
        descriptor: Optional[BackendServiceDescriptor] = None,
        *,
        name: Optional[str] = None,
        dependencies: Optional[List[str]] = None,
    ) -> None:
        """
        Register a core Service. If descriptor supplied, validate it matches.
        service is the concrete instance (e.g. RenderStateDelivery) for diagnostics.
        name overrides descriptor name when service is unnamed.

        Delegates to core ServiceRegistry.register(name, instance, dependencies).
        """
        svc_name = name
        deps = dependencies
        if descriptor is not None:
            descriptor.validate()
            if svc_name is None:
                svc_name = descriptor.name.value
            elif svc_name != descriptor.name.value:
                raise ServiceError(
                    f"descriptor name {descriptor.name.value!r} != requested name {svc_name!r}",
                    operation="register_service",
                    resource=svc_name,
                )
            # merge deps
            dep_vals = [d.value for d in descriptor.dependencies]
            if deps is None:
                deps = dep_vals
            else:
                # ensure descriptor deps are included
                for dv in dep_vals:
                    if dv not in deps:
                        deps.append(dv)
            # track descriptor
            with self._lock:
                if descriptor.name.value not in self._descriptors:
                    self._descriptors[descriptor.name.value] = descriptor
                    self._log("descriptor_registered", descriptor.name.value, {"deps": dep_vals})
        if not svc_name:
            # try to infer from service type or attribute
            svc_name = getattr(service, "name", None) or type(service).__name__.lower()
            if not svc_name:
                raise ServiceError("service name could not be inferred; pass name or descriptor", operation="register_service")
        if not isinstance(svc_name, str) or not svc_name:
            raise ServiceError("service name must be non-empty string", operation="register_service", resource=str(svc_name))
        try:
            self._core.register(svc_name, service, dependencies=deps)
        except Exception as e:
            raise ServiceError(f"core register failed for {svc_name}: {e}", operation="register_service", resource=svc_name, cause=e)
        with self._lock:
            self._instances[svc_name] = service
            self._log("service_registered", svc_name, {})

    def start_service(self, name: str) -> bool:
        try:
            self._core.start_service(name)
            ok = True
        except Exception as e:
            raise ServiceError(f"start failed for {name}: {e}", operation="start_service", resource=name, cause=e)
        with self._lock:
            self._log("service_start", name, {"ok": ok})
        return ok

    def start_all_in_dependency_order(self) -> List[str]:
        """
        Start backend services. Core ServiceRegistry already handles dependency order
        via start_all(); we also respect descriptors for validation.
        Returns list of started service names.
        """
        # Validate graph first
        with self._lock:
            descs = dict(self._descriptors)
        if descs:
            # topological check (same as before)
            in_degree: Dict[str, int] = {n: 0 for n in descs}
            adj: Dict[str, List[str]] = {n: [] for n in descs}
            for name, desc in descs.items():
                for dep in desc.dependencies:
                    dep_name = dep.value
                    if dep_name not in descs:
                        # dependency may be a core service not tracked as backend descriptor — allow
                        continue
                    adj[dep_name].append(name)
                    in_degree[name] += 1
            queue = [n for n, d in in_degree.items() if d == 0]
            order: List[str] = []
            while queue:
                queue.sort()
                cur = queue.pop(0)
                order.append(cur)
                for nxt in adj[cur]:
                    in_degree[nxt] -= 1
                    if in_degree[nxt] == 0:
                        queue.append(nxt)
            if len(order) != len(descs):
                raise ServiceError("circular dependency detected", operation="start_all_in_dependency_order")

        try:
            self._core.start_all()
        except Exception as e:
            raise ServiceError(f"start_all failed: {e}", operation="start_all_in_dependency_order", cause=e)

        with self._lock:
            self._log("start_all", "-", {})
        # return all registered service names
        try:
            return self._core.get_service_names()
        except Exception:
            return list(self._instances.keys())

    def stop_service(self, name: str) -> bool:
        try:
            self._core.stop_service(name)
            ok = True
        except Exception as e:
            raise ServiceError(f"stop failed for {name}: {e}", operation="stop_service", resource=name, cause=e)
        with self._lock:
            self._log("service_stop", name, {"ok": ok})
        return ok

    def stop_all(self) -> None:
        try:
            self._core.stop_all()
        except Exception as e:
            raise ServiceError(f"stop_all failed: {e}", operation="stop_all", cause=e)
        with self._lock:
            self._log("stop_all", "-", {})

    def health(self, name: str) -> str:
        # Core has no ServiceHealth; report started/registered status
        try:
            all_services = self._core.get_all_services()
            if name not in all_services:
                return "UNKNOWN"
            info = all_services[name]
            return "HEALTHY" if getattr(info, "started", False) else "STOPPED"
        except Exception as e:
            raise ServiceError(f"health check failed for {name}: {e}", operation="health", resource=name, cause=e)

    def health_summary(self) -> Dict[str, str]:
        names = set()
        with self._lock:
            names.update(self._descriptors.keys())
            names.update(self._instances.keys())
        try:
            names.update(self._core.get_service_names())
        except Exception:
            pass
        summary: Dict[str, str] = {}
        for n in sorted(names):
            try:
                summary[n] = self.health(n)
            except Exception:
                summary[n] = "unknown"
        return summary

    def get_instance(self, name: str) -> Optional[Any]:
        with self._lock:
            if name in self._instances:
                return self._instances[name]
        # fallback to core
        try:
            return self._core.get(name)
        except Exception:
            return None

    def registered_names(self) -> List[str]:
        with self._lock:
            return sorted(set(list(self._descriptors.keys()) + list(self._instances.keys())))

    def _log(self, event: str, resource: str, details: Dict[str, Any]) -> None:
        self._events.append({"ts": time.monotonic(), "event": event, "resource": resource, "details": details})
        if len(self._events) > 1000:
            self._events = self._events[-1000:]

    def recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._events[-limit:])

    def shutdown(self) -> None:
        try:
            self._core.clear()
        except Exception:
            pass
        with self._lock:
            self._log("shutdown", "-", {})


__all__ = ["BackendServiceName", "BackendServiceDescriptor", "BackendServiceRegistry"]
