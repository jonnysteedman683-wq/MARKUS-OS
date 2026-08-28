# Handoff Report: Requirement R2 (Offline IPC Bridge Synchronization)

## 1. Observation
- **`markus_hermes_bridge.py`**:
  - Contains `HermesBridgeConfig` (defaulting `private_workspace_root` to `C:/Users/jonny/OneDrive/Desktop/New folder/markus_private` and `hermes_host` to `http://localhost:8080`).
  - Contains `MarkusHermesBridge` with methods `init_private_infra()`, `send_to_hermes_session()`, and `bridge_daemon()`.
  - Currently, `send_to_hermes_session()` only logs a thought in `kernel.memory` and queues a `KernelMessage(topic="HERMES_OUTBOUND")`. No disk-backed offline spooling, connection checking, or persistent queue exists.
  - `bridge_daemon()` currently executes an idle sleep loop without draining queued offline events or checking gateway health.
- **`markus_vorpal_bridge.py`**:
  - Implements `MarkusVorpalBridge`, `VORPALStatus`, and parsers for `GOALS.md`, `NOTES.md`, and `SOUL.md`.
  - Implements `write_markus_telemetry()`, which writes JSON telemetry to `MARKUS_LEDGER_PATH` (`EVOLVE/MARKUS_TELEMETRY.json`) and fails open by returning `None` if `VORPAL_ROOT` does not exist.
  - Passes its internal self-test (`_self_test()`) with `[OK] Markus-Vorpal Bridge: PASSED`.
- **`hermes_verify_vorpal_bridge.py`**:
  - Runs `py_compile`, module self-test, real VORPAL goal DAG parse, temp ledger write, telemetry validation, and fail-open test.
  - Direct execution: `OVERALL: PASS`.
- **`hermes_verify_evolution_loops.py`**:
  - Runs 7 verification gates (AST gate, Reflexion self-test/contract, Population Dice self-test/contract, RedTeam self-test/contract).
  - Direct execution: `TOTAL PASS=7 TOTAL_FAIL=0 (of 7)`, `RESULT: PASS`.
- **`py_compile` on target modules**:
  - Executed `python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_db.py markus_context_pruner.py`.
  - Output: Exit code 0, all compiled cleanly.

## 2. Logic Chain
1. *Observation*: Air-gapped / offline operation requires that MARKUS OS communicate reliably with HERMES and VORPAL even when networks are disconnected or subsystems start up asynchronously.
2. *Inference from `markus_hermes_bridge.py`*: In-memory queueing is insufficient for offline air-gapped environments because unsent messages are lost across restarts or when Hermes is not yet active. A disk-backed FIFO queue (`hermes_offline_queue.jsonl` under `private_workspace_root / "ipc"`) is required.
3. *Inference from `markus_vorpal_bridge.py`*: While file-based parsing is naturally offline-compatible, missing `VORPAL_ROOT` currently causes telemetry writes to be dropped rather than spooled locally. Adding a local spool buffer under `markus_private/ipc/vorpal_telemetry_spool.json` ensures zero telemetry loss.
4. *Inference from Verification Harnesses*: Any updates to `markus_vorpal_bridge.py` and `markus_hermes_bridge.py` must strictly preserve existing method signatures, fail-open contracts, and dataclass fields to keep `hermes_verify_vorpal_bridge.py` and `hermes_verify_evolution_loops.py` passing at 100%.

## 3. Caveats
- `hermes_verify_evolution_loops.py` relies on `markus_reflexion.py`, `markus_population_dice.py`, and `markus_redteam.py`. While those modules pass today, their memory cortex thought emission touches `markus_db.py` (which is being updated in R3). Cross-requirement regression testing is critical.
- On Windows systems with non-UTF-8 console code pages (e.g. cp1252), emoji output in standalone print statements can cause `UnicodeEncodeError` in certain scripts if not properly sanitized or encoded. Ensure all bridge logging and self-test outputs use ASCII or properly configured UTF-8 streams.

## 4. Conclusion
Requirement R2 is clearly defined and ready for implementation. The primary implementation deliverables are:
1. Enhancing `markus_hermes_bridge.py` with:
   - Persistent offline JSONL queue (`enqueue_offline`, `flush_offline_queue`, `get_pending_offline_count`).
   - Gateway health probe (`check_gateway_connectivity`) and offline fallback.
   - Background drainage loop in `bridge_daemon`.
   - Comprehensive self-test (`_self_test()`).
2. Enhancing `markus_vorpal_bridge.py` with:
   - Local offline telemetry fallback spooling when `VORPAL_ROOT` is absent.
   - Outbound spool flush routine upon reconnection.
   - Cross-bridge cortex memory synchronization.
3. Maintaining 100% pass on all existing verification suites (`hermes_verify_vorpal_bridge.py`, `hermes_verify_evolution_loops.py`, `py_compile`).

## 5. Verification Method
Independently verify all findings and test suites by executing the following commands from workspace root (`C:\Users\jonny\OneDrive\Desktop\MARKUS-OS`):

```bash
# Test 1: Compile all core targets
python -m py_compile markus_router.py markus_brain_backend.py markus_hermes_bridge.py markus_db.py markus_context_pruner.py markus_vorpal_bridge.py

# Test 2: Run VORPAL Bridge Verification (Expect: OVERALL: PASS)
python hermes_verify_vorpal_bridge.py

# Test 3: Run Evolution Loops Verification (Expect: TOTAL PASS=7 TOTAL_FAIL=0)
python hermes_verify_evolution_loops.py

# Test 4: Run Hermes Bridge Self-Test
python markus_hermes_bridge.py
```
