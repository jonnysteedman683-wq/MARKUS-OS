# Survey Report: Requirement R2 — Offline IPC Bridge Synchronization

**Author**: Explorer 2 (Survey Phase)  
**Date**: 2026-08-27  
**Focus Area**: Offline IPC Bridge Synchronization (`markus_hermes_bridge.py`, `markus_vorpal_bridge.py`)  
**Acceptance Test Targets**: `hermes_verify_vorpal_bridge.py` (OVERALL: PASS), `hermes_verify_evolution_loops.py` (TOTAL PASS=7 TOTAL_FAIL=0), and `python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_db.py markus_context_pruner.py`

---

## 1. Executive Summary

Requirement R2 mandates robust **Offline IPC Bridge Synchronization** across the OMNIPRIME triad:
1. **MARKUS OS Microkernel & Memory Cortex** (`markus_kernel.py`, `markus_db.py`, `markus_ring_buffer.py`)
2. **HERMES Agent Integration Bridge** (`markus_hermes_bridge.py`)
3. **VORPAL Goal DAG & Evolve Synchronizer** (`markus_vorpal_bridge.py`)

Under air-gapped or offline conditions (network disconnected, remote endpoints unreachable, or asynchronous agent lifecycles), the bridges must:
- Prevent blocking, deadlocks, and unhandled exceptions.
- Provide persistent disk-backed offline queueing for outbound messages, intents, and telemetry snapshots.
- Perform automated disconnection recovery and FIFO buffer flushing once connectivity or target storage is re-established.
- Maintain cross-bridge synchronization via the MARKUS Memory Cortex L2/L3 substrate.
- Satisfy all verification criteria in `hermes_verify_vorpal_bridge.py` (`OVERALL: PASS`) and `hermes_verify_evolution_loops.py` (`TOTAL PASS=7`).

---

## 2. Current Architecture & Codebase Inspection

### 2.1 `markus_hermes_bridge.py`
- **Location**: `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\markus_hermes_bridge.py` (112 lines)
- **Current Role**: Bidirectional bridge adapter between the MARKUS OS microkernel and Hermes Agent gateway.
- **Key Components**:
  - `HermesBridgeConfig` (lines 28–34):
    - `hermes_host: str = "http://localhost:8080"`
    - `markus_profile: str = "markus"`
    - `private_workspace_root: Path = Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private")`
    - `poll_interval_s: float = 2.0`
  - `MarkusHermesBridge` (lines 35–91):
    - `init_private_infra()` (lines 44–64): Creates directories (`workspace`, `logs`, `vault`, `ipc`) and sets memory registers `"HERMES_BRIDGE_STATUS": "READY"` and `"MARKUS_PRIVATE_INFRA"`.
    - `send_to_hermes_session(prompt: str)` (lines 65–84): Commits thought to `kernel.memory`, posts `KernelMessage` with `topic="HERMES_OUTBOUND"`.
    - `bridge_daemon(kernel, proc)` (lines 85–91): Async background task that currently only loops `await asyncio.sleep(...)`.
  - Standalone entrypoint `start_markus_with_bridge()` (lines 92–111).
- **Deficiencies & Gaps Identified**:
  1. **No Offline Queueing**: If Hermes gateway is offline / unreachable, messages are posted only to in-memory `KernelMessage` queue and not persisted to disk for offline queuing.
  2. **No Transport or HTTP Client**: `send_to_hermes_session` lacks actual REST delivery / connection probing logic to `http://localhost:8080`.
  3. **No Buffer Draining / Flushing**: `bridge_daemon` does not monitor an outbound queue or drain offline spools upon reconnection.
  4. **Path Inflexibility**: `private_workspace_root` hardcodes a specific path; it should support `MARKUS_PRIVATE_ROOT` / `HERMES_PRIVATE_ROOT` environment variables with fallback.
  5. **Missing Self-Test / Status API**: Lacks a standalone test routine (`_self_test()`) returning exit code 0 for CI/verification.

