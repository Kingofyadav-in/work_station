#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import behavior


class BehaviorTests(unittest.TestCase):
    def test_shell_action_is_high_risk(self) -> None:
        risk = behavior.get_risk_profile("shell", "pwd")
        self.assertEqual(risk["tier"], "high")
        self.assertTrue(risk["requires_confirmation"])

    def test_repeated_status_prefers_short_output(self) -> None:
        rules = behavior.build_behavior_rules(
            {"HI": {"preferred_response_mode": "adaptive", "preferred_command_style": "natural"}},
            {"last_action": "status", "last_intent": "status"},
            "status",
            action="status",
        )
        self.assertTrue(rules["prefer_short_output"])

    def test_unknown_repeat_suggests_help(self) -> None:
        rules = behavior.build_behavior_rules(
            {"HI": {"preferred_response_mode": "adaptive", "preferred_command_style": "natural"}},
            {"last_action": "unknown", "last_intent": "what is this"},
            "what is this",
            action="unknown",
        )
        text = behavior.apply_behavior_to_text(
            text="Unknown intent: what is this",
            ok=False,
            action="unknown",
            behavior=rules,
        )
        self.assertIn("Suggestions:", text)

    @patch("behavior.get_system_info")
    def test_short_status_text_is_applied(self, get_system_info) -> None:
        get_system_info.return_value = {
            "hostname": "JarvisBox",
            "connectivity": "online",
            "local_time": "2026-04-23 10:00:00",
        }
        result = behavior.apply_behavior_to_text(
            text="System Status\n-------------\nLong output",
            ok=True,
            action="status",
            behavior={"prefer_short_output": True},
        )
        self.assertEqual(result, "System healthy on JarvisBox | online | 2026-04-23 10:00:00")


if __name__ == "__main__":
    unittest.main()
