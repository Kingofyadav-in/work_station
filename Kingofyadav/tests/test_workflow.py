#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import state_manager
import workflow


class WorkflowTests(unittest.TestCase):
    def test_add_task_sets_focus_and_persists_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            with patch.object(state_manager, "STATE_PATH", path):
                result = workflow.add_task("finish semantic memory", due="2026-05-01", estimate_minutes=90)

        task = result["tasks"][0]
        self.assertEqual(result["current_focus"], "finish semantic memory")
        self.assertEqual(task["status"], "todo")
        self.assertEqual(task["due"], "2026-05-01")
        self.assertEqual(task["estimate_minutes"], 90)
        self.assertTrue(task["id"].startswith("finish-semantic-memory-"))

    def test_task_status_blocker_and_due_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            with patch.object(state_manager, "STATE_PATH", path):
                created = workflow.add_task("ship public Jarvis")
                task_id = created["tasks"][0]["id"]
                workflow.update_task_status(task_id, "doing")
                workflow.add_task_blocker(task_id, "needs public memory filter")
                result = workflow.update_task_due(task_id, "2026-06-15")

        task = result["tasks"][0]
        self.assertEqual(task["status"], "blocked")
        self.assertEqual(task["blockers"], ["needs public memory filter"])
        self.assertEqual(task["due"], "2026-06-15")

    def test_summary_lists_open_and_blocked_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            with patch.object(state_manager, "STATE_PATH", path):
                first = workflow.add_task("build Telegram bridge")
                workflow.add_task("archive old memory")
                workflow.add_task_blocker(first["tasks"][0]["id"], "bot token not set")
                summary = workflow.get_workflow_summary()

        self.assertIn("tasks=2, open=2, blocked=1", summary["text"])
        self.assertIn("build Telegram bridge", summary["text"])


if __name__ == "__main__":
    unittest.main()
