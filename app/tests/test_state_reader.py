#!/usr/bin/env python3
"""Tests for state_reader and log_reader modules."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "app"))


class TestReadJson(unittest.TestCase):
    def setUp(self):
        import services.state_reader as sr
        self._sr = sr

    def test_reads_valid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"key": "value"}, f)
            path = Path(f.name)
        result = self._sr._read_json(path)
        path.unlink()
        self.assertEqual(result, {"key": "value"})

    def test_returns_default_for_missing_file(self):
        result = self._sr._read_json(Path("/nonexistent/file.json"), default={"fallback": True})
        self.assertEqual(result, {"fallback": True})

    def test_returns_empty_dict_when_no_default(self):
        result = self._sr._read_json(Path("/nonexistent/file.json"))
        self.assertEqual(result, {})

    def test_returns_default_for_corrupt_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("this is not json {{{")
            path = Path(f.name)
        result = self._sr._read_json(path, default={"safe": True})
        path.unlink()
        self.assertEqual(result, {"safe": True})

    def test_returns_nested_data(self):
        data = {"profile": {"name": "Amit"}, "memory": [1, 2, 3]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)
        result = self._sr._read_json(path)
        path.unlink()
        self.assertEqual(result["profile"]["name"], "Amit")
        self.assertEqual(len(result["memory"]), 3)


class TestListenerStatus(unittest.TestCase):
    def setUp(self):
        import services.state_reader as sr
        self._sr = sr

    def test_no_pid_file_returns_offline(self):
        with patch("services.state_reader.resolve_listener_pid", return_value=None), \
             patch("services.state_reader.pid_file_is_recent", return_value=False):
            status = self._sr.get_listener_status()
        self.assertFalse(status["online"])
        self.assertEqual(status["pids"], [])

    def test_valid_pid_returns_online(self):
        with patch("services.state_reader.resolve_listener_pid", return_value=12345), \
             patch("services.state_reader.pid_file_is_recent", return_value=True):
            status = self._sr.get_listener_status()
        self.assertTrue(status["online"])
        self.assertIn("12345", status["pids"])

    def test_recent_pid_file_no_pid_returns_online(self):
        with patch("services.state_reader.resolve_listener_pid", return_value=None), \
             patch("services.state_reader.pid_file_is_recent", return_value=True):
            status = self._sr.get_listener_status()
        self.assertTrue(status["online"])
        self.assertEqual(status["pids"], [])


class TestGetAutomationSnapshot(unittest.TestCase):
    def setUp(self):
        import services.state_reader as sr
        self._sr = sr

    def test_returns_default_on_import_error(self):
        with patch("services.state_reader.sys") as mock_sys:
            mock_sys.path = sys.path[:]
            with patch.dict("sys.modules", {"services.automation_client": None}):
                result = self._sr.get_automation_snapshot()
        for key in ("daemon_alive", "stop_active", "dry_run", "rule_count"):
            self.assertIn(key, result)

    def test_returns_automation_status_when_available(self):
        fake_status = {"daemon_alive": True, "stop_active": False, "dry_run": False,
                       "rule_count": 5, "enabled_count": 4, "pending_count": 0}
        mock_mod = MagicMock()
        mock_mod.get_automation_status.return_value = fake_status
        with patch.dict("sys.modules", {"services.automation_client": mock_mod}):
            result = self._sr.get_automation_snapshot()
        self.assertEqual(result["rule_count"], 5)
        self.assertTrue(result["daemon_alive"])


class TestLogReader(unittest.TestCase):
    def setUp(self):
        import services.log_reader as lr
        self._lr = lr

    def _write_tmp_log(self, lines: list[str]) -> Path:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n".join(lines) + "\n")
            return Path(f.name)

    def test_tail_lines_returns_last_n(self):
        path = self._write_tmp_log([f"line{i}" for i in range(20)])
        result = self._lr._tail_lines(path, lines=5)
        path.unlink()
        self.assertEqual(len(result), 5)
        self.assertIn("line19", result)

    def test_tail_lines_missing_file_returns_empty(self):
        result = self._lr._tail_lines(Path("/nonexistent/bus.log"))
        self.assertEqual(result, [])

    def test_parse_bus_line_json(self):
        line = json.dumps({"ts": "2026-01-01T00:00:00Z", "msg": "hello world"})
        result = self._lr._parse_bus_line(line)
        self.assertIn("hello world", result)
        self.assertIn("2026-01-01T00:00:00Z", result)

    def test_parse_bus_line_plain_fallback(self):
        result = self._lr._parse_bus_line("plain text line")
        self.assertEqual(result, "plain text line")

    def test_read_bus_log_filtered_by_keyword(self):
        with patch.object(self._lr, "_tail_lines",
                          return_value=["[ts] alpha", "[ts] beta", "[ts] alpha again"]):
            result = self._lr.read_bus_log_filtered(lines=10, keyword="alpha")
        self.assertEqual(len(result), 2)
        self.assertTrue(all("alpha" in r.lower() for r in result))

    def test_read_bus_log_filtered_no_keyword(self):
        with patch.object(self._lr, "_tail_lines", return_value=["line1", "line2"]):
            result = self._lr.read_bus_log_filtered(lines=10, keyword="")
        self.assertEqual(len(result), 2)

    def test_get_last_event_returns_none_when_empty(self):
        with patch.object(self._lr, "read_event_lines", return_value=[]):
            result = self._lr.get_last_event()
        self.assertIsNone(result)

    def test_get_last_event_parses_json(self):
        event = {"ts": "2026-01-01T00:00:00Z", "type": "focus_set"}
        with patch.object(self._lr, "read_event_lines", return_value=[json.dumps(event)]):
            result = self._lr.get_last_event()
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "focus_set")

    def test_get_last_bus_log_time_no_log(self):
        with patch.object(self._lr, "read_bus_log", return_value=[]):
            result = self._lr.get_last_bus_log_time()
        self.assertEqual(result, "none")

    def test_get_last_bus_log_time_parses_bracket_ts(self):
        with patch.object(self._lr, "read_bus_log", return_value=["[2026-01-01T12:00:00Z] msg"]):
            result = self._lr.get_last_bus_log_time()
        self.assertEqual(result, "2026-01-01T12:00:00Z")

    def test_read_event_objects_skips_invalid_json(self):
        with patch.object(self._lr, "read_event_lines",
                          return_value=["not json", '{"ts": "x", "type": "ok"}']):
            objects = self._lr.read_event_objects(lines=5)
        self.assertEqual(len(objects), 1)
        self.assertEqual(objects[0]["type"], "ok")


if __name__ == "__main__":
    unittest.main()
