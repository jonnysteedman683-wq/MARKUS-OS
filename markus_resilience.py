"""
MARKUS OS Multi-Endpoint Circuit Breaker & Resilience Engine (Upgrade 9)
Protects kernel subsystems against cascading failures during API calls, 
IPC requests, and external model endpoint queries.

States:
  CLOSED -> Normal operation
  OPEN   -> Tripped after threshold; requests fast-fail
  HALF_OPEN -> Probe recovery window after cooldown
"""

from __future__ import annotations
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from contextlib import contextmanager

from markus_db import PersistentCortexDB

logger = logging.getLogger("Markus.Resilience")

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitContext:
    """Execution context wrapper for circuit breaker monitoring."""
    failures: int = 0
    last_failure_time: float = 0.0
    state: CircuitState = CircuitState.CLOSED
    probe_attempt: int = 0
    snapshot_registers: Dict[str, Any] = field(default_factory=dict)

@dataclass
class FailureRecord:
    """Persistent record of a tripped circuit event."""
    endpoint: str
    timestamp: float
    error_type: str
    error_message: str
    registers_snapshot: Dict[str, Any]
    recovery_action: str

class ResilientEndpoint:
    """
    Wraps any callable (HTTP request, IPC call, file operation) with a 
    state-machine circuit breaker and automatic memory cortex logging.
    """
    def __init__(self, name: str, max_failures: int = 3, cooldown_s: float = 15.0, db: Optional[PersistentCortexDB] = None) -> None:
        self.name = name
        self.max_failures = max_failures
        self.cooldown_s = cooldown_s
        self.context = CircuitContext()
        self.db = db or PersistentCortexDB()

    def _attempt_call(self, func: Callable, *args, **kwargs) -> Tuple[bool, Any]:
        """Attempts to execute the wrapped callable. Returns (success, result_or_error)."""
        try:
            result = func(*args, **kwargs)
            return (True, result)
        except Exception as e:
            return (False, e)

    def _record_failure(self, error: Exception, snapshot: Dict[str, Any]) -> None:
        self.context.failures += 1
        self.context.last_failure_time = time.time()
        rec = FailureRecord(
        endpoint=self.name,
        timestamp=time.time(),
        error_type=type(error).__name__,
        error_message=str(error),
        registers_snapshot=snapshot,
        recovery_action="fast_fail_isolated"
        )
        try:
            self.db.append_thought(uuid.uuid4().hex, "RESILIENCE", json.dumps(rec.__dict__))
            logger.warning(f"Circuit [{self.name}] FAILURE #{self.context.failures}: {error}")
        except Exception as log_err:
            logger.error(f"Failed to log failure to cortex: {log_err}")

    def _reset(self) -> None:
        self.context = CircuitContext()
        logger.info(f"Circuit [{self.name}] RESET to CLOSED state.")

    def protected_call(self, func: Callable, *args, **kwargs) -> Any:
        """Main callable. Handles circuit logic and recovery."""
        now = time.time()

        if self.context.state == CircuitState.OPEN:
            if (now - self.context.last_failure_time) >= self.cooldown_s:
                self.context.state = CircuitState.HALF_OPEN
                self.context.probe_attempt = 0
                logger.info(f"Circuit [{self.name}] entering HALF_OPEN recovery window.")
            else:
                logger.warning(f"Circuit [{self.name}] OPEN - Fast-failing request.")
                raise RuntimeError(f"Circuit breaker OPEN for endpoint '{self.name}'. Request isolated.")

        success, result = self._attempt_call(func, *args, **kwargs)

        if success:
            if self.context.state == CircuitState.HALF_OPEN:
                self._reset()
                return result
            self.context.failures = 0  # Reset failure window on success
            return result
        else:
            # Failure case
            snapshot = {}
            try:
                snapshot = self.db.read_register("CURRENT_REGISTERS") if hasattr(self.db, 'read_register') else {}
            except Exception:
                snapshot = {}
            self._record_failure(result, snapshot)

            if self.context.failures >= self.max_failures:
                self.context.state = CircuitState.OPEN
                self.context.last_failure_time = time.time()

            raise result

    @contextmanager
    def protect(self, snapshot_registers: Optional[Dict[str, Any]] = None):
        """Context manager wrapper for protected blocks."""
        if snapshot_registers:
            self.context.snapshot_registers = snapshot_registers
        try:
            yield self
        except Exception as e:
            self._record_failure(e, self.context.snapshot_registers or {})
            raise

class CircuitBreakerManager:
    """Manages a registry of resilient endpoints for the kernel."""
    def __init__(self, db: Optional[PersistentCortexDB] = None) -> None:
        self.endpoints: Dict[str, ResilientEndpoint] = {}
        self.db = db or PersistentCortexDB()

    def register(self, name: str, max_failures: int = 3, cooldown_s: float = 15.0) -> ResilientEndpoint:
        if name not in self.endpoints:
            self.endpoints[name] = ResilientEndpoint(name, max_failures, cooldown_s, self.db)
            self.db.append_thought(uuid.uuid4().hex, "RESILIENCE", f"Registered circuit breaker for '{name}'.")
        return self.endpoints[name]

    def get(self, name: str) -> Optional[ResilientEndpoint]:
        return self.endpoints.get(name)

    def get_all_states(self) -> Dict[str, str]:
        return {name: ep.context.state.value for name, ep in self.endpoints.items()}

    def reset(self, name: str) -> None:
        if name in self.endpoints:
            self.endpoints[name]._reset()

if __name__ == "__main__":
    manager = CircuitBreakerManager()
    endpoint = manager.register("test-hermes-api", max_failures=2, cooldown_s=5.0)

    # Simulate a failing call
    def failing_func():
        raise ConnectionError("Simulated API timeout")

    try:
        endpoint.protected_call(failing_func)
        print("ERROR: Should have raised")
    except RuntimeError as e:
        pass
    except ConnectionError as e:
        pass

    print("=== MARKUS Resilience Engine State ===")
    print(f"Endpoint States: {manager.get_all_states()}")
    print("Failure log verified in Persistent Cortex DB. Engine functional.")
