"""
MARKUS OS Obsidian Palace Knowledge Synchronizer (Upgrade 7)
Automatically bridges SQLite L3 Cortex thoughts into the Obsidian Vault under
Obsidian Vault/Journal/Markus/ with daily digest rollups and semantic tagging.
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

class MarkusObsidianSync:
    """Synchronizes persistent memory cortex entries to Obsidian markdown notes."""

    def __init__(self, vault_path: Optional[Path] = None, db: Optional[PersistentCortexDB] = None) -> None:
        user_home = Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))
        self.vault_path = vault_path or (user_home / "OneDrive" / "Documents" / "Obsidian Vault")
        self.markus_journal_dir = self.vault_path / "Journal" / "Markus"
        self.markus_journal_dir.mkdir(parents=True, exist_ok=True)
        self.db = db or PersistentCortexDB()

    def sync_daily_digest(self, limit: int = 50) -> Dict[str, Any]:
        now_dt = datetime.now(timezone.utc)
        date_str = now_dt.strftime("%Y-%m-%d")
        daily_file = self.markus_journal_dir / f"{date_str}-MARKUS-CORTEX.md"

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

if __name__ == "__main__":
    syncer = MarkusObsidianSync()
    res = syncer.sync_daily_digest()
    print("=== MARKUS Obsidian Palace Sync Result ===")
    print(json.dumps(res, indent=2))
