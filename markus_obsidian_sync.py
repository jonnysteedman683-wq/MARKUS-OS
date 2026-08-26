"""
MARKUS OS Obsidian Palace Knowledge Synchronizer (Upgrade 7)
Automatically bridges SQLite L3 Cortex thoughts into the Obsidian Vault under
<vault>/Journal/Markus/ with daily digest rollups, semantic tagging, and an
append-only live thought stream.

Vault targeting (2026-08-26): the canonical live vault is now `VORPAL Vault`
under Documents. The legacy `Obsidian Vault` path is a frozen reference and is
kept only as a fallback when VORPAL Vault is absent.

Two outputs per day under Journal/Markus/:
  YYYY-MM-DD-MARKUS-CORTEX.md  — rolling digest of the N most recent thoughts
                                 (regenerated on each sync run)
  YYYY-MM-DD-MARKUS-LIVE.md    — append-only live thought stream. New thoughts
                                 are appended as markdown bullets, tracked by a
                                 VAULT_SYNC_LAST_TS watermark in the cortex DB,
                                 so nothing is ever rewritten or duplicated.
"""

from __future__ import annotations
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from markus_db import PersistentCortexDB

logger = logging.getLogger("Markus.ObsidianSync")

WATERMARK_KEY = "VAULT_SYNC_LAST_TS"


def _resolve_vault_path() -> Path:
    """Prefer the live VORPAL Vault; fall back to the frozen Obsidian Vault ref."""
    user_home = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
    vorpal = user_home / "OneDrive" / "Documents" / "VORPAL Vault"
    legacy = user_home / "OneDrive" / "Documents" / "Obsidian Vault"
    if vorpal.exists():
        return vorpal
    return legacy