### 2.2 `markus_vorpal_bridge.py`
- **Location**: `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\markus_vorpal_bridge.py` (294 lines)
- **Current Role**: Bidirectional file-based bridge synchronizing VORPAL Markdown goal DAGs/notes to MARKUS and writing MARKUS telemetry back to VORPAL.
- **Key Components**:
  - Environment paths (lines 41–53): `VORPAL_ROOT`, `GOALS_PATH`, `NOTES_PATH`, `SOUL_PATH`, `MARKUS_LEDGER_PATH`.
  - `VORPALGoal` & `VORPALStatus` dataclasses (lines 55–80) with `goal_pulse` property (`open_goal_count / goal_count`).
  - `MarkusVorpalBridge` (lines 82–246):
    - `read_vorpal_status()`: Downstream parser for `GOALS.md`, `NOTES.md`, and `SOUL.md`.
    - `write_markus_telemetry()`: Upstream writer for `MARKUS_LEDGER_PATH` (`EVOLVE/MARKUS_TELEMETRY.json`).
    - `snapshot_from_markus()`: Pulls live status from `markus_adaptive_matrix`, `markus_network_intel`, and server health.
    - `vorpal_goal_weight_bias()`: Calculates dynamic dice engine bias.
  - `_self_test()` (lines 248–273): Full self-test verifying goal parsing and telemetry writing.
- **Deficiencies & Gaps Identified**:
  1. **Telemetry Spooling on Detached Storage**: If `VORPAL_ROOT` is inaccessible (e.g. disconnected drive or air-gapped machine without VORPAL clone), telemetry writes return `None` without saving to a local offline spool.
  2. **Cross-Bridge Ingestion**: No direct helper to pass parsed VORPAL goals/status into the Hermes bridge or kernel registers for HERMES task claiming.

### 2.3 `hermes_verify_vorpal_bridge.py`
- **Location**: `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\hermes_verify_vorpal_bridge.py` (87 lines)
- **Verified Assertions**:
  1. `py_compile.compile("markus_vorpal_bridge.py", doraise=True)` -> PASS.
  2. Subprocess execution `python markus_vorpal_bridge.py` -> exit code 0, contains "PASSED" -> PASS.
  3. Real VORPAL goal DAG parsing (when path exists): `st.goal_count >= 20`, `0.0 <= st.goal_pulse <= 1.0`, `st.implemented_goal_count > 0` -> PASS (`goals=35`, `pulse=0.029`, `implemented=26`).
  4. Telemetry write path to temp ledger -> PASS.
  5. Telemetry payload schema validation -> PASS (`server_ok == True`).
  6. Fail-open on non-existent VORPAL root -> PASS (`goal_count == 0`).
- **Current Execution Status**: **OVERALL: PASS**.

### 2.4 `hermes_verify_evolution_loops.py`
- **Location**: `C:\Users\jonny\OneDrive\Desktop\MARKUS-OS\hermes_verify_evolution_loops.py` (172 lines)
- **Verified Gates**:
  - G1: `py_compile` AST gate on `markus_reflexion.py`, `markus_population_dice.py`, `markus_redteam.py`.
  - G2: `ReflexionLoopEngine` self-test (`_test_reflexion`).
  - G3: `ReflexionLoopEngine` contract verification.
  - G4: `PopulationDiceEngine` self-test (`_test_population_dice`).
  - G5: `PopulationDiceEngine` contract verification.
  - G6: `RedTeamOrchestrator` self-test (`_test_redteam`).
  - G7: `RedTeamOrchestrator` contract verification.
- **Current Execution Status**: **TOTAL PASS=7 TOTAL_FAIL=0**.

---

## 3. Detailed Gap Analysis & Requirements Mapping for R2

| Dimension | Current Implementation | Target R2 Requirement | Proposed Design |
|---|---|---|---|
| **Hermes Bridge Offline Queue** | In-memory `asyncio.Queue` only; messages lost on restart or offline | Persistent disk-backed spool (`ipc/offline_queue.jsonl` or SQLite) | Append-only JSONL queue with item IDs, timestamps, and retry counters. |
| **Hermes Gateway Connection Detection** | None (assumes always running or ignores) | Probe `/api/health` or `/status` with short timeout; fallback to offline mode | Fast-probe helper with `CircuitBreaker` / timeout; sets `is_offline` flag. |
| **Queue Flushing / Reconnection** | No queue drainage loop | Daemon auto-detects connectivity and drains offline queue in FIFO order | Background worker reads unconsumed items, sends to gateway, removes from spool. |
| **VORPAL Telemetry Spooling** | Returns `None` when `VORPAL_ROOT` absent | Writes to local offline spool (`markus_private/ipc/vorpal_telemetry_spool.json`) | Local fallback buffer with timestamped snapshots, syncs when VORPAL root is mounted. |
| **Cross-Bridge Synchronization** | Independent silos | VORPAL status -> MARKUS Cortex -> Hermes task bridge | Memory registers `VORPAL_GOAL_STATUS` and `HERMES_OUTBOUND_QUEUE` accessible across modules. |
| **AST & Self-Tests** | Vorpal bridge has self-test; Hermes bridge has basic boot script | Both modules pass AST compilation and comprehensive self-tests | Add full offline test harness to `markus_hermes_bridge.py`. |

