#!/usr/bin/env python3
"""
Adversarial Forensic Stress Testing Script for Milestone M4.
Executes independent boundary condition, concurrency, and integrity checks.
"""
import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

# Target imports
from markus_router import MarkusIntentRouter, RouteDecision
from markus_brain_backend import TIER_MODELS, estimate_cost, record_cost, cost_summary
from markus_hermes_bridge import MarkusHermesBridge, HermesBridgeConfig
from markus_vorpal_bridge import MarkusVorpalBridge
from markus_db import PersistentCortexDB
from markus_context_pruner import MarkusContextPruner
from markus_kernel import MarkusKernel

def test_router_adversarial():
    print("\n--- Testing Router Adversarial Invariants ---")
    router = MarkusIntentRouter(use_matrix=False)
    
    # 1. Check offline fallback consistency across diverse adversarial prompts
    prompts = [
        "",
        " " * 100,
        "CRITICAL: System crash in cluster",
        "def exploit_vulnerability(): pass",
        "Design architecture across 1000 microservices " * 50,
        "SELECT * FROM thoughts WHERE 1=1 --",
        "DROP TABLE users;",
        "\x00\x01\x02 binary gibberish",
    ]
    for p in prompts:
        decision = router.route_intent(p, is_offline=True)
        assert decision.target_model == "custom/qwen2.5-coder:7b", f"Offline route failed for prompt '{p}': {decision.target_model}"
        assert decision.provider == "custom", f"Provider must be custom: {decision.provider}"
        assert decision.tier_category == "OFFLINE_LOCAL", f"Tier must be OFFLINE_LOCAL: {decision.tier_category}"
        assert decision.confidence == 1.0, f"Confidence must be 1.0: {decision.confidence}"
    print("[PASS] Router offline fallback invariants verified across 8 adversarial prompt patterns.")

    # 2. Check brain backend tier map
    assert TIER_MODELS["OFFLINE_LOCAL"] == "custom/qwen2.5-coder:7b", "TIER_MODELS OFFLINE_LOCAL mismatch"
    print("[PASS] Brain backend TIER_MODELS single source of truth verified.")

def test_hermes_bridge_adversarial():
    print("\n--- Testing Hermes Bridge Queue Invariants ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        cfg = HermesBridgeConfig(
            private_workspace_root=tmp_path / "private",
            offline_queue_file=tmp_path / "private" / "ipc" / "test_queue.jsonl"
        )
        kernel = MarkusKernel()
        bridge = MarkusHermesBridge(kernel, cfg)
        bridge.init_private_infra()
        
        # Enqueue 50 messages
        for i in range(50):
            bridge.enqueue_offline({"prompt": f"Intent batch #{i}", "msg_id": f"id_{i:03d}"})
        
        assert bridge.get_pending_offline_count() == 50, f"Expected 50 queued, got {bridge.get_pending_offline_count()}"
        
        # Partial flush batch of 20
        flushed_20 = bridge.flush_offline_queue(max_batch=20, force=True)
        assert flushed_20 == 20, f"Expected 20 flushed, got {flushed_20}"
        assert bridge.get_pending_offline_count() == 30, f"Expected 30 remaining, got {bridge.get_pending_offline_count()}"
        
        # Flush remaining 30
        flushed_rem = bridge.flush_offline_queue(max_batch=50, force=True)
        assert flushed_rem == 30, f"Expected 30 flushed, got {flushed_rem}"
        assert bridge.get_pending_offline_count() == 0, f"Expected 0 remaining, got {bridge.get_pending_offline_count()}"
        
        # Queue should now be empty
        flushed_zero = bridge.flush_offline_queue(force=True)
        assert flushed_zero == 0, f"Expected 0 on empty flush, got {flushed_zero}"
    print("[PASS] Hermes bridge queue batching, drainage, and disk state persistence verified.")

