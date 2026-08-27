#!/usr/bin/env python3
"""End-to-end integration test across MARKUS, VORPAL, and Citadel."""
from __future__ import annotations
import json
import urllib.request
import uuid

MARKUS = "http://127.0.0.1:8128"

def req(path, method="GET", payload=None):
    data = json.dumps(payload).encode() if payload else None
    r = urllib.request.Request(MARKUS + path, data=data, method=method, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(r, timeout=15) as resp:
        return resp.status, json.loads(resp.read())

def main():
    results = []

    # 1. MARKUS health
    s, _ = req("/api/health")
    results.append(("MARKUS health", s == 200))

    # 2. Create run
    rid = "e2e-" + uuid.uuid4().hex
    s, b = req("/api/runs", "POST", {"run_id": rid, "goal_id": "GOAL_E2E", "mode": "FIELD"})
    trace = b.get("run", b)
    results.append(("Run created", s == 201 and trace.get("run_id") == rid))

    # 3. Transition: ROUTED
    s, _ = req(f"/api/runs/{rid}/transition", "POST", {"status": "ROUTED", "idempotency_key": "e2e-route"})
    results.append(("→ ROUTED", s == 200))

    # 4. Resume (simulating recovery)
    s, b = req(f"/api/runs/{rid}/resume", "POST", {"checkpoint": "intent-received", "prompt": "e2e-test"})
    run_data = b.get("run", b)
    events = {e["event_type"] for e in run_data.get("events", [])}
    results.append(("→ Resume", s == 200 and "RUNNING" in events))

    # 5. VORPAL status (external gate)
    s, b = req("/api/goals")
    results.append(("VORPAL goals live", s == 200 and b.get("goal_count") == 33))

    # 6. Trace page served (HTML, not JSON)
    r = urllib.request.Request(MARKUS + "/trace")
    with urllib.request.urlopen(r, timeout=15) as resp:
        trace_html = resp.read()
    results.append(("Trace page", resp.status == 200 and b"<title>MARKUS Run Trace" in trace_html))

    # 7. List runs
    s, b = req("/api/runs")
    results.append(("List runs", s == 200 and len(b["runs"]) > 0))

    # 8. Citadel recall (via citadel_recall module directly)
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("citadel_recall", "C:/Users/jonny/OneDrive/Desktop/The-Citadel-Vault/The-Citadel-Vault/scripts/citadel_recall.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["citadel_recall"] = mod
    spec.loader.exec_module(mod)
    hits = mod.search("MARKUS VORPAL", limit=5)
    results.append(("Citadel recall", bool(hits) and hits[0]["score"] > 0.5))

    # 9. Citadel write (provenance-bound)
    try:
        created = mod.create_note("E2E Test Note", "Verified via end-to-end test", section="Memory", source_run_id=rid, reason="e2e verification", evidence="[VERIFIED]")
        results.append(("Citadel write", bool(created.get("path")) and bool(created.get("sha256"))))
    except Exception as e:
        results.append(("Citadel write", False))

    # 10. Workspace parity
    spec2 = importlib.util.spec_from_file_location("mk_ws", "markus_workspace.py")
    ws_mod = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(ws_mod)
    import asyncio
    local = asyncio.run(ws_mod.LocalWorkspace().execute_python("print('WS_OK')"))
    sandbox = asyncio.run(ws_mod.SandboxWorkspace().execute_python("print('WS_OK')"))
    results.append(("Workspace parity", local.result.stdout.strip() == "WS_OK" and sandbox.result.stdout.strip() == "WS_OK"))

    # Report
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"{'PASS' if ok else 'FAIL'} - {name}")
    print(f"\n=== E2E: {passed}/{len(results)} passed ===")
    return 0 if passed == len(results) else 1

if __name__ == "__main__":
    raise SystemExit(main())
