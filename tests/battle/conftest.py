"""
conftest — battle-test suite bootstrap.

Adds the MARKUS-OS repo root and the sibling VORPAL repo to sys.path so tests
can import the real modules under test (no copies, no stubs). All tests use
temp dirs / fake secrets; they never touch the live vault, DB, or API.

These are REGRESSION tests: every test encodes the SECURE behaviour and
currently FAILS against the unpatched code (see battle-test-report.md).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VORPAL_ROOT = Path(os.environ.get(
    "BATTLE_TEST_VORPAL_ROOT",
    r"C:\Users\jonny\OneDrive\Desktop\VORPAL",
))

for _p in (REPO_ROOT, VORPAL_ROOT, VORPAL_ROOT / "CORE"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# Keep any accidental ledger/auth writes OUT of the real store.
os.environ.setdefault("MARKUS_RUN_LEDGER",
                      str(Path(os.environ.get("TEMP", "/tmp")) / "battletest_runs.db"))
