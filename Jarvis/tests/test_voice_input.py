#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import voice_input


class VoiceInputTests(unittest.TestCase):
    def test_normalize_library_wait_timeout_to_builtin_timeout(self) -> None:
        fake_timeout = type("FakeWaitTimeoutError", (Exception,), {})

        with patch.object(voice_input, "sr") as mock_sr:
            mock_sr.WaitTimeoutError = fake_timeout
            normalized = voice_input._normalize_capture_error(
                fake_timeout("listening timed out while waiting for phrase to start")
            )

        self.assertIsInstance(normalized, TimeoutError)
        self.assertEqual(str(normalized), voice_input.TIMEOUT_MESSAGE)

    def test_normalize_timeout_like_runtime_message(self) -> None:
        normalized = voice_input._normalize_capture_error(
            RuntimeError("listening timed out while waiting for phrase to start")
        )

        self.assertIsInstance(normalized, TimeoutError)
        self.assertEqual(str(normalized), voice_input.TIMEOUT_MESSAGE)


if __name__ == "__main__":
    unittest.main()
