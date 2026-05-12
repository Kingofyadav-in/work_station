#!/usr/bin/env python3
"""Tests for dashboard SQLite storage layer."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "app"))


class TestDashboardDB(unittest.TestCase):
    def setUp(self):
        import services.dashboard_db as db_mod
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "test.db"
        self._orig_path = db_mod._DB_PATH
        db_mod._DB_PATH = self._db_path
        db_mod._init()

    def tearDown(self):
        import services.dashboard_db as db_mod
        db_mod._DB_PATH = self._orig_path
        self._tmpdir.cleanup()

    def test_log_action_and_retrieve(self):
        import services.dashboard_db as db
        db.log_action("test_action", command="automation status", result="ok text", ok=True)
        actions = db.get_recent_actions(limit=10)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["action_type"], "test_action")
        self.assertEqual(actions[0]["command"], "automation status")

    def test_log_action_failed(self):
        import services.dashboard_db as db
        db.log_action("fail_action", ok=False)
        actions = db.get_recent_actions()
        self.assertEqual(actions[0]["ok"], 0)

    def test_multiple_actions_ordered_desc(self):
        import services.dashboard_db as db
        db.log_action("first")
        db.log_action("second")
        db.log_action("third")
        actions = db.get_recent_actions(limit=3)
        self.assertEqual(actions[0]["action_type"], "third")
        self.assertEqual(actions[2]["action_type"], "first")

    def test_save_and_retrieve_snapshot(self):
        import services.dashboard_db as db
        db.save_automation_snapshot(
            daemon_alive=True, stop_active=False, dry_run=False,
            rule_count=4, enabled_count=3, pending_count=1,
        )
        snaps = db.get_recent_snapshots(limit=5)
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["rule_count"], 4)
        self.assertEqual(snaps[0]["enabled_count"], 3)
        self.assertEqual(snaps[0]["daemon_alive"], 1)
        self.assertEqual(snaps[0]["pending_count"], 1)

    def test_snapshot_retains_only_500(self):
        import services.dashboard_db as db
        for i in range(505):
            db.save_automation_snapshot(
                daemon_alive=True, stop_active=False, dry_run=False,
                rule_count=4, enabled_count=4, pending_count=0,
            )
        snaps = db.get_recent_snapshots(limit=600)
        self.assertLessEqual(len(snaps), 500)

    def test_result_truncated_at_500_chars(self):
        import services.dashboard_db as db
        long_result = "x" * 1000
        db.log_action("long_result", result=long_result)
        actions = db.get_recent_actions()
        self.assertLessEqual(len(actions[0]["result"]), 500)

    def test_empty_db_returns_empty_list(self):
        import services.dashboard_db as db
        self.assertEqual(db.get_recent_actions(), [])
        self.assertEqual(db.get_recent_snapshots(), [])


class TestAutomationClient(unittest.TestCase):
    def test_status_returns_dict_with_required_keys(self):
        sys.path.insert(0, str(_ROOT / "app"))
        from services.automation_client import get_automation_status
        status = get_automation_status()
        for key in ("daemon_alive", "stop_active", "dry_run", "rule_count", "enabled_count", "pending_count"):
            self.assertIn(key, status)

    def test_rules_returns_list(self):
        from services.automation_client import get_automation_rules
        rules = get_automation_rules()
        self.assertIsInstance(rules, list)

    def test_pending_returns_list(self):
        from services.automation_client import get_automation_pending
        pending = get_automation_pending()
        self.assertIsInstance(pending, list)

    def test_audit_returns_list(self):
        from services.automation_client import get_automation_audit
        audit = get_automation_audit(n=5)
        self.assertIsInstance(audit, list)

    def test_log_tail_returns_list(self):
        from services.automation_client import get_automation_log_tail
        lines = get_automation_log_tail(n=10)
        self.assertIsInstance(lines, list)


if __name__ == "__main__":
    unittest.main()
