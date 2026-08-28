#!/usr/bin/env python3
"""
OMNIPRIME M4 Adversarial Empirical Stress Test Suite (Challenger 1)
Focus: Offline Model Fallback Routing & Offline IPC Bridge Synchronization.

Tests:
- T1: Router Dynamic Fallback & Network State Matrix
- T2: Brain Backend Single Source of Truth Alignment
- T3: High-Concurrency Burst Offline Queueing (Hermes Bridge)
- T4: Corrupted / Malformed Line Tolerance in Hermes Queue
- T5: Partial Batch Drainage & Resumption (Hermes Bridge)
- T6: Vorpal Bridge Detached Storage Fallback Matrix
- T7: Vorpal Bridge Reconnection & Drainage Stress
- T8: Vorpal Spool File Corruption Resistance
- T9: Vorpal Goal DAG & Soul Parser Adversarial Resilience
- T10: Full Acceptance Suite & Module Compilation Check
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Workspace root
WORKSPACE_ROOT = Path(r"C:\Users\jonny\OneDrive\Desktop\MARKUS-OS")
sys.path.insert(0, str(WORKSPACE_ROOT))

# Import target modules
import markus_router
from markus_router import MarkusIntentRouter, RouteDecision
import markus_brain_backend
from markus_brain_backend import TIER_MODELS, route_brain_model, estimate_cost, record_cost
import markus_hermes_bridge
from markus_hermes_bridge import MarkusHermesBridge, HermesBridgeConfig
import markus_vorpal_bridge
from markus_vorpal_bridge import MarkusVorpalBridge, VORPALStatus
from markus_kernel import MarkusKernel

test_results: List[Tuple[str, bool, str]] = []


def record_test(name: str, passed: bool, details: str = "") -> bool:
    test_results.append((name, passed, details))
    status_str = "PASS" if passed else "FAIL"
    print(f"[{status_str}] {name}" + (f" -> {details}" if details else ""))
    return passed


# ==============================================================================
# TEST 1: Router Dynamic Fallback & Network State Matrix
# ==============================================================================
def test_1_router_dynamic_fallback() -> bool:
    print("\n--- TEST 1: Router Dynamic Fallback & Network State Matrix ---")
    router = MarkusIntentRouter(use_matrix=True)
    all_ok = True

    # 1.1 Test explicit is_offline=True across diverse prompts
    diverse_prompts = [
        "def quicksort(arr): return arr",
        "Design multi-repo distributed pipeline across 10 microservices",
        "status ping health metrics port 8128",
        "Simple greeting hello",
        "AST constant folding refactor in compiler pass",
        "Massive architecture document " + ("x " * 16000),
        "",  # Empty prompt
        "!@#$%^&*()_+ special characters",
        "Air-gapped offline query execution",
    ]

    for p in diverse_prompts:
        dec = router.route_intent(p, is_offline=True)
        if not (
            dec.target_model == "custom/qwen2.5-coder:7b"
            and dec.provider == "custom"
            and dec.tier_category == "OFFLINE_LOCAL"
            and dec.confidence == 1.0
        ):
            all_ok = False
            record_test(f"T1.1 is_offline=True prompt '{p[:30]}'", False, f"got {dec}")
            break
    else:
        record_test("T1.1 Diverse prompts with is_offline=True all route to custom/qwen2.5-coder:7b", True)

    # 1.2 Test auto-offline detection with simulated network state file
    with tempfile.TemporaryDirectory() as tmpdir:
        net_path = Path(tmpdir) / "markus_network_state.json"
        orig_net_path = markus_router.NETWORK_STATE_PATH
        markus_router.NETWORK_STATE_PATH = net_path

        try:
            # Case A: Fresh snapshot with has_internet: False -> Auto-offline
            net_path.write_text(json.dumps({
                "generated_at": time.time(),
                "has_internet": False,
                "primary_connection_type": "none"
            }), encoding="utf-8")
            dec_auto = router.route_intent("Optimize AST compiler", is_offline=False)
            ok_a = (dec_auto.target_model == "custom/qwen2.5-coder:7b" and dec_auto.network_down is True)
            record_test("T1.2 Case A: Fresh network down snapshot forces offline local model", ok_a, f"model={dec_auto.target_model}, down={dec_auto.network_down}")
            all_ok = all_ok and ok_a

            # Case B: Fresh snapshot with has_internet: True -> Online routing
            net_path.write_text(json.dumps({
                "generated_at": time.time(),
                "has_internet": True,
                "primary_connection_type": "wifi"
            }), encoding="utf-8")
            dec_online = router.route_intent("Optimize AST compiler", is_offline=False)
            ok_b = (dec_online.target_model == TIER_MODELS["CODE_SPECIALIST"] and dec_online.network_down is False)
            record_test("T1.2 Case B: Fresh network UP snapshot uses online model tier", ok_b, f"model={dec_online.target_model}")
            all_ok = all_ok and ok_b

            # Case C: Stale snapshot (>600s old) with has_internet: False -> Fail-open to online
            net_path.write_text(json.dumps({
                "generated_at": time.time() - 700,
                "has_internet": False,
                "primary_connection_type": "none"
            }), encoding="utf-8")
            dec_stale = router.route_intent("Optimize AST compiler", is_offline=False)
            ok_c = (dec_stale.target_model == TIER_MODELS["CODE_SPECIALIST"])
            record_test("T1.2 Case C: Stale network down snapshot fails open to online", ok_c, f"model={dec_stale.target_model}")
            all_ok = all_ok and ok_c

            # Case D: Corrupted JSON in network state -> Fail-open without exception
            net_path.write_text("CORRUPTED_JSON_DATA{{{{", encoding="utf-8")
            dec_corrupt = router.route_intent("Optimize AST compiler", is_offline=False)
            ok_d = (dec_corrupt.target_model == TIER_MODELS["CODE_SPECIALIST"])
            record_test("T1.2 Case D: Corrupted network state fails open cleanly", ok_d, f"model={dec_corrupt.target_model}")
            all_ok = all_ok and ok_d

            # Case E: Missing network state file -> Fail-open without exception
            net_path.unlink(missing_ok=True)
            dec_missing = router.route_intent("Optimize AST compiler", is_offline=False)
            ok_e = (dec_missing.target_model == TIER_MODELS["CODE_SPECIALIST"])
            record_test("T1.2 Case E: Missing network state fails open cleanly", ok_e, f"model={dec_missing.target_model}")
            all_ok = all_ok and ok_e

        finally:
            markus_router.NETWORK_STATE_PATH = orig_net_path

    # 1.3 Rapid oscillation test (200 alternating turns)
    osc_ok = True
    for i in range(200):
        flag = (i % 2 == 0)
        d = router.route_intent("Test prompt", is_offline=flag)
        if flag and d.target_model != "custom/qwen2.5-coder:7b":
            osc_ok = False
            break
        if not flag and d.target_model == "custom/qwen2.5-coder:7b":
            osc_ok = False
            break
    record_test("T1.3 200 rapid online/offline oscillations with 0 state leakage", osc_ok)
    all_ok = all_ok and osc_ok

    return all_ok


# ==============================================================================
# TEST 2: Brain Backend Single Source of Truth Alignment
# ==============================================================================
def test_2_brain_backend_alignment() -> bool:
    print("\n--- TEST 2: Brain Backend Single Source of Truth Alignment ---")
    all_ok = True

    # 2.1 OFFLINE_LOCAL tier mapping in TIER_MODELS
    t_model = TIER_MODELS.get("OFFLINE_LOCAL")
    ok_tier = (t_model == "custom/qwen2.5-coder:7b")
    record_test("T2.1 TIER_MODELS['OFFLINE_LOCAL'] == 'custom/qwen2.5-coder:7b'", ok_tier, f"got {t_model}")
    all_ok = all_ok and ok_tier

    # 2.2 route_brain_model mapping
    rbm = route_brain_model("OFFLINE_LOCAL")
    ok_rbm = (rbm == "custom/qwen2.5-coder:7b")
    record_test("T2.2 route_brain_model('OFFLINE_LOCAL') == 'custom/qwen2.5-coder:7b'", ok_rbm, f"got {rbm}")
    all_ok = all_ok and ok_rbm

    # 2.3 Pricing & zero-cost calculation for offline model
    cost = estimate_cost("custom/qwen2.5-coder:7b", prompt_tokens=50000, completion_tokens=20000)
    ok_cost = (cost == 0.0)
    record_test("T2.3 estimate_cost for offline model is exactly $0.00", ok_cost, f"cost={cost}")
    all_ok = all_ok and ok_cost

    # 2.4 Cost ledger write with offline model to temp ledger
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_ledger = Path(tmpdir) / "test_cost_ledger.jsonl"
        orig_ledger = markus_brain_backend.COST_LEDGER
        markus_brain_backend.COST_LEDGER = tmp_ledger
        try:
            c = record_cost("custom/qwen2.5-coder:7b", 1000, 500, 12.5, tier="OFFLINE_LOCAL")
            ok_rec = (c == 0.0 and tmp_ledger.exists())
            if ok_rec:
                entry = json.loads(tmp_ledger.read_text(encoding="utf-8").strip())
                ok_rec = (entry.get("model") == "custom/qwen2.5-coder:7b" and entry.get("cost_usd") == 0.0)
            record_test("T2.4 record_cost writes zero-cost offline ledger entry", ok_rec)
            all_ok = all_ok and ok_rec
        finally:
            markus_brain_backend.COST_LEDGER = orig_ledger

    return all_ok


# ==============================================================================
# TEST 3: High-Concurrency Burst Offline Queueing (Hermes Bridge)
# ==============================================================================
def test_3_high_concurrency_queue_burst() -> bool:
    print("\n--- TEST 3: High-Concurrency Burst Offline Queueing (Hermes Bridge) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        kernel = MarkusKernel()
        q_path = Path(tmpdir) / "hermes_offline_queue.jsonl"
        config = HermesBridgeConfig(
            private_workspace_root=Path(tmpdir),
            offline_queue_file=q_path
        )
        bridge = MarkusHermesBridge(kernel, config)
        bridge.init_private_infra()

        BURST_COUNT = 1000
        CONCURRENCY = 25

        async def run_burst():
            sem = asyncio.Semaphore(CONCURRENCY)

            async def send_one(idx: int):
                async with sem:
                    return await bridge.send_to_hermes_session(
                        prompt=f"Burst prompt #{idx} with payload entropy {idx * 137}",
                        is_offline=True,
                        extra={"burst_idx": idx}
                    )

            tasks = [send_one(i) for i in range(BURST_COUNT)]
            return await asyncio.gather(*tasks)

        t0 = time.time()
        results = asyncio.run(run_burst())
        elapsed = time.time() - t0

        # Check all returned QUEUED_OFFLINE
        all_queued = all(r.get("status") == "QUEUED_OFFLINE" for r in results)
        record_test(f"T3.1 All {BURST_COUNT} async messages dispatched as QUEUED_OFFLINE", all_queued, f"time={elapsed:.2f}s ({BURST_COUNT/elapsed:.0f} msg/s)")

        # Verify disk file line count
        lines = [l.strip() for l in q_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        line_count_ok = (len(lines) == BURST_COUNT)
        record_test(f"T3.2 Persistent JSONL file contains exactly {BURST_COUNT} lines", line_count_ok, f"count={len(lines)}")

        # Verify get_pending_offline_count
        pending = bridge.get_pending_offline_count()
        pending_ok = (pending == BURST_COUNT)
        record_test(f"T3.3 get_pending_offline_count() reports {BURST_COUNT}", pending_ok, f"pending={pending}")

        # Verify all message IDs are unique
        msg_ids = set()
        for line in lines:
            try:
                rec = json.loads(line)
                msg_ids.add(rec["msg_id"])
            except Exception:
                pass
        unique_ok = (len(msg_ids) == BURST_COUNT)
        record_test(f"T3.4 Zero ID collisions across {BURST_COUNT} burst messages", unique_ok, f"unique={len(msg_ids)}")

        return all_queued and line_count_ok and pending_ok and unique_ok


# ==============================================================================
# TEST 4: Corrupted / Malformed Line Tolerance in Hermes Queue
# ==============================================================================
def test_4_corrupted_line_tolerance() -> bool:
    print("\n--- TEST 4: Corrupted / Malformed Line Tolerance in Hermes Queue ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        kernel = MarkusKernel()
        q_path = Path(tmpdir) / "hermes_offline_queue.jsonl"
        config = HermesBridgeConfig(
            private_workspace_root=Path(tmpdir),
            offline_queue_file=q_path
        )
        bridge = MarkusHermesBridge(kernel, config)
        bridge.init_private_infra()

        # Build an adversarial file content with valid + corrupt entries interleaved
        adversarial_entries = [
            json.dumps({"msg_id": "valid_1", "status": "QUEUED", "prompt": "Alpha"}),
            "",  # Empty line
            "   ",  # Whitespace only
            '{"msg_id": "truncated_1", "status": "QUE',  # Truncated JSON
            '{"invalid_json": }',  # Syntax error
            "NOT_JSON_AT_ALL_JUST_RANDOM_TEXT!@#$%",  # Pure garbage
            json.dumps({"msg_id": "valid_2", "status": "QUEUED", "prompt": "Beta with emoji 🚀🔥"}),
            json.dumps([1, 2, 3, "array_instead_of_dict"]),  # Valid JSON, wrong structure
            json.dumps("string_json_record"),  # Valid JSON string
            json.dumps({"msg_id": "already_flushed", "status": "FLUSHED", "prompt": "Old"}),
            "\x00\x01\x02\x03\xff\xfe",  # Non-printable binary bytes
            json.dumps({"msg_id": "valid_3", "status": "QUEUED", "prompt": "Gamma", "extra": {"nested": [1, 2, 3]}}),
            '{"msg_id": "valid_4", "status": "QUEUED", "prompt": "Delta\\nwith\\nnewlines"}',
            "   \n\n\n   ",
            json.dumps({"msg_id": "valid_5", "status": "QUEUED", "prompt": "Epsilon"}),
        ]

        q_path.write_text("\n".join(adversarial_entries) + "\n", encoding="utf-8", errors="replace")

        # 4.1 Check pending count (should count only the 5 valid QUEUED entries)
        pending = bridge.get_pending_offline_count()
        ok_count = (pending == 5)
        record_test("T4.1 get_pending_offline_count() correctly filters 5 valid QUEUED entries out of adversarial corruption", ok_count, f"got {pending}")

        # 4.2 Flush offline queue with force=True
        flushed = bridge.flush_offline_queue(force=True)
        ok_flush = (flushed == 5)
        record_test("T4.2 flush_offline_queue() successfully flushes 5 valid items without throwing exception", ok_flush, f"flushed={flushed}")

        # 4.3 Queue after full flush should be 0 depth
        pending_after = bridge.get_pending_offline_count()
        ok_after = (pending_after == 0)
        record_test("T4.3 Queue depth is 0 after flush", ok_after, f"depth={pending_after}")

        return ok_count and ok_flush and ok_after


# ==============================================================================
# TEST 5: Partial Batch Drainage & Resumption (Hermes Bridge)
# ==============================================================================
def test_5_partial_batch_drainage() -> bool:
    print("\n--- TEST 5: Partial Batch Drainage & Resumption (Hermes Bridge) ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        kernel = MarkusKernel()
        q_path = Path(tmpdir) / "hermes_offline_queue.jsonl"
        config = HermesBridgeConfig(
            private_workspace_root=Path(tmpdir),
            offline_queue_file=q_path
        )
        bridge = MarkusHermesBridge(kernel, config)
        bridge.init_private_infra()

        # Enqueue 150 items
        for i in range(150):
            bridge.enqueue_offline({"msg_id": f"msg_batch_{i:03d}", "prompt": f"Task {i}"})

        init_pending = bridge.get_pending_offline_count()
        ok_init = (init_pending == 150)

        # Batch 1: flush 50
        f1 = bridge.flush_offline_queue(max_batch=50, force=True)
        p1 = bridge.get_pending_offline_count()
        ok_b1 = (f1 == 50 and p1 == 100)
        record_test("T5.1 Batch 1: flushed 50 / 150, exactly 100 remaining", ok_b1, f"flushed={f1}, rem={p1}")

        # Batch 2: flush 60
        f2 = bridge.flush_offline_queue(max_batch=60, force=True)
        p2 = bridge.get_pending_offline_count()
        ok_b2 = (f2 == 60 and p2 == 40)
        record_test("T5.2 Batch 2: flushed 60 / 100, exactly 40 remaining", ok_b2, f"flushed={f2}, rem={p2}")

        # Batch 3: flush 100 (should only flush 40)
        f3 = bridge.flush_offline_queue(max_batch=100, force=True)
        p3 = bridge.get_pending_offline_count()
        ok_b3 = (f3 == 40 and p3 == 0)
        record_test("T5.3 Batch 3: flushed remaining 40 / 40, queue fully drained (0 remaining)", ok_b3, f"flushed={f3}, rem={p3}")

        # Batch 4: flush again on empty queue (idempotence)
        f4 = bridge.flush_offline_queue(max_batch=50, force=True)
        p4 = bridge.get_pending_offline_count()
        ok_b4 = (f4 == 0 and p4 == 0)
        record_test("T5.4 Batch 4: idempotent flush on empty queue returns 0", ok_b4, f"flushed={f4}, rem={p4}")

        return ok_init and ok_b1 and ok_b2 and ok_b3 and ok_b4


# ==============================================================================
# TEST 6: Vorpal Bridge Detached Storage Fallback Matrix
# ==============================================================================
def test_6_vorpal_detached_storage_fallback() -> bool:
    print("\n--- TEST 6: Vorpal Bridge Detached Storage Fallback Matrix ---")
    bridge = MarkusVorpalBridge()
    all_ok = True

    with tempfile.TemporaryDirectory() as tmpdir:
        orig_root = markus_vorpal_bridge.VORPAL_ROOT
        orig_ledger = markus_vorpal_bridge.MARKUS_LEDGER_PATH
        orig_spool = markus_vorpal_bridge.VORPAL_SPOOL_PATH

        try:
            # 6.1 Detached VORPAL_ROOT -> Spools to VORPAL_SPOOL_PATH
            absent_root = Path(tmpdir) / "non_existent_vorpal_root"
            spool_file = Path(tmpdir) / "ipc" / "vorpal_telemetry_spool.jsonl"
            ledger_file = absent_root / "EVOLVE" / "MARKUS_TELEMETRY.json"

            markus_vorpal_bridge.VORPAL_ROOT = absent_root
            markus_vorpal_bridge.MARKUS_LEDGER_PATH = ledger_file
            markus_vorpal_bridge.VORPAL_SPOOL_PATH = spool_file

            # Write 50 telemetry entries in detached state
            for i in range(50):
                p = bridge.write_markus_telemetry(
                    matrix_state=[{"model": "qwen2.5-coder:7b", "w": 1.0}],
                    network_state={"has_internet": False},
                    server_ok=True,
                    extra={"entry_idx": i}
                )
                if p != spool_file:
                    all_ok = False
                    break

            spool_count = bridge.get_spooled_telemetry_count()
            ok_spool = (spool_count == 50 and spool_file.exists() and not ledger_file.exists())
            record_test("T6.1 Detached VORPAL_ROOT correctly routes 50 snapshots to spool file without touching ledger", ok_spool, f"spool_count={spool_count}")
            all_ok = all_ok and ok_spool

            # 6.2 Explicit ledger path override outside VORPAL_ROOT
            explicit_ledger_dir = Path(tmpdir) / "explicit_dir"
            explicit_ledger_dir.mkdir(parents=True, exist_ok=True)
            explicit_ledger = explicit_ledger_dir / "custom_telemetry.json"
            markus_vorpal_bridge.MARKUS_LEDGER_PATH = explicit_ledger

            p_exp = bridge.write_markus_telemetry(
                matrix_state=[{"model": "explicit", "w": 0.9}],
                server_ok=True
            )
            ok_exp = (p_exp == explicit_ledger and explicit_ledger.exists())
            record_test("T6.2 Explicit ledger override outside VORPAL_ROOT writes directly", ok_exp, f"path={p_exp}")
            all_ok = all_ok and ok_exp

        finally:
            markus_vorpal_bridge.VORPAL_ROOT = orig_root
            markus_vorpal_bridge.MARKUS_LEDGER_PATH = orig_ledger
            markus_vorpal_bridge.VORPAL_SPOOL_PATH = orig_spool

    return all_ok


# ==============================================================================
# TEST 7: Vorpal Bridge Reconnection & Drainage Stress
# ==============================================================================
def test_7_vorpal_reconnection_and_flush() -> bool:
    print("\n--- TEST 7: Vorpal Bridge Reconnection & Drainage Stress ---")
    bridge = MarkusVorpalBridge()

    with tempfile.TemporaryDirectory() as tmpdir:
        orig_root = markus_vorpal_bridge.VORPAL_ROOT
        orig_ledger = markus_vorpal_bridge.MARKUS_LEDGER_PATH
        orig_spool = markus_vorpal_bridge.VORPAL_SPOOL_PATH

        try:
            vorpal_root = Path(tmpdir) / "vorpal_mnt"
            spool_file = Path(tmpdir) / "ipc" / "vorpal_telemetry_spool.jsonl"
            ledger_file = vorpal_root / "EVOLVE" / "MARKUS_TELEMETRY.json"

            markus_vorpal_bridge.VORPAL_ROOT = vorpal_root
            markus_vorpal_bridge.MARKUS_LEDGER_PATH = ledger_file
            markus_vorpal_bridge.VORPAL_SPOOL_PATH = spool_file

            # Phase 1: Detached spooling (75 entries)
            for i in range(75):
                bridge.write_markus_telemetry(
                    matrix_state=[{"model": f"model_{i}", "w": float(i)}],
                    server_ok=(i % 2 == 0),
                    extra={"seq": i}
                )

            assert bridge.get_spooled_telemetry_count() == 75, "Must have 75 spooled entries"

            # Flush before reconnection (should return 0 because VORPAL_ROOT and ledger.parent do not exist)
            f_early = bridge.flush_spooled_telemetry()
            ok_early = (f_early == 0 and bridge.get_spooled_telemetry_count() == 75)
            record_test("T7.1 Flush attempt before reconnection safely no-ops and preserves 75 spooled entries", ok_early)

            # Phase 2: Reconnection - VORPAL_ROOT comes online
            vorpal_root.mkdir(parents=True, exist_ok=True)
            f_reconn = bridge.flush_spooled_telemetry()
            ok_reconn = (f_reconn == 75)
            record_test("T7.2 Flush after reconnection flushes exactly 75 spooled entries", ok_reconn, f"flushed={f_reconn}")

            # Verify ledger content has latest state (seq 74)
            ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
            ok_latest = (ledger_data.get("extra", {}).get("seq") == 74 and ledger_data.get("server_ok") is True)
            record_test("T7.3 Target ledger contains latest spooled telemetry payload (seq=74)", ok_latest)

            # Verify spool file unlinked and count is 0
            spool_rem = bridge.get_spooled_telemetry_count()
            ok_cleaned = (spool_rem == 0 and not spool_file.exists())
            record_test("T7.4 Spool file unlinked and spooled count resets to 0", ok_cleaned, f"spool_rem={spool_rem}")

            # Idempotent flush
            f_idem = bridge.flush_spooled_telemetry()
            ok_idem = (f_idem == 0)
            record_test("T7.5 Idempotent subsequent flush returns 0", ok_idem)

            return ok_early and ok_reconn and ok_latest and ok_cleaned and ok_idem

        finally:
            markus_vorpal_bridge.VORPAL_ROOT = orig_root
            markus_vorpal_bridge.MARKUS_LEDGER_PATH = orig_ledger
            markus_vorpal_bridge.VORPAL_SPOOL_PATH = orig_spool


# ==============================================================================
# TEST 8: Vorpal Spool File Corruption Resistance
# ==============================================================================
def test_8_vorpal_spool_corruption() -> bool:
    print("\n--- TEST 8: Vorpal Spool File Corruption Resistance ---")
    bridge = MarkusVorpalBridge()

    with tempfile.TemporaryDirectory() as tmpdir:
        orig_root = markus_vorpal_bridge.VORPAL_ROOT
        orig_ledger = markus_vorpal_bridge.MARKUS_LEDGER_PATH
        orig_spool = markus_vorpal_bridge.VORPAL_SPOOL_PATH

        try:
            vorpal_root = Path(tmpdir) / "vorpal_corrupt_test"
            vorpal_root.mkdir(parents=True, exist_ok=True)
            spool_file = Path(tmpdir) / "ipc" / "vorpal_telemetry_spool.jsonl"
            ledger_file = vorpal_root / "EVOLVE" / "MARKUS_TELEMETRY.json"

            markus_vorpal_bridge.VORPAL_ROOT = vorpal_root
            markus_vorpal_bridge.MARKUS_LEDGER_PATH = ledger_file
            markus_vorpal_bridge.VORPAL_SPOOL_PATH = spool_file

            # Create corrupt spool file
            spool_file.parent.mkdir(parents=True, exist_ok=True)
            corrupt_lines = [
                '{"written_at": 100.0, "matrix": [], "server_ok": true, "extra": {"valid": 1}}',
                '{"BROKEN_JSON_TRUNCATED": ',
                '',
                '   ',
                '<<<BINARY_GARBAGE_BYTES>>>',
                '{"written_at": 200.0, "matrix": [], "server_ok": false, "extra": {"valid": 2}}',
                '{INVALID_KEYS: 123}',
                '{"written_at": 300.0, "matrix": [{"model": "recovered", "w": 1.0}], "server_ok": true, "extra": {"valid": 3}}',
            ]
            spool_file.write_text("\n".join(corrupt_lines) + "\n", encoding="utf-8")

            # get_spooled_telemetry_count
            count = bridge.get_spooled_telemetry_count()
            ok_cnt = (count == 8)  # counts non-empty lines
            record_test("T8.1 get_spooled_telemetry_count() does not crash on corrupted lines", ok_cnt, f"count={count}")

            # Flush
            flushed = bridge.flush_spooled_telemetry()
            ok_fl = (flushed == 8)
            record_test("T8.2 flush_spooled_telemetry() survives corrupted lines without exception", ok_fl, f"flushed={flushed}")

            # Check recovered ledger contains valid 3
            ledger_data = json.loads(ledger_file.read_text(encoding="utf-8"))
            ok_rec = (ledger_data.get("extra", {}).get("valid") == 3 and ledger_data.get("server_ok") is True)
            record_test("T8.3 Ledger correctly updated with the last valid payload (valid=3)", ok_rec)

            return ok_cnt and ok_fl and ok_rec

        finally:
            markus_vorpal_bridge.VORPAL_ROOT = orig_root
            markus_vorpal_bridge.MARKUS_LEDGER_PATH = orig_ledger
            markus_vorpal_bridge.VORPAL_SPOOL_PATH = orig_spool


# ==============================================================================
# TEST 9: Vorpal Goal DAG & Soul Parser Adversarial Resilience
# ==============================================================================
def test_9_vorpal_parser_resilience() -> bool:
    print("\n--- TEST 9: Vorpal Goal DAG & Soul Parser Adversarial Resilience ---")
    bridge = MarkusVorpalBridge()
    all_ok = True

    with tempfile.TemporaryDirectory() as tmpdir:
        goals_file = Path(tmpdir) / "GOALS.md"
        notes_file = Path(tmpdir) / "NOTES.md"
        soul_file = Path(tmpdir) / "SOUL.md"

        # 9.1 Empty files
        goals_file.write_text("", encoding="utf-8")
        notes_file.write_text("", encoding="utf-8")
        soul_file.write_text("", encoding="utf-8")

        tot, opn, imp = bridge._parse_goals(goals_file)
        errs = bridge._parse_recent_errors(notes_file)
        objs, cards = bridge._parse_soul(soul_file)

        ok_empty = (tot == 0 and opn == 0 and imp == 0 and errs == [] and objs == [] and cards == {})
        record_test("T9.1 Parser handles empty markdown files safely", ok_empty)
        all_ok = all_ok and ok_empty

        # 9.2 High-volume synthetic goals (5,000 goals with complex nesting)
        synth_lines = ["# VORPAL EVOLVE GOALS\n"]
        for i in range(5000):
            if i % 3 == 0:
                synth_lines.append(f"## Phase {i // 100}")
            if i % 4 == 0:
                synth_lines.append(f"- GOAL_{i:04d}: Implementation task {i} [IMPLEMENTED: 2026-08-20]")
            elif i % 4 == 1:
                synth_lines.append(f"- GOAL_{i:04d}: Complete task {i} (COMPLETE)")
            elif i % 4 == 2:
                synth_lines.append(f"- GOAL_{i:04d}: Tier 0 apex goal {i} tier_0_apex")
            else:
                synth_lines.append(f"- GOAL_{i:04d}: Active open goal {i} tier_2_stagnant")
                synth_lines.append(f"    - Subtask {i}.1 details")

        goals_file.write_text("\n".join(synth_lines), encoding="utf-8")
        t0 = time.time()
        tot, opn, imp = bridge._parse_goals(goals_file)
        el = time.time() - t0

        ok_vol = (tot == 5000 and imp == 1250 and opn == 1250 and el < 1.0)
        record_test(f"T9.2 Parsed 5,000 synthetic goals in {el*1000:.1f}ms with exact count", ok_vol, f"tot={tot}, open={opn}, impl={imp}")
        all_ok = all_ok and ok_vol

        # 9.3 2,000 error lines in NOTES.md
        notes_lines = [f"2026-08-26 Note line {i} with [ERR_CODE_{i % 50}] detail" for i in range(2000)]
        notes_file.write_text("\n".join(notes_lines), encoding="utf-8")
        errs = bridge._parse_recent_errors(notes_file)
        ok_err = (len(errs) == 10 and "ERR_CODE_" in errs[-1])
        record_test("T9.3 Parsed 2,000 error lines -> returned last 10 errors cleanly", ok_err, f"len={len(errs)}")
        all_ok = all_ok and ok_err

        # 9.4 Complex SOUL.md with objectives and cardinal directions
        soul_text = """
