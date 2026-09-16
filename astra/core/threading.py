"""ASTRA Core threading and authority management.

This module implements a single authoritative simulation-thread model.
Only the registered simulation thread can obtain authority to mutate
simulation state.
"""

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, Set
from enum import Enum
import weakref
import time as time_module

from astra.core.exceptions import AuthorityError, AstraError
from astra.core.logging import get_logger


class SimulationThreadState(Enum):
    """Simulation thread lifecycle states."""
    
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


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
                    cls._instance._registration_count = 0
                    cls._instance._shutdown = False
                    cls._instance._registry_lock = threading.Lock()
        return cls._instance
    
    def register_simulation_thread(self, thread_id: int):
        """Register a thread as the authoritative simulation thread."""
        with self._registry_lock:
            if self._shutdown:
                raise AuthorityError(
                    "Simulation thread registry has been shut down",
                    operation="register_simulation_thread",
                )
            if self._sim_thread_id is not None and self._sim_thread_id != thread_id:
                raise AuthorityError(
                    "Simulation thread already registered to different thread",
                    operation="register_simulation_thread",
                    context={
                        "existing_thread_id": self._sim_thread_id,
                        "new_thread_id": thread_id,
                    }
                )
            self._sim_thread_id = thread_id
            self._registration_count += 1
    
    def unregister_simulation_thread(self, thread_id: int):
        """Unregister the simulation thread."""
        with self._registry_lock:
            if self._sim_thread_id != thread_id:
                return
            self._registration_count = max(0, self._registration_count - 1)
            if self._registration_count == 0:
                self._sim_thread_id = None
    
    def is_simulation_thread(self, thread_id: Optional[int] = None) -> bool:
        """Check if the given thread ID is the registered simulation thread.
        
        If thread_id is None, uses the current thread's ID.
        """
        if thread_id is None:
            thread_id = threading.current_thread().ident
        with self._registry_lock:
            return self._sim_thread_id is not None and self._sim_thread_id == thread_id
    
    def get_simulation_thread_id(self) -> Optional[int]:
        """Get the registered simulation thread ID."""
        with self._registry_lock:
            return self._sim_thread_id
    
    def is_registered(self) -> bool:
        """Check if a simulation thread is registered."""
        with self._registry_lock:
            return self._sim_thread_id is not None
    
    def shutdown(self):
        """Mark the registry as shut down."""
        with self._registry_lock:
            self._shutdown = True
            self._registration_count = 0
            self._sim_thread_id = None
    
    def reset(self):
        """Reset the registry (for testing only)."""
        with self._registry_lock:
            self._sim_thread_id = None
            self._registration_count = 0
            self._shutdown = False


# Global singleton instance
_sim_thread_registry = SimulationThreadRegistry()


