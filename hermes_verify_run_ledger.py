#!/usr/bin/env python3
"""Focused verification for MARKUS durable run/event ledger."""
from __future__ import annotations
import tempfile
from pathlib import Path
from markus_run_ledger import RunLedger, RunLedgerError


def check(name, ok):
    print(f"{'PASS' if ok else 'FAIL'} - {name}")
    return ok


def main():
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "runs.db"
        with RunLedger(path) as ledger:
            run = ledger.create_run(run_id="run-1", goal_id="GOAL_1.1", mode="FORGE")
            ledger.transition("run-1", "ROUTED", idempotency_key="route-1")
            ledger.transition("run-1", "RUNNING", idempotency_key="start-1")
            ledger.checkpoint("run-1", "tool-complete", {"artifact": "x"})
            ledger.transition("run-1", "VERIFYING", idempotency_key="verify-1")
            ledger.transition("run-1", "PASSED", idempotency_key="pass-1")
            ledger.transition("run-1", "PASSED", idempotency_key="pass-1")
            events = ledger.events("run-1")
            results.append(check("legal lifecycle", ledger.get_run("run-1").status == "PASSED"))
            results.append(check("idempotent event append", len([e for e in events if e.idempotency_key == "pass-1"]) == 1))
            results.append(check("ordered event sequence", [e.sequence for e in events] == list(range(1, len(events) + 1))))
            try:
                ledger.transition("run-1", "RECEIVED", idempotency_key="bad")
                results.append(check("illegal transition rejected", False))
            except RunLedgerError:
                results.append(check("illegal transition rejected", True))
            trace = ledger.trace("run-1")
            results.append(check("trace contains run and events", trace["run"]["run_id"] == "run-1" and trace["events"]))
        with RunLedger(path) as reopened:
            resumed = reopened.get_run("run-1")
            results.append(check("restart recovery", resumed.checkpoint == "tool-complete" and resumed.status == "PASSED"))
            results.append(check("events survive reopen", len(reopened.events("run-1")) == len(events)))
    print(f"OVERALL: {'PASS' if all(results) else 'FAIL'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