# SOUL OF VORPAL
## OBJECTIVES
1. **Pioneer Autonomous Air-Gapped Intelligence**
2. **Master Zero-Latency Swarm IPC**
3. **Execute Continuous Memory Evolution**

## CARDINAL STARS
- **NORTH** — Autonomous Air-Gapped Sovereignty
- **SOUTH** — Sub-Millisecond Ring-Buffer IPC
- **EAST** — Deterministic Context Pruning
- **WEST** — Resilient Telemetry Ledger
"""
        soul_file.write_text(soul_text, encoding="utf-8")
        objs, cards = bridge._parse_soul(soul_file)
        ok_soul = (len(objs) == 3 and len(cards) == 4 and "NORTH" in cards and "SOUTH" in cards)
        record_test("T9.4 Parsed SOUL.md objectives (3) and cardinal stars (4)", ok_soul, f"cards={list(cards.keys())}")
        all_ok = all_ok and ok_soul

    return all_ok


# ==============================================================================
# TEST 10: Full Acceptance Suite & Module Compilation Check
# ==============================================================================
def test_10_acceptance_and_compilation() -> bool:
    print("\n--- TEST 10: Full Acceptance Suite & Module Compilation Check ---")
    all_ok = True

    # 10.1 py_compile targets
    targets = [
        "markus_router.py",
        "markus_brain_backend.py",
        "markus_hermes_bridge.py",
        "markus_vorpal_bridge.py",
        "markus_db.py",
        "markus_context_pruner.py"
    ]
    compile_ok = True
    for t in targets:
        p = WORKSPACE_ROOT / t
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as exc:
            compile_ok = False
            record_test(f"T10.1 py_compile {t}", False, str(exc))
            break
    if compile_ok:
        record_test("T10.1 py_compile passes across all 6 core targets", True)
    all_ok = all_ok and compile_ok

    # 10.2 hermes_verify_router.py
    proc_r = subprocess.run([sys.executable, str(WORKSPACE_ROOT / "hermes_verify_router.py")],
                            capture_output=True, text=True, cwd=str(WORKSPACE_ROOT))
    ok_r = (proc_r.returncode == 0 and "OVERALL: PASS" in proc_r.stdout)
    record_test("T10.2 hermes_verify_router.py execution", ok_r, f"returncode={proc_r.returncode}")
    if not ok_r:
        print("STDOUT:", proc_r.stdout)
        print("STDERR:", proc_r.stderr)
    all_ok = all_ok and ok_r

    # 10.3 hermes_verify_vorpal_bridge.py
    proc_v = subprocess.run([sys.executable, str(WORKSPACE_ROOT / "hermes_verify_vorpal_bridge.py")],
                            capture_output=True, text=True, cwd=str(WORKSPACE_ROOT))
    ok_v = (proc_v.returncode == 0 and "OVERALL: PASS" in proc_v.stdout)
    record_test("T10.3 hermes_verify_vorpal_bridge.py execution", ok_v, f"returncode={proc_v.returncode}")
    if not ok_v:
        print("STDOUT:", proc_v.stdout)
        print("STDERR:", proc_v.stderr)
    all_ok = all_ok and ok_v

    # 10.4 hermes_verify_evolution_loops.py
    proc_e = subprocess.run([sys.executable, str(WORKSPACE_ROOT / "hermes_verify_evolution_loops.py")],
                            capture_output=True, text=True, cwd=str(WORKSPACE_ROOT))
    ok_e = (proc_e.returncode == 0 and "TOTAL PASS=7 TOTAL_FAIL=0" in proc_e.stdout)
    record_test("T10.4 hermes_verify_evolution_loops.py execution (TOTAL PASS=7 TOTAL_FAIL=0)", ok_e, f"returncode={proc_e.returncode}")
    if not ok_e:
        print("STDOUT:", proc_e.stdout)
        print("STDERR:", proc_e.stderr)
    all_ok = all_ok and ok_e

    return all_ok


# ==============================================================================
# MAIN RUNNER
# ==============================================================================
def main() -> int:
    print("================================================================================")
    print("      OMNIPRIME M4 ADVERSARIAL STRESS TEST SUITE (CHALLENGER 1)               ")
    print("================================================================================")

    t_start = time.time()
    t1 = test_1_router_dynamic_fallback()
    t2 = test_2_brain_backend_alignment()
    t3 = test_3_high_concurrency_queue_burst()
    t4 = test_4_corrupted_line_tolerance()
    t5 = test_5_partial_batch_drainage()
    t6 = test_6_vorpal_detached_storage_fallback()
    t7 = test_7_vorpal_reconnection_and_flush()
    t8 = test_8_vorpal_spool_corruption()
    t9 = test_9_vorpal_parser_resilience()
    t10 = test_10_acceptance_and_compilation()
    total_elapsed = time.time() - t_start

    passed_count = sum(1 for _, ok, _ in test_results if ok)
    total_count = len(test_results)
    failed_count = total_count - passed_count

    print("\n================================================================================")
    print(f"STRESS TEST SUMMARY: {passed_count}/{total_count} PASSED in {total_elapsed:.2f}s")
    if failed_count == 0:
        print("OVERALL VERDICT: APPROVE (Zero failures under stress)")
    else:
        print(f"OVERALL VERDICT: REQUEST_CHANGES ({failed_count} failures detected)")
    print("================================================================================")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
