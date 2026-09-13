"""ASTRA Core threading and authority management."""

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Set
import weakref

from astra.core.exceptions import AuthorityError
from astra.core.logging import get_logger


@dataclass
class AuthorityToken:
    """Token proving authority to mutate simulation state."""

    thread_id: int
    context_id: str
    granted_operations: Set[str] = field(default_factory=set)

    def can_perform(self, operation: str) -> bool:
        """Check if this token grants permission for the given operation."""
        return not self.granted_operations or operation in self.granted_operations


class AuthorityContext:
    """Context manager for acquiring mutation authority."""

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
        """Check if the current context has authority for the given operation."""
        token = cls.get_current_token()
        return token is not None and token.can_perform(operation)

    @classmethod
    def require_authority(cls, operation: str):
        """Require authority for the given operation or raise an error."""
        if not cls.has_authority(operation):
            token = cls.get_current_token()
            details = {
                "operation": operation,
                "has_token": token is not None,
                "thread_id": threading.current_thread().ident,
            }
            if token:
                details["granted_operations"] = list(token.granted_operations)
            raise AuthorityError(
                f"Operation '{operation}' requires authority",
                operation=operation,
                context=details,
            )


class SimulationThread:
    """Manages the authoritative simulation thread."""

    def __init__(self, name: str = "SimulationThread"):
        self.name = name
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        self._pause_condition = threading.Condition(self._lock)
        self._logger = get_logger("simulation_thread")
        self._tasks: list = []
        self._sim_thread_id: Optional[int] = None

    def start(self, target: Callable[[], Any]):
        """Start the simulation thread."""
        with self._lock:
            if self._running:
                raise RuntimeError("Simulation thread already running")

            def wrapper():
                self._sim_thread_id = threading.current_thread().ident
                self._logger.info(f"Simulation thread started with ID {self._sim_thread_id}")
                target()

            self._thread = threading.Thread(target=wrapper, name=self.name)
            self._running = True
            self._paused = False
            self._thread.start()

    def stop(self):
        """Stop the simulation thread."""
        with self._lock:
            self._running = False
            self._pause_condition.notify_all()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        self._logger.info("Simulation thread stopped")

    def pause(self):
        """Pause the simulation thread (called from within the thread)."""
        with self._pause_condition:
            self._paused = True
            while self._paused and self._running:
                self._pause_condition.wait()

    def resume(self):
        """Resume the simulation thread."""
        with self._pause_condition:
            self._paused = False
            self._pause_condition.notify_all()
        self._logger.debug("Simulation thread resumed")

    def is_running(self) -> bool:
        """Check if the simulation thread is running."""
        return self._running and (self._thread is None or self._thread.is_alive())

    def is_paused(self) -> bool:
        """Check if the simulation thread is paused."""
        return self._paused

    def is_simulation_thread(self) -> bool:
        """Check if the current thread is the simulation thread."""
        current_id = threading.current_thread().ident
        return current_id == self._sim_thread_id

    def require_simulation_thread(self, operation: str):
        """Require that the current thread is the simulation thread."""
        if not self.is_simulation_thread():
            raise AuthorityError(
                f"Operation '{operation}' must be performed on the simulation thread",
                operation=operation,
                context={
                    "current_thread": threading.current_thread().name,
                    "simulation_thread": self.name,
                },
            )
