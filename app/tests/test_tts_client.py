#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

from services import tts_client


class TtsClientTests(unittest.TestCase):
    def test_speak_full_result_uses_full_result_text(self) -> None:
        result = {
            "ok": True,
            "data": {
                "action": "status",
                "payload": "system status",
                "result": "System healthy on JarvisBox | online | 2026-04-26 22:49 UTC",
            },
        }

        with patch.object(tts_client, "speak_text") as speak_text:
            tts_client.speak_full_result(result, max_chars=700)

        speak_text.assert_called_once()
        spoken_text = speak_text.call_args.args[0]
        self.assertIn("Status.", spoken_text)
        self.assertIn("Details system status.", spoken_text)
        self.assertIn("System healthy on JarvisBox", spoken_text)

    def test_speak_full_result_uses_error_text(self) -> None:
        result = {
            "ok": False,
            "data": {
                "action": "shell_exec",
                "error": "Confirmation required for high-risk action.",
            },
        }

        with patch.object(tts_client, "speak_text") as speak_text:
            tts_client.speak_full_result(result, max_chars=700)

        speak_text.assert_called_once()
        spoken_text = speak_text.call_args.args[0]
        self.assertIn("Shell exec.", spoken_text)
        self.assertIn("Error Confirmation required for high-risk action.", spoken_text)

    def test_load_profile_includes_offline_voice(self) -> None:
        profile = tts_client._load_tts_profile()
        self.assertIn("offline_voice", profile)
        self.assertEqual(profile["offline_voice"], "en-gb-x-rp")


if __name__ == "__main__":
    unittest.main()
