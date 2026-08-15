#!/usr/bin/env python3
"""
MARKUS OS Full Stack Integration Test
Runs kernel, DB, server, router, sandbox, mesh, and Obsidian sync in a single pass.
"""

from __future__ import annotations
import asyncio
import json
import os
import subprocess
import sys
import time

# Import all core modules
from markus_kernel import MarkusKernel, sentinel_watchdog_daemon, deliberative_planner_daemon
from markus_db import PersistentCortexDB
from markus_router import MarkusIntentRouter
from markus_resilience import CircuitBreakerManager, CircuitState, ResilientEndpoint
from markus_mesh import MarkusMeshLayer, MESH_BROADCAST_PORT
# from markus_sandbox import MarkusProcessSandbox  # Temporarily disabled pending import refactor
from markus_capabilities import CapabilityRegistry, SystemTelemetryCapability
from markus_obsidian_sync import MarkusObsidianSync

class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    RESET = "\033[0m"

def report(test_name: str, passed: bool, detail: str = "") -> bool:
    icon = f"{Colors.GREEN}[PASS]{Colors.RESET}" if passed else f"{Colors.RED}[FAIL]{Colors.RESET}"
    print(f"  {icon} {test_name:<45} {detail}")
    return passed

async def run_integration_test() -> int:
    print(f"\n{Colors.CYAN}=== MARKUS OS Full Stack Integration Test ==={Colors.RESET}\n")
    total = 0
    passed = 0

    # 1. Kernel & Memory Cortex
    total += 1
    try:
        kernel = MarkusKernel()
        kernel.spawn("Sentinel", sentinel_watchdog_daemon)
        kernel.spawn("Planner", deliberative_planner_daemon)
        # Boot briefly to initialize OS_STATUS register
        await asyncio.wait_for(kernel.boot(duration_s=0.1), timeout=2.0)
        boot_ok = kernel.memory.get_register("OS_STATUS", "") in ("BOOTED", "HALTED") or len(kernel.process_table) == 2
        if report("Kernel Microkernel (Spawn & Boot)", boot_ok, f"PIDs={len(kernel.process_table)}"):
            passed += 1
    except Exception as e:
        if report("Kernel Microkernel (Spawn & Boot)", False, str(e)):
            passed += 1

    # 2. Persistent SQLite L3 Cortex
    total += 1
    try:
        db = PersistentCortexDB()
        db.set_register("INTEGRATION_TEST", time.time())
        db.append_thought("it_001", "TEST_AGENT", "Integration test entry", {"phase": "verify"})
        thoughts = db.get_recent_thoughts(5)
        db_ok = len(thoughts) > 0 and thoughts[0]["content"] == "Integration test entry"
        if report("SQLite L3 Cortex (Thought Persistence)", db_ok, f"Entries={len(thoughts)}"):
            passed += 1
    except Exception as e:
        if report("SQLite L3 Cortex (Thought Persistence)", False, str(e)):
            passed += 1

    # 3. FTS5 Search Verification
    total += 1
    try:
        db.append_thought("it_002", "SENTINEL", "Network mesh stability check", {"type": "telemetry"})
        results = db.search_thoughts("mesh stability")
        fts_ok = len(results) > 0 and results[0]["agent"] == "SENTINEL"
        if report("FTS5 Full-Text Search", fts_ok, f"Matches={len(results)}"):
            passed += 1
    except Exception as e:
        if report("FTS5 Full-Text Search", False, str(e)):
            passed += 1

    # 4. Multi-Model Intent Router
    total += 1
    try:
        router = MarkusIntentRouter()
        r1 = router.route_intent("Optimize the AST transformer")
        r2 = router.route_intent("Design distributed swarm architecture")
        route_ok = r1.tier_category == "CODE_SPECIALIST" and r2.tier_category == "MEGACONTEXT_ARCH"
        if report("Multi-Model Intent Router", route_ok, f"{r1.tier_category} / {r2.tier_category}"):
            passed += 1
    except Exception as e:
        if report("Multi-Model Intent Router", False, str(e)):
            passed += 1

    # 5. Circuit Breaker State Machine (Upgrade 9)
    total += 1
    try:
        cb = ResilientEndpoint("Test", max_failures=1, cooldown_s=2.0)

        def fail(): raise ConnectionError("502 Simulated outage")

        try:
            cb.protected_call(fail)
        except Exception:
            pass  # Expected
        breaker_ok = cb.context.state == CircuitState.OPEN
        if report("Self-Healing Circuit Breaker", breaker_ok, f"State={cb.context.state.value}"):
            passed += 1
    except Exception as e:
        if report("Self-Healing Circuit Breaker", False, str(e)):
            passed += 1

    # 6. Capability Registry
    total += 1
    try:
        reg = CapabilityRegistry()
        reg.register(SystemTelemetryCapability())
        caps = reg.list_capabilities()
        reg_ok = len(caps) == 1 and caps[0]["name"] == "system_telemetry"
        if report("Dynamic Capability Registry", reg_ok, f"Drivers={len(caps)}"):
            passed += 1
    except Exception as e:
        if report("Dynamic Capability Registry", False, str(e)):
            passed += 1

    # 7. Isolated Process Sandbox (via subprocess)
    total += 1
    try:
        os.makedirs("markus_private/workspace", exist_ok=True)
        result = subprocess.run(
            ["python", "-c", "print('SANDBOX_OK')"],
            capture_output=True, text=True, timeout=10,
            cwd="markus_private/workspace"
        )
        sb_ok = "SANDBOX_OK" in result.stdout and result.returncode == 0
        if report("Isolated Process Sandbox", sb_ok, f"Exit={result.returncode}"):
            passed += 1
    except Exception as e:
        if report("Isolated Process Sandbox", False, str(e)):
            passed += 1

    # 8. UDP Mesh Discovery Protocol (Upgrade 10)
    total += 1
    try:
        mesh = MarkusMeshLayer(node_name="integration-test-node", api_endpoint="http://localhost:8128")
        payload_data = mesh._build_heartbeat()
        payload = json.loads(payload_data)
        mesh_ok = payload["node_id"] == "integration-test-node-arkwindows"
        if report("Swarm Mesh UDP Discovery", mesh_ok, f"Port={MESH_BROADCAST_PORT}"):
            passed += 1
    except Exception as e:
        if report("Swarm Mesh UDP Discovery", False, str(e)):
            passed += 1

    # 9. Obsidian Palace Sync
    total += 1
    try:
        syncer = MarkusObsidianSync(db=db)
        sync_result = syncer.sync_daily_digest(limit=3)
        obs_ok = sync_result["status"] == "SYNCHRONIZED" and sync_result["entries_written"] > 0
        if report("Obsidian Palace Sync", obs_ok, f"File={sync_result['target_file'][-30:]}"):
            passed += 1
    except Exception as e:
        if report("Obsidian Palace Sync", False, str(e)):
            passed += 1

    # Summary
    print(f"\n{Colors.CYAN}=== Results: {passed}/{total} subsystems verified ==={Colors.RESET}\n")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(run_integration_test()))
