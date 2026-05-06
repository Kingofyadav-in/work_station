#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import message_bus


class MessageBusTests(unittest.TestCase):
    def test_request_claim_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with patch.object(message_bus, "REQUESTS_DIR", root / "requests"), patch.object(
                message_bus, "RESPONSES_DIR", root / "responses"
            ), patch.object(message_bus, "PROCESSED_DIR", root / "processed"), patch.object(
                message_bus, "DEADLETTER_DIR", root / "deadletter"
            ), patch.object(message_bus, "LOG_DIR", root / "logs"), patch.object(
                message_bus, "BUS_LOG", root / "logs" / "bus.log"
            ):
                sender = message_bus.MessageBus(actor="Jarvis")
                receiver = message_bus.MessageBus(actor="Kingofyadav")
                sender.send_request("hi_get_profile", "Kingofyadav", {"text": "profile", "args": {}})
                claimed = receiver.list_requests_for_me()
                self.assertEqual(len(claimed), 1)
                self.assertTrue(claimed[0].name.endswith(".processing"))
                self.assertEqual(receiver.list_requests_for_me(), [])

    def test_wait_for_response_uses_request_specific_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with patch.object(message_bus, "REQUESTS_DIR", root / "requests"), patch.object(
                message_bus, "RESPONSES_DIR", root / "responses"
            ), patch.object(message_bus, "PROCESSED_DIR", root / "processed"), patch.object(
                message_bus, "DEADLETTER_DIR", root / "deadletter"
            ), patch.object(message_bus, "LOG_DIR", root / "logs"), patch.object(
                message_bus, "BUS_LOG", root / "logs" / "bus.log"
            ):
                jarvis = message_bus.MessageBus(actor="Jarvis")
                king = message_bus.MessageBus(actor="Kingofyadav")
                request = jarvis.send_request("hi_get_profile", "Kingofyadav", {"text": "profile", "args": {}})
                king.send_response(request, {"text": "ok"})
                response = jarvis.wait_for_response(request["request_id"], timeout=1, poll_interval=0.01)
                self.assertIsNotNone(response)
                self.assertEqual(response["intent"], "hi_get_profile_response")
