#!/usr/bin/env python3
"""Local durable execution journal for MARKUS task side effects.

[◈MARKUS◈] Inspired by documented deterministic-replay patterns in
AWS CLI Agent Orchestrator and Temporal; no upstream source is copied.

A journal of life for MARKUS DAG nodes: append starts, failures, and completions.
On replay, completed work is returned from journal without re-invoking the side effect.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional


_RECOVERY_POLICIES = {"idempotent", "reconcile", "manual"}
_SECRET_PATTERNS = (
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(?:sk|ghp|xoxb|xoxp)-[A-Za-z0-9._-]{8,}"),
    re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret)\s*[:=]\s*[^,;\s}]+"),
)


class ManualRecoveryRequired(RuntimeError):
    """Raised when resuming a side effect requires human authorization."""


class ExecutionJournal:
    """Append-only local journal with deterministic completion replay."""

    def __init__(self, journal_path: str | Path, breaker: Optional[Any] = None) -> None:
        self.journal_path = Path(journal_path)
        self.quarantine_path = self.journal_path.with_suffix(self.journal_path.suffix + ".corrupt")
        self._lock = threading.RLock()
        self._records: dict[str, dict[str, Any]] = {}
        self.corrupt_lines: list[str] = []
        self.breaker = breaker
        self._load()

    def _load(self) -> None:
        if not self.journal_path.exists():
            return
        for line in self.journal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                execution_id = record["execution_id"]
                state = record["state"]
                if not isinstance(execution_id, str) or not isinstance(state, str):
                    raise ValueError("invalid journal record")
                self._records[execution_id] = record
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                self.corrupt_lines.append(line)
        if self.corrupt_lines:
            self.quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            with self.quarantine_path.open("a", encoding="utf-8") as handle:
                for line in self.corrupt_lines:
                    handle.write(line + "\n")

    @staticmethod
    def _redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): ExecutionJournal._redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [ExecutionJournal._redact(item) for item in value]
        if isinstance(value, tuple):
            return [ExecutionJournal._redact(item) for item in value]
        if isinstance(value, str):
            result = value
            for pattern in _SECRET_PATTERNS:
                result = pattern.sub("[REDACTED]", result)
            return result
        return value

    def _append(self, record: dict[str, Any]) -> None:
        safe_record = self._redact(record)
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe_record, sort_keys=True, default=str) + "\n")
        self._records[safe_record["execution_id"]] = safe_record

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def state(self, execution_id: str) -> str | None:
        with self._lock:
            record = self._records.get(execution_id)
            return record.get("state") if record else None

    def record(self, execution_id: str) -> dict[str, Any] | None:
        with self._lock:
            current = self._records.get(execution_id)
            return dict(current) if current else None

    def run(self, execution_id: str, *, recovery: str, action: Callable[[], Any]) -> Any:
        """Run or replay one synchronous side effect under an explicit policy."""
        if not execution_id or recovery not in _RECOVERY_POLICIES:
            raise ValueError("execution_id is required and recovery must be idempotent, reconcile, or manual")

        with self._lock:
            previous = self._records.get(execution_id)
            if previous and previous.get("state") == "completed":
                return previous.get("result")
            if previous and previous.get("state") in {"started", "manual_required"}:
                if recovery != "idempotent":
                    self._append({
                        "execution_id": execution_id,
                        "state": "manual_required",
                        "recovery": recovery,
                        "attempt": previous.get("attempt", 1),
                        "timestamp": self._timestamp(),
                    })
                    raise ManualRecoveryRequired(
                        f"manual recovery required for execution '{execution_id}'"
                    )
            attempt = int(previous.get("attempt", 0)) + 1 if previous else 1
            self._append({
                "execution_id": execution_id,
                "state": "started",
                "recovery": recovery,
                "attempt": attempt,
                "timestamp": self._timestamp(),
            })

        try:
            if self.breaker is not None:
                result = self.breaker.protected_call(action)
            else:
                result = action()
        except Exception as exc:
            with self._lock:
                self._append({
                    "execution_id": execution_id,
                    "state": "failed",
                    "recovery": recovery,
                    "attempt": attempt,
                    "error": f"{type(exc).__name__}: {exc}",
                    "timestamp": self._timestamp(),
                })
            raise

        with self._lock:
            self._append({
                "execution_id": execution_id,
                "state": "completed",
                "recovery": recovery,
                "attempt": attempt,
                "result": result,
                "timestamp": self._timestamp(),
            })
        return result

    async def arun(
        self,
        execution_id: str,
        *,
        recovery: str,
        action: Callable[[], Awaitable[Any]],
    ) -> Any:
        """Run or replay one asynchronous side effect under an explicit policy."""
        if not execution_id or recovery not in _RECOVERY_POLICIES:
            raise ValueError("execution_id is required and recovery must be idempotent, reconcile, or manual")

        with self._lock:
            previous = self._records.get(execution_id)
            if previous and previous.get("state") == "completed":
                return previous.get("result")
            if previous and previous.get("state") in {"started", "manual_required"}:
                if recovery != "idempotent":
                    self._append({
                        "execution_id": execution_id,
                        "state": "manual_required",
                        "recovery": recovery,
                        "attempt": previous.get("attempt", 1),
                        "timestamp": self._timestamp(),
                    })
                    raise ManualRecoveryRequired(
                        f"manual recovery required for execution '{execution_id}'"
                    )
            attempt = int(previous.get("attempt", 0)) + 1 if previous else 1
            self._append({
                "execution_id": execution_id,
                "state": "started",
                "recovery": recovery,
                "attempt": attempt,
                "timestamp": self._timestamp(),
            })

        try:
            result = await action()
        except Exception as exc:
            with self._lock:
                self._append({
                    "execution_id": execution_id,
                    "state": "failed",
                    "recovery": recovery,
                    "attempt": attempt,
                    "error": f"{type(exc).__name__}: {exc}",
                    "timestamp": self._timestamp(),
                })
            raise

        with self._lock:
            self._append({
                "execution_id": execution_id,
                "state": "completed",
                "recovery": recovery,
                "attempt": attempt,
                "result": result,
                "timestamp": self._timestamp(),
            })
        return result


__all__ = ["ExecutionJournal", "ManualRecoveryRequired"]
