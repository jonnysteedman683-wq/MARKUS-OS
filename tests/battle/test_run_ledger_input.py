"""
Battle-test: run ledger input validation (markus_run_ledger).

REG-12 (MED): /api/runs accepts an attacker-supplied `run_id` verbatim into
a PRIMARY KEY. Path-traversal-style / SQL-style run_ids (e.g. "../../x",
"x' OR '1'='1") are stored and echoed. Must be rejected or sanitised.
REG-13 (LOW): arbitrary transition to terminal states by any caller with no
authorization boundary (state machine itself enforces legality, but there is
no auth and no audit of who mutated a run).
"""
from __future__ import annotations

from pathlib import Path

import pytest

# markus_run_ledger.py was added on local master only (not on origin/master),
# so in CI it is absent and these tests skip with a clear reason.
pytest.importorskip(
    "markus_run_ledger",
    reason="markus_run_ledger is not present on origin/master (local-master only)",
)
from markus_run_ledger import RunLedger, RunLedgerError


@pytest.fixture()
def ledger(tmp_path: Path) -> RunLedger:
    return RunLedger(tmp_path / "runs.db")


@pytest.mark.parametrize("bad_id", [
    "../../../etc/evil",
    "x' OR '1'='1",
    "a\nb",
    "run id with spaces",
])
def test_unsafe_run_id_rejected(ledger, bad_id: str) -> None:
    """REG-12: run_id must be constrained to a safe charset."""
    with pytest.raises((RunLedgerError, ValueError)):
        ledger.create_run(run_id=bad_id)


def test_arbitrary_transition_to_terminal_blocked(ledger) -> None:
    """REG-13: a run can't jump straight to COMMITTED from RECEIVED."""
    run = ledger.create_run(mode="FIELD")
    with pytest.raises(RunLedgerError):
        ledger.transition(run.run_id, "COMMITTED")
