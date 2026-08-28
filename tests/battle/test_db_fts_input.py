"""
Battle-test: FTS5 / SQLite input handling (markus_db.PersistentCortexDB).

REG-05 (HIGH): malformed FTS5 queries (unterminated quotes, '*', '(', ')',
NEAR with bad args) raise sqlite3.OperationalError straight through the API
surface -> HTTP 500 / crash. Must be validated and rejected cleanly.
REG-06 (HIGH): negative or huge `limit` flows into `LIMIT ?` unvalidated;
SQLite treats LIMIT -1 as "unlimited" -> full table dump (data exposure).
REG-07 (LOW): query '(...)' / very large queries cause slow paths — no cap.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from markus_db import PersistentCortexDB


@pytest.fixture()
def db(tmp_path: Path) -> PersistentCortexDB:
    d = PersistentCortexDB(db_path=tmp_path / "cortex.db")
    for i in range(10):
        d.append_thought(f"t{i}", "AGENT", f"token alpha {i} beta", {"i": i})
    d.set_register("OS_STATUS", "BOOTED")
    d.set_register("PRIVATE_REGISTER", "s3cr3t")
    return d


@pytest.mark.parametrize("bad_query", [
    '"unterminated',
    "*",
    "(",
    ")",
    "NEAR(a b",
    "a OR b OR c OR d OR e",
    '"quote" NEAR(',
])
def test_malformed_fts_query_does_not_crash(db, bad_query: str) -> None:
    """REG-05: malformed FTS5 syntax must not raise OperationalError."""
    try:
        db.search_thoughts(bad_query, limit=5)
    except sqlite3.OperationalError as exc:  # current behaviour: crash
        pytest.fail(f"FTS query {bad_query!r} crashed with {exc!r}")


def test_negative_limit_is_clamped(db, tmp_path) -> None:
    """REG-06: limit=-1 must not dump the whole table.

    SQLite treats `LIMIT -1` as "no limit". The fixture alone only has 10
    matching rows, which would satisfy the old <= 10 assertion vacuously, so
    we insert enough rows to exceed the cap and prove the clamp.
    """
    for i in range(10, 25):
        db.append_thought(f"t{i}", "AGENT", f"token alpha {i} beta", {"i": i})
    rows = db.search_thoughts("token", limit=-1)
    assert len(rows) <= 10, f"negative limit returned {len(rows)} rows (unbounded)"


def test_huge_limit_is_capped(db, tmp_path) -> None:
    """REG-06b: a pathological limit must be bounded, not allocated."""
    for i in range(10, 130):
        db.append_thought(f"t{i}", "AGENT", f"token alpha {i} beta", {"i": i})
    rows = db.get_recent_thoughts(limit=10**9)
    assert len(rows) <= 100, f"huge limit returned {len(rows)} rows (unbounded)"


def test_sql_injection_cannot_read_registers(db) -> None:
    """REG-08: search must not let query escape into the registers table."""
    payload = "token') UNION SELECT val_json FROM registers --"
    rows = db.search_thoughts(payload, limit=5)
    for r in rows:
        assert "s3cr3t" not in json_safe(r), "register data leaked via search"


def json_safe(row) -> str:
    return str(row)
