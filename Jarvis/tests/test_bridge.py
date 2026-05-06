#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import bridge


class BridgeIntentTests(unittest.TestCase):
    def test_who_are_you_routes_to_identity_handler(self) -> None:
        self.assertEqual(bridge.interpret_intent("who are you"), ("who_are_you", ""))

    def test_hello_routes_to_greeting(self) -> None:
        self.assertEqual(bridge.interpret_intent("hello"), ("greet_user", ""))

    def test_hi_intro_literal_routes_to_typed_hi_intent(self) -> None:
        self.assertEqual(bridge.interpret_intent("hi_intro"), ("hi_get_intro", ""))

    def test_set_name_routes_to_hi_profile_field_update(self) -> None:
        self.assertEqual(
            bridge.interpret_intent("set my name Amit Kumar Yadav"),
            ("hi_set_profile_field", {"field": "name", "value": "Amit Kumar Yadav"}),
        )

    def test_plan_routes_to_plan_mode(self) -> None:
        self.assertEqual(bridge.interpret_intent("plan release workflow"), ("plan", "release workflow"))

    @patch("router.update_session_field")
    def test_shell_requires_confirmation(self, _update_session_field) -> None:
        with patch("router.load_profiles", return_value={"HI": {"preferred_response_mode": "adaptive"}}), patch(
            "router.get_session", return_value={}
        ):
            result = bridge.process_intent("run pwd")
        self.assertFalse(result["ok"])
        self.assertEqual(result["action"], "confirmation_required")
        self.assertEqual(result["behavior"]["risk_tier"], "high")

    def test_unknown_phrase_falls_back_to_ai(self) -> None:
        # Phase 3: unrecognised phrases route to the AI action, not "unknown"
        action, _ = bridge.interpret_intent("some completely unrecognised gibberish xyz")
        self.assertEqual(action, "ai")

    def test_profile_routes_to_hi_layer(self) -> None:
        with patch("router.load_profiles", return_value={"HI": {"preferred_response_mode": "adaptive"}}), patch(
            "router.get_session", return_value={}
        ), patch("router.send_hi_request", return_value="profile summary"), patch(
            "router.update_session_field"
        ), patch("router.append_event"):
            result = bridge.process_intent("profile")
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "hi_get_profile")
        self.assertIn("profile summary", result["result"])

    def test_profile_sends_structured_hi_args(self) -> None:
        with patch("router.load_profiles", return_value={"HI": {"preferred_response_mode": "adaptive"}}), patch(
            "router.get_session", return_value={}
        ), patch("router.send_hi_request", return_value="profile summary") as send_hi_request, patch(
            "router.update_session_field"
        ), patch("router.append_event"):
            result = bridge.process_intent("profile")
        self.assertTrue(result["ok"])
        send_hi_request.assert_called_once_with(
            "hi_get_profile",
            "",
            text="profile",
        )

    def test_successful_local_action_records_event_journal_entry(self) -> None:
        with patch("router.load_profiles", return_value={"HI": {"preferred_response_mode": "adaptive"}}), patch(
            "router.get_session", return_value={}
        ), patch("router.execute_action", return_value="system ok"), patch(
            "router.update_session_field"
        ), patch("router.append_event") as append_event:
            result = bridge.process_intent("status")
        self.assertTrue(result["ok"])
        append_event.assert_called_once()

    def test_add_memory_routes_to_typed_memory_add(self) -> None:
        self.assertEqual(
            bridge.interpret_intent("add memory finished bus concurrency fix"),
            ("hi_memory_add", {"entry": "finished bus concurrency fix", "source": "user"}),
        )

    def test_workflow_task_commands_route_to_hi_layer(self) -> None:
        self.assertEqual(
            bridge.interpret_intent("add task finish semantic memory"),
            ("hi_workflow_add_task", {"title": "finish semantic memory"}),
        )
        self.assertEqual(
            bridge.interpret_intent("set task status task-123 doing"),
            ("hi_workflow_set_task_status", {"task_id": "task-123", "status": "doing"}),
        )
        self.assertEqual(
            bridge.interpret_intent("block task task-123 waiting on token"),
            ("hi_workflow_add_blocker", {"task_id": "task-123", "blocker": "waiting on token"}),
        )
        self.assertEqual(
            bridge.interpret_intent("set task due task-123 2026-06-15"),
            ("hi_workflow_set_due", {"task_id": "task-123", "due": "2026-06-15"}),
        )


if __name__ == "__main__":
    unittest.main()
