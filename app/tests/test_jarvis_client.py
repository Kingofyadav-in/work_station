#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

from services import jarvis_client


class JarvisClientTests(unittest.TestCase):
    def test_preview_command_exposes_route_and_risk(self) -> None:
        preview = jarvis_client.preview_command("auto detect device primary-control-device")

        self.assertEqual(preview["parsed_action"], "auto_detect_device")
        self.assertEqual(preview["route"], "local")
        self.assertEqual(preview["risk_tier"], "medium")
        self.assertTrue(preview["takes_payload"])

    def test_run_command_includes_trace_metadata(self) -> None:
        fake_result = {
            "ok": True,
            "intent": "status",
            "action": "status",
            "payload": "",
            "result": "ok",
            "error": None,
            "behavior": {},
        }
        with patch.object(jarvis_client.bridge, "process_intent", return_value=fake_result):
            result = jarvis_client.run_command("status")

        self.assertIn("trace_id", result)
        self.assertIn("duration_ms", result)
        self.assertEqual(result["parsed_action"], "status")
        self.assertEqual(result["route"], "local")


if __name__ == "__main__":
    unittest.main()