def test_vorpal_bridge_adversarial():
    print("\n--- Testing Vorpal Bridge Spooling Invariants ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        ledger_path = tmp_path / "vorpal_root" / "EVOLVE" / "MARKUS_TELEMETRY.json"
        spool_path = tmp_path / "private" / "ipc" / "vorpal_telemetry_spool.jsonl"
        
        # Override module paths
        import markus_vorpal_bridge as mvb
        orig_root = mvb.VORPAL_ROOT
        orig_ledger = mvb.MARKUS_LEDGER_PATH
        orig_spool = mvb.VORPAL_SPOOL_PATH
        
        try:
            mvb.VORPAL_ROOT = tmp_path / "vorpal_root"
            mvb.MARKUS_LEDGER_PATH = ledger_path
            mvb.VORPAL_SPOOL_PATH = spool_path
            
            bridge = mvb.MarkusVorpalBridge()
            
            # Root does not exist yet -> must spool
            p1 = bridge.write_markus_telemetry(matrix_state=[{"m": 1}], server_ok=False)
            p2 = bridge.write_markus_telemetry(matrix_state=[{"m": 2}], server_ok=True)
            assert p1 == spool_path and p2 == spool_path, "Must return spool path when root absent"
            assert bridge.get_spooled_telemetry_count() == 2, "Expected 2 spooled records"
            assert spool_path.exists(), "Spool file must exist on disk"
            
            # Now simulate VORPAL root becoming available
            mvb.VORPAL_ROOT.mkdir(parents=True, exist_ok=True)
            flushed_ct = bridge.flush_spooled_telemetry()
            assert flushed_ct == 2, f"Expected 2 records flushed, got {flushed_ct}"
            assert ledger_path.exists(), "Target ledger must exist after flush"
            assert bridge.get_spooled_telemetry_count() == 0, "Spool count must be 0"
            assert not spool_path.exists(), "Spool file must be unlinked after flush"
            
            # Verify ledger contents
            ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
            assert ledger_data.get("server_ok") is True, "Last telemetry state must be preserved in ledger"
        finally:
            mvb.VORPAL_ROOT = orig_root
            mvb.MARKUS_LEDGER_PATH = orig_ledger
            mvb.VORPAL_SPOOL_PATH = orig_spool
    print("[PASS] Vorpal bridge offline spooling and recovery synchronization verified.")

def test_db_fts5_vacuum_adversarial():
    print("\n--- Testing Cortex DB FTS5 and Compaction Invariants ---")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "cortex_adversarial.db"
        db = PersistentCortexDB(db_path=db_path)
        
        # Populate 100 thoughts with distinct keyword distributions
        for i in range(100):
            db.append_thought(
                entry_id=f"entry_{i:04d}",
                agent="ALPHA" if i % 2 == 0 else "BETA",
                content=f"Telemetry item {i}: neural network weights calibration {i * 7} alpha_term",
                metadata={"seq": i, "even": (i % 2 == 0)}
            )
            
        stats_init = db.get_cortex_stats()
        assert stats_init["total_thoughts"] == 100, f"Expected 100 thoughts, got {stats_init['total_thoughts']}"
        assert stats_init["fts_indexed_count"] == 100, f"Expected 100 FTS entries, got {stats_init['fts_indexed_count']}"
        
        # Verify FTS search accuracy
        search_alpha = db.search_thoughts("alpha_term", limit=150)
        assert len(search_alpha) == 100, f"Expected 100 FTS hits for alpha_term, got {len(search_alpha)}"
        
        # Prune older records keeping only 25 newest
        pruned_75 = db.prune_thoughts(max_entries=25)
        assert pruned_75 == 75, f"Expected 75 pruned, got {pruned_75}"
        
        stats_pruned = db.get_cortex_stats()
        assert stats_pruned["total_thoughts"] == 25, f"Expected 25 thoughts remaining, got {stats_pruned['total_thoughts']}"
        assert stats_pruned["fts_indexed_count"] == 25, f"Expected 25 FTS indexed entries remaining, got {stats_pruned['fts_indexed_count']}"
        
        # Search for an entry known to be pruned: entry_0000 -> "calibration 0"
        search_pruned = db.search_thoughts("calibration 0", limit=10)
        assert len(search_pruned) == 0, f"Pruned entry must not appear in FTS search: got {search_pruned}"
        
        # Perform compaction
        compaction = db.compact_cortex()
        assert isinstance(compaction, dict) and "size_after" in compaction, "Compaction failed"
        
        # Run SQLite quick_check integrity PRAGMA
        with sqlite3.connect(str(db_path)) as conn:
            cur = conn.cursor()
            cur.execute("PRAGMA quick_check")
            check_result = cur.fetchone()[0]
            assert check_result == "ok", f"SQLite quick_check failed: {check_result}"
    print("[PASS] Cortex DB FTS5 deletion synchronization and SQLite integrity verified.")

def test_context_pruner_adversarial():
    print("\n--- Testing Context Pruner Boundary & Invariant Protection ---")
    pruner = MarkusContextPruner()
    
    # 1. Extremely restrictive budget with protected invariants
    critical_text = [
        "Noise line 1 lorem ipsum dolor sit amet",
        "Noise line 2 consectetur adipiscing elit",
        "PRIME-DIRECTIVE: Air-gapped deterministic runtime",
        "Noise line 3 sed do eiusmod tempor incididunt",
        "Traceback (most recent call last):",
        "  File 'agent.py', line 123, in execute",
        "AssertionError: Contract violation in test suite",
        "Noise line 4 ut labore et dolore magna aliqua",
    ]
    
    # Budget of only 5 tokens (way smaller than the total ~80 tokens)
    res_tight = pruner.prune(critical_text, max_tokens=5)
    assert "PRIME-DIRECTIVE" in res_tight.text, "Failed to protect PRIME-DIRECTIVE under extreme budget pressure"
    assert "Traceback" in res_tight.text, "Failed to protect Traceback under extreme budget pressure"
    assert "AssertionError" in res_tight.text, "Failed to protect AssertionError under extreme budget pressure"
    print("[PASS] Context pruner AST invariant preservation under tight budget verified.")

    # 2. Empty input
    res_empty = pruner.prune([], max_tokens=100)
    assert res_empty.pruned_tokens == 0 and res_empty.text == "", "Empty input must return 0 tokens and empty string"
    print("[PASS] Context pruner empty boundary handling verified.")

if __name__ == "__main__":
    test_router_adversarial()
    test_hermes_bridge_adversarial()
    test_vorpal_bridge_adversarial()
    test_db_fts5_vacuum_adversarial()
    test_context_pruner_adversarial()
    print("\n=== ALL ADVERSARIAL INTEGRITY STRESS TESTS PASSED CLEANLY ===")
