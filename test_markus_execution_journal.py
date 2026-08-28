#!/usr/bin/env python3
"""Focused tests for the MARKUS execution journal."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from markus_execution_journal import ExecutionJournal, ManualRecoveryRequired


class ExecutionJournalTests(unittest.TestCase):
    def test_completed_execution_replays_without_calling_side_effect(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "journal.jsonl"
            first = ExecutionJournal(journal)
            calls = []
            self.assertEqual(
                first.run("run-1:fetch", recovery="idempotent", action=lambda: calls.append(1) or {"ok": True}),
                {"ok": True},
            )
            self.assertEqual(calls, [1])

            second = ExecutionJournal(journal)
            self.assertEqual(
                second.run("run-1:fetch", recovery="idempotent", action=lambda: calls.append(2)),
                {"ok": True},
            )
            self.assertEqual(calls, [1])

    def test_manual_recovery_never_reexecutes_started_step(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "journal.jsonl"
            journal.write_text(
                json.dumps({
                    "execution_id": "run-2:charge",
                    "state": "started",
                    "recovery": "manual",
                    "attempt": 1,
                }) + "\n",
                encoding="utf-8",
            )
            calls = []
            env = ExecutionJournal(journal)
            with self.assertRaises(ManualRecoveryRequired):
                env.run("run-2:charge", recovery="manual", action=lambda: calls.append(1))
            self.assertEqual(calls, [])
            self.assertEqual(env.state("run-2:charge"), "manual_required")

    def test_idempotent_recovery_reexecutes_incomplete_step_once(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "journal.jsonl"
            journal.write_text(
                json.dumps({
                    "execution_id": "run-3:fetch",
                    "state": "started",
                    "recovery": "idempotent",
                    "attempt": 1,
                }) + "\n",
                encoding="utf-8",
            )
            calls = []
            env = ExecutionJournal(journal)
            self.assertEqual(
                env.run("run-3:fetch", recovery="idempotent", action=lambda: calls.append(1) or "fresh"),
                "fresh",
            )
            self.assertEqual(calls, [1])
            self.assertEqual(env.state("run-3:fetch"), "completed")

    def test_corrupt_final_line_is_quarantined_without_false_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "journal.jsonl"
            journal.write_text('{"execution_id":"x","state":"started"}\n{"broken"', encoding="utf-8")
            env = ExecutionJournal(journal)
            self.assertEqual(env.state("x"), "started")
            self.assertEqual(len(env.corrupt_lines), 1)
            self.assertTrue(env.quarantine_path.exists())

    def test_secret_like_values_are_redacted_in_journal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            journal = Path(td) / "journal.jsonl"
            env = ExecutionJournal(journal)
            env.run(
                "run-4:secret",
                recovery="idempotent",
                action=lambda: {"token": "Bearer super-secret-token", "nested": ["sk-1234567890"]},
            )
            text = journal.read_text(encoding="utf-8")
            self.assertNotIn("super-secret-token", text)
            self.assertNotIn("sk-1234567890", text)
            self.assertIn("[REDACTED]", text)


if __name__ == "__main__":
    unittest.main()