# Adversarial Stress Test & Forensic Audit Handoff Report

**Milestone**: M4 - Offline Fallback Routing & Offline IPC Bridge Synchronization  
**Agent**: Challenger 1 (`critic`, `specialist`)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

Direct empirical observations from executing the 10-module stress test harness (`stress_test_harness.py`):

1. **Router Offline Fallback & Auto-Offline Transport Gate (`markus_router.py:86-103`)**:
   - `route_intent(..., is_offline=True)` with diverse prompt payloads (AST code refactor, megacontext multi-repo architecture, lint/telemetry, empty strings, unicode) deterministically returns:
     - `target_model == "custom/qwen2.5-coder:7b"`
     - `provider == "custom"`
     - `tier_category == "OFFLINE_LOCAL"`
     - `confidence == 1.0`
   - Network state auto-detection (`markus_router.py:58-68` reading `markus_network_state.json`):
     - Fresh snapshot (<600s) with `has_internet: false` routes to `"custom/qwen2.5-coder:7b"` with `network_down=True`.
     - Fresh snapshot (<600s) with `has_internet: true` routes to online tier (`"poolside/laguna-s-2.1:free"`).
     - Stale snapshot (>600s old), missing snapshot, or corrupted JSON snapshot cleanly fails open to online tier without raising an exception.
     - 200 rapid alternating switches between online and offline modes showed 0 state leakage.

2. **Brain Backend Tier & Cost Ledger (`markus_brain_backend.py:40-66`)**:
   - `TIER_MODELS["OFFLINE_LOCAL"]` and `route_brain_model("OFFLINE_LOCAL")` return `"custom/qwen2.5-coder:7b"`.
   - `estimate_cost("custom/qwen2.5-coder:7b", prompt_tokens=50000, completion_tokens=20000)` returns `0.0`.
   - `record_cost` appends zero-cost ledger entries for offline model invocations.

3. **High-Concurrency Queue Burst (`markus_hermes_bridge.py:151-175, 233-287`)**:
   - 1,000 asynchronous messages dispatched under offline mode were all queued into `hermes_offline_queue.jsonl` with zero dropped messages and zero duplicate IDs (`unique_count == 1000`).
   - `get_pending_offline_count()` reported exactly 1,000.
   - Batch drainage test verified: flushing in increments of 50, 60, and 40 items accurately maintained residual queue depth (100 -> 40 -> 0) and unlinked/emptied the queue file upon full flush.

4. **Defect in Hermes Offline Queue Flush on Non-Dict JSON (`markus_hermes_bridge.py:200-231`)**:
   - When `hermes_offline_queue.jsonl` contains non-dict valid JSON records (e.g. `[1, 2, 3]`, `"a_string"`, or `12345`), running `flush_offline_queue(force=True)` crashed with:
     ```
     [WARNING] [MARKUS-OS] Failed to flush offline queue: 'list' object has no attribute 'get'
     ```
   - In `markus_hermes_bridge.py` lines 200-206:
     ```python
     try:
         record = json.loads(line)
     except Exception:
         continue

     if record.get("status") == "QUEUED" and flushed_count < max_batch:
     ```
   - `json.loads("[1, 2, 3]")` successfully returns a `list`.
   - `record.get("status")` is called outside the `try...except Exception` block for JSON parsing without checking `isinstance(record, dict)`.
   - Result: An unhandled `AttributeError` is raised, caught by the outer function handler `except Exception as exc: logger.warning(...); return 0`, causing `flush_offline_queue` to prematurely abort and return 0 flushed, leaving all remaining valid queued items stranded in the queue.

5. **Spool File Dict Validation in Vorpal Bridge (`markus_vorpal_bridge.py:249-258`)**:
   - In `markus_vorpal_bridge.py` lines 249-258:
     ```python
     last_payload = None
     for line in lines:
         try:
             last_payload = json.loads(line)
         except Exception:
             continue
     if last_payload:
         target.parent.mkdir(parents=True, exist_ok=True)
         target.write_text(json.dumps(last_payload, indent=2, default=str), encoding="utf-8")
     ```
   - If the last non-empty line of `vorpal_telemetry_spool.jsonl` is a valid JSON list or primitive (e.g. `[1, 2, 3]`), `last_payload` is written to `MARKUS_TELEMETRY.json` as a raw list rather than a dictionary object, breaking downstream consumers that access dictionary keys.

