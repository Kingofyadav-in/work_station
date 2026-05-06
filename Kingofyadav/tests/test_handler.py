#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import handler


class HandlerTests(unittest.TestCase):
    def test_hi_get_profile_routes_to_profile_summary(self) -> None:
        with patch("handler.get_profile_summary", return_value={"text": "profile", "args": {}}) as get_profile_summary:
            result = handler.handle_request({"intent": "hi_get_profile", "payload": {"text": "profile", "args": {}}})
        self.assertEqual(result["text"], "profile")
        get_profile_summary.assert_called_once_with("")

    def test_hi_set_preference_updates_state(self) -> None:
        with patch("handler.set_preference", return_value={"response_mode": "adaptive"}) as set_preference, patch(
            "handler.append_event"
        ):
            result = handler.handle_request(
                {
                    "intent": "hi_set_preference",
                    "payload": {"text": "set response mode adaptive", "args": {"raw_payload": {"key": "response_mode", "value": "adaptive"}}},
                }
            )
        self.assertIn("Preference set", result["text"])
        set_preference.assert_called_once_with("response_mode", "adaptive")

    def test_hi_memory_add_appends_curated_memory(self) -> None:
        with patch("handler.add_memory", return_value=["note"]) as add_memory, patch("handler.append_event"):
            result = handler.handle_request(
                {
                    "intent": "hi_memory_add",
                    "payload": {"text": "add memory note", "args": {"raw_payload": {"entry": "note", "source": "user"}}},
                }
            )
        self.assertIn("Memory stored", result["text"])
        add_memory.assert_called_once_with("note")

    def test_hi_workflow_add_task_routes_to_workflow_module(self) -> None:
        workflow_state = {
            "tasks": [
                {
                    "id": "ship-memory-12345678",
                    "title": "ship memory",
                    "status": "todo",
                    "due": "2026-05-01",
                    "estimate_minutes": 60,
                    "blockers": [],
                }
            ]
        }
        with patch("handler.add_task", return_value=workflow_state) as add_task, patch("handler.append_event"):
            result = handler.handle_request(
                {
                    "intent": "hi_workflow_add_task",
                    "payload": {
                        "text": "add task ship memory",
                        "args": {"raw_payload": {"title": "ship memory", "due": "2026-05-01", "estimate_minutes": 60}},
                    },
                }
            )

        self.assertIn("Workflow task added", result["text"])
        add_task.assert_called_once_with("ship memory", due="2026-05-01", estimate_minutes=60)
