#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import listener_status


class ListenerStatusTests(unittest.TestCase):
    def test_pid_file_is_recent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_path = Path(tmpdir) / "kingofyadav.pid"
            pid_path.write_text("16", encoding="utf-8")
            now = os.path.getmtime(pid_path)
            self.assertTrue(listener_status.pid_file_is_recent(pid_path, max_age_seconds=300))

            old = now - 600
            os.utime(pid_path, (old, old))
            self.assertFalse(listener_status.pid_file_is_recent(pid_path, max_age_seconds=300))

    def test_resolve_listener_pid_rewrites_stale_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_path = Path(tmpdir) / "kingofyadav.pid"
            pid_path.write_text("999999", encoding="utf-8")
            with patch.object(listener_status.os, "kill", side_effect=ProcessLookupError), patch.object(
                listener_status, "find_listener_pid", return_value=16
            ):
                pid = listener_status.resolve_listener_pid(pid_path)

            self.assertEqual(pid, 16)
            self.assertEqual(pid_path.read_text(encoding="utf-8").strip(), "16")

    def test_resolve_listener_pid_returns_none_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_path = Path(tmpdir) / "kingofyadav.pid"
            with patch.object(listener_status, "find_listener_pid", return_value=None):
                pid = listener_status.resolve_listener_pid(pid_path)

            self.assertIsNone(pid)


if __name__ == "__main__":
    unittest.main()
