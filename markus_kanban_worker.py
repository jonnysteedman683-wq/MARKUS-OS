"""
MARKUS OS Autonomous SQLite Kanban Task Bridge Worker (Upgrade 6 / Dice Chain 2)
Monitors hermes kanban.db, claims ready tasks assigned to 'markus', executes
them inside the isolated sandbox, and records verification results.

v1.1 — UPGRADE_AI_AGENT (dice chain [6,6,3]):
  * Executes the REAL task body in the sandbox instead of a canned stub print.
  * Syncs with the live kanban schema: task_runs, consecutive_failures,
    last_failure_error, max_retries, claim_lock/claim_expires, worker_pid.
  * Atomic claim that respects stale/in-progress claims and expiry.
  * Honest outcome recording: SUCCESS only when the sandbox run exits 0;
    failures increment consecutive_failures and release the claim for retry
    (up to max_retries) instead of silently marking done.
"""

from __future__ import annotations
import asyncio
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from markus_sandbox import MarkusProcessSandbox

logger = logging.getLogger("Markus.KanbanWorker")
DEFAULT_KANBAN_DB = Path("C:/Users/jonny/AppData/Local/hermes/kanban.db")

# Body may be raw python, or markdown fenced (```python ... ```)
_FENCE_RE = re.compile(r"```(?:python|py)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass
class KanbanTask:
    id: str
    title: str
    body: str
    assignee: str
    status: str
    priority: int
    workspace_path: Optional[str] = None
    max_retries: int = 3
    consecutive_failures: int = 0


@dataclass
class TaskRunRecord:
    """Mirror of the live `task_runs` table row we create per execution."""
    run_id: int = 0
    task_id: str = ""
    status: str = "running"
    outcome: str = ""
    summary: str = ""
    error: str = ""


def extract_executable_body(body: str) -> Optional[str]:
    """Return runnable python from the task body, or None if it is not code.

    Handles raw python and markdown-fenced blocks. A body with no code block
    and no python-looking statements is treated as non-executable.
    """
    if not body or not body.strip():
        return None
    fenced = _FENCE_RE.findall(body)
    if fenced:
        code = "\n".join(f.strip() for f in fenced if f.strip())
        return code or None
    stripped = body.strip()
    # Loose python detection: look for common statement/expression signals.
    if re.search(r"^(def |class |import |from |print\(|if __name__|async |await )", stripped, re.MULTILINE):
        return stripped
    return None


class MarkusKanbanWorker:
    """Autonomous worker daemon claiming and executing tasks from Hermes kanban.db."""

    def __init__(self, db_path: Path = DEFAULT_KANBAN_DB, poll_interval_s: float = 3.0) -> None:
        self.db_path = db_path
        self.poll_interval_s = poll_interval_s
        self.sandbox = MarkusProcessSandbox()
        self._running = False

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    # ---------------------------------------------------------------- reads

    def fetch_ready_tasks(self, assignee: str = "markus", limit: int = 10) -> List[KanbanTask]:
        """Ready tasks not already claimed (claim expired or never held)."""
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT id, title, body, assignee, status, priority,
                           workspace_path, max_retries, consecutive_failures
                    FROM tasks
                    WHERE assignee IN (?, 'auroral')
                      AND status = 'ready'
                      AND (claim_lock IS NULL OR claim_expires IS NULL OR claim_expires < ?)
                    ORDER BY priority ASC, created_at ASC
                    LIMIT ?
                    """,
                    (assignee, now, limit),
                )
                rows = cursor.fetchall()
            except sqlite3.OperationalError:
                # Fallback for older boards missing the resilience columns.
                cursor.execute(
                    """
                    SELECT id, title, body, assignee, status, priority, workspace_path,
                           3 AS max_retries, 0 AS consecutive_failures
                    FROM tasks
                    WHERE assignee IN (?, 'auroral') AND status = 'ready'
                    ORDER BY priority ASC, created_at ASC
                    LIMIT ?
                    """,
                    (assignee, limit),
                )
                rows = cursor.fetchall()
            return [
                KanbanTask(
                    id=r["id"],
                    title=r["title"],
                    body=r["body"] or "",
                    assignee=r["assignee"],
                    status=r["status"],
                    priority=r["priority"],
                    workspace_path=r["workspace_path"],
                    max_retries=int(r["max_retries"] or 3),
                    consecutive_failures=int(r["consecutive_failures"] or 0),
                )
                for r in rows
            ]

    def get_task(self, task_id: str) -> Optional[KanbanTask]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if row is None:
            return None
        return KanbanTask(
            id=row["id"],
            title=row["title"],
            body=row["body"] or "",
            assignee=row["assignee"],
            status=row["status"],
            priority=row["priority"],
            workspace_path=row["workspace_path"],
            max_retries=int(row["max_retries"] or 3),
            consecutive_failures=int(row["consecutive_failures"] or 0),
        )

    def recover_stale_claims(self, max_age_s: float = 300.0) -> int:
        """Reap tasks stranded 'in_progress' by a crashed worker.

        Any task whose claim_expires (an absolute deadline) has passed is
        released back to 'ready' so a live worker can pick it up.
        Returns the number recovered.
        """
        now = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE tasks
                    SET status = 'ready',
                        claim_lock = NULL,
                        claim_expires = NULL,
                        worker_pid = NULL,
                        started_at = NULL
                    WHERE status = 'in_progress'
                      AND claim_expires IS NOT NULL
                      AND claim_expires < ?
                    """,
                    (now,),
                )
                recovered = cursor.rowcount
                conn.commit()
            except sqlite3.OperationalError:
                recovered = 0
        if recovered:
            logger.warning(f"Recovered {recovered} stale-claimed task(s) back to ready.")
        return recovered

    # ------------------------------------------------------------- writes

    def claim_task(self, task_id: str, worker_pid: Optional[int] = None) -> bool:
        """Atomically claim a ready task, creating a task_runs row.

        Only wins when the task is still 'ready' and any prior claim has
        expired — two workers cannot claim the same task.
        """
        now = time.time()
        pid = worker_pid or int(time.time() * 1000) % 1000000
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE tasks
                SET status = 'in_progress',
                    started_at = ?,
                    claim_lock = 'markus_worker',
                    claim_expires = ?,
                    worker_pid = ?
                WHERE id = ?
                  AND status = 'ready'
                  AND (claim_lock IS NULL OR claim_expires IS NULL OR claim_expires < ?)
                """,
                (now, now + 300, pid, task_id, now),
            )
            if cursor.rowcount == 0:
                return False
            # Create the run record for this execution attempt.
            try:
                cursor.execute(
                    """
                    INSERT INTO task_runs
                        (task_id, profile, status, claim_lock, worker_pid,
                         max_runtime_seconds, started_at)
                    VALUES (?, 'markus', 'running', 'markus_worker', ?, NULL, ?)
                    """,
                    (task_id, pid, now),
                )
                run_id = int(cursor.lastrowid or 0)
            except sqlite3.OperationalError:
                run_id = 0  # board has no task_runs table — degrade gracefully
            conn.commit()
            if run_id:
                cursor.execute("UPDATE tasks SET current_run_id = ? WHERE id = ?", (run_id, task_id))
                conn.commit()
        return True

    def _close_run(self, run_id: int, outcome: str, summary: str = "", error: str = "") -> None:
        if not run_id:
            return
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE task_runs
                    SET status = ?, outcome = ?, summary = ?, error = ?, ended_at = ?
                    WHERE id = ?
                    """,
                    ("done", outcome, summary, error, time.time(), run_id),
                )
                conn.commit()
        except sqlite3.OperationalError:
            pass

    def complete_task(self, task_id: str, result_summary: str, run: Optional[TaskRunRecord] = None) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute(
                """
                UPDATE tasks
                SET status = 'done', completed_at = ?, result = ?,
                    claim_lock = NULL, claim_expires = NULL, worker_pid = NULL
                WHERE id = ?
                """,
                (now, result_summary, task_id),
            )
            conn.commit()
        self._close_run(run.run_id if run else 0, "SUCCESS", summary=result_summary)
        logger.info(f"Marked Kanban Task [{task_id}] COMPLETED.")

    def fail_task(self, task_id: str, error: str, run: Optional[TaskRunRecord] = None,
                  max_retries: int = 3, consecutive_failures: int = 0) -> str:
        """Record a failed run; release for retry or mark failed permanently."""
        failures = consecutive_failures + 1
        retrying = failures <= max_retries
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute(
                """
                UPDATE tasks
                SET consecutive_failures = ?,
                    last_failure_error = ?,
                    status = ?,
                    claim_lock = NULL,
                    claim_expires = NULL,
                    worker_pid = NULL,
                    started_at = NULL
                WHERE id = ?
                """,
                (failures, error[:2000], "ready" if retrying else "failed", task_id),
            )
            conn.commit()
        self._close_run(run.run_id if run else 0, "FAILED" if not retrying else "RETRY", summary="", error=error)
        logger.warning(
            f"Kanban Task [{task_id}] failed ({failures} consecutive) -> "
            f"{'released for retry' if retrying else 'permanently failed'}"
        )
        return "RETRY" if retrying else "FAILED"

    # --------------------------------------------------------- execution

    async def execute_task_cycle(self, task: KanbanTask) -> Dict[str, Any]:
        logger.info(f"Claiming Kanban Task [{task.id}]: {task.title}")
        if not self.claim_task(task.id):
            return {"status": "SKIPPED", "reason": "Already claimed or stale lock"}

        run = TaskRunRecord(task_id=task.id)
        # recover the run id we just created
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM task_runs WHERE task_id = ? AND status = 'running' ORDER BY started_at DESC LIMIT 1",
                (task.id,),
            ).fetchone()
        run.run_id = int(row["id"]) if row else 0

        payload = extract_executable_body(task.body)
        if payload is None:
            # Honest non-completion: no executable payload, don't fake SUCCESS.
            self.fail_task(
                task.id,
                f"No executable payload in task body (title='{task.title}')",
                run=run,
                max_retries=task.max_retries,
                consecutive_failures=task.consecutive_failures,
            )
            return {"status": "NO_EXECUTABLE_PAYLOAD", "task_id": task.id}

        try:
            res = await self.sandbox.execute_python_code(payload, timeout_s=10.0)
        except Exception as exc:  # sandbox-level failure
            self.fail_task(
                task.id, f"Sandbox execution error: {exc}",
                run=run, max_retries=task.max_retries,
                consecutive_failures=task.consecutive_failures,
            )
            return {"status": "SANDBOX_ERROR", "task_id": task.id, "error": str(exc)}

        summary = json.dumps({
            "task_id": task.id,
            "title": task.title,
            "stdout": (res.stdout or "").strip()[:2000],
            "stderr": (res.stderr or "").strip()[:1000],
            "runtime_ms": round(res.runtime_ms, 2),
            "exit_code": res.exit_code,
        })

        if res.exit_code == 0:
            self.complete_task(task.id, summary, run=run)
            return {"status": "SUCCESS", "task_id": task.id, "summary": summary}
        self.fail_task(
            task.id, f"Sandbox exited {res.exit_code}: {(res.stderr or '').strip()[:800]}",
            run=run, max_retries=task.max_retries,
            consecutive_failures=task.consecutive_failures,
        )
        return {"status": "FAILED", "task_id": task.id, "summary": summary}

    async def run_worker_pass(self, limit: int = 10) -> List[Dict[str, Any]]:
        self.recover_stale_claims()
        tasks = self.fetch_ready_tasks(assignee="markus", limit=limit)
        results = []
        for t in tasks:
            res = await self.execute_task_cycle(t)
            results.append(res)
        return results


