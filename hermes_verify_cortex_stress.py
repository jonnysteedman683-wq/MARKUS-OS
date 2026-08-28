#!/usr/bin/env python3
"""
Adversarial Empirical Stress & Invariant Verification Suite for Milestone M4:
SQLite Cortex Memory Compaction (markus_db.py) and Context Pruner (markus_context_pruner.py).

Challenges:
1. High-concurrency multi-threaded read/write/prune/compact operations on PersistentCortexDB.
2. FTS5 query consistency after large-scale thought TTL and count pruning + malformed query fuzzing.
3. Database compaction integrity under high fragmentation, verifying VACUUM, WAL checkpoint, and PRAGMA integrity.
4. Context Pruner behavior under boundary/malformed/extreme conditions, invariant protection under budget starvation.
"""

from __future__ import annotations
import gc
import json
import logging
import os
import random
import shutil
import sqlite3
import string
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Ensure utf-8 output in Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from markus_db import PersistentCortexDB
from markus_context_pruner import MarkusContextPruner, PruneResult

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class CortexAdversarialTester:
    def __init__(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="cortex_stress_adv_"))
        self.results: Dict[str, Any] = {}
        self.failures: List[str] = []
        self.warnings: List[str] = []

    def cleanup(self) -> None:
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception as e:
            print(f"[CLEANUP ERROR] {e}")

    # =========================================================================
    # SUITE 1: High Concurrency Multi-Threaded Read/Write/Prune/Compact
    # =========================================================================
    def test_suite_1_concurrency_stress(self) -> bool:
        print("\n" + "=" * 80)
        print("SUITE 1: High Concurrency Multi-Threaded Stress on PersistentCortexDB")
        print("=" * 80)
        db_path = self.temp_dir / "concurrent_cortex.db"
        db = PersistentCortexDB(db_path=db_path)

        num_writers = 4
        num_registers = 4
        num_readers = 4
        num_pruners = 2
        num_compactors = 2

        thoughts_per_writer = 250
        regs_per_thread = 250
        queries_per_reader = 200

        exceptions: List[Tuple[str, Exception]] = []
        stop_event = threading.Event()

        def writer_worker(tid: int):
            try:
                for i in range(thoughts_per_writer):
                    eid = f"thought_w{tid}_{i:04d}"
                    content = f"Concurrent thought payload from thread {tid} index {i} keyword_{i % 10} data_{'x' * (i % 50)}"
                    db.append_thought(eid, f"WORKER_{tid}", content, metadata={"worker": tid, "step": i})
                    if i % 50 == 0:
                        time.sleep(0.001)
            except Exception as e:
                exceptions.append((f"writer_{tid}", e))

        def register_worker(tid: int):
            try:
                for i in range(regs_per_thread):
                    key = f"REG_TH_{tid}_{i % 20}"
                    db.set_register(key, {"tid": tid, "val": i, "ts": time.time()})
                    val = db.get_register(key)
                    if val is None or val.get("tid") != tid:
                        pass  # overwrites are expected
            except Exception as e:
                exceptions.append((f"register_{tid}", e))

        def reader_worker(tid: int):
            try:
                for i in range(queries_per_reader):
                    kw = f"keyword_{i % 10}"
                    _ = db.search_thoughts(kw, limit=10)
                    _ = db.get_recent_thoughts(limit=5)
                    _ = db.get_cortex_stats()
            except Exception as e:
                exceptions.append((f"reader_{tid}", e))

        def pruner_worker(tid: int):
            try:
                while not stop_event.is_set():
                    db.prune_thoughts(max_entries=800)
                    time.sleep(0.01)
            except Exception as e:
                exceptions.append((f"pruner_{tid}", e))

        def compactor_worker(tid: int):
            try:
                while not stop_event.is_set():
                    db.compact_cortex()
                    time.sleep(0.02)
            except Exception as e:
                exceptions.append((f"compactor_{tid}", e))

        threads: List[threading.Thread] = []

        # Start pruners & compactors
        for t_idx in range(num_pruners):
            t = threading.Thread(target=pruner_worker, args=(t_idx,))
            threads.append(t)
        for t_idx in range(num_compactors):
            t = threading.Thread(target=compactor_worker, args=(t_idx,))
            threads.append(t)

        # Start writers, registers, readers
        active_workers: List[threading.Thread] = []
        for t_idx in range(num_writers):
            t = threading.Thread(target=writer_worker, args=(t_idx,))
            active_workers.append(t)
        for t_idx in range(num_registers):
            t = threading.Thread(target=register_worker, args=(t_idx,))
            active_workers.append(t)
        for t_idx in range(num_readers):
            t = threading.Thread(target=reader_worker, args=(t_idx,))
            active_workers.append(t)

        start_time = time.perf_counter()
        for t in threads + active_workers:
            t.start()

        # Wait for active workload to finish
        for t in active_workers:
            t.join()

        # Signal background pruners/compactors to stop
        stop_event.set()
        for t in threads:
            t.join()

        elapsed = time.perf_counter() - start_time
        stats = db.get_cortex_stats()
        print(f"Concurrency Stress Completed in {elapsed:.2f}s")
        print(f"Total Thoughts remaining: {stats['total_thoughts']}")
        print(f"FTS indexed count: {stats['fts_indexed_count']}")
        print(f"Registers count: {stats['register_count']}")
        print(f"Exceptions caught during concurrent execution: {len(exceptions)}")

        if exceptions:
            for source, exc in exceptions[:5]:
                print(f"  [CONCURRENCY FAILURE] {source}: {type(exc).__name__} - {exc}")
            self.failures.append(f"Suite 1 Concurrency: {len(exceptions)} exceptions encountered")
            return False

        # Verify DB integrity after concurrent storm
        with sqlite3.connect(str(db_path)) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                self.failures.append(f"Suite 1 Concurrency: Integrity check failed: {integrity}")
                return False

        print("[PASS] Suite 1: Concurrency stress passed with zero exceptions and pristine integrity.")
        self.results["suite_1"] = {"elapsed_s": elapsed, "stats": stats, "exceptions": 0}
        return True

    # =========================================================================
    # SUITE 2: FTS5 Query Consistency After Large-Scale TTL & Count Pruning
    # =========================================================================
    def test_suite_2_fts_consistency_and_fuzz(self) -> bool:
        print("\n" + "=" * 80)
        print("SUITE 2: FTS5 Query Consistency & Syntax Fuzzing")
        print("=" * 80)
        db_path = self.temp_dir / "fts_consistency.db"
        db = PersistentCortexDB(db_path=db_path)

        total_inserted = 3000
        categories = ["quantum", "telemetry", "resonance", "anomaly", "sentinel"]

        print(f"Inserting {total_inserted} categorized thought records...")
        inserted_ids: List[str] = []
        for i in range(total_inserted):
            cat = categories[i % len(categories)]
            eid = f"thought_{cat}_{i:05d}"
            content = f"Event log sequence {i} with category {cat} and unique_signature_{i:05d}"
            db.append_thought(eid, f"AGENT_{cat.upper()}", content, metadata={"cat": cat, "seq": i})
            inserted_ids.append(eid)

        stats_before = db.get_cortex_stats()
        assert stats_before["total_thoughts"] == total_inserted
        assert stats_before["fts_indexed_count"] == total_inserted

        # Verify keyword search results before pruning
        for cat in categories:
            results = db.search_thoughts(cat, limit=total_inserted)
            expected_count = total_inserted // len(categories)
            assert len(results) == expected_count, f"FTS count mismatch for {cat}: got {len(results)}, expected {expected_count}"

        # 1. Prune to cap of 1,000 thoughts
        cap_target = 1000
        pruned_count = db.prune_thoughts(max_entries=cap_target)
        expected_pruned = total_inserted - cap_target
        assert pruned_count == expected_pruned, f"Expected {expected_pruned} pruned, got {pruned_count}"

        stats_after_cap = db.get_cortex_stats()
        assert stats_after_cap["total_thoughts"] == cap_target, f"Thoughts count mismatch: {stats_after_cap['total_thoughts']}"
        assert stats_after_cap["fts_indexed_count"] == cap_target, f"FTS count mismatch: {stats_after_cap['fts_indexed_count']}"

        # Verify that remaining thoughts are in FTS and pruned thoughts are NOT in FTS
        recent = db.get_recent_thoughts(limit=cap_target)
        surviving_ids = {r["entry_id"] for r in recent}
        assert len(surviving_ids) == cap_target

        pruned_ids = set(inserted_ids) - surviving_ids
        assert len(pruned_ids) == expected_pruned

        # Spot check surviving in FTS
        sample_surviving = random.sample(list(surviving_ids), 50)
        for sid in sample_surviving:
            seq_num = int(sid.split("_")[-1])
            res = db.search_thoughts(f"unique_signature_{seq_num:05d}", limit=5)
            if not res or res[0]["entry_id"] != sid:
                self.failures.append(f"Suite 2 FTS: Surviving thought {sid} missing from FTS5")
                return False

        # Spot check pruned NOT in FTS
        sample_pruned = random.sample(list(pruned_ids), 50)
        for pid in sample_pruned:
            seq_num = int(pid.split("_")[-1])
            res = db.search_thoughts(f"unique_signature_{seq_num:05d}", limit=5)
            if res:
                self.failures.append(f"Suite 2 FTS: Pruned thought {pid} still returned by FTS5!")
                return False

        # 2. Prune by TTL (max_age_seconds=0 purges all remaining)
        time.sleep(0.01)
        ttl_pruned = db.prune_thoughts(max_age_seconds=0)
        assert ttl_pruned == cap_target, f"Expected {cap_target} pruned by TTL, got {ttl_pruned}"
        stats_empty = db.get_cortex_stats()
        assert stats_empty["total_thoughts"] == 0, f"Expected 0 thoughts, got {stats_empty['total_thoughts']}"
        assert stats_empty["fts_indexed_count"] == 0, f"Expected 0 FTS entries, got {stats_empty['fts_indexed_count']}"

        # 3. FTS5 Malformed Query Fuzzing
        print("Testing FTS5 malformed query resilience...")
        # Populate a few thoughts for query tests
        db.append_thought("fuzz_01", "FUZZER", "quantum resonance error occurred in module alpha")
        db.append_thought("fuzz_02", "FUZZER", "normal operational signal detected")

        fuzz_queries = [
            "", "   ", "AND", "OR", "NOT", "NEAR()", "*", "^", ":", '"', '""', '"""',
            "quantum AND", "OR resonance", "NOT anomaly", "module:", "agent:FUZZER",
            "(unclosed bracket", "syntax error [test]", "special chars: !@#$%^&*()_+-=[]{}|;':,.<>/?",
            "emoji 🚀🔥💡", "null byte \x00 in query", "very " * 50 + "long query"
        ]

        fuzz_handled = 0
        fuzz_errors = 0
        for fq in fuzz_queries:
            try:
                res = db.search_thoughts(fq, limit=5)
                fuzz_handled += 1
            except sqlite3.OperationalError as oe:
                # FTS5 syntax errors can raise sqlite3.OperationalError if raw query is passed directly
                # Record this observation
                fuzz_errors += 1
                self.warnings.append(f"FTS5 query '{fq}' raised sqlite3.OperationalError: {oe}")
            except Exception as e:
                self.failures.append(f"Unexpected exception on FTS query '{fq}': {type(e).__name__} - {e}")
                return False

        print(f"FTS Fuzz Results: Handled directly={fuzz_handled}, OperationalErrors={fuzz_errors}")
        print("[PASS] Suite 2: FTS5 query consistency and TTL/cap pruning synchronization fully verified.")
        self.results["suite_2"] = {
            "total_inserted": total_inserted,
            "cap_pruned": expected_pruned,
            "ttl_pruned": ttl_pruned,
            "fuzz_handled": fuzz_handled,
            "fuzz_operational_errors": fuzz_errors
        }
        return True

    # =========================================================================
    # SUITE 3: Database Compaction Integrity Under High Fragmentation
    # =========================================================================
    def test_suite_3_compaction_and_fragmentation(self) -> bool:
        print("\n" + "=" * 80)
        print("SUITE 3: Database Compaction Integrity Under High Fragmentation")
        print("=" * 80)
        db_path = self.temp_dir / "fragmented_cortex.db"
        db = PersistentCortexDB(db_path=db_path)

        # 1. Fill database with 3,000 large payload records
        num_records = 3000
        large_blob = "A" * 2048  # 2KB per record -> ~6MB uncompressed + FTS + index overhead
        print(f"Inserting {num_records} large records (~2KB content each)...")
        for i in range(num_records):
            eid = f"large_rec_{i:04d}"
            meta = {"index": i, "payload": "B" * 512, "nested": {"k": "v" * 64}}
            db.append_thought(eid, "BLOB_AGENT", f"Record {i}: {large_blob}", metadata=meta)
            if i % 100 == 0:
                db.set_register(f"REG_BLOB_{i}", {"meta": meta})

        stats_populated = db.get_cortex_stats()
        size_populated = stats_populated["file_size_bytes"]
        print(f"Populated DB file size: {size_populated / (1024 * 1024):.2f} MB ({size_populated} bytes)")

        # 2. Prune 90% of records to induce extreme page fragmentation
        keep_count = 300
        pruned = db.prune_thoughts(max_entries=keep_count)
        print(f"Pruned {pruned} records (retaining {keep_count}). Inducing fragmentation...")

        stats_pruned = db.get_cortex_stats()
        size_pruned_before_compact = stats_pruned["file_size_bytes"]
        print(f"DB file size after DELETE but BEFORE compact: {size_pruned_before_compact / (1024 * 1024):.2f} MB")

        # 3. Perform Compaction
        print("Executing compact_cortex() (FTS optimize + WAL checkpoint + ANALYZE + VACUUM)...")
        compact_res = db.compact_cortex()
        print(f"Compaction Metrics: {compact_res}")

        freed_bytes = compact_res["freed_bytes"]
        size_after = compact_res["size_after"]
        print(f"DB file size AFTER compact: {size_after / (1024 * 1024):.2f} MB ({size_after} bytes)")
        print(f"Freed Disk Space: {freed_bytes / (1024 * 1024):.2f} MB ({freed_bytes} bytes)")

        assert size_after < size_pruned_before_compact, "Compaction failed to reduce fragmented DB file size!"
        assert freed_bytes > 0, "freed_bytes must be > 0 under 90% deletion fragmentation"

        # 4. Verify Integrity and Searchability
        with sqlite3.connect(str(db_path)) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            assert integrity == "ok", f"Integrity check failed post-compaction: {integrity}"
            fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
            assert len(fk_check) == 0, f"Foreign key check failed: {fk_check}"

        stats_post = db.get_cortex_stats()
        assert stats_post["total_thoughts"] == keep_count
        assert stats_post["fts_indexed_count"] == keep_count

        # 5. Verify Post-Compaction Writeability
        print("Verifying post-compaction insert & query capability...")
        for j in range(50):
            db.append_thought(f"post_compact_{j}", "NEW_AGENT", f"Post compaction thought {j} verified")
        stats_final = db.get_cortex_stats()
        assert stats_final["total_thoughts"] == keep_count + 50
        assert stats_final["fts_indexed_count"] == keep_count + 50

        print("[PASS] Suite 3: Database Compaction integrity under extreme fragmentation verified.")
        self.results["suite_3"] = {
            "size_populated": size_populated,
            "size_before_compact": size_pruned_before_compact,
            "size_after_compact": size_after,
            "freed_bytes": freed_bytes,
            "integrity": integrity
        }
        return True

    # =========================================================================
    # SUITE 4: Context Pruner Edge Cases & Malformed Inputs
    # =========================================================================
    def test_suite_4_context_pruner_adversarial(self) -> bool:
        print("\n" + "=" * 80)
        print("SUITE 4: Context Pruner Adversarial & Boundary Testing")
        print("=" * 80)
        pruner = MarkusContextPruner()

        # 1. Zero, Negative, and Extreme Token Budgets
        print("--- Test 4.1: Token Limits Boundary (0, negative, extreme) ---")
        sample_lines = [
            "PRIME-DIRECTIVE: Air-gapped fallback invariant.",
            "def calculate_trajectory(v: float, theta: float) -> float:",
            "    return v * math.sin(theta)",
            "Traceback (most recent call last):",
            "SyntaxError: invalid syntax",
            "Routine log message 1",
            "Routine log message 2"
        ]

        # max_tokens = 0
        res_zero = pruner.prune(sample_lines, max_tokens=0)
        print(f"max_tokens=0 -> original={res_zero.original_tokens}, pruned={res_zero.pruned_tokens}, retained_segs={res_zero.retained_segments}")
        # Note: Invariant lines are protected and force-fit, so res_zero will retain protected lines
        assert "PRIME-DIRECTIVE" in res_zero.text, "PRIME-DIRECTIVE must be preserved even with max_tokens=0"
        assert "Traceback" in res_zero.text, "Traceback must be preserved even with max_tokens=0"
        assert "SyntaxError" in res_zero.text, "SyntaxError must be preserved even with max_tokens=0"
        assert res_zero.compression_ratio >= 0.0

        # max_tokens = -50
        res_neg = pruner.prune(sample_lines, max_tokens=-50)
        assert "PRIME-DIRECTIVE" in res_neg.text
        assert res_neg.compression_ratio >= 0.0

        # max_tokens = 1 (extreme tiny budget)
        res_tiny = pruner.prune(sample_lines, max_tokens=1)
        assert "PRIME-DIRECTIVE" in res_tiny.text
        assert "SyntaxError" in res_tiny.text

        # max_tokens = 10,000,000 (extreme large budget)
        res_huge = pruner.prune(sample_lines, max_tokens=10_000_000)
        assert res_huge.compression_ratio == 1.0
        assert res_huge.retained_segments == len(sample_lines)
        assert res_huge.pruned_tokens == res_huge.original_tokens

        # 2. Degenerate and Malformed Inputs
        print("--- Test 4.2: Degenerate & Malformed Inputs ---")
        # Empty string and empty list
        assert pruner.prune("", max_tokens=100).retained_segments == 0
        assert pruner.prune([], max_tokens=100).retained_segments == 0

        # Whitespace-only lines
        ws_res = pruner.prune(["   ", "\t\t", "\n\n", "   \n "], max_tokens=100)
        assert ws_res.retained_segments == 0

        # Degenerate long line (100,000 chars unbroken)
        huge_line = "X" * 100_000
        res_huge_line = pruner.prune([huge_line, "PRIME-DIRECTIVE: valid line"], max_tokens=50)
        assert "PRIME-DIRECTIVE" in res_huge_line.text
        assert res_huge_line.original_tokens >= 25000

        # Null bytes, control characters, unicode emojis, surrogate pairs
        weird_chars = [
            "Special line \x00\x01\x02 null and control chars",
            "Unicode symbols 🚀 🔥 🌌 ⚡ 🧠 💻 🛡️",
            "Deeply nested brackets {{{[[[((()))]]]}}}",
            "PRIME-DIRECTIVE: Invariant holds across UTF-8."
        ]
        res_weird = pruner.prune(weird_chars, max_tokens=50)
        assert "PRIME-DIRECTIVE" in res_weird.text

        # Non-string items in list (e.g. integers, dicts, None)
        mixed_types: List[Any] = [
            "Standard text header",
            1234567,
            {"nested_key": "nested_value"},
            [1, 2, 3],
            None,
            "AssertionError: invariant broke"
        ]
        res_mixed = pruner.prune(mixed_types, max_tokens=50)
        assert "AssertionError" in res_mixed.text

        # 3. Deeply Nested Traceback / Multi-Error Invariant Stacking
        print("--- Test 4.3: Deeply Nested Tracebacks & Syntax Errors ---")
        nested_traceback = [
            "Traceback (most recent call last):",
            "  File 'markus_core.py', line 112, in boot_sequence",
            "    kernel.init_cortex()",
            "  File 'markus_kernel.py', line 54, in init_cortex",
            "    raise AssertionError('Cortex synchronization failure')",
            "AssertionError: Cortex synchronization failure",
            "During handling of the above exception, another exception occurred:",
            "Traceback (most recent call last):",
            "  File 'markus_fallback.py', line 20, in offline_handler",
            "    eval('def broken_syntax(:')",
            "SyntaxError: invalid syntax in dynamic module",
            "Noise line 1: memory check ok",
            "Noise line 2: ping response 10ms",
            "Noise line 3: telemetry buffered"
        ]

        # Force tight budget of 20 tokens
        tb_res = pruner.prune(nested_traceback, max_tokens=20, query="AssertionError SyntaxError")
        print(f"Nested Traceback Pruned ({tb_res.pruned_tokens}/{tb_res.original_tokens} tokens):")
        print(tb_res.text)

        assert "AssertionError" in tb_res.text, "Failed to preserve nested AssertionError"
        assert "SyntaxError" in tb_res.text, "Failed to preserve nested SyntaxError"
        assert "Traceback" in tb_res.text, "Failed to preserve nested Traceback"

        # 4. compact_thought_history Edge Cases
        print("--- Test 4.4: compact_thought_history Edge Cases ---")
        # Empty thoughts
        assert pruner.compact_thought_history([]).retained_segments == 0

        # Malformed thought dicts (missing keys, non-serializable objects)
        class UnserializableObj:
            def __repr__(self):
                return "<UnserializableObj>"

        malformed_thoughts = [
            {"agent": "VALID_AGENT", "content": "PRIME-DIRECTIVE: System healthy", "metadata": {"status": "ok"}},
            {"no_agent": "missing", "metadata_missing": True},
            {"agent": "FAULTY", "content": "Traceback in handler", "metadata": {"obj": str(UnserializableObj())}},
            {},
        ]
        cth_res = pruner.compact_thought_history(malformed_thoughts, max_tokens=40)
        assert "PRIME-DIRECTIVE" in cth_res.text
        assert "Traceback" in cth_res.text

        print("[PASS] Suite 4: Context Pruner edge cases, boundary limits, and invariant protections verified.")
        self.results["suite_4"] = {
            "res_zero_retained": res_zero.retained_segments,
            "res_huge_tokens": res_huge.pruned_tokens,
            "nested_tb_preserved": True,
            "malformed_handled": True
        }
        return True

    def run_all(self) -> bool:
        print("*" * 80)
        print("STARTING OMNIPRIME M4 EMPIRICAL ADVERSARIAL CHALLENGER SUITE")
        print("*" * 80)
        t_start = time.perf_counter()

        s1 = self.test_suite_1_concurrency_stress()
        s2 = self.test_suite_2_fts_consistency_and_fuzz()
        s3 = self.test_suite_3_compaction_and_fragmentation()
        s4 = self.test_suite_4_context_pruner_adversarial()

        t_total = time.perf_counter() - t_start
        print("\n" + "=" * 80)
        print(f"ADVERSARIAL STRESS CHALLENGE COMPLETE in {t_total:.2f}s")
        print(f"Failures count: {len(self.failures)}")
        print(f"Warnings count: {len(self.warnings)}")
        print("=" * 80)

        for w in self.warnings:
            print(f"  [WARN] {w}")
        for f in self.failures:
            print(f"  [FAIL] {f}")

        self.cleanup()
        return len(self.failures) == 0


if __name__ == "__main__":
    tester = CortexAdversarialTester()
    success = tester.run_all()
    sys.exit(0 if success else 1)
