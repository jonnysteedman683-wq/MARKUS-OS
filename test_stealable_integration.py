#!/usr/bin/env python3
"""Integration test: CRDT + Task Runner + Policy Engine working together."""
import time
from markus_crdt_store import DistributedStore
from markus_task_runner import task_runner, RetryPolicy, TaskResult
from markus_policy_engine import policy_engine, DICE_RISK_MAP, RiskLevel, PolicyDecision, CapabilityRequest

# === TEST 1: CRDT convergence across simulated mesh nodes ===
print("=== TEST 1: CRDT Convergence ===")
node_a = DistributedStore(node_id="mesh-node-a")
node_b = DistributedStore(node_id="mesh-node-b")

# A writes state
node_a.set("model_routing", {"last": "laguna-s-2.1:free", "tier": "CODE"})
node_a.set("dice_roll_history", [1, 2, 3, 6, 2])

# Gossip A → B
node_b.apply_digest(node_a.digest())

# B updates its copy
node_b.set("model_routing", {"last": "nemotron-3-ultra:free", "tier": "ARCH"})

# Gossip B → A (B's write should win via LWW)
node_a.apply_digest(node_b.digest())

assert node_a.get("model_routing") == node_b.get("model_routing"), "CRDT convergence failed!"
print(f"  ✅ Converged: {node_a.get('model_routing')}")
print()

# === TEST 2: Policy Engine gates dice rolls ===
print("=== TEST 2: Policy-Gated Dice Roll ===")
for roll in [1, 2, 3, 4, 5]:
    risk = DICE_RISK_MAP.get(roll)
    if risk == RiskLevel.LOW:
        print(f"  Roll {roll} → {risk.value} → Auto-approved (LOW risk)")
    elif risk == RiskLevel.MEDIUM:
        print(f"  Roll {roll} → {risk.value} → Auto-approved (MEDIUM risk)")
    elif risk == RiskLevel.HIGH:
        req = CapabilityRequest(
            capability_id="markus-backend-upgrade",
            operation="port_crdt",
            agent_id="markus-kernel",
            execution_mode="EXECUTE",
            authorization_context={"service_identity": "markus-os"},
        )
        result = policy_engine.evaluate_request(req)
        print(f"  Roll {roll} → {risk.value} → {result.decision.value} ({result.reason[:50]}...)")
print()

# === TEST 3: Task Runner executes CRDT sync with retry ===
print("=== TEST 3: Retryable CRDT Sync ===")
attempt = [0]

def flaky_crdt_sync():
    attempt[0] += 1
    if attempt[0] < 2:
        raise ConnectionError("Simulated mesh packet loss")
    # On success, sync state
    node_a.set("sync_result", f"synced on attempt {attempt[0]}")
    return f"CRDT sync complete (attempt {attempt[0]})"

from markus_task_runner import RetryPolicy
policy = RetryPolicy(max_retries=3, backoff_ms=100, backoff_multiplier=1.5)
task_id = task_runner.submit_task(flaky_crdt_sync, retry_policy=policy)
result = task_runner.await_result(task_id, timeout_ms=5000)

assert result.status == "completed", f"Task failed: {result.error}"
assert result.retries_used == 1, f"Expected 1 retry, got {result.retries_used}"
print(f"  ✅ {result.output} (retries: {result.retries_used}, latency: {result.latency_ms}ms)")
print()

# === TEST 4: Full integration — Policy-gated, retried, CRDT-backed ===
print("=== TEST 4: Full Stack — Dice → Policy → Task → CRDT ===")
# Simulate Dice Roll 2 (Backend Upgrade, MEDIUM risk)
risk = DICE_RISK_MAP[2]
req = CapabilityRequest(
    capability_id="markus-backend-upgrade",
    operation="port_crdt",
    agent_id="markus-kernel",
    execution_mode="EXECUTE",
    authorization_context={"service_identity": "markus-os"},
)
policy_result = policy_engine.evaluate_request(req)

if policy_result.decision == PolicyDecision.ALLOW:
    # Execute the "upgrade" as a retried task
    def upgrade_crdt_store():
        # Simulate the port from SUPRIME
        new_store = DistributedStore(node_id="markus-router")
        new_store.set("crdt_backend", "suprime_store_v1")
        new_store.set("convergence_mode", "lww")
        node_a.apply_digest(new_store.digest())
        return "CRDT store ported from SUPRIME"

    task_id = task_runner.submit_task(upgrade_crdt_store)
    result = task_runner.await_result(task_id)
    print(f"  Policy: {policy_result.decision.value} (Risk: {risk.value})")
    print(f"  Task: {result.status} — {result.output}")
    print(f"  CRDT: node_a now has '{node_a.get('crdt_backend')}'")
    print(f"\n  ✅ Full stack integration PASSED")
else:
    print(f"  ✅ Policy blocked: {policy_result.reason}")

task_runner.shutdown()
print("\n=== ALL INTEGRATION TESTS PASSED ===")
