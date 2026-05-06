#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import state_manager


class StateManagerTests(unittest.TestCase):
    def test_load_state_normalizes_missing_and_invalid_types(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            path.write_text(
                json.dumps({"workflow": {"current_focus": None, "next_actions": "bad"}, "memory": "bad"}),
                encoding="utf-8",
            )
            with patch.object(state_manager, "STATE_PATH", path):
                state = state_manager.load_state()
        self.assertEqual(state["workflow"]["current_focus"], "")
        self.assertEqual(state["workflow"]["next_actions"], [])
        self.assertEqual(state["workflow"]["tasks"], [])
        self.assertEqual(state["memory"], [])

    def test_save_state_persists_normalized_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            with patch.object(state_manager, "STATE_PATH", path):
                state_manager.save_state({"workflow": {"current_focus": None}})
                state = state_manager.load_state()
        self.assertEqual(state["workflow"]["current_focus"], "")

    def test_load_state_normalizes_workflow_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "workflow": {
                            "tasks": [
                                {
                                    "title": "Ship Jarvis plugins",
                                    "status": "invalid",
                                    "estimate_minutes": "45",
                                    "blockers": "needs tests",
                                },
                                {"title": ""},
                                "bad",
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(state_manager, "STATE_PATH", path):
                state = state_manager.load_state()

        self.assertEqual(
            state["workflow"]["tasks"],
            [
                {
                    "id": "ship-jarvis-plugins",
                    "title": "Ship Jarvis plugins",
                    "status": "todo",
                    "due": "",
                    "estimate_minutes": 45,
                    "blockers": ["needs tests"],
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            ],
        )

    def test_load_state_normalizes_mixed_memory_and_dedupes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            path.write_text(
                json.dumps(
                    {
                        "memory": [
                            {"event": "status", "command": "status"},
                            # duplicate event — should be deduped
                            {"type": "event", "event": "status", "command": "status"},
                            "finished bus concurrency fix",
                            # duplicate note — should be deduped
                            {"type": "note", "text": "finished bus concurrency fix"},
                            {"text": "keep this note"},
                            "",  # empty — should be dropped
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(state_manager, "STATE_PATH", path):
                state = state_manager.load_state()
                state_manager.save_state(state)
                saved = json.loads(path.read_text(encoding="utf-8"))
        # Events are now preserved (fix: they were previously silently dropped)
        self.assertEqual(
            state["memory"],
            [
                {"type": "event", "event": "status", "command": "status", "created_at": "2026-01-01T00:00:00+00:00"},
                {"type": "note", "text": "finished bus concurrency fix", "created_at": "2026-01-01T00:00:00+00:00"},
                {"type": "note", "text": "keep this note", "created_at": "2026-01-01T00:00:00+00:00"},
            ],
        )
        self.assertEqual(saved["memory"], state["memory"])
