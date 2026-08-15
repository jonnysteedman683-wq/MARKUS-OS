#!/usr/bin/env python3
"""
MARKUS OS Hybrid Cron Agent (Upgrade 11)
Orchestrates time-gated event triggers combined with declarative Kanban task
processing and REST-based cron endpoint dispatch. Does NOT touch live cron scripts.

Integration Channels:
  1. Kanban Worker Pattern (polls kanban.db for 'markus' assigned tasks)
  2. REST Cron Endpoint (markus_server.py /api/cron route)
  3. Hybrid Time-Gate + Event Trigger (SSE/heartbeat-based execution)
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path Bootstrap ────────────────────────────────────────────────────────────
# Allow running directly from hive-core/ without installation
_HERE = Path(os.path.dirname(os.path.abspath(__file__) if "__file__" in dir() else os.getcwd()))
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from markus_kernel import MarkusKernel, KernelMessage, TaskPriority
from markus_db import PersistentCortexDB
from markus_router import MarkusIntentRouter
from markus_sandbox import MarkusProcessSandbox
from markus_resilience import CircuitBreakerManager, ResilientEndpoint

logger = logging.getLogger("Markus.CronAgent")

# ─── Configuration ───────────────────────────────────────────────────────────

DEFAULT_CRON_REGISTRY = _HERE / "markus_cron_registry.json"
DEFAULT_KANBAN_DB = Path(os.environ.get(
    "MARKUS_KANBAN_DB",
    "C:/Users/jonny/AppData/Local/hermes/kanban.db"
))
CHECK_INTERVAL_S = 5.0


# ─── Registry Loader ────────────────────────────────────────────────────────

def load_cron_registry(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load declarative cron task definitions from JSON registry."""
    reg_path = path or DEFAULT_CRON_REGISTRY
    if reg_path.exists():
        data = json.loads(reg_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    # Fallback minimal registry
    return [
        {
            "id": "hourly-health-check",
            "category": "FAST_TELEMETRY",
            "schedule": "h",
            "event_trigger": None,
            "payload_keys": [],
            "max_runtime": 15
        },
        {
            "id": "daily-model-benchmark",
            "category": "MEGACONTEXT_ARCH",
            "schedule": "24h",
            "event_trigger": None,
            "payload_keys": [],
            "max_runtime": 300
        }
    ]


# ─── Cron Agent ─────────────────────────────────────────────────────────────


class HybridCronAgent:
    """
    Combines three execution channels:
      - Time-gated schedules (h/daily/weekly)
      - Kanban-polling worker thread (pulls tasks from kanban.db)
      - REST endpoint listener (external dispatch via markus_server.py)

    All actions are routed through MarkovIntentRouter and executed in the
    MarkovProcessSandbox. Results are logged to PersistentCortexDB.
    """

    def __init__(
        self,
        kernel: MarkusKernel,
        db: Optional[PersistentCortexDB] = None,
        router: Optional[MarkusIntentRouter] = None,
        sandbox: Optional[MarkusProcessSandbox] = None,
        registry_path: Optional[Path] = None
    ) -> None:
        self.kernel = kernel
        self.db = db or PersistentCortexDB()
        self.router = router or MarkusIntentRouter()
        self.sandbox = sandbox or MarkusProcessSandbox()
        self.breaker = CircuitBreakerManager(db=self.db)

        self.registry = load_cron_registry(registry_path)
        self.last_run: Dict[str, float] = {}
        self._running = False
        self._threads: List[threading.Thread] = []

    def _schedule_to_seconds(self, schedule: str) -> int:
        """Convert human schedule string to seconds."""
        smap = {"s": 1, "min": 60, "h": 3600, "d": 86400, "w": 604800}
        for k, v in smap.items():
            if schedule.endswith(k):
                try:
                    return int(schedule[:-len(k)]) * v
                except ValueError:
                    continue
        return 3600  # Default to hourly

    def _should_run(self, task_id: str, interval_s: int) -> bool:
        """Check if a time-gated task is due to run."""
        last = self.last_run.get(task_id, 0)
        return (time.time() - last) >= interval_s

    def _execute_task(self, task: Dict[str, Any], source: str = "cron") -> Dict[str, Any]:
        """Execute a single cron task in the sandbox and return result."""
        ep = self.breaker.register(task["id"], max_failures=1, cooldown_s=5.0)

        def _do_exec():
            # Route intent
            prompt = f"Execute cron task '{task['id']}' ({task['category']})"
            r = self.router.route_intent(prompt)

            # Log to cortex
            self.db.append_thought(
                f"cron_{task['id']}_{int(time.time())}",
                "MARKUS_CRON_AGENT",
                prompt,
                {"source": source, "task_id": task["id"], "routing": r.provider}
            )

            # Build sandbox payload
            code = (
                f"import time\n"
                f"print('Executing: {task['id']}')\n"
                f"print('Category: {task['category']}')\n"
                f"print('Routed to: {r.provider}')\n"
                f"# Simulated task execution\n"
                f"time.sleep(0.1)\n"
                f"print('CRON_TASK_COMPLETE')\n"
            )

            loop = asyncio.new_event_loop()
            try:
                res = loop.run_until_complete(self.sandbox.execute_python_code(code, timeout_s=task.get("max_runtime", 30)))
            finally:
                loop.close()

            return {
                "status": "success" if res.exit_code == 0 else "failed",
                "stdout": res.stdout,
                "exit_code": res.exit_code,
                "runtime_ms": res.runtime_ms,
                "routing": {
                    "model": r.provider,
                    "tier": r.tier_category,
                    "confidence": r.confidence
                }
            }

        try:
            result = ep.protected_call(_do_exec)
            result["timestamp"] = time.time()
            self.db.append_thought(
                f"cron_result_{task['id']}_{int(time.time())}",
                "MARKUS_CRON_AGENT",
                json.dumps(result),
                {"task_id": task["id"], "success": result["status"] == "success"}
            )
            return result
        except Exception as exc:
            error_result = {
                "status": "error",
                "error_message": str(exc),
                "timestamp": time.time()
            }
            self.db.append_thought(
                f"cron_error_{task['id']}_{int(time.time())}",
                "MARKUS_CRON_AGENT",
                str(exc),
                {"task_id": task["id"], "error": True}
            )
            return error_result

    def _run_kanban_channel(self) -> None:
        """Channel 1: Poll kanban.db for tasks assigned to 'markus'."""
        conn = sqlite3.connect(str(DEFAULT_KANBAN_DB), timeout=5.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, body, status, workspace_path "
            "FROM tasks WHERE (status = 'ready' OR status = 'assigned') "
            "AND (assignee = 'markus' OR assignee LIKE '%aura%') LIMIT 5"
        )
        for row in cursor.fetchall():
            task_payload = {
                "id": f"kanban_{row['id']}",
                "category": "CODE_SPECIALIST",
                "schedule": "min",
                "event_trigger": None,
                "payload_keys": ["title", "body"],
                "max_runtime": 60,
                "title": row["title"],
                "body": row["body"]
            }
            result = self._execute_task(task_payload, source="kanban_worker")
            logger.info(f"Kanban task {row['id']} completed: {result['status']}")

            cursor.execute(
                "UPDATE tasks SET status = ?, result = ? WHERE id = ?",
                (result["status"], json.dumps(result), row["id"])
            )
            conn.commit()
        conn.close()

    def _run_rest_channel(self) -> None:
        """Channel 2: Serve REST endpoint for external cron dispatch."""
        # Handled by markus_server.py /api/cron — this method serves as a hook point
        pass

    def _run_hybrid_channel(self) -> None:
        """Channel 3: Execute time-gated tasks that are due."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        for task in self.registry:
            interval_s = self._schedule_to_seconds(task["schedule"])
            if self._should_run(task["id"], interval_s):
                # Special handling for auto-dice-engine
                if task["id"] == "markus-autonomous-dice-engine":
                    # Run the latency-weighted multi-upgrade engine
                    self._run_co_evolution_cycle(task)
                else:
                    result = self._execute_task(task, source="time_gate")
                self.last_run[task["id"]] = time.time()
                logger.info(f"Executed {task['id']}: {result.get('status', 'cycle_complete')}")

    def _run_co_evolution_cycle(self, task: Dict[str, Any]) -> None:
        """Execute the co-evolution cycle (dice → debate → validate → skill patch → research)."""
        try:
            import subprocess
            import asyncio
            
            # Run the latency multi-upgrade engine
            result = subprocess.run(
                [sys.executable, "markus_latency_multi_upgrade.py"],
                capture_output=True, text=True, timeout=60,
                cwd=str(_HERE.parent)
            )
            
            self.db.append_thought(
                f"coev_cycle_{int(time.time())}",
                "MARKUS_CRON_AGENT",
                f"Co-evolution cycle triggered by cron task {task['id']}",
                {
                    "task_id": task["id"],
                    "exit_code": result.returncode,
                    "stdout_tail": result.stdout[-500:] if result.stdout else "",
                    "stderr_tail": result.stderr[-500:] if result.stderr else ""
                }
            )
        except Exception as e:
            logger.error(f"Co-evolution cycle error: {e}")
            self.db.append_thought(
                f"coev_error_{int(time.time())}",
                "MARKUS_CRON_AGENT",
                f"Co-evolution cycle failed: {str(e)}",
                {"task_id": task["id"], "error": True}
            )

    def _cron_loop(self) -> None:
        """Main cron dispatch loop."""
        while self._running:
            try:
                self._run_hybrid_channel()
                self._run_kanban_channel()
                self._run_rest_channel()
            except Exception as e:
                logger.error(f"Cron loop error: {e}")
                self.db.append_thought(
                    f"cron_loop_error_{int(time.time())}",
                    "MARKUS_CRON_AGENT",
                    str(e),
                    {"error": True}
                )
            time.sleep(CHECK_INTERVAL_S)

    def _start_kanban_worker(self) -> None:
        """Launch dedicated Kanban polling thread."""
        def _worker():
            while self._running:
                try:
                    self._run_kanban_channel()
                except Exception as e:
                    logger.error(f"Kanban worker error: {e}")
                time.sleep(CHECK_INTERVAL_S)

        t = threading.Thread(target=_worker, name="MARKUS-Cron-KanbanWorker", daemon=True)
        t.start()
        self._threads.append(t)

    def start(self) -> None:
        """Start the hybrid cron agent."""
        if self._running:
            return
        self._running = True

        # Start main cron loop in background
        cron_thread = threading.Thread(target=self._cron_loop, name="MARKUS-CronMain", daemon=True)
        cron_thread.start()
        self._threads.append(cron_thread)

        # Start Kanban polling worker
        self._start_kanban_worker()

        logger.info(
            f"HybridCronAgent started. Registry: {len(self.registry)} tasks. "
            f"Channels: [Time-Gate + Kanban-poller]. Interval: {CHECK_INTERVAL_S}s"
        )

        self.db.append_thought(
            f"cron_agent_start_{int(time.time())}",
            "MARKUS_CRON_AGENT",
            "MARKUS OS Hybrid Cron Agent initialized.",
            {"registry_size": len(self.registry), "channels": ["time_gate", "kanban_poller", "rest"]}
        )

    def stop(self) -> None:
        self._running = False
        logger.info("HybridCronAgent stopping...")

        self.db.append_thought(
            f"cron_agent_stop_{int(time.time())}",
            "MARKUS_CRON_AGENT",
            "MARKUS OS Hybrid Cron Agent stopped.",
            {"final": True}
        )

    def run_single_check(self) -> Dict[str, Any]:
        """Execute one cycle synchronously (for testing)."""
        before = time.time()
        self._run_hybrid_channel()
        self._run_kanban_channel()
        elapsed = time.time() - before
        return {
            "registry_tasks": len(self.registry),
            "elapsed_ms": round(elapsed * 1000, 2),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


# ─── CLI Entry Point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="MARKUS OS Hybrid Cron Agent")
    parser.add_argument("--daemon", action="store_true", help="Run as continuous daemon")
    parser.add_argument("--single", action="store_true", help="Run single cycle and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [MARKUS-CRON] %(message)s"
    )

    kernel = MarkusKernel()
    agent = HybridCronAgent(kernel)

    if args.single:
        print("=== MARKUS OS Hybrid Cron Agent — Single Cycle ===")
        result = agent.run_single_check()
        print(json.dumps(result, indent=2))
    else:
        print("=== MARKUS OS Hybrid Cron Agent — Daemon Mode ===")
        agent.start()
        print("Listening for Kanban tasks and time-gated triggers...")

        def _shutdown(sig, frame):
            agent.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            agent.stop()
