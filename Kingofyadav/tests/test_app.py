#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "shared"))

import app
import message_bus


class AppTests(unittest.TestCase):
    def test_process_files_handles_preclaimed_paths(self) -> None:
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
                request = jarvis.send_request("hi_get_memory", "Kingofyadav", {"text": "memory", "args": {}})
                claimed = king.list_requests_for_me()

                with patch("app.handle_request", return_value={"text": "memory ok", "args": {}}):
                    app._process_files(king, claimed)

                response = jarvis.wait_for_response(request["request_id"], timeout=1, poll_interval=0.01)
                self.assertIsNotNone(response)
                self.assertEqual(response["payload"]["text"], "memory ok")
                self.assertEqual(king.list_requests_for_me(), [])


if __name__ == "__main__":
    unittest.main()
