"""ASTRA Core threading and authority management.

This module implements a single authoritative simulation-thread model.
Only the registered simulation thread can obtain authority to mutate
simulation state.
"""

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Set
import weakref

from astra.core.exceptions import AuthorityError
from astra.core.logging import get_logger


@dataclass
class AuthorityToken:
    """Token proving authority to mutate simulation state.
    
    Authority is granted ONLY to the registered simulation thread.
    """

    thread_id: int
    context_id: str
    granted_operations: Set[str] = field(default_factory=set)

    def can_perform(self, operation: str) -> bool:
        """Check if this token grants permission for the given operation."""
        return not self.granted_operations or operation in self.granted_operations


class SimulationThreadRegistry:
    """Central registry for the authoritative simulation thread.
    
    This class maintains the identity of the single authoritative
    simulation thread. Authority checks consult this registry.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sim_thread_id: Optional[int] = None
                    cls._instance._registered = False
                    cls._instance._shutdown = False
                    cls._instance._registry_lock = threading.Lock()
        return cls._instance
    
    def register_simulation_thread(self, thread_id: int):
        """Register a thread as the authoritative simulation thread."""
        with self._registry_lock:
            if self._registered and self._sim_thread_id != thread_id:
                raise AuthorityError(
                    "Simulation thread already registered to different thread",
                    operation="register_simulation_thread",
                    context={
                        "existing_thread_id": self._sim_thread_id,
                        "new_thread_id": thread_id,
                    }
                )
            if self._shutdown:
                raise AuthorityError(
                    "Simulation thread registry has been shut down",
                    operation="register_simulation_thread",
                )
            self._sim_thread_id = thread_id
            self._registered = True
    
    def unregister_simulation_thread(self, thread_id: int):
        """Unregister the simulation thread."""
        with self._registry_lock:
            if self._sim_thread_id == thread_id:
                self._sim_thread_id = None
                self._registered = False
    
    def is_simulation_thread(self, thread_id: Optional[int] = None) -> bool:
        """Check if the given thread ID is the registered simulation thread.
        
        If thread_id is None, uses the current thread's ID.
        """
        if thread_id is None:
            thread_id = threading.current_thread().ident
        with self._registry_lock:
            return self._registered and self._sim_thread_id == thread_id
    
    def get_simulation_thread_id(self) -> Optional[int]:
        """Get the registered simulation thread ID."""
        with self._registry_lock:
            return self._sim_thread_id
    
    def is_registered(self) -> bool:
        """Check if a simulation thread is registered."""
        with self._registry_lock:
            return self._registered
    
    def shutdown(self):
        """Mark the registry as shut down."""
        with self._registry_lock:
            self._shutdown = True
            self._registered = False
            self._sim_thread_id = None
    
    def reset(self):
        """Reset the registry (for testing only)."""
        with self._registry_lock:
            self._sim_thread_id = None
            self._registered = False
            self._shutdown = False


# Global singleton instance
_sim_thread_registry = SimulationThreadRegistry()


class AuthorityContext:
    """Context manager for acquiring mutation authority.
    
    Authority is ONLY granted to the registered simulation thread.
    Attempting to enter an AuthorityContext from any other thread
    will raise an AuthorityError.
    """

    _current_token: threading.local = threading.local()

    def __init__(
        self,
        operation: str,
        granted_operations: Optional[Set[str]] = None,
    ):
        self.operation = operation
        self.granted_operations = granted_operations or set()
        self.token: Optional[AuthorityToken] = None
        self._logger = get_logger("authority")

    def __enter__(self) -> AuthorityToken:
        thread_id = threading.current_thread().ident
        if thread_id is None:
            raise AuthorityError("Cannot determine thread identity", self.operation)
        
        # CRITICAL: Verify this is the registered simulation thread
        if not _sim_thread_registry.is_simulation_thread(thread_id):
            reg_thread_id = _sim_thread_registry.get_simulation_thread_id()
            raise AuthorityError(
                f"Authority denied: thread {thread_id} is not the registered simulation thread",
                operation=self.operation,
                context={
                    "current_thread_id": thread_id,
                    "registered_simulation_thread_id": reg_thread_id,
                    "is_registered": _sim_thread_registry.is_registered(),
                }
            )

        self.token = AuthorityToken(
            thread_id=thread_id,
            context_id=f"{thread_id}_{id(self)}",
            granted_operations=self.granted_operations.copy() if self.granted_operations else set(),
        )
        AuthorityContext._current_token.value = self.token
        self._logger.debug(f"Authority granted for {self.operation}", context_id=self.token.context_id)
        return self.token

    def __exit__(self, exc_type, exc_val, exc_tb):
        AuthorityContext._current_token.value = None
        self._logger.debug(f"Authority released for {self.operation}")
        return False

    @classmethod
    def get_current_token(cls) -> Optional[AuthorityToken]:
        """Get the current authority token for this thread."""
        return getattr(cls._current_token, "value", None)

    @classmethod
    def has_authority(cls, operation: str) -> bool:
        """Check if the current context has authority for the given operation.
        
        This verifies BOTH that we have a token AND that the current thread
        is the registered simulation thread.
        """
        token = cls.get_current_token()
        if token is None:
            return False
        # Double-check thread registration
        if not _sim_thread_registry.is_simulation_thread(token.thread_id):
            return False
        return token.can_perform(operation)

    @classmethod
    def require_authority(cls, operation: str):
        """Require authority for the given operation or raise an error."""
        if not cls.has_authority(operation):
            token = cls.get_current_token()
            details = {
                "operation": operation,
                "has_token": token is not None,
                "thread_id": threading.current_thread().ident,
                "is_simulation_thread": _sim_thread_registry.is_simulation_thread(),
            }
            if token:
                details["granted_operations"] = list(token.granted_operations)
            raise AuthorityError(
                f"Operation '{operation}' requires authority from simulation thread",
                operation=operation,
                context=details,
            )


def get_simulation_thread_registry() -> SimulationThreadRegistry:
    """Get the global simulation thread registry."""
    return _sim_thread_registry


def reset_simulation_thread_registry():
    """Reset the simulation thread registry (for testing only)."""
    _sim_thread_registry.reset()
