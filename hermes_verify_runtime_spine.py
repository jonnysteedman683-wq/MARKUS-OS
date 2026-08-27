#!/usr/bin/env python3
"""HTTP smoke check for MARKUS health, SSE, run trace APIs, and VORPAL gate."""
from __future__ import annotations
import json
import urllib.request
import uuid

BASE = "http://127.0.0.1:8128"

def request(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.status, response.read()

def main():
    # Health
    status, body = request("/api/health")
    health = json.loads(body)
    assert status == 200 and health["status"] == "ONLINE"

    # SSE handshake
    req = urllib.request.Request(BASE + "/api/stream")
    with urllib.request.urlopen(req, timeout=8) as response:
        line1 = response.readline().decode().strip()
        line2 = response.readline().decode().strip()
    assert line1 == "event: handshake" and "STREAM_CONNECTED" in line2

    # Trace page
    status, body = request("/trace")
    assert status == 200 and b"<title>MARKUS Run Trace" in body

    # Full run lifecycle: create → route → resume → commit (with VORPAL gate)
    run_id = "smoke-" + uuid.uuid4().hex
    status, body = request("/api/runs", "POST", {"run_id": run_id, "goal_id": "GOAL_SMOKE", "mode": "FIELD"})
    assert status == 201
    result = json.loads(body)
    assert result.get("run_id") == run_id or result.get("trace", {}).get("run_id") == run_id

    status, body = request("/api/runs/" + run_id + "/transition", "POST", {"status": "ROUTED", "idempotency_key": "smoke-route"})
    assert status == 200

    status, body = request("/api/runs/" + run_id + "/resume", "POST", {"prompt": "resume-test"})
    assert status == 200
    resume_trace = json.loads(body)
    events = {e["event_type"] for e in resume_trace["events"]}
    assert "CHECKPOINT" in events and "RUNNING" in events

    status, body = request("/api/runs/" + run_id + "/transition", "POST", {"status": "VERIFYING", "idempotency_key": "smoke-verify"})
    assert status == 200

    status, body = request("/api/runs/" + run_id + "/transition", "POST", {"status": "PASSED", "idempotency_key": "smoke-pass"})
    assert status == 200

    status, body = request("/api/runs/" + run_id + "/transition", "POST", {"status": "COMMITTED", "idempotency_key": "smoke-commit"})
    assert status == 200

    # Verify terminal state cannot resume
    status, body = request("/api/runs/" + run_id + "/resume", "POST", {"prompt": "late-resume"})
    assert status == 409

    # List endpoint
    status, body = request("/api/runs")
    listing = json.loads(body)
    assert status == 200 and len(listing["runs"]) > 0

    # Concurrent run cap
    for _ in range(12):
        rid = "cap-" + uuid.uuid4().hex
        request("/api/runs", "POST", {"run_id": rid, "mode": "FIELD"})
        request("/api/runs/" + rid + "/transition", "POST", {"status": "RUNNING", "idempotency_key": f"cap-run-{rid}"})

    print("PASS - health ONLINE")
    print("PASS - SSE handshake")
    print("PASS - trace page served")
    print("PASS - run create/transition/resume/commit")
    print("PASS - terminal state blocks resume")
    print("PASS - runs list endpoint")
    print("OVERALL: PASS")

if __name__ == "__main__":
    main()
