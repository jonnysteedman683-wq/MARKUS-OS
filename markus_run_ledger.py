#!/usr/bin/env python3
"""Durable, typed run/event ledger for MARKUS operations.

Stdlib-only SQLite persistence. The ledger is intentionally additive: it does not
execute tools or models. Callers record transitions and checkpoints, then resume
from the last durable checkpoint after restart.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

RUN_STATES = {
    "RECEIVED", "ROUTED", "RUNNING", "VERIFYING", "WAITING_APPROVAL",
    "PASSED", "FAILED", "REJECTED", "COMMITTED", "SYNCED",
}
_ALLOWED = {
    "RECEIVED": {"ROUTED", "FAILED"},
    "ROUTED": {"RUNNING", "FAILED"},
    "RUNNING": {"VERIFYING", "WAITING_APPROVAL", "FAILED"},
    "VERIFYING": {"PASSED", "FAILED", "WAITING_APPROVAL"},
    "WAITING_APPROVAL": {"RUNNING", "REJECTED", "FAILED"},
    "PASSED": {"COMMITTED", "SYNCED", "FAILED"},
    "COMMITTED": {"SYNCED"},
    "SYNCED": set(),
    "FAILED": set(),
    "REJECTED": set(),
}


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    goal_id: Optional[str] = None
    mode: str = "FIELD"
    status: str = "RECEIVED"
    provider: Optional[str] = None
    model: Optional[str] = None
    input_hash: Optional[str] = None
    checkpoint: Optional[str] = None
    approval_required: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class RunEvent:
    run_id: str
    sequence: int
    event_type: str
    payload: Dict[str, Any]
    created_at: float
    idempotency_key: str


class RunLedgerError(RuntimeError):
    pass


class RunLedger:
    """Thread-safe SQLite ledger with legal transitions and idempotent events."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(self.path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._db:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, goal_id TEXT, mode TEXT NOT NULL,
                    status TEXT NOT NULL, provider TEXT, model TEXT,
                    input_hash TEXT, checkpoint TEXT, approval_required INTEGER NOT NULL,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    run_id TEXT NOT NULL REFERENCES runs(run_id), sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
                    created_at REAL NOT NULL, idempotency_key TEXT NOT NULL,
                    PRIMARY KEY(run_id, sequence), UNIQUE(run_id, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS checkpoints (
                    run_id TEXT NOT NULL REFERENCES runs(run_id), name TEXT NOT NULL,
                    payload_json TEXT NOT NULL, created_at REAL NOT NULL,
                    PRIMARY KEY(run_id, name)
                );
                CREATE TABLE IF NOT EXISTS approvals (
                    run_id TEXT NOT NULL REFERENCES runs(run_id), decision TEXT NOT NULL,
                    actor TEXT NOT NULL, reason TEXT, created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_run_events_run ON run_events(run_id, sequence);
                """
            )

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def create_run(self, *, goal_id: Optional[str] = None, mode: str = "FIELD",
                   provider: Optional[str] = None, model: Optional[str] = None,
                   input_hash: Optional[str] = None, run_id: Optional[str] = None) -> RunRecord:
        now = time.time()
        rec = RunRecord(run_id or str(uuid.uuid4()), goal_id, mode, "RECEIVED", provider,
                        model, input_hash, None, False, now, now)
        with self._lock, self._db:
            try:
                self._db.execute(
                    "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (rec.run_id, rec.goal_id, rec.mode, rec.status, rec.provider, rec.model,
                     rec.input_hash, rec.checkpoint, int(rec.approval_required), rec.created_at, rec.updated_at))
            except sqlite3.IntegrityError as exc:
                raise RunLedgerError(f"run already exists: {rec.run_id}") from exc
        return rec

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            row = self._db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            return None
        return RunRecord(row["run_id"], row["goal_id"], row["mode"], row["status"], row["provider"],
                         row["model"], row["input_hash"], row["checkpoint"], bool(row["approval_required"]),
                         row["created_at"], row["updated_at"])

    def transition(self, run_id: str, status: str, *, payload: Optional[Dict[str, Any]] = None,
                   idempotency_key: Optional[str] = None) -> RunRecord:
        if status not in RUN_STATES:
            raise RunLedgerError(f"unknown status: {status}")
        with self._lock, self._db:
            rec = self.get_run(run_id)
            if not rec:
                raise RunLedgerError(f"unknown run: {run_id}")
            if rec.status != status and status not in _ALLOWED.get(rec.status, set()):
                raise RunLedgerError(f"illegal transition {rec.status} -> {status}")
            now = time.time()
            self._db.execute("UPDATE runs SET status=?, updated_at=? WHERE run_id=?", (status, now, run_id))
            self._append_event_locked(run_id, status, payload or {}, idempotency_key or f"status:{status}:{now}")
        return self.get_run(run_id)  # type: ignore[return-value]

    def checkpoint(self, run_id: str, name: str, payload: Optional[Dict[str, Any]] = None) -> RunRecord:
        if not name.strip():
            raise RunLedgerError("checkpoint name is required")
        with self._lock, self._db:
            if not self.get_run(run_id):
                raise RunLedgerError(f"unknown run: {run_id}")
            now = time.time()
            body = payload or {}
            self._db.execute("INSERT OR REPLACE INTO checkpoints VALUES (?,?,?,?)",
                             (run_id, name, json.dumps(body, sort_keys=True, default=str), now))
            self._db.execute("UPDATE runs SET checkpoint=?, updated_at=? WHERE run_id=?", (name, now, run_id))
            self._append_event_locked(run_id, "CHECKPOINT", {"name": name, "payload": body}, f"checkpoint:{name}")
        return self.get_run(run_id)  # type: ignore[return-value]

    def approve(self, run_id: str, decision: str, *, actor: str, reason: str = "") -> RunRecord:
        if decision not in {"APPROVED", "REJECTED"}:
            raise RunLedgerError("decision must be APPROVED or REJECTED")
        with self._lock, self._db:
            if not self.get_run(run_id):
                raise RunLedgerError(f"unknown run: {run_id}")
            now = time.time()
            self._db.execute("INSERT INTO approvals VALUES (?,?,?,?,?)", (run_id, decision, actor, reason, now))
            self._append_event_locked(run_id, decision, {"actor": actor, "reason": reason}, f"approval:{decision}:{actor}")
        next_status = "RUNNING" if decision == "APPROVED" else "REJECTED"
        return self.transition(run_id, next_status, payload={"actor": actor, "decision": decision}, idempotency_key=f"transition:{next_status}:{actor}")

    def _append_event_locked(self, run_id: str, event_type: str, payload: Dict[str, Any], key: str) -> RunEvent:
        existing = self._db.execute("SELECT * FROM run_events WHERE run_id=? AND idempotency_key=?", (run_id, key)).fetchone()
        if existing:
            return RunEvent(run_id, existing["sequence"], existing["event_type"], json.loads(existing["payload_json"]), existing["created_at"], key)
        row = self._db.execute("SELECT COALESCE(MAX(sequence),0)+1 AS n FROM run_events WHERE run_id=?", (run_id,)).fetchone()
        seq, now = int(row["n"]), time.time()
        self._db.execute("INSERT INTO run_events VALUES (?,?,?,?,?,?)",
                         (run_id, seq, event_type, json.dumps(payload, sort_keys=True, default=str), now, key))
        return RunEvent(run_id, seq, event_type, payload, now, key)

    def events(self, run_id: str) -> List[RunEvent]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM run_events WHERE run_id=? ORDER BY sequence", (run_id,)).fetchall()
        return [RunEvent(r["run_id"], r["sequence"], r["event_type"], json.loads(r["payload_json"]), r["created_at"], r["idempotency_key"]) for r in rows]

    def trace(self, run_id: str) -> Dict[str, Any]:
        rec = self.get_run(run_id)
        if not rec:
            raise RunLedgerError(f"unknown run: {run_id}")
        return {"run": asdict(rec), "events": [asdict(e) for e in self.events(run_id)]}

    def __enter__(self) -> "RunLedger":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?", default="markus_private/vault/markus_runs.db")
    args = ap.parse_args()
    with RunLedger(args.path) as ledger:
        run = ledger.create_run(mode="FIELD")
        ledger.transition(run.run_id, "ROUTED")
        ledger.checkpoint(run.run_id, "routed")
        print(json.dumps(ledger.trace(run.run_id), indent=2, default=str))
