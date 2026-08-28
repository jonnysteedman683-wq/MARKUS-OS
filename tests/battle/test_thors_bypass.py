"""
Battle-test: Thors retaliation engine bypasses (markus_thors).

REG-09 (HIGH): Thors trusts 127.0.0.1 / ::1 unconditionally
(TRUSTED_IPS), and the server binds 127.0.0.1 by default — so every real
request is "trusted loopback" and NO attack payload is ever analyzed. The
entire WAF is a no-op for the primary deployment.
REG-10 (MED): ThorsEngine._load_state() calls db.cortex_query(), which does
NOT exist on PersistentCortexDB (it exposes cortex_execute). State loading
silently no-ops -> attacker profiles never persist across restarts, so
blocking never survives a reboot and retaliation state is volatile.
REG-11 (MED): analysis only looks at body+path text; a payload that reaches
the code-exec endpoints via JSON values (not raw text) may dodge pattern
detection; and the pattern list misses common shell/`;` variants.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from markus_db import PersistentCortexDB
from markus_thors import ThorsEngine


@pytest.fixture()
def db(tmp_path: Path) -> PersistentCortexDB:
    return PersistentCortexDB(db_path=tmp_path / "thors.db")


@pytest.fixture()
def thors(db) -> ThorsEngine:
    t = ThorsEngine(cortex_db=db)
    t._init_cortex_tables()
    return t


def test_attack_detected_from_loopback(thors) -> None:
    """REG-09: an SQLi payload from 127.0.0.1 must NOT be waved through."""
    v = thors.analyze_request("POST", "/api/chat", {},
                              "'; DROP TABLE users; --", "127.0.0.1")
    assert v.threat_level > 0, "SQLi from loopback was not detected"


def test_path_traversal_detected_from_loopback(thors) -> None:
    v = thors.analyze_request("GET", "/../../../etc/passwd", {}, "", "127.0.0.1")
    assert v.threat_level > 0, "path traversal from loopback was not detected"


def test_forbidden_call_detected_from_loopback(thors) -> None:
    v = thors.analyze_request("POST", "/api/sandbox/eval", {},
                              "exec(open('/etc/passwd').read())", "127.0.0.1")
    assert v.threat_level > 0, "forbidden call from loopback was not detected"


def test_block_persists_across_engine_restart(db) -> None:
    """REG-10: a blocked attacker must still be blocked after restart."""
    t1 = ThorsEngine(cortex_db=db)
    t1._init_cortex_tables()
    v = t1.analyze_request("GET", "/api/chat", {},
                           "'; DROP TABLE users; --", "10.0.0.99")
    t1.retaliate(v, request_handler=None)

    t2 = ThorsEngine(cortex_db=db)  # fresh engine, same DB
    assert t2.is_blocked("10.0.0.99"), "blocked IP was forgotten across restart"


def test_code_exec_payload_in_json_body_detected(thors) -> None:
    """REG-11: attack payloads nested in JSON must still trip detection."""
    body = json.dumps({"code": "exec(compile('import os', '<s>', 'exec'))"})
    v = thors.analyze_request("POST", "/api/sandbox/eval", {}, body, "10.0.0.99")
    assert v.threat_level > 0, "exec payload inside JSON body not detected"
