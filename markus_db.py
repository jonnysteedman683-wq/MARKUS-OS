"""
MARKUS OS SQLite L3 Persistent Cortex Storage (Upgrade 2)
Provides durable FTS5-backed thought database, register persistence,
and post-mortem session forensic logging surviving kernel reboots.
"""

from __future__ import annotations
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("Markus.DB")

DEFAULT_DB_PATH = Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/vault/markus_cortex.db")

class PersistentCortexDB:
    """Thread-safe SQLite storage engine for MARKUS L3 Memory Cortex."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
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
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO registers (key, val_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    val_json=excluded.val_json,
                    updated_at=excluded.updated_at
            """, (key, val_json, time.time()))
            conn.commit()

    def get_register(self, key: str, default: Any = None) -> Any:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT val_json FROM registers WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row["val_json"])
            return default

    def append_thought(self, entry_id: str, agent: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        meta_json = json.dumps(metadata or {})
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO thoughts (entry_id, agent, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (entry_id, agent, content, meta_json, now))
            
            # Update FTS index
            cursor.execute("""
                INSERT OR REPLACE INTO thoughts_fts (entry_id, agent, content)
                VALUES (?, ?, ?)
            """, (entry_id, agent, content))
            conn.commit()

    def search_thoughts(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
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
            return [
                {
                    "entry_id": r["entry_id"],
                    "agent": r["agent"],
                    "content": r["content"],
                    "metadata": json.loads(r["metadata_json"]),
                    "created_at": r["created_at"]
                }
                for r in rows
            ]

    def cortex_execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a raw SQL statement against the Cortex DB (used by modules like Thors)."""
        with self._get_connection() as conn:
            conn.execute(sql, params)
            conn.commit()

    def get_recent_thoughts(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT entry_id, agent, content, metadata_json, created_at
                FROM thoughts
                ORDER BY created_at DESC
                LIMIT ?""",
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "entry_id": r["entry_id"],
                "agent": r["agent"],
                "content": r["content"],
                "metadata": json.loads(r["metadata_json"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

if __name__ == "__main__":
    db = PersistentCortexDB()
    db.set_register("OS_BOOT_COUNT", db.get_register("OS_BOOT_COUNT", 0) + 1)
    db.append_thought("t_001", "SENTINEL", "Kernel initialized cleanly", {"boot_phase": "POST"})
    db.append_thought("t_002", "PLANNER", "Orchestrating capability drivers", {"target": "markus_capabilities"})
    
    print(f"Boot Count: {db.get_register('OS_BOOT_COUNT')}")
    print("\nRecent Thoughts:", db.get_recent_thoughts(2))
    print("\nFTS Search 'Orchestrating':", db.search_thoughts("Orchestrating"))
