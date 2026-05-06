#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import profile_manager


class ProfileManagerTests(unittest.TestCase):
    def test_hi_field_update_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "profiles.json"
            no_state = Path(tmpdir) / "state.json"  # non-existent — disables overlay
            with patch.object(profile_manager, "PROFILE_PATH", path), patch.object(profile_manager, "_HI_STATE_PATH", no_state):
                profile_manager.save_profiles(profile_manager.load_profiles())
                profile_manager.update_hi_field("language", "EN")
                self.assertEqual(profile_manager.load_profiles()["HI"]["language"], "EN")

    def test_session_update_persists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "profiles.json"
            with patch.object(profile_manager, "PROFILE_PATH", path):
                profile_manager.save_profiles(profile_manager.load_profiles())
                profile_manager.update_session_field("last_command", "status")
                self.assertEqual(profile_manager.get_session()["last_command"], "status")


if __name__ == "__main__":
    unittest.main()