class SimulationThread:
    """The authoritative simulation thread.
    
    This class owns and manages the actual Python thread that performs
    authoritative simulation mutations. It registers its thread identity
    with the SimulationThreadRegistry upon startup and unregisters upon
    shutdown.
    """
    
    def __init__(self, name: str = "ASTRA_Simulation"):
        self._name = name
        self._state = SimulationThreadState.CREATED
        self._thread: Optional[threading.Thread] = None
        self._logger = get_logger("sim_thread")
        self._lock = threading.Lock()
        self._work_queue: list = []
        self._work_available = threading.Event()
        self._stop_requested = False
        self._registry = _sim_thread_registry
    
    @property
    def name(self) -> str:
        """Get the thread name."""
        return self._name
    
    @property
    def state(self) -> SimulationThreadState:
        """Get the current thread state."""
        return self._state
    
    @property
    def thread_id(self) -> Optional[int]:
        """Get the underlying thread's ID (None if not started)."""
        if self._thread and self._thread.ident:
            return self._thread.ident
        return None
    
    def start(self):
        """Start the simulation thread."""
        with self._lock:
            if self._state != SimulationThreadState.CREATED:
                raise AstraError(
                    f"Cannot start simulation thread from state: {self._state.value}"
                )
            
            self._state = SimulationThreadState.STARTING
            self._stop_requested = False
            self._thread = threading.Thread(target=self._run_loop, name=self._name)
            self._thread.daemon = True
            self._thread.start()
            
            # Wait briefly for thread to register itself
            self._work_available.wait(timeout=5.0)
            
            if self._state != SimulationThreadState.RUNNING:
                raise AstraError("Simulation thread failed to start properly")
            
            self._logger.info(f"Simulation thread '{self._name}' started with ID {self._thread.ident}")
    
    def _run_loop(self):
        """Main loop running on the simulation thread."""
        try:
            # Register this thread as the authoritative simulation thread
            thread_id = threading.current_thread().ident
            if thread_id is None:
                raise AuthorityError("Cannot determine thread identity", "simulation_thread_start")
            
            self._registry.register_simulation_thread(thread_id)
            self._state = SimulationThreadState.RUNNING
            self._work_available.set()  # Signal that we're ready
            
            self._logger.debug(f"Simulation thread registered with ID {thread_id}")
            
            while not self._stop_requested:
                # Process any pending work
                work_items = []
                with self._lock:
                    if self._work_queue:
                        work_items = self._work_queue[:]
                        self._work_queue.clear()
                
                for work_func, result_holder in work_items:
                    try:
                        result = work_func()
                        if result_holder is not None:
                            result_holder.append(result)
                    except Exception as e:
                        self._logger.error(f"Work item failed: {e}")
                        if result_holder is not None:
                            result_holder.append(e)
                
                # Small sleep to prevent busy-waiting
                self._work_available.wait(timeout=0.001)
                self._work_available.clear()
            
        except Exception as e:
            self._logger.error(f"Simulation thread error: {e}")
            self._state = SimulationThreadState.STOPPED
            raise
        finally:
            # Unregister on exit
            try:
                thread_id = threading.current_thread().ident
                if thread_id:
                    self._registry.unregister_simulation_thread(thread_id)
            except Exception:
                pass
    
    def execute(self, work_func: Callable[[], Any], timeout: Optional[float] = None) -> Any:
        """Execute a function on the simulation thread.
        
        This is used to marshal work onto the authoritative thread.
        """
        if self._state != SimulationThreadState.RUNNING:
            raise AstraError(
                f"Cannot execute work: simulation thread is {self._state.value}"
            )
        
        result_holder: list = []
        with self._lock:
            self._work_queue.append((work_func, result_holder))
            self._work_available.set()
        
        # Wait for result
        start_time = time_module.time()
        while not result_holder:
            if timeout and (time_module.time() - start_time) > timeout:
                raise AstraError(f"Work execution timed out after {timeout}s")
            time_module.sleep(0.001)
        
        result = result_holder[0]
        if isinstance(result, Exception):
            raise result
        return result
    
    def stop(self, timeout: Optional[float] = 5.0):
        """Stop the simulation thread."""
        with self._lock:
            if self._state not in (SimulationThreadState.RUNNING, SimulationThreadState.STARTING):
                return
            
            self._state = SimulationThreadState.STOPPING
            self._stop_requested = True
            self._work_available.set()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        
        self._state = SimulationThreadState.STOPPED
        self._logger.info(f"Simulation thread '{self._name}' stopped")
    
    def is_alive(self) -> bool:
        """Check if the underlying thread is alive."""
        return self._thread is not None and self._thread.is_alive()


class AuthorityContext:
    """Context manager for acquiring mutation authority.
    
    Authority is ONLY granted to the registered simulation thread.
    Attempting to enter an AuthorityContext from any other thread
    will raise an AuthorityError.
    """

    _token_stack: threading.local = threading.local()

    @classmethod
    def _stack(cls) -> list:
        """Get or create the per-thread token stack."""
        stack = getattr(cls._token_stack, "stack", None)
        if stack is None:
            stack = []
            cls._token_stack.stack = stack
        return stack

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
        self._stack().append(self.token)
        self._logger.debug(f"Authority granted for {self.operation}", context_id=self.token.context_id)
        return self.token

    def __exit__(self, exc_type, exc_val, exc_tb):
        st = self._stack()
        if st:
            st.pop()
        self._logger.debug(f"Authority released for {self.operation}")
        return False

    @classmethod
    def get_current_token(cls) -> Optional[AuthorityToken]:
        """Get the current authority token for this thread."""
        st = cls._stack()
        return st[-1] if st else None

    @classmethod
    def has_authority(cls, operation: str) -> bool:
        """Check if the current context has authority for the given operation.
        
        This verifies BOTH that we have a token, that the token belongs to the
        executing thread, AND that the executing thread is the registered simulation thread.
        """
        token = cls.get_current_token()
        if token is None:
            return False
        current_thread_id = threading.current_thread().ident
        if token.thread_id != current_thread_id:
            return False
        # Double-check thread registration
        if not _sim_thread_registry.is_simulation_thread(current_thread_id):
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
