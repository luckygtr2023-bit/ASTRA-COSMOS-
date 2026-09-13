"""ASTRA Core testing utilities."""

import pytest
from typing import Any, Dict, Callable
import threading
import time


def run_with_timeout(func: Callable, timeout: float = 5.0) -> bool:
    """Run a function with a timeout.
    
    Returns True if completed successfully, False if timed out.
    """
    result = {"completed": False, "error": None}
    
    def wrapper():
        try:
            func()
            result["completed"] = True
        except Exception as e:
            result["error"] = e
    
    thread = threading.Thread(target=wrapper)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if not result["completed"]:
        return False
    if result["error"]:
        raise result["error"]
    return True


def assert_deterministic(func: Callable[[], Any], iterations: int = 3) -> bool:
    """Verify that a function produces deterministic results.
    
    Returns True if all iterations produce identical results.
    """
    results = []
    for _ in range(iterations):
        results.append(func())
    
    # Compare all results to the first
    first = results[0]
    for result in results[1:]:
        if result != first:
            return False
    return True


class TestContext:
    """Context manager for test setup and teardown."""
    
    def __init__(self, setup: Callable = None, teardown: Callable = None):
        self._setup = setup
        self._teardown = teardown
    
    def __enter__(self):
        if self._setup:
            self._setup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._teardown:
            self._teardown()
        return False


def skip_if_slow(reason: str = "Test is slow"):
    """Decorator to skip slow tests unless explicitly enabled."""
    import os
    if not os.environ.get("ASTRA_RUN_SLOW_TESTS"):
        return pytest.skip(reason)
    return lambda f: f


__all__ = [
    "run_with_timeout",
    "assert_deterministic",
    "TestContext",
    "skip_if_slow",
]
