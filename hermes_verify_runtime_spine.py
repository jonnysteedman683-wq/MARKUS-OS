#!/usr/bin/env python3
"""HTTP smoke check for MARKUS health, SSE, and durable run trace APIs."""
from __future__ import annotations
import json
import urllib.request

BASE = "http://127.0.0.1:8128"

def request(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.status, response.read()

def main():
    status, body = request("/api/health")
    health = json.loads(body)
    assert status == 200 and health["status"] == "ONLINE"
    req = urllib.request.Request(BASE + "/api/stream")
    with urllib.request.urlopen(req, timeout=8) as response:
        line1 = response.readline().decode().strip()
        line2 = response.readline().decode().strip()
    assert line1 == "event: handshake" and "STREAM_CONNECTED" in line2
    status, body = request("/api/runs", "POST", {"run_id":"smoke-run", "goal_id":"GOAL_SMOKE", "mode":"FIELD"})
    assert status == 201
    status, body = request("/api/runs/smoke-run/transition", "POST", {"status":"ROUTED", "idempotency_key":"smoke-route"})
    assert status == 200
    status, body = request("/api/runs/smoke-run")
    trace = json.loads(body)
    assert status == 200 and trace["run"]["run_id"] == "smoke-run" and trace["events"]
    print("PASS - health ONLINE")
    print("PASS - SSE handshake")
    print("PASS - run create/transition/trace")
    print("OVERALL: PASS")

if __name__ == "__main__":
    main()
