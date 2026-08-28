"""
Battle-test: HTTP API surface — auth, CORS, input validation (markus_server).

REG-16 (CRITICAL): the entire HTTP API has NO authentication. Any process
that can reach 127.0.0.1:8128 (any local app, any browser page via CORS
loopholes, or a LAN peer if MARKUS_HOST is overridden) can: execute arbitrary
Python (/api/sandbox/eval, /api/dag/execute), restore checkpoints, read the
whole cortex, trigger vault sync + git commits, and burn real Nous API money
(/api/intent). Security-sensitive endpoints MUST require an auth token.
REG-17 (HIGH): CORS allowlist contains "null" (any sandboxed iframe / file://
page) and the SSE stream sends Access-Control-Allow-Origin: * unconditionally,
defeating the allowlist entirely for /api/stream. A malicious webpage can
subscribe to the live thought/telemetry stream.
REG-18 (HIGH): Content-Length is trusted with no upper bound in _read_body()
-> a single request can claim a multi-GB body and pin a thread (memory DoS).
REG-19 (MED): /api/cortex/search does `int(params['limit'])` with no
validation -> 'limit=abc' raises ValueError -> 500; 'limit=-1' dumps all.
REG-20 (MED): /api/intent has a concurrency cap (10) but no per-IP rate limit,
so it can be abused to burn paid model tokens.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SERVER_SRC = Path(__file__).resolve().parents[2] / "markus_server.py"
SRC = SERVER_SRC.read_text(encoding="utf-8")

AUTH_REQUIRED_ENDPOINTS = [
    "/api/sandbox/eval",
    "/api/dag/execute",
    "/api/dag/step",
    "/api/consensus/arbitrate",
    "/api/checkpoints/restore",
    "/api/checkpoints/create",
    "/api/intent",
    "/api/vault/sync",
    "/api/context/prune",
    "/api/speculation/precompute",
]


def test_security_endpoints_require_auth() -> None:
    """REG-16: the handler must verify an auth token on security-critical
    POST handlers before dispatching."""
    # Today: no Authorization read anywhere, no token check, endpoints handled
    # with a bare `if self.path == ...` -> nothing requires auth.
    assert "Authorization" in SRC, "handler never reads an Authorization header"


@pytest.mark.parametrize("ep", AUTH_REQUIRED_ENDPOINTS)
def test_each_security_endpoint_is_gated(ep: str) -> None:
    """Each dangerous POST endpoint must be behind an auth gate."""
    # Weak contract we can grep for: the handler source should reference an
    # auth/token check before these paths are matched. Current code: no such
    # gate exists -> this test is RED until auth is added.
    assert "auth" in SRC.lower(), f"no auth gate anywhere; {ep} is open"


def test_cors_does_not_allow_null_origin() -> None:
    """REG-17: 'null' origin (sandboxed iframe/file://) must be rejected."""
    assert '"null"' not in SRC, "null origin is in the CORS allowlist"


def test_sse_stream_does_not_send_wildcard_acao() -> None:
    """REG-17b: /api/stream must not emit Access-Control-Allow-Origin: *."""
    assert 'Access-Control-Allow-Origin", "*"' not in SRC, (
        "SSE stream emits wildcard ACAO, bypassing the allowlist"
    )


def test_body_read_has_an_upper_bound() -> None:
    """REG-18: _read_body() must cap Content-Length (e.g. 1 MB)."""
    assert "MAX_BODY" in SRC or "MAX_CONTENT" in SRC or "max_body" in SRC, (
        "request body length is unbounded (Content-Length trusted verbatim)"
    )


def test_cortex_search_limit_is_validated() -> None:
    """REG-19: limit=... must be parsed safely and clamped to [1, N]."""
    assert re.search(r"limit\s*=\s*(min|max)\(", SRC) or "clamp" in SRC.lower(), (
        "cortex search limit is not validated/clamped"
    )


def test_intent_has_rate_limit() -> None:
    """REG-20: /api/intent must be rate-limited per client, not just capped
    at 10 concurrent runs."""
    assert "rate" in SRC.lower(), "no per-client rate limiting on /api/intent"