class MarkusObsidianSync:
    """Synchronizes persistent memory cortex entries to Obsidian markdown notes."""

    def __init__(self, vault_path: Optional[Path] = None, db: Optional[PersistentCortexDB] = None) -> None:
        self.vault_path = vault_path or _resolve_vault_path()
        self.markus_journal_dir = self.vault_path / "Journal" / "Markus"
        self.markus_journal_dir.mkdir(parents=True, exist_ok=True)
        self.db = db or PersistentCortexDB()

    # ------------------------------------------------------------------ utils
    def _daily_paths(self, now_dt: datetime) -> tuple:
        date_str = now_dt.strftime("%Y-%m-%d")
        digest = self.markus_journal_dir / f"{date_str}-MARKUS-CORTEX.md"
        live = self.markus_journal_dir / f"{date_str}-MARKUS-LIVE.md"
        return date_str, digest, live

    # ------------------------------------------------------ rolling digest
    def sync_daily_digest(self, limit: int = 50) -> Dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        date_str, daily_file, _ = self._daily_paths(now_dt)

        thoughts = self.db.get_recent_thoughts(limit=limit)
        registers = self.db.get_register("OS_STATUS", "ACTIVE")
        boot_count = self.db.get_register("OS_BOOT_COUNT", 1)

        lines = [
            f"# MARKUS OS Memory Cortex Digest — {date_str}",
            "",
            f"- **Generated At:** `{now_dt.isoformat()}`",
            f"- **Kernel Status:** `{registers}`",
            f"- **Boot Count:** `{boot_count}`",
            f"- **Synchronized Entries:** `{len(thoughts)}`",
            "",
            "---",
            "",
            "## 🧠 Recent L3 Cortex Thoughts & Forensics",
            "",
            "| Time (UTC) | Agent | Thought Content | Metadata |",
            "|---|---|---|---|"
        ]

        for t in thoughts:
            ts = datetime.fromtimestamp(t["created_at"], tz=timezone.utc).strftime("%H:%M:%S")
            meta_str = f"`{json.dumps(t['metadata'])}`" if t["metadata"] else "—"
            clean_content = t["content"].replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {ts} | `{t['agent']}` | {clean_content} | {meta_str} |")

        lines.extend([
            "",
            "---",
            "*Autonomously synchronized by MARKUS OS Obsidian Palace Bridge.*"
        ])

        content = "\n".join(lines)
        daily_file.write_text(content, encoding="utf-8")
        logger.info(f"Synchronized {len(thoughts)} thoughts to Obsidian note: {daily_file}")

        return {
            "status": "SYNCHRONIZED",
            "target_file": str(daily_file),
            "entries_written": len(thoughts),
            "timestamp": time.time()
        }

    # ------------------------------------------------- append-only live stream
    def append_new_thoughts(self, batch: int = 200) -> Dict[str, Any]:
        """Append cortex thoughts newer than the watermark to the day's LIVE file.

        Watermark (VAULT_SYNC_LAST_TS) lives in the cortex DB registers, so the
        stream is idempotent across restarts and never rewrites old bullets.
        """
        now_dt = datetime.now(timezone.utc)
        date_str, _, live_file = self._daily_paths(now_dt)
        watermark = self.db.get_register(WATERMARK_KEY, 0.0) or 0.0

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT entry_id, agent, content, metadata_json, created_at "
                "FROM thoughts WHERE created_at > ? ORDER BY created_at ASC LIMIT ?",
                (float(watermark), batch),
            )
            rows = cursor.fetchall()

        if not rows:
            return {
                "status": "UP_TO_DATE",
                "target_file": str(live_file),
                "entries_written": 0,
                "watermark": watermark,
                "timestamp": time.time(),
            }

        new_watermark = max(r["created_at"] for r in rows)
        bullets = [
            "",
            f"## Live Stream — {datetime.fromtimestamp(new_watermark, tz=timezone.utc).strftime('%H:%M:%S')}",
            "",
        ]
        for r in rows:
            ts = datetime.fromtimestamp(r["created_at"], tz=timezone.utc).strftime("%H:%M:%S")
            content = r["content"].replace("\n", " ").strip()
            meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
            meta_str = f" `{json.dumps(meta)}`" if meta else ""
            bullets.append(f"- **{ts}** · `{r['agent']}` · {content}{meta_str}")

        with open(live_file, "a", encoding="utf-8") as f:
            f.write("\n".join(bullets) + "\n")

        self.db.set_register(WATERMARK_KEY, new_watermark)
        logger.info(f"Appended {len(rows)} new thoughts to {live_file} (watermark -> {new_watermark})")

        return {
            "status": "APPENDED",
            "target_file": str(live_file),
            "entries_written": len(rows),
            "watermark": new_watermark,
            "timestamp": time.time(),
        }

    # ----------------------------------------------- interactive canvas graph
    def generate_canvas_graph(self) -> Dict[str, Any]:
        """Generate an interactive Obsidian Canvas (.canvas) knowledge graph map
        visualizing system components, active cortex thoughts, and VORPAL goals.
        """
        canvas_file = self.markus_journal_dir / "MARKUS-OS-KNOWLEDGE-GRAPH.canvas"

        thoughts = self.db.get_recent_thoughts(limit=10)
        os_status = self.db.get_register("OS_STATUS", "ACTIVE")

        nodes = []
        edges = []

        # Central Kernel Node
        nodes.append({
            "id": "node_kernel",
            "type": "text",
            "text": f"# 🧠 MARKUS OS Kernel\n- **Status:** `{os_status}`\n- **Vault:** `VORPAL Vault`",
            "x": 0, "y": 0, "width": 300, "height": 160, "color": "1"
        })

        # Subsystem Nodes
        subsystems = [
            ("node_router", "⚡ Zero-Cost Router", "markus_router.py\nRoutes to free-tier & local Ollama", -400, -200, "2"),
            ("node_vorpal", "🎯 VORPAL Goal DAG", "markus_vorpal_bridge.py\n35 North Star Goals (26 done)", 400, -200, "3"),
            ("node_cortex", "💾 L3 Cortex DB", "markus_db.py\nSQLite FTS5 Persistent Memory", -400, 200, "4"),
            ("node_ui", "🖥️ Cyberpunk UI OS", "markus_ui_os.html\nLive SSE Stream & Web Audio", 400, 200, "5"),
            ("node_hermes", "🛠️ HERMES Task Engine", "markus_kanban_worker.py\nKanban Task Execution Bridge", 0, -350, "6"),
        ]

        for sub_id, title, desc, x, y, color in subsystems:
            nodes.append({
                "id": sub_id,
                "type": "text",
                "text": f"### {title}\n{desc}",
                "x": x, "y": y, "width": 280, "height": 140, "color": color
            })
            edges.append({
                "id": f"edge_kernel_{sub_id}",
                "fromNode": "node_kernel", "fromSide": "top" if y < 0 else "bottom",
                "toNode": sub_id, "toSide": "bottom" if y < 0 else "top"
            })

        # Recent Thought Nodes
        y_offset = 450
        for i, t in enumerate(thoughts[:5]):
            t_id = f"node_thought_{i}"
            clean_text = t["content"].replace("\n", " ")[:120]
            nodes.append({
                "id": t_id,
                "type": "text",
                "text": f"**Thought #{t['entry_id']}** (`{t['agent']}`)\n{clean_text}",
                "x": (i - 2) * 320, "y": y_offset, "width": 280, "height": 130
            })
            edges.append({
                "id": f"edge_cortex_{t_id}",
                "fromNode": "node_cortex",
                "toNode": t_id
            })

        canvas_data = {"nodes": nodes, "edges": edges}
        canvas_file.write_text(json.dumps(canvas_data, indent=2), encoding="utf-8")
        logger.info(f"Generated Obsidian Canvas graph: {canvas_file}")

        return {
            "status": "CANVAS_GENERATED",
            "target_file": str(canvas_file),
            "node_count": len(nodes),
            "edge_count": len(edges),
            "timestamp": time.time()
        }


if __name__ == "__main__":
    syncer = MarkusObsidianSync()
    res = syncer.sync_daily_digest()
    live = syncer.append_new_thoughts()
    canvas = syncer.generate_canvas_graph()
    print("=== MARKUS Obsidian Palace Sync Result ===")
    print(json.dumps({"digest": res, "live": live, "canvas": canvas}, indent=2))
    print(f"Vault: {syncer.vault_path}")
