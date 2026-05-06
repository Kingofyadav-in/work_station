#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import public_intake


class PublicIntakeTests(unittest.TestCase):
    def test_submit_public_enquiry_writes_local_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "public_intake.jsonl"
            with patch.object(public_intake, "INTAKE_LOG", log_path):
                record = public_intake.submit_public_enquiry(
                    name="Amit",
                    email="amit@example.com",
                    subject="Services",
                    message="Tell me more",
                    client_ip="198.51.100.9",
                    page="https://example.com/contact",
                )
                self.assertEqual(record["kind"], "enquiry")
                self.assertTrue(log_path.exists())
                saved = log_path.read_text(encoding="utf-8").strip()
                self.assertIn("amit@example.com", saved)
                self.assertIn("Services", saved)

    def test_submit_public_signup_writes_local_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "public_intake.jsonl"
            with patch.object(public_intake, "INTAKE_LOG", log_path):
                record = public_intake.submit_public_signup(
                    name="King",
                    email="king@example.com",
                    handle="@king",
                    reason="Collaboration",
                    message="Need access",
                    client_ip="198.51.100.8",
                )
                self.assertEqual(record["kind"], "signup")
                self.assertTrue(log_path.exists())
                saved = log_path.read_text(encoding="utf-8").strip()
                self.assertIn("king@example.com", saved)
                self.assertIn("Collaboration", saved)


if __name__ == "__main__":
    unittest.main()
