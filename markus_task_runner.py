"""
MARKUS OS Task Runner with Retry & Backoff (Port of HERMES-HIVE taskRunner.ts)

Provides async task execution with exponential backoff retry policies,
pending-result resolution via promise-map pattern, and configurable timeouts.

Integration point: markus_kanban_worker.py claims tasks from kanban.db and
submits them here for execution with automatic retry on failure.
"""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor, Future


@dataclass
class RetryPolicy:
    """Exponential backoff retry configuration."""
    max_retries: int = 3
    backoff_ms: int = 5000  # 5s initial
    backoff_multiplier: float = 2.0
    max_backoff_ms: int = 60000  # 60s cap
    timeout_ms: int = 120000  # 120s default timeout

    def get_backoff(self, attempt: int) -> float:
        """Calculate backoff for the given attempt number (0-indexed)."""
        backoff = self.backoff_ms * (self.backoff_multiplier ** attempt)
        return min(backoff, self.max_backoff_ms) / 1000.0  # convert to seconds


@dataclass
class TaskResult:
    """Result of a task execution."""
    task_id: str
    status: str  # "completed" | "failed" | "cancelled"
    output: Any = None
    error: Optional[str] = None
    retries_used: int = 0
    latency_ms: int = 0
    completed_at: str = ""
    execution_metadata: Dict[str, Any] = field(default_factory=dict)


class TaskRunnerService:
    """Async task executor with retry policies and pending-wait resolution.

    Ported from HERMES-HIVE (taskRunner.ts). Uses threading for async
    execution with a ThreadPoolExecutor.
    """

    def __init__(self, max_workers: int = 8) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="Markus-TaskRunner")
        self._pending_waits: Dict[str, threading.Event] = {}
        self._results: Dict[str, TaskResult] = {}
        self._lock = threading.Lock()

    def _generate_id(self) -> str:
        return f"task-{int(time.time() * 1000)}-{threading.get_ident() % 10000:04d}"

    def submit_task(
        self,
        func: Callable[..., Any],
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        retry_policy: Optional[RetryPolicy] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """Submit a task for async execution. Returns the task ID immediately."""
        if task_id is None:
            task_id = self._generate_id()

        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        if retry_policy is None:
            retry_policy = RetryPolicy()

        # Create event for await_result
        event = threading.Event()
        with self._lock:
            self._pending_waits[task_id] = event

        # Submit to executor
        future = self._executor.submit(self._execute_with_retry, task_id, func, args, kwargs, retry_policy)

        # Set callback to resolve waiters
        future.add_done_callback(lambda f: self._resolve_waiter(task_id, f))

        return task_id

    def _execute_with_retry(
        self,
        task_id: str,
        func: Callable[..., Any],
        args: tuple,
        kwargs: dict,
        retry_policy: RetryPolicy,
    ) -> TaskResult:
        """Execute a task with retry logic and exponential backoff."""
        start_time = time.monotonic()
        retries_used = 0

        while True:
            try:
                result = func(*args, **kwargs)
                latency_ms = int((time.monotonic() - start_time) * 1000)
                return TaskResult(
                    task_id=task_id,
                    status="completed",
                    output=result,
                    retries_used=retries_used,
                    latency_ms=latency_ms,
                    completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
            except Exception as e:
                if retries_used >= retry_policy.max_retries:
                    latency_ms = int((time.monotonic() - start_time) * 1000)
                    return TaskResult(
                        task_id=task_id,
                        status="failed",
                        error=str(e),
                        retries_used=retries_used,
                        latency_ms=latency_ms,
                        completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    )

                # Backoff before retry
                backoff_seconds = retry_policy.get_backoff(retries_used)
                time.sleep(backoff_seconds)
                retries_used += 1

    def _resolve_waiter(self, task_id: str, future: Future) -> None:
        """Resolve pending await_result callers."""
        try:
            result = future.result()
        except Exception as e:
            result = TaskResult(
                task_id=task_id,
                status="failed",
                error=str(e),
                latency_ms=0,
                completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )

        with self._lock:
            self._results[task_id] = result

        event = self._pending_waits.pop(task_id, None)
        if event:
            event.set()

    def await_result(self, task_id: str, timeout_ms: int = 120000) -> TaskResult:
        """Wait for a task to complete. Returns TaskResult or raises TimeoutError."""
        # Fast path: result already available
        with self._lock:
            if task_id in self._results:
                return self._results[task_id]

        event = self._pending_waits.get(task_id)
        if event is None:
            return TaskResult(
                task_id=task_id,
                status="cancelled",
                error=f"Task {task_id} not found or already resolved",
            )

        # Wait with timeout
        timeout_s = timeout_ms / 1000.0
        signaled = event.wait(timeout=timeout_s)

        if not signaled:
            return TaskResult(
                task_id=task_id,
                status="failed",
                error=f"Task {task_id} timed out after {timeout_ms}ms",
                latency_ms=timeout_ms,
                completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )

        with self._lock:
            return self._results.get(task_id, TaskResult(
                task_id=task_id,
                status="failed",
                error="Unknown state",
            ))

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running or queued task."""
        with self._lock:
            event = self._pending_waits.pop(task_id, None)
            if event:
                event.set()
                return True
            return False

    def shutdown(self) -> None:
        """Graceful shutdown of the thread pool."""
        self._executor.shutdown(wait=True, cancel_futures=True)

    def pending_count(self) -> int:
        """Number of tasks pending completion."""
        with self._lock:
            return len(self._pending_waits)


# Default instance for MARKUS
task_runner = TaskRunnerService()

if __name__ == "__main__":
    # Demo: submit a flaky task that fails twice then succeeds
    attempt_count = [0]

    def flaky_task():
        attempt_count[0] += 1
        print(f"  [EXEC] Attempt {attempt_count[0]}")
        if attempt_count[0] < 3:
            raise RuntimeError(f"Flaky failure on attempt {attempt_count[0]}")
        return "success on attempt 3"

    policy = RetryPolicy(max_retries=3, backoff_ms=100, backoff_multiplier=2.0)
    task_id = task_runner.submit_task(flaky_task, retry_policy=policy)
    print(f"[TASK] Submitted task {task_id}")

    result = task_runner.await_result(task_id, timeout_ms=10000)
    print(f"[RESULT] status={result.status}, output={result.output}, retries={result.retries_used}, latency={result.latency_ms}ms")
    assert result.status == "completed"
    assert result.output == "success on attempt 3"
    assert result.retries_used == 2
    print("\n[TASK RUNNER] Self-test PASSED")
