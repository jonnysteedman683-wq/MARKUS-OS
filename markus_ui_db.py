"""
MARKUS OS User Interface Database (markus_ui_db.py)
Provides thread-safe persistent state management, UI component layout registers,
command history, active session tracking, and notification queueing for the 
MARKUS OS Command Deck (markus-os.html) and live telemetry server (markus_server.py).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Markus.UIDB")

DEFAULT_UI_DB_PATH = Path("C:/Users/jonny/OneDrive/Desktop/New folder/markus_private/vault/markus_ui.db")


@dataclass
class UIComponentState:
    component_id: str
    visible: bool
    theme: str
    config: Dict[str, Any]
    updated_at: float


@dataclass
class UINotification:
    id: str
    level: str  # "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"
    title: str
    message: str
    timestamp: float
    read: bool = False


class MarkusUIDatabase:
    """Thread-safe SQLite database manager for MARKUS OS UI state and telemetry."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or DEFAULT_UI_DB_PATH
        self._shared_conn: Optional[sqlite3.Connection] = None
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if str(self.db_path) == ":memory:":
            if self._shared_conn is None:
                self._shared_conn = sqlite3.connect(":memory:", timeout=10.0, check_same_thread=False)
                self._shared_conn.row_factory = sqlite3.Row
            return self._shared_conn
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Component Layout & Configuration State Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ui_components (
                    component_id TEXT PRIMARY KEY,
                    visible INTEGER NOT NULL,
                    theme TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # Session Telemetry Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ui_sessions (
                    session_id TEXT PRIMARY KEY,
                    active_view TEXT NOT NULL,
                    sound_enabled INTEGER NOT NULL,
                    metrics_json TEXT NOT NULL,
                    last_active_at REAL NOT NULL
                )
            """)

            # Command History Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ui_command_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    command TEXT NOT NULL,
                    execution_status TEXT NOT NULL,
                    execution_time_ms REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

            # Notification Queue Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ui_notifications (
                    id TEXT PRIMARY KEY,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    read INTEGER NOT NULL DEFAULT 0
                )
            """)

            conn.commit()
            logger.info(f"MARKUS UI Database initialized at: {self.db_path}")

    # --- Component Registers ---

    def set_component(self, component_id: str, visible: bool = True, theme: str = "cyan", config: Optional[Dict[str, Any]] = None) -> UIComponentState:
        config_dict = config or {}
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ui_components (component_id, visible, theme, config_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(component_id) DO UPDATE SET
                    visible=excluded.visible,
                    theme=excluded.theme,
                    config_json=excluded.config_json,
                    updated_at=excluded.updated_at
            """, (component_id, 1 if visible else 0, theme, json.dumps(config_dict), now))
            conn.commit()
        return UIComponentState(component_id, visible, theme, config_dict, now)

    def get_component(self, component_id: str) -> Optional[UIComponentState]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ui_components WHERE component_id = ?", (component_id,))
            row = cursor.fetchone()
            if row:
                return UIComponentState(
                    component_id=row["component_id"],
                    visible=bool(row["visible"]),
                    theme=row["theme"],
                    config=json.loads(row["config_json"]),
                    updated_at=row["updated_at"]
                )
        return None

    def list_components(self) -> List[UIComponentState]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ui_components ORDER BY component_id ASC")
            rows = cursor.fetchall()
            return [
                UIComponentState(
                    component_id=row["component_id"],
                    visible=bool(row["visible"]),
                    theme=row["theme"],
                    config=json.loads(row["config_json"]),
                    updated_at=row["updated_at"]
                ) for row in rows
            ]

    # --- Session Management ---

    def record_session(self, session_id: str, active_view: str = "command-deck", sound_enabled: bool = True, metrics: Optional[Dict[str, Any]] = None) -> None:
        now = time.time()
        metrics_dict = metrics or {}
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ui_sessions (session_id, active_view, sound_enabled, metrics_json, last_active_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    active_view=excluded.active_view,
                    sound_enabled=excluded.sound_enabled,
                    metrics_json=excluded.metrics_json,
                    last_active_at=excluded.last_active_at
            """, (session_id, active_view, 1 if sound_enabled else 0, json.dumps(metrics_dict), now))
            conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ui_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "active_view": row["active_view"],
                    "sound_enabled": bool(row["sound_enabled"]),
                    "metrics": json.loads(row["metrics_json"]),
                    "last_active_at": row["last_active_at"]
                }
        return None

    # --- Command History ---

    def push_command(self, session_id: str, command: str, status: str = "SUCCESS", execution_time_ms: float = 0.0) -> int:
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ui_command_history (session_id, command, execution_status, execution_time_ms, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, command, status, execution_time_ms, now))
            conn.commit()
            return cursor.lastrowid or 0

    def get_recent_commands(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ui_command_history ORDER BY id DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Notifications ---

    def add_notification(self, notif_id: str, level: str, title: str, message: str) -> UINotification:
        now = time.time()
        notif = UINotification(notif_id, level, title, message, now, read=False)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ui_notifications (id, level, title, message, timestamp, read)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (notif_id, level, title, message, now))
            conn.commit()
        return notif

    def get_unread_notifications(self) -> List[UINotification]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM ui_notifications WHERE read = 0 ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            return [
                UINotification(
                    id=row["id"],
                    level=row["level"],
                    title=row["title"],
                    message=row["message"],
                    timestamp=row["timestamp"],
                    read=bool(row["read"])
                ) for row in rows
            ]

    def mark_notifications_read(self, ids: Optional[List[str]] = None) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if ids:
                placeholders = ",".join("?" for _ in ids)
                cursor.execute(f"UPDATE ui_notifications SET read = 1 WHERE id IN ({placeholders})", ids)
            else:
                cursor.execute("UPDATE ui_notifications SET read = 1")
            conn.commit()


def _test_markus_ui_db() -> None:
    """Self-test harness for MarkusUIDatabase."""
    logger.info("Executing _test_markus_ui_db self-test...")
    db = MarkusUIDatabase(db_path=Path(":memory:"))

    # Test Component API
    comp = db.set_component("hud_brand", visible=True, theme="cyan", config={"title": "MARKUS OS"})
    assert comp.component_id == "hud_brand"
    retrieved = db.get_component("hud_brand")
    assert retrieved is not None
    assert retrieved.theme == "cyan"
    assert retrieved.config["title"] == "MARKUS OS"

    # Test Session API
    db.record_session("sess_001", active_view="command-deck", sound_enabled=True, metrics={"fps": 60})
    sess = db.get_session("sess_001")
    assert sess is not None
    assert sess["active_view"] == "command-deck"
    assert sess["metrics"]["fps"] == 60

    # Test Command History API
    cmd_id = db.push_command("sess_001", "UPGRADE_ACOUSTIC_SYNAPSE", status="SUCCESS", execution_time_ms=12.5)
    assert cmd_id > 0
    cmds = db.get_recent_commands(limit=5)
    assert len(cmds) == 1
    assert cmds[0]["command"] == "UPGRADE_ACOUSTIC_SYNAPSE"

    # Test Notification Queue API
    notif = db.add_notification("n_01", "INFO", "System Boot", "Command deck online.")
    assert notif.read is False
    unread = db.get_unread_notifications()
    assert len(unread) == 1
    db.mark_notifications_read(["n_01"])
    unread_after = db.get_unread_notifications()
    assert len(unread_after) == 0

    print("ALL TESTS PASSED for markus_ui_db.py!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _test_markus_ui_db()