6. **Detached Storage Fallback & Goal Parser Stress (`markus_vorpal_bridge.py`)**:
   - Telemetry automatically spools to `VORPAL_SPOOL_PATH` when `VORPAL_ROOT` is detached.
   - Reconnecting `VORPAL_ROOT` and calling `flush_spooled_telemetry()` cleanly transfers the latest payload to `MARKUS_LEDGER_PATH` and unlinks the spool file.
   - `_parse_goals` successfully parsed a synthetic 5,000-goal nested DAG in 25.1ms with 100% count accuracy.
   - `_parse_recent_errors` handled 2,000 notes lines and cleanly extracted the latest 10 errors.

7. **Project Verification Suites**:
   - `py_compile` passed on all 6 targets (`markus_router.py`, `markus_brain_backend.py`, `markus_hermes_bridge.py`, `markus_vorpal_bridge.py`, `markus_db.py`, `markus_context_pruner.py`).
   - `hermes_verify_router.py` passed with `OVERALL: PASS`.
   - `hermes_verify_vorpal_bridge.py` passed with `OVERALL: PASS`.
   - `hermes_verify_evolution_loops.py` passed with `TOTAL PASS=7 TOTAL_FAIL=0`.

---

## 2. Logic Chain

1. From **Observation 1**, `markus_router.py` deterministic offline gating and fail-open auto-offline transport detection comply with interface requirements §R1 and PROJECT.md specifications.
2. From **Observation 2**, `markus_brain_backend.py` single source of truth mapping and zero-cost pricing for `custom/qwen2.5-coder:7b` are verified.
3. From **Observation 3**, `markus_hermes_bridge.py` handles high-concurrency writes and multi-batch drains accurately under normal queue operations.
4. From **Observation 4**, when corrupt or non-standard JSON payloads (lists, strings, numbers) enter `hermes_offline_queue.jsonl`, `flush_offline_queue` crashes on `.get()` due to missing type validation `isinstance(record, dict)`. This aborts the entire flush operation, causing a Denial of Service on IPC queue draining.
5. From **Observation 5**, `markus_vorpal_bridge.py`'s `flush_spooled_telemetry` similarly lacks dictionary type checking on `last_payload`, exposing `MARKUS_TELEMETRY.json` to potential JSON schema corruption upon flush.
6. From **Observation 6 & 7**, all baseline acceptance test suites pass, but the system fails under adversarial malformed IPC queue injections.

---

## 3. Caveats

- Benchmark testing for high-concurrency burst queueing (1,000 items) was executed on Windows NTFS with SQLite WAL mode. While queue integrity was 100% preserved, burst latency was ~4 msgs/sec due to repeated `get_pending_offline_count()` whole-file rescanning inside `enqueue_offline`.
- Multi-gigabyte SQLite database compaction under disk quota pressure was not evaluated as part of this IPC/routing stress pass.

---

## 4. Conclusion & Required Actions

**Verdict**: **REQUEST_CHANGES**

The core offline routing, detached storage fallbacks, and baseline verifications are functionally sound. However, the implementation requires two defensive fixes to ensure air-gapped resilience against corrupted IPC queues:

### Required Changes:

1. **Fix `markus_hermes_bridge.py:200-206` (`flush_offline_queue`)**:
   Add dictionary type validation before accessing `.get("status")`:
   ```python
   for line in lines:
       line = line.strip()
       if not line:
           continue
       try:
           record = json.loads(line)
       except Exception:
           continue

       if not isinstance(record, dict):
           continue

       if record.get("status") == "QUEUED" and flushed_count < max_batch:
   ```

2. **Fix `markus_vorpal_bridge.py:250-258` (`flush_spooled_telemetry`)**:
   Validate that `last_payload` is a dictionary before writing to `MARKUS_TELEMETRY.json`:
   ```python
   for line in lines:
       try:
           payload = json.loads(line)
           if isinstance(payload, dict):
               last_payload = payload
       except Exception:
           continue
   if last_payload and isinstance(last_payload, dict):
       target.parent.mkdir(parents=True, exist_ok=True)
       target.write_text(json.dumps(last_payload, indent=2, default=str), encoding="utf-8")
   ```

---

## 5. Verification Method

To independently verify the fixes:

1. **Run Targeted Fix Validation**:
   ```bash
   python .agents/challenger_1/test_fix_validation.py
   ```
2. **Execute Full Adversarial Stress Suite**:
   ```bash
   python .agents/challenger_1/stress_test_harness.py
   ```
   *Expected output*: `STRESS TEST SUMMARY: 40/40 PASSED` with `OVERALL VERDICT: APPROVE`.
3. **Execute Official Acceptance Verification**:
   ```bash
   python hermes_verify_router.py
   python hermes_verify_vorpal_bridge.py
   python hermes_verify_evolution_loops.py
   ```
