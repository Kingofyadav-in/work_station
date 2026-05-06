from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[2]
SHARED_DIR = ROOT_DIR / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

import local_admin_registry


class LocalAdminRegistryTests(unittest.TestCase):
    def test_record_and_summarize_local_admin_user(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "local_admin_users.jsonl"
            with patch.object(local_admin_registry, "REGISTRY_LOG", log_path):
                local_admin_registry.record_local_admin_user(
                    username="alice",
                    password_hash="hash-1234567890abcdef",
                    password_salt="salt-1",
                    hash_version="pbkdf2-sha256",
                    action="signup",
                    source="web",
                    device_id="dev-1",
                )
                local_admin_registry.record_local_admin_user(
                    username="alice",
                    password_hash="hash-1234567890abcdef",
                    password_salt="salt-1",
                    hash_version="pbkdf2-sha256",
                    action="login",
                    source="web",
                    device_id="dev-1",
                )
                local_admin_registry.record_local_admin_user(
                    username="alice",
                    password_hash="hash-9999999999999999",
                    password_salt="salt-2",
                    hash_version="pbkdf2-sha256",
                    action="login",
                    source="web",
                    device_id="dev-2",
                )

                summary = local_admin_registry.get_local_admin_users(limit=20)

                self.assertEqual(summary["count"], 2)
                self.assertEqual(summary["active_count"], 2)
                self.assertEqual(summary["latest"]["username"], "alice")
                self.assertEqual(summary["latest"]["action"], "login")
                self.assertIn(summary["latest"].get("session_key", ""), {"alice::dev-1", "alice::dev-2"})
                self.assertTrue(summary["latest"]["has_salt"])

                local_admin_registry.clear_local_admin_users()
                cleared = local_admin_registry.get_local_admin_users(limit=20)
                self.assertEqual(cleared["count"], 0)


if __name__ == "__main__":
    unittest.main()
