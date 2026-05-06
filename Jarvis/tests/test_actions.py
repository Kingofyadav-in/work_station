#!/usr/bin/env python3

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

import actions
import command_registry
import intent_parser
import plugin_loader
import router


class ActionTests(unittest.TestCase):
    def test_shell_blocks_outside_workspace(self) -> None:
        self.assertIn("outside the Jarvis workspace", actions.execute_shell_command("ls ../"))

    @patch("actions.load_profiles")
    @patch("actions.get_session")
    @patch("actions.get_system_info")
    def test_memory_report_contains_expected_fields(self, get_system_info, get_session, load_profiles) -> None:
        load_profiles.return_value = {
            "HI": {
                "name": "Amit Kumar Yadav",
                "domain": "kingofyadav.in",
                "language": "HI",
                "preferred_intro_mode": "normal",
                "preferred_response_mode": "adaptive",
                "preferred_command_style": "natural",
                "preferred_mic_device": 5,
                "wake_phrase": "jarvis",
            }
        }
        get_session.return_value = {
            "last_command": "status",
            "last_successful_action": "status",
        }
        get_system_info.return_value = {"hostname": "Jarvis"}

        report = actions.get_memory_report()
        self.assertIn("kingofyadav.in", report)
        self.assertIn("Preferred Intro Mode: normal", report)
        self.assertIn("Preferred Response Mode: adaptive", report)
        self.assertIn("Last Command: status", report)

    def test_set_response_mode_validates_input(self) -> None:
        self.assertIn("adaptive, concise, or detailed", actions.set_response_mode("fast"))

    @patch("actions.format_device_report")
    def test_device_report_uses_registry(self, format_device_report) -> None:
        format_device_report.return_value = "Device Trust Report\nTrusted: True"

        report = actions.get_device_report()

        self.assertIn("Device Trust Report", report)
        format_device_report.assert_called_once_with(detail=False)

    def test_bridge_format_result_is_human_readable(self) -> None:
        import bridge

        formatted = bridge.format_result(
            {
                "ok": True,
                "intent": "device report",
                "action": "device_report",
                "payload": "",
                "result": "Trusted device is ready.",
                "behavior": {"risk_tier": "low", "response_mode": "adaptive"},
            }
        )

        self.assertIn("Command completed successfully.", formatted)
        self.assertIn("Action : Device report", formatted)
        self.assertIn("Result : Trusted device is ready.", formatted)

    def test_plugin_action_loads_from_skills_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)
            (skills_dir / "demo_skill.py").write_text(
                "\n".join([
                    "ACTIONS = [{",
                    "    'action': 'demo_plugin_echo',",
                    "    'aliases': ['demo plugin'],",
                    "    'description': 'Echo from a plugin.',",
                    "    'risk_tier': 'low',",
                    "    'handler': 'run',",
                    "}]",
                    "def run(payload):",
                    "    return 'plugin alive'",
                    "",
                ]),
                encoding="utf-8",
            )
            with patch.object(plugin_loader, "SKILLS_DIR", skills_dir):
                action, payload = intent_parser.interpret_intent("demo plugin")
                result = actions.execute_action(action, payload)
                help_text = command_registry.format_help_text()

        self.assertEqual(action, "demo_plugin_echo")
        self.assertEqual(result, "plugin alive")
        self.assertIn("demo plugin", help_text)


class RegistryCoverageTests(unittest.TestCase):
    """Every registered action must have a real handler."""

    def test_all_registry_actions_have_handlers(self) -> None:
        # Trigger execute_action once so _ACTION_MAP is populated
        actions.execute_action("time")
        handled = actions.get_action_names()

        # Actions routed to the HI layer — they never reach execute_action
        hi_routed = set(router.HI_INTENTS)
        # Actions handled by router directly before reaching execute_action
        router_handled = {"confirm"}

        missing: list[str] = []
        for cmd in command_registry.REGISTRY:
            if cmd.action in hi_routed or cmd.action in router_handled:
                continue
            if cmd.action not in handled:
                missing.append(cmd.action)

        self.assertEqual(
            missing, [],
            f"Registry actions with no execute_action handler: {missing}",
        )

    def test_risk_sets_cover_all_registry_actions(self) -> None:
        all_actions = {cmd.action for cmd in command_registry.REGISTRY}
        covered = (
            command_registry.LOW_RISK_ACTIONS
            | command_registry.MEDIUM_RISK_ACTIONS
            | command_registry.HIGH_RISK_ACTIONS
        )
        missing = all_actions - covered
        self.assertEqual(missing, set(), f"Registry actions missing from any risk set: {missing}")

    def test_help_text_is_non_empty(self) -> None:
        text = command_registry.format_help_text()
        self.assertIn("Jarvis Commands", text)
        self.assertIn("[INFO", text)
        self.assertIn("[SYSTEM", text)

    def test_exact_table_has_no_duplicate_aliases(self) -> None:
        seen: dict[str, str] = {}
        for cmd in command_registry.REGISTRY:
            for alias in cmd.aliases:
                if alias in seen:
                    self.fail(
                        f"Duplicate alias '{alias}': claimed by both "
                        f"'{seen[alias]}' and '{cmd.action}'"
                    )
                seen[alias] = cmd.action


if __name__ == "__main__":
    unittest.main()
