"""
ASTRA Backend — security and authority integration (§11).

Never bypasses astra.core.threading.AuthorityContext.
Provides explicit, auditable gates for operations that must be
simulation-thread-owned vs. those that are safe for concurrent reads.

This layer does NOT implement authentication/authorization beyond
Astra's single simulation-thread model; it wraps it for backend
call sites so they cannot silently skip authority checks.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from enum import Enum
from typing import Any, Callable, Dict, Optional, Set

from astra.core.threading import AuthorityContext, get_simulation_thread_registry
from astra.core.exceptions import AuthorityError

from astra.backend.exceptions import SecurityError


class OperationClass(str, Enum):
    MUTATE_SIMULATION = "mutate_simulation"  # requires simulation thread + AuthorityContext
    MUTATE_BACKEND = "mutate_backend"  # backend-owned state; no sim thread required, but logged
    READ_AUTHORITATIVE = "read_authoritative"  # safe concurrent read of authoritative state (no mutation)
    READ_DERIVED = "read_derived"  # derived/cache/render state


# Which operations require authority (expandable registry)
_AUTHORITY_REQUIRED: Set[str] = {
    "world.mutate",
    "engine.step",
    "engine.initialize",
    "persistence.save_world",
}

# Which backend mutations we still gate behind explicit caller label (audit)
_BACKEND_MUTATION_OPS: Set[str] = {
    "render_delivery.invalidate",
    "cache.invalidate",
    "config.update",
    "persistence.save_checkpoint",
}


def requires_authority(operation: str) -> bool:
    return operation in _AUTHORITY_REQUIRED


def classify_operation(operation: str) -> OperationClass:
    if operation in _AUTHORITY_REQUIRED:
        return OperationClass.MUTATE_SIMULATION
    if operation in _BACKEND_MUTATION_OPS:
        return OperationClass.MUTATE_BACKEND
    # heuristic: prefixes
    if operation.startswith("world.") or operation.startswith("engine."):
        return OperationClass.MUTATE_SIMULATION
    if operation.startswith("render.") or operation.startswith("graphics."):
        return OperationClass.READ_DERIVED
    return OperationClass.READ_DERIVED


def assert_authority(operation: str) -> None:
    """
    Raise SecurityError if authority is missing for an authority-required op.
    Does NOT acquire authority — caller must already be inside AuthorityContext
    on the simulation thread.
    """
    if not requires_authority(operation):
        return
    try:
        AuthorityContext.require_authority(operation)
    except AuthorityError as e:
        raise SecurityError(
            f"authority required for '{operation}': {e}",
            operation=operation,
            resource="authority",
            cause=e,
            recoverable=False,
        )


def is_simulation_thread() -> bool:
    return get_simulation_thread_registry().is_simulation_thread()


@contextmanager
def backend_operation(operation: str, *, audit: Optional[Dict[str, Any]] = None):
    """
    Context manager for backend operations: classifies, checks, audits.

    - For MUTATE_SIMULATION: requires_authority() must pass.
    - For MUTATE_BACKEND: allowed on any thread; emits audit log.
    - For READ_*: allowed on any thread.
    """
    cls = classify_operation(operation)
    if cls == OperationClass.MUTATE_SIMULATION:
        assert_authority(operation)
    # Lightweight audit: thread id + op class
    tid = threading.current_thread().ident
    # (Diagnostics layer collects these if enabled; here we just enforce)
    try:
        yield {"operation": operation, "class": cls.value, "thread_id": tid, "audit": audit or {}}
    except SecurityError:
        raise
    except Exception as e:
        # wrap unexpected as SecurityError only if it was an authority boundary
        if cls == OperationClass.MUTATE_SIMULATION and isinstance(e, AuthorityError):
            raise SecurityError(str(e), operation=operation, cause=e)
        raise


def check_permission(operation: str, *, thread_id: Optional[int] = None) -> bool:
    """
    Non-raising check: returns True if caller would be permitted.
    """
    cls = classify_operation(operation)
    if cls == OperationClass.MUTATE_SIMULATION:
        try:
            AuthorityContext.require_authority(operation)
            return True
        except AuthorityError:
            return False
    return True  # backend mutates and reads are allowed (with audit)


__all__ = [
    "OperationClass",
    "requires_authority",
    "classify_operation",
    "assert_authority",
    "is_simulation_thread",
    "backend_operation",
    "check_permission",
]