---

## 4. Proposed Implementation Details for R2

### 4.1 `markus_hermes_bridge.py` Enhancements
1. **Persistent Offline Queue Manager**:
   - Define `HermesOfflineMessage` dataclass: `msg_id`, `topic`, `payload`, `created_at`, `status`, `attempts`.
   - File path: `config.private_workspace_root / "ipc" / "hermes_offline_queue.jsonl"`.
   - Methods:
     - `enqueue_offline(msg: KernelMessage) -> bool`
     - `get_pending_offline_count() -> int`
     - `flush_offline_queue(max_batch: int = 50) -> int`
2. **Connectivity Prober & Offline Gate**:
   - `check_gateway_connectivity(timeout_s: float = 1.0) -> bool`:
     - Tries connecting to `http://localhost:8080/health` or `http://localhost:8080/api/status`.
     - Returns `False` on connection refused or timeout without raising.
3. **Smart Message Dispatching**:
   - In `send_to_hermes_session(prompt: str, force_offline: bool = False)`:
     - If gateway reachable and not `force_offline`: dispatch HTTP POST / gateway payload.
     - Else: enqueue into `hermes_offline_queue.jsonl` and record thought in L2/L3 cortex: `"Queued offline Hermes intent: <id>"`.
4. **Daemon Drainage Loop**:
   - In `bridge_daemon(kernel, proc)`:
     - Check gateway health.
     - If online and offline queue > 0: call `flush_offline_queue()`.
     - Forward incoming Hermes thoughts/events to `kernel.memory`.
5. **Self-Test Function**:
   - Add `_self_test_hermes_bridge()` that tests:
     - Infra initialization.
     - Offline queueing when gateway is offline.
     - Offline queue persistence across instances.
     - Queue flush simulation.
     - Clean exit with `[OK] Markus-Hermes Bridge: PASSED`.

### 4.2 `markus_vorpal_bridge.py` Enhancements
1. **Offline Telemetry Spooling**:
   - In `write_markus_telemetry()`:
     - If `VORPAL_ROOT.exists()`: write `MARKUS_LEDGER_PATH`.
     - If `not VORPAL_ROOT.exists()`: write to fallback local spool: `DEFAULT_LOCAL_SPOOL = Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/ipc/vorpal_telemetry_spool.json")`.
     - Return the path written.
2. **Sync Outbound Spool**:
   - When VORPAL directory becomes available, `sync_offline_spool()` copies the latest offline telemetry to `MARKUS_LEDGER_PATH`.
3. **Cross-Bridge Data Bridge**:
   - Add `sync_vorpal_to_memory(memory_cortex)`: sets registers `VORPAL_GOAL_PULSE`, `VORPAL_OPEN_GOALS`, `VORPAL_STATUS_SUMMARY`.

---

## 5. Verification Protocol

The implementation must be validated against the following commands:

```bash
# 1. AST compilation of all target modules
python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_db.py markus_context_pruner.py markus_vorpal_bridge.py

# 2. VORPAL Bridge Verification (Must output OVERALL: PASS)
python hermes_verify_vorpal_bridge.py

# 3. Evolution Loops Verification (Must output TOTAL PASS=7 TOTAL_FAIL=0)
python hermes_verify_evolution_loops.py

# 4. Hermes Bridge Standalone Self-Test
python markus_hermes_bridge.py
```

---

## 6. Risk Assessment & Invariants

1. **Zero External Dependency Invariant**: Both bridges must remain strictly standard-library-only (`urllib.request`, `json`, `sqlite3`, `pathlib`, `dataclasses`).
2. **Fail-Open Invariant**: Never crash or raise uncaught exceptions when paths, networks, or ports are absent.
3. **Verification Invariant**: `hermes_verify_vorpal_bridge.py` tests specific line attributes and return types; all existing method signatures and return value formats must be preserved.
