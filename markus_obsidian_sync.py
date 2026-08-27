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

Plus (Upgrade 8, 2026-08-27):
  Journal/Markus/MARKUS-OS-KNOWLEDGE-GRAPH.canvas — interactive knowledge graph
  Index/Now.md                  — live command deck: kernel state, VORPAL goal
                                  pulse, sync watermark, today's links.
  Git provenance                — every sync auto-commits the vault, so the
                                  vault itself obeys VORPAL invariant #3.
"""

from __future__ import annotations
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from markus_db import PersistentCortexDB
from markus_vorpal_bridge import MarkusVorpalBridge

logger = logging.getLogger("Markus.ObsidianSync")

WATERMARK_KEY = "VAULT_SYNC_LAST_TS"

# Cap for a single day's LIVE stream file. When a daily stream exceeds this,
# it is rotated into Journal/Markus/Archive/ and the day starts fresh, so no
# single Obsidian note grows into a multi-MB parse burden. (The 2026-08-26
# stream hit 4.3 MB / 19k lines — this prevents that from recurring.)
LIVE_STREAM_CAP_BYTES = 256 * 1024  # 256 KB per daily stream

# The shared cortex DB's OS_STATUS register can be clobbered to "HALTED" by a
# stale markus_server instance shutting down after the live server booted.
# The vault must reflect the *live* kernel state, so probe the running server
# first and fall back to the register only when nothing answers.
SERVER_STATUS_URL = "http://localhost:8128/api/status"


def _live_kernel_status(fallback: str = "UNKNOWN") -> str:
    """Return the live kernel_state from the running server, else `fallback`."""
    try:
        import urllib.request
        with urllib.request.urlopen(SERVER_STATUS_URL, timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("kernel_state") or fallback
    except Exception:  # noqa: BLE001 — server down or not reachable
        return fallback


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

        # Prefer the live kernel state; the DB register can lag behind reality.
        live_status = _live_kernel_status(fallback=registers)
        lines = [
            f"# MARKUS OS Memory Cortex Digest — {date_str}",
            "",
            f"- **Generated At:** `{now_dt.isoformat()}`",
            f"- **Kernel Status:** `{live_status}`",
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
    def _rotate_live_stream(self, live_file: Path) -> bool:
        """If `live_file` exceeds the cap, move it to Archive/ and return True.

        The daily stream then restarts empty; the archived copy keeps the full
        provenance under git. Never deletes data — only relocates it.
        """
        try:
            if not live_file.exists():
                return False
            if live_file.stat().st_size < LIVE_STREAM_CAP_BYTES:
                return False
            archive_dir = self.markus_journal_dir / "Archive"
            archive_dir.mkdir(parents=True, exist_ok=True)
            target = archive_dir / live_file.name
            live_file.replace(target)
            logger.info(f"Rotated oversized live stream to {target} ({live_file.stat().st_size if live_file.exists() else 'moved'} bytes)")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"live-stream rotation failed (fail-open): {exc}")
            return False

    def append_new_thoughts(self, batch: int = 200) -> Dict[str, Any]:
        """Append cortex thoughts newer than the watermark to the day's LIVE file.

        Watermark (VAULT_SYNC_LAST_TS) lives in the cortex DB registers, so the
        stream is idempotent across restarts and never rewrites old bullets.
        """
        now_dt = datetime.now(timezone.utc)
        date_str, _, live_file = self._daily_paths(now_dt)
        # Rotate an oversized previous day's stream before appending today's.
        self._rotate_live_stream(live_file)
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
    def _parse_goal_nodes(self) -> List[Dict[str, Any]]:
        """Parse GOALS.md into lightweight goal nodes (id, phase, label, done).

        Reuses MarkusVorpalBridge's regex so the canvas always shows the same
        33 goals the pulse counter sees — no drift between dashboard + graph.
        """
        try:
            import markus_vorpal_bridge as _vb
            if not _vb.GOALS_PATH.exists():
                return []
            text = _vb.GOALS_PATH.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            logger.warning("goal nodes unavailable: %s", exc)
            return []

        nodes = []
        phase = "UNCATEGORISED"
        for line in text.splitlines():
            if line.startswith("## "):
                phase = line[3:].strip()
                continue
            if MarkusVorpalBridge._is_goal_title(line):
                m = re.search(r"GOAL_(\d+)\.(\d+)\s*:\*\*\s*(.+)", line)
                title = m.group(3).strip() if m else line
                if len(title) > 60:
                    title = title[:57] + "…"
                done = "[x]" in line.lower() or "COMPLETE" in line.upper()
                nodes.append({
                    "id": f"node_goal_{len(nodes)}",
                    "phase": phase,
                    "label": title,
                    "done": done,
                })
        return nodes

    def generate_canvas_graph(self) -> Dict[str, Any]:
        """Generate an interactive Obsidian Canvas (.canvas) knowledge graph map
        visualizing system components, active cortex thoughts, and VORPAL goals.
        """
        canvas_file = self.markus_journal_dir / "MARKUS-OS-KNOWLEDGE-GRAPH.canvas"

        thoughts = self.db.get_recent_thoughts(limit=10)
        os_status = _live_kernel_status(fallback=self.db.get_register("OS_STATUS", "ACTIVE"))
        goal_count = open_ct = impl_ct = 0
        try:
            vorpal_st = MarkusVorpalBridge().read_vorpal_status()
            goal_count, open_ct, impl_ct = (vorpal_st.goal_count,
                                            vorpal_st.open_goal_count,
                                            vorpal_st.implemented_goal_count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vorpal status unavailable for canvas: %s", exc)

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
            ("node_vorpal", "🎯 VORPAL Goal DAG", f"markus_vorpal_bridge.py\n{goal_count} North Star Goals ({impl_ct} done, {open_ct} open)", 400, -200, "3"),
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

        # Goal DAG nodes — one row per phase, color-coded done/open.
        goal_nodes = self._parse_goal_nodes()
        if goal_nodes:
            # place each goal in a 4-column grid below the subsystems
            y_goal = 620
            for idx, g in enumerate(goal_nodes):
                col = idx % 4
                row_in_col = idx // 4
                x = -960 + col * 480
                y = y_goal + row_in_col * 120
                nodes.append({
                    "id": g["id"],
                    "type": "text",
                    "text": f"**{'✅' if g['done'] else '⬜'} {g['label']}**\n`{g['phase']}`",
                    "x": x, "y": y, "width": 430, "height": 90,
                    "color": "3" if g["done"] else "6",
                })
                edges.append({
                    "id": f"edge_dag_{g['id']}",
                    "fromNode": "node_vorpal",
                    "toNode": g["id"],
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
            "goal_nodes": len(goal_nodes),
            "timestamp": time.time()
        }


    # --------------------------------------------------- live command deck
    def generate_dashboard(self, limit: int = 12) -> Dict[str, Any]:
        """Regenerate the vault's command-deck page (Index/Now.md).

        Shows live kernel state, VORPAL goal pulse, sync watermark, and links
        to today's digest / live stream / canvas / newest daily note. Because
        the newest daily note is resolved at write time, Index/Home never need
        hand-editing to follow the calendar.
        """
        now_dt = datetime.now(timezone.utc)
        date_str = now_dt.strftime("%Y-%m-%d")
        now_file = self.vault_path / "Index" / "Now.md"
        now_file.parent.mkdir(parents=True, exist_ok=True)

        os_status = _live_kernel_status(fallback=self.db.get_register("OS_STATUS", "ACTIVE"))
        watermark = self.db.get_register(WATERMARK_KEY, 0.0) or 0.0

        goal_count = open_ct = impl_ct = 0
        try:
            vorpal_st = MarkusVorpalBridge().read_vorpal_status()
            goal_count, open_ct, impl_ct = (vorpal_st.goal_count,
                                            vorpal_st.open_goal_count,
                                            vorpal_st.implemented_goal_count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vorpal status unavailable for dashboard: %s", exc)

        daily_dir = self.vault_path / "Journal" / "Daily"
        dailies = sorted(daily_dir.glob("*.md")) if daily_dir.exists() else []
        newest_daily = dailies[-1].stem if dailies else None

        thoughts = self.db.get_recent_thoughts(limit=limit)
        pulse = round(open_ct / goal_count, 3) if goal_count else 0.0

        lines = [
            "---",
            "type: index",
            "tags:",
            "  - type/index",
            "---",
            "# ⚡ VORPAL Vault — Command Deck",
            "",
            "> Auto-generated by **MARKUS OS Obsidian Palace Bridge** on every sync.",
            "",
            "## Live State",
            "",
            f"- **Kernel:** `{os_status}`",
            f"- **Vault:** `VORPAL Vault`",
            f"- **Generated At:** `{now_dt.isoformat()}`",
            "",
            "## 🎯 VORPAL Goal DAG",
            "",
            f"- **{goal_count} North Star Goals** — `{impl_ct}` implemented · `{open_ct}` open · pulse `{pulse}`",
            "",
            "## 📅 Today",
            "",
        ]
        if newest_daily:
            lines.append(f"- **Daily note:** [[Journal/Daily/{newest_daily}]]")
        lines += [
            f"- **MARKUS digest:** [[Journal/Markus/{date_str}-MARKUS-CORTEX]]",
            f"- **MARKUS live stream:** [[Journal/Markus/{date_str}-MARKUS-LIVE]]",
            f"- **Knowledge graph:** [[Journal/Markus/MARKUS-OS-KNOWLEDGE-GRAPH]]",
            "",
            "## 🧠 Recent Cortex Thoughts",
            "",
            "| Time (UTC) | Agent | Thought |",
            "|---|---|---|",
        ]
        for t in thoughts[:10]:
            ts = datetime.fromtimestamp(t["created_at"], tz=timezone.utc).strftime("%H:%M:%S")
            clean_content = t["content"].replace("|", "\\|").replace("\n", " ")[:90]
            lines.append(f"| {ts} | `{t['agent']}` | {clean_content} |")

        lines.extend(["", "---", f"*Watermark: `{watermark}` · sync healthy.*"])

        now_file.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Regenerated command deck: {now_file}")

        return {
            "status": "DASHBOARD_GENERATED",
            "target_file": str(now_file),
            "kernel_state": os_status,
            "goal_count": goal_count,
            "open_goals": open_ct,
            "implemented_goals": impl_ct,
            "newest_daily": newest_daily,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------- provenance
    def _git_commit(self, message: str) -> bool:
        """Commit the vault's current state (no-op when nothing changed).

        Gives the vault the same provenance the rest of VORPAL enforces
        (invariant #3: provenance or perish). Every MARKUS write lands in a
        versioned, timestamped commit.
        """
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"], cwd=str(self.vault_path),
                capture_output=True, text=True, timeout=15,
            )
            if not status.stdout.strip():
                return False
            subprocess.run(
                ["git", "add", "-A"], cwd=str(self.vault_path),
                capture_output=True, text=True, timeout=15,
            )
            subprocess.run(
                ["git", "commit", "-m", message], cwd=str(self.vault_path),
                capture_output=True, text=True, timeout=30,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("vault git commit failed (fail-open): %s", exc)
            return False

    # ---------------------------------------------------- full pipeline
    def generate_weekly_rollup(self) -> Dict[str, Any]:
        """Roll up the current ISO week's cortex thoughts into
        Journal/Markus/Weekly/YYYY-Www.md (regenerated on each sync, so it is
        a live week view rather than an append-only log)."""
        now_dt = datetime.now(timezone.utc)
        iso = now_dt.isocalendar()
        week_dir = self.markus_journal_dir / "Weekly"
        week_dir.mkdir(parents=True, exist_ok=True)
        week_file = week_dir / f"{now_dt.year}-W{iso.week:02d}.md"

        thoughts = self.db.get_recent_thoughts(limit=500)
        # filter to this ISO week
        week_start = iso.week
        in_week = []
        for t in thoughts:
            dt = datetime.fromtimestamp(t["created_at"], tz=timezone.utc)
            if dt.isocalendar().week == week_start and dt.year == now_dt.year:
                in_week.append(t)

        agents: Dict[str, int] = {}
        for t in in_week:
            agents[t["agent"]] = agents.get(t["agent"], 0) + 1
        top_agents = sorted(agents.items(), key=lambda kv: kv[1], reverse=True)[:10]

        lines = [
            f"# MARKUS Weekly Rollup — {now_dt.year}-W{iso.week:02d}",
            "",
            f"- **Generated At:** `{now_dt.isoformat()}`",
            f"- **Thoughts this week:** `{len(in_week)}`",
            "",
            "## Agent activity",
            "",
            "| Agent | Thoughts |",
            "|---|---|",
        ]
        for agent, count in top_agents:
            lines.append(f"| `{agent}` | {count} |")

        lines.extend([
            "",
            "## Latest thoughts this week",
            "",
            "| Time (UTC) | Agent | Thought |",
            "|---|---|---|",
        ])
        for t in in_week[-25:]:
            ts = datetime.fromtimestamp(t["created_at"], tz=timezone.utc).strftime("%m-%d %H:%M")
            clean_content = t["content"].replace("|", "\\|").replace("\n", " ")[:90]
            lines.append(f"| {ts} | `{t['agent']}` | {clean_content} |")

        lines.extend(["", "---", "*Rollup regenerated by MARKUS OS Obsidian Palace Bridge.*"])
        week_file.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Regenerated weekly rollup: {week_file}")

        return {
            "status": "WEEKLY_ROLLUP",
            "target_file": str(week_file),
            "thoughts_in_week": len(in_week),
            "timestamp": time.time(),
        }

    def generate_monthly_dag_snapshot(self) -> Dict[str, Any]:
        """Snapshot the VORPAL goal DAG into Journal/Markus/Monthly/YYYY-MM.md
        so the month-end state is preserved even as the live DAG evolves."""
        now_dt = datetime.now(timezone.utc)
        month_dir = self.markus_journal_dir / "Monthly"
        month_dir.mkdir(parents=True, exist_ok=True)
        month_file = month_dir / f"{now_dt.year}-{now_dt.month:02d}.md"

        goal_count = open_ct = impl_ct = 0
        goal_nodes: List[Dict[str, Any]] = []
        try:
            vorpal_st = MarkusVorpalBridge().read_vorpal_status()
            goal_count, open_ct, impl_ct = (vorpal_st.goal_count,
                                            vorpal_st.open_goal_count,
                                            vorpal_st.implemented_goal_count)
            goal_nodes = self._parse_goal_nodes()
        except Exception as exc:  # noqa: BLE001
            logger.warning("vorpal status unavailable for monthly snapshot: %s", exc)

        lines = [
            f"# VORPAL Goal DAG Snapshot — {now_dt.year}-{now_dt.month:02d}",
            "",
            f"- **Captured At:** `{now_dt.isoformat()}`",
            f"- **Goals:** `{goal_count}` total · `{impl_ct}` implemented · `{open_ct}` open",
            "",
            "## DAG",
            "",
        ]
        for g in goal_nodes:
            marker = "✅" if g["done"] else "⬜"
            lines.append(f"- {marker} `{g['phase']}` — {g['label']}")

        lines.extend(["", "---", "*Snapshot preserved by MARKUS OS Obsidian Palace Bridge.*"])
        month_file.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Generated monthly DAG snapshot: {month_file}")

        return {
            "status": "MONTHLY_SNAPSHOT",
            "target_file": str(month_file),
            "goal_count": goal_count,
            "timestamp": time.time(),
        }

    def sync_all(self) -> Dict[str, Any]:
        """Run the complete vault pipeline: digest + live + canvas + deck + commit."""
        digest = self.sync_daily_digest()
        live = self.append_new_thoughts()
        canvas = self.generate_canvas_graph()
        dashboard = self.generate_dashboard()
        weekly = self.generate_weekly_rollup()
        monthly = self.generate_monthly_dag_snapshot()
        committed = self._git_commit(f"sync(vault): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
        return {
            "digest": digest,
            "live": live,
            "canvas": canvas,
            "dashboard": dashboard,
            "weekly": weekly,
            "monthly": monthly,
            "committed": committed,
        }


if __name__ == "__main__":
    syncer = MarkusObsidianSync()
    result = syncer.sync_all()
    print("=== MARKUS Obsidian Palace Sync Result ===")
    print(json.dumps(result, indent=2))
    print(f"Vault: {syncer.vault_path}")
    print(f"Committed: {result['committed']}")
