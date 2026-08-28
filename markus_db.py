"""
MARKUS OS SQLite L3 Persistent Cortex Storage (Upgrade 2 & Enhancement R3)
Provides durable FTS5-backed thought database, register persistence,
TTL thought pruning, database compaction (VACUUM/ANALYZE), cortex stats,
and post-mortem session forensic logging surviving kernel reboots.
"""

from __future__ import annotations
import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger("Markus.DB")

DEFAULT_DB_PATH = Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/vault/markus_cortex.db")

class PersistentCortexDB:
    """Thread-safe SQLite storage engine for MARKUS L3 Memory Cortex."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                # L1 Persistent Registers Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS registers (
                        key TEXT PRIMARY KEY,
                        val_json TEXT NOT NULL,
                        updated_at REAL NOT NULL
                    )
                """)
                # L3 Memory Thoughts Table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS thoughts (
                        entry_id TEXT PRIMARY KEY,
                        agent TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at REAL NOT NULL
                    )
                """)
                # FTS5 Virtual Table for Fast Semantic Keyword Search
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS thoughts_fts USING fts5(
                        entry_id UNINDEXED,
                        agent,
                        content,
                        tokenize='porter unicode61'
                    )
                """)
                conn.commit()
                logger.info(f"Initialized Persistent Cortex DB at: {self.db_path}")

    def set_register(self, key: str, value: Any) -> None:
        val_json = json.dumps(value)
        now = time.time()
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO registers (key, val_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        val_json=excluded.val_json,
                        updated_at=excluded.updated_at
                """, (key, val_json, now))
                conn.commit()

    def get_register(self, key: str, default: Any = None) -> Any:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT val_json FROM registers WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    try:
                        return json.loads(row["val_json"])
                    except Exception:
                        return row["val_json"]
                return default

    def append_thought(self, entry_id: str, agent: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        meta_json = json.dumps(metadata or {})
        now = time.time()
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO thoughts (entry_id, agent, content, metadata_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (entry_id, agent, content, meta_json, now))
                
                # Update FTS index
                cursor.execute("DELETE FROM thoughts_fts WHERE entry_id = ?", (entry_id,))
                cursor.execute("""
                    INSERT INTO thoughts_fts (entry_id, agent, content)
                    VALUES (?, ?, ?)
                """, (entry_id, agent, content))
                conn.commit()

    def search_thoughts(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT t.entry_id, t.agent, t.content, t.metadata_json, t.created_at
                    FROM thoughts_fts f
                    JOIN thoughts t ON f.entry_id = t.entry_id
                    WHERE thoughts_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, limit))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    try:
                        meta = json.loads(r["metadata_json"])
                    except Exception:
                        meta = {}
                    results.append({
                        "entry_id": r["entry_id"],
                        "agent": r["agent"],
                        "content": r["content"],
                        "metadata": meta,
                        "created_at": r["created_at"]
                    })
                return results

    def cortex_execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a raw SQL statement against the Cortex DB (used by modules like Thors)."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(sql, params)
                conn.commit()

    def get_recent_thoughts(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT entry_id, agent, content, metadata_json, created_at
                    FROM thoughts
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    try:
                        meta = json.loads(r["metadata_json"])
                    except Exception:
                        meta = {}
                    results.append({
                        "entry_id": r["entry_id"],
                        "agent": r["agent"],
                        "content": r["content"],
                        "metadata": meta,
                        "created_at": r["created_at"],
                    })
                return results

    def prune_thoughts(self, max_age_seconds: Optional[int] = None, max_entries: Optional[int] = None) -> int:
        """
        Prunes older or excess thought records from the thoughts table while keeping the most recent
        entries within max_entries or younger than max_age_seconds. Synchronously deletes matching
        rows from the thoughts_fts table.
        Returns the count of pruned thought rows.
        """
        if max_age_seconds is None and max_entries is None:
            return 0

        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                prune_ids: Set[str] = set()

                if max_age_seconds is not None:
                    cutoff_time = time.time() - float(max_age_seconds)
                    cursor.execute("SELECT entry_id FROM thoughts WHERE created_at < ?", (cutoff_time,))
                    for row in cursor.fetchall():
                        prune_ids.add(row["entry_id"])

                if max_entries is not None and max_entries >= 0:
                    cursor.execute(
                        "SELECT entry_id FROM thoughts ORDER BY created_at DESC LIMIT -1 OFFSET ?",
                        (int(max_entries),)
                    )
                    for row in cursor.fetchall():
                        prune_ids.add(row["entry_id"])

                if not prune_ids:
                    return 0

                id_tuples = [(eid,) for eid in prune_ids]
                cursor.executemany("DELETE FROM thoughts_fts WHERE entry_id = ?", id_tuples)
                cursor.executemany("DELETE FROM thoughts WHERE entry_id = ?", id_tuples)
                conn.commit()
                logger.info(f"Pruned {len(prune_ids)} thoughts from cortex DB (TTL: {max_age_seconds}s, Cap: {max_entries})")
                return len(prune_ids)

    def compact_cortex(self) -> Dict[str, Any]:
        """
        Performs full compaction on the SQLite Cortex database:
        1. Optimizes FTS5 index segments.
        2. Checkpoints WAL journal.
        3. Runs SQLite ANALYZE for query planner statistics.
        4. Executes VACUUM to reclaim free disk pages.
        Measures file size before and after, returning compaction metrics.
        """
        with self._lock:
            size_before = self.db_path.stat().st_size if self.db_path.exists() else 0
            now = time.time()

            conn = self._get_connection()
            try:
                # 1. Optimize FTS5 table
                try:
                    conn.execute("INSERT INTO thoughts_fts(thoughts_fts) VALUES('optimize')")
                    conn.commit()
                except Exception as e:
                    logger.debug(f"FTS optimize notice: {e}")

                # 2. Checkpoint WAL
                try:
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    conn.commit()
                except Exception as e:
                    logger.debug(f"WAL checkpoint notice: {e}")

                # 3. Analyze table statistics
                try:
                    conn.execute("ANALYZE")
                    conn.commit()
                except Exception as e:
                    logger.debug(f"ANALYZE notice: {e}")

                # 4. VACUUM (outside active transaction)
                old_isolation = conn.isolation_level
                conn.isolation_level = None
                try:
                    conn.execute("VACUUM")
                finally:
                    conn.isolation_level = old_isolation
            finally:
                conn.close()

            size_after = self.db_path.stat().st_size if self.db_path.exists() else 0
            freed_bytes = max(0, size_before - size_after)

            return {
                "freed_bytes": freed_bytes,
                "size_before": size_before,
                "size_after": size_after,
                "timestamp": now,
            }

    compact_db = compact_cortex  # Operational alias

    def get_cortex_stats(self) -> Dict[str, Any]:
        """Returns summary dictionary containing register count, total thoughts count, FTS indexed count, DB path, and file size in bytes."""
        with self._lock:
            size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM registers")
                reg_count = int(cursor.fetchone()[0])

                cursor.execute("SELECT COUNT(*) FROM thoughts")
                thoughts_count = int(cursor.fetchone()[0])

                cursor.execute("SELECT COUNT(*) FROM thoughts_fts")
                fts_count = int(cursor.fetchone()[0])

            return {
                "register_count": reg_count,
                "total_thoughts": thoughts_count,
                "thoughts_count": thoughts_count,
                "fts_indexed_count": fts_count,
                "fts_count": fts_count,
                "db_path": str(self.db_path),
                "file_size_bytes": size_bytes,
                "size_bytes": size_bytes,
            }


def _test_db() -> None:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    print("=== MARKUS Persistent Cortex DB Subsystem Test ===")
    import tempfile
    import shutil
    temp_dir = Path(tempfile.mkdtemp(prefix="markus_cortex_test_"))
    test_db_path = temp_dir / "test_cortex.db"

    try:
        db = PersistentCortexDB(db_path=test_db_path)

        # 1. Test Registers
        db.set_register("TEST_KEY", {"version": "1.0", "status": "ACTIVE"})
        reg_val = db.get_register("TEST_KEY")
        assert isinstance(reg_val, dict) and reg_val.get("status") == "ACTIVE", "Register fetch failed"
        assert db.get_register("NON_EXISTENT", default="DEF") == "DEF", "Register default fallback failed"

        # Overwrite register
        db.set_register("TEST_KEY", {"version": "2.0", "status": "UPGRADED"})
        reg_val2 = db.get_register("TEST_KEY")
        assert reg_val2.get("version") == "2.0", "Register update failed"

        # 2. Test Thoughts & FTS
        for i in range(10):
            db.append_thought(
                entry_id=f"t_{i:03d}",
                agent="AGENT_ALPHA" if i % 2 == 0 else "AGENT_BETA",
                content=f"Log event {i}: Quantum resonance frequency calibration {i * 100}MHz",
                metadata={"iteration": i, "severity": "INFO"}
            )

        recent = db.get_recent_thoughts(limit=5)
        assert len(recent) == 5, f"Expected 5 recent thoughts, got {len(recent)}"
        assert recent[0]["entry_id"] == "t_009", "Recent thoughts ordering mismatch"

        search_res = db.search_thoughts("calibration", limit=10)
        assert len(search_res) == 10, f"Expected 10 FTS search matches, got {len(search_res)}"

        # 3. Test Stats before pruning
        stats_before = db.get_cortex_stats()
        assert stats_before["register_count"] == 1, "Register count mismatch"
        assert stats_before["total_thoughts"] == 10, "Thoughts count mismatch"
        assert stats_before["fts_indexed_count"] == 10, "FTS count mismatch"
        assert stats_before["file_size_bytes"] > 0, "File size should be positive"

        # 4. Test Thought Pruning (max_entries cap)
        pruned_count = db.prune_thoughts(max_entries=4)
        assert pruned_count == 6, f"Expected 6 pruned thoughts, got {pruned_count}"

        stats_after_cap = db.get_cortex_stats()
        assert stats_after_cap["total_thoughts"] == 4, f"Expected 4 thoughts left, got {stats_after_cap['total_thoughts']}"
        assert stats_after_cap["fts_indexed_count"] == 4, f"Expected 4 FTS entries left, got {stats_after_cap['fts_indexed_count']}"

        # 5. Test Thought Pruning (max_age_seconds)
        # Pruning thoughts older than 0 seconds prunes all remaining
        pruned_ttl = db.prune_thoughts(max_age_seconds=0)
        assert pruned_ttl == 4, f"Expected 4 thoughts pruned by TTL, got {pruned_ttl}"
        assert db.get_cortex_stats()["total_thoughts"] == 0, "Expected 0 thoughts after full TTL purge"
        assert db.get_cortex_stats()["fts_indexed_count"] == 0, "Expected 0 FTS entries after full TTL purge"

        # 6. Test Compaction (VACUUM and ANALYZE)
        compaction = db.compact_cortex()
        assert "freed_bytes" in compaction and "size_before" in compaction and "size_after" in compaction and "timestamp" in compaction, "Compaction metrics incomplete"
        assert compaction["size_after"] > 0, "Compacted size should be positive"

        # 7. Concurrent Thread Safety Test
        errors = []
        def worker_task(thread_id: int):
            try:
                for j in range(5):
                    db.set_register(f"THREAD_REG_{thread_id}_{j}", j)
                    db.append_thought(f"t_thread_{thread_id}_{j}", "CONCURRENT_WORKER", f"Concurrent thought {thread_id}-{j}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker_task, args=(tid,)) for tid in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Concurrent thread errors encountered: {errors}"
        concurrent_stats = db.get_cortex_stats()
        assert concurrent_stats["total_thoughts"] == 20, f"Expected 20 concurrent thoughts, got {concurrent_stats['total_thoughts']}"
        assert concurrent_stats["fts_indexed_count"] == 20, f"Expected 20 concurrent FTS entries, got {concurrent_stats['fts_indexed_count']}"

        print(f"Stats summary: {concurrent_stats}")
        print(f"Compaction summary: {compaction}")
        print("[PASS] Persistent Cortex DB Subsystem Test: PASSED")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    _test_db()