async def _self_test() -> None:
    """End-to-end verification against a throwaway temp board."""
    import tempfile, shutil

    tmpdir = Path(tempfile.mkdtemp(prefix="markus_kanban_test_"))
    db_path = tmpdir / "kanban.db"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.executescript(
            """
            CREATE TABLE tasks (
                id TEXT PRIMARY KEY, title TEXT, body TEXT, assignee TEXT,
                status TEXT, priority INTEGER, created_at INTEGER,
                workspace_path TEXT, max_retries INTEGER DEFAULT 3,
                consecutive_failures INTEGER DEFAULT 0, claim_lock TEXT,
                claim_expires INTEGER, worker_pid INTEGER, started_at INTEGER,
                completed_at INTEGER, result TEXT, current_run_id INTEGER,
                last_failure_error TEXT
            );
            CREATE TABLE task_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, profile TEXT,
                status TEXT, claim_lock TEXT, claim_expires INTEGER,
                worker_pid INTEGER, max_runtime_seconds INTEGER,
                last_heartbeat_at INTEGER, started_at INTEGER, ended_at INTEGER,
                outcome TEXT, summary TEXT, metadata TEXT, error TEXT
            );
            """
        )
        now = time.time()
        conn.execute(
            "INSERT INTO tasks (id, title, body, assignee, status, priority, created_at) VALUES (?,?,?,?,?,?,?)",
            ("t_ok", "Real task", "def work():\n    return 7\nprint('WORKED', work())\n", "markus", "ready", 1, now),
        )
        conn.execute(
            "INSERT INTO tasks (id, title, body, assignee, status, priority, created_at) VALUES (?,?,?,?,?,?,?)",
            ("t_fail", "Crashing task", "import sys\nprint('about to fail')\nsys.exit(3)\n", "markus", "ready", 2, now),
        )
        conn.execute(
            "INSERT INTO tasks (id, title, body, assignee, status, priority, created_at) VALUES (?,?,?,?,?,?,?)",
            ("t_prose", "Non-code task", "Please refactor the markus router for speed.", "markus", "ready", 3, now),
        )
        conn.commit()
        conn.close()

        worker = MarkusKanbanWorker(db_path=db_path)
        ready = worker.fetch_ready_tasks()
        print(f"  1. fetch_ready_tasks -> {len(ready)} ready (expect 3)")

        # Atomic claim: first claim wins, second is refused.
        first = worker.claim_task("t_ok")
        second = worker.claim_task("t_ok")
        print(f"  2. atomic claim -> first={first}, second={second} (expect True/False)")

        # Crashed worker reaping: an in_progress task with an expired claim
        # must be released back to 'ready' and become claimable again.
        with worker._get_connection() as c:
            c.execute("UPDATE tasks SET claim_expires = ? WHERE id = 't_ok'", (time.time() - 5,))
            c.commit()
        recovered = worker.recover_stale_claims()
        with worker._get_connection() as c:
            row = c.execute("SELECT status FROM tasks WHERE id = 't_ok'").fetchone()
        reclaimed = worker.claim_task("t_ok")
        print(f"  3. stale claim reap -> recovered={recovered}, status={row['status']}, reclaimed={reclaimed} (expect 1/ready/True)")

        # Reset t_ok so the worker pass exercises the real body again.
        with worker._get_connection() as c:
            c.execute(
                "UPDATE tasks SET status='ready', claim_lock=NULL, claim_expires=NULL, worker_pid=NULL WHERE id='t_ok'"
            )
            c.commit()

        results = await worker.run_worker_pass()
        print(f"  4. worker pass -> {len(results)} outcomes (expect 3)")
        for r in results:
            print(f"     {r['task_id']}: {r['status']}")

        ok = (
            len(ready) == 3
            and first is True and second is False
            and recovered == 1 and row["status"] == "ready" and reclaimed is True
            and any(r["status"] == "SUCCESS" for r in results)
            and any(r["status"] == "FAILED" for r in results)
            and any(r["status"] == "NO_EXECUTABLE_PAYLOAD" for r in results)
        )
        print("  RESULT:", "ALL GREEN" if ok else "FAILURES PRESENT")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(_self_test()))
