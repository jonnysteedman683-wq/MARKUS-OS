"""
Battle-test: VORPAL CORE — syscalls (path traversal + ledger races).

REG-24 (MED): syscalls.send() builds the inbox path as
BUS / f"inbox_{to_profile}" with NO sanitisation of to_profile — a profile
name containing ../ escapes the bus directory (path traversal on write).
REG-25 (MED): syscalls.ledger_spend() does a non-atomic read-modify-write on
registry.json with no file lock. Two concurrent spends can both pass the
balance check and overdraw the ledger (TOCTOU).
REG-26 (LOW): quarantine(category) interpolates category into the repair dir
path without validation -> path traversal via category.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

# The sibling VORPAL repo is local-only (no remote; not published), so in CI it
# is absent and these tests skip with a clear reason.
pytest.importorskip(
    "syscalls",
    reason="sibling VORPAL repo (syscalls) not available in CI",
)


@pytest.fixture()
def syscalls():
    import syscalls as sc
    return sc


def test_send_rejects_path_traversal_profile(syscalls, tmp_path: Path) -> None:
    """REG-24: a profile name must not escape the bus dir."""
    syscalls.BUS = tmp_path / "bus"
    with pytest.raises((ValueError, OSError)) or _noop():
        syscalls.send("../evil", "type", {"k": "v"})
    # After a failed/guarded send, nothing may exist above BUS.
    escaped = tmp_path / "evil"
    assert not escaped.exists(), "path-traversal profile created a dir outside BUS"


def test_ledger_spend_is_atomic_under_race(syscalls, tmp_path: Path) -> None:
    """REG-25: concurrent spends must not overdraw the ledger."""
    reg = tmp_path / "registry.json"
    reg.write_text('{"ledger_balance": 100}', encoding="utf-8")
    syscalls.REGISTRY = reg

    results = []
    lock = threading.Lock()

    def spender():
        r = syscalls.ledger_spend(70)
        with lock:
            results.append(r)

    threads = [threading.Thread(target=spender) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = [r for r in results if r == "P"]
    assert len(successes) <= 1, (
        f"3 concurrent spends of 70 on a 100 balance: {len(successes)} passed "
        "(TOCTOU overdraw)"
    )
    final = json.loads(reg.read_text(encoding="utf-8"))["ledger_balance"]
    assert final >= 0, "ledger went negative"


def test_quarantine_rejects_path_traversal_category(syscalls, tmp_path: Path) -> None:
    """REG-26: category must not escape the repair root."""
    syscalls.ROOT = tmp_path
    victim = tmp_path / "victim.py"
    victim.write_text("x=1", encoding="utf-8")
    with pytest.raises((ValueError, OSError)) or _noop():
        syscalls.quarantine(victim, category="../outside")
    assert not (tmp_path.parent / "outside").exists()


class _noop:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False
