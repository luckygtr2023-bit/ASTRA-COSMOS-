"""ASTRA Core recovery system."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import threading

from astra.core.logging import get_logger
from astra.core.exceptions import AstraError


class RecoveryPolicy(Enum):
    """Recovery policies for handling failures."""

    FAIL_FAST = "fail_fast"  # Immediately fail and stop
    RETRY_STEP = "retry_step"  # Retry the failed step
    DROP_EVENT = "drop_event"  # Drop the failing event/command and continue
    ROLLBACK = "rollback"  # Rollback to last known good state


@dataclass
class FailureRecord:
    """Record of a failure event."""

    failure_type: str
    operation: str
    tick: int
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovered: bool = False
    recovery_method: str = ""


@dataclass
class RecoveryState:
    """Snapshot of recovery system state."""

    policy: RecoveryPolicy
    consecutive_failures: int
    total_failures: int
    last_failure_tick: int
    is_recovering: bool


class RecoveryManager:
    """Manages recovery from simulation failures."""

    def __init__(self, policy: RecoveryPolicy = RecoveryPolicy.FAIL_FAST):
        self._policy = policy
        self._max_retry_attempts = 3
        self._failure_history: List[FailureRecord] = []
        self._consecutive_failures = 0
        self._total_failures = 0
        self._is_recovering = False
        self._retry_counts: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._logger = get_logger("recovery")
        self._rollback_callbacks: list = []
        self._last_good_state: Optional[Any] = None

    def set_policy(self, policy: RecoveryPolicy):
        """Set the recovery policy."""
        with self._lock:
            old_policy = self._policy
            self._policy = policy
            self._logger.info(f"Recovery policy changed: {old_policy.value} -> {policy.value}")

    def get_policy(self) -> RecoveryPolicy:
        """Get the current recovery policy."""
        return self._policy

    def set_max_retry_attempts(self, attempts: int):
        """Set maximum retry attempts for RETRY_STEP policy."""
        self._max_retry_attempts = attempts

    def register_rollback_callback(self, callback: Callable[[], None]):
        """Register a callback for rollback operations."""
        self._rollback_callbacks.append(callback)

    def record_failure(
        self,
        failure_type: str,
        operation: str,
        tick: int,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Record a failure and determine if recovery should be attempted.
        
        Returns True if the operation should be retried/continued,
        False if it should fail.
        """
        with self._lock:
            self._consecutive_failures += 1
            self._total_failures += 1

            record = FailureRecord(
                failure_type=failure_type,
                operation=operation,
                tick=tick,
                message=message,
                context=context or {},
            )
            self._failure_history.append(record)

            self._logger.error(
                f"Failure recorded: {failure_type} in {operation} at tick {tick}: {message}"
            )

            if self._policy == RecoveryPolicy.FAIL_FAST:
                self._logger.critical("FAIL_FAST policy: stopping simulation")
                return False

            elif self._policy == RecoveryPolicy.RETRY_STEP:
                retry_key = f"{operation}_{tick}"
                current_retries = self._retry_counts.get(retry_key, 0)

                if current_retries >= self._max_retry_attempts:
                    self._logger.error(
                        f"Max retries ({self._max_retry_attempts}) exceeded for {operation}"
                    )
                    record.recovered = False
                    record.recovery_method = "max_retries_exceeded"
                    return False

                self._retry_counts[retry_key] = current_retries + 1
                self._is_recovering = True
                record.recovered = True
                record.recovery_method = "retry"
                self._logger.info(f"Retrying {operation} (attempt {current_retries + 1})")
                return True

            elif self._policy == RecoveryPolicy.DROP_EVENT:
                self._logger.warning(f"Dropping failed event: {operation}")
                record.recovered = True
                record.recovery_method = "drop"
                self._consecutive_failures = 0
                self._is_recovering = False
                return True

            elif self._policy == RecoveryPolicy.ROLLBACK:
                self._logger.info(f"Initiating rollback for {operation}")
                self._is_recovering = True
                try:
                    for callback in self._rollback_callbacks:
                        callback()
                    record.recovered = True
                    record.recovery_method = "rollback"
                    self._consecutive_failures = 0
                    return True
                except Exception as e:
                    self._logger.error(f"Rollback failed: {e}")
                    record.recovered = False
                    record.recovery_method = "rollback_failed"
                    return False

            return False

    def record_success(self, operation: str, tick: int):
        """Record a successful operation."""
        with self._lock:
            retry_key = f"{operation}_{tick}"
            if retry_key in self._retry_counts:
                del self._retry_counts[retry_key]
            self._consecutive_failures = 0
            self._is_recovering = False

    def save_good_state(self, state: Any):
        """Save a known good state for potential rollback."""
        self._last_good_state = state

    def get_last_good_state(self) -> Optional[Any]:
        """Get the last saved good state."""
        return self._last_good_state

    def get_failure_history(
        self,
        from_tick: int = 0,
        to_tick: Optional[int] = None,
        failure_type: Optional[str] = None,
    ) -> List[FailureRecord]:
        """Get failure history, optionally filtered."""
        with self._lock:
            result = self._failure_history.copy()

        if from_tick > 0:
            result = [r for r in result if r.tick >= from_tick]
        if to_tick is not None:
            result = [r for r in result if r.tick <= to_tick]
        if failure_type:
            result = [r for r in result if r.failure_type == failure_type]

        return result

    def get_state(self) -> RecoveryState:
        """Get current recovery state."""
        return RecoveryState(
            policy=self._policy,
            consecutive_failures=self._consecutive_failures,
            total_failures=self._total_failures,
            last_failure_tick=self._failure_history[-1].tick if self._failure_history else 0,
            is_recovering=self._is_recovering,
        )

    def reset(self):
        """Reset recovery state."""
        with self._lock:
            self._consecutive_failures = 0
            self._is_recovering = False
            self._retry_counts.clear()
            self._logger.debug("Recovery manager reset")

    def clear_history(self):
        """Clear failure history."""
        with self._lock:
            self._failure_history.clear()
            self._logger.debug("Failure history cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get recovery statistics."""
        with self._lock:
            return {
                "policy": self._policy.value,
                "consecutive_failures": self._consecutive_failures,
                "total_failures": self._total_failures,
                "pending_retries": len(self._retry_counts),
                "is_recovering": self._is_recovering,
            }
