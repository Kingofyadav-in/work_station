#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import device_registry


def _inventory(
    fingerprint: str,
    machine_id_hash: str = "machine-1",
    hostname: str = "host-a",
    user: str = "king",
) -> dict:
    return {
        "fingerprint": fingerprint,
        "identity": {
            "hostname": hostname,
            "user": user,
            "machine_id_hash": machine_id_hash,
            "network_hash": "network-1",
        },
        "hardware": {
            "machine": "x86_64",
        },
        "software": {
            "operating_system": "Linux",
        },
        "network": {},
        "environment": {},
    }


class DeviceRegistryTests(unittest.TestCase):
    def test_verify_trusts_stable_identity_when_fingerprint_is_stale(self) -> None:
        registered = {
            "label": "primary",
            "registered_at": "2026-04-27T00:00:00+00:00",
            "trusted": True,
            "inventory": _inventory("old-fingerprint"),
        }
        with (
            patch("device_registry.collect_device_inventory", return_value=_inventory("new-fingerprint")),
            patch("device_registry.load_registered_device", return_value=registered),
        ):
            result = device_registry.verify_current_device()

        self.assertTrue(result["registered"])
        self.assertTrue(result["trusted"])
        self.assertEqual(result["trust_match"], "stable_identity")

    def test_auto_detect_registers_when_registry_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "device_registry.json"
            with (
                patch.object(device_registry, "REGISTRY_PATH", registry_path),
                patch("device_registry.collect_device_inventory", return_value=_inventory("fp-1")),
            ):
                result = device_registry.auto_detect_and_register_device("primary-control-device")

        self.assertEqual(result["action"], "registered")
        self.assertTrue(result["trusted"])
        self.assertEqual(result["record"]["label"], "primary-control-device")

    def test_auto_detect_replaces_different_machine_identity(self) -> None:
        registered = {
            "label": "primary",
            "registered_at": "2026-04-27T00:00:00+00:00",
            "trusted": True,
            "inventory": _inventory("old-fingerprint", machine_id_hash="machine-1", hostname="host-a"),
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            registry_path = Path(tmpdir) / "device_registry.json"
            registry_path.write_text("{}\n", encoding="utf-8")
            with (
                patch.object(device_registry, "REGISTRY_PATH", registry_path),
                patch("device_registry.collect_device_inventory", return_value=_inventory("new-fingerprint", machine_id_hash="machine-2", hostname="host-b")),
                patch("device_registry.load_registered_device", return_value=registered),
            ):
                result = device_registry.auto_detect_and_register_device("primary-control-device")

        self.assertEqual(result["action"], "replaced")
        self.assertTrue(result["trusted"])
        self.assertEqual(result["record"]["previous_fingerprint"], "old-fingerprint")


if __name__ == "__main__":
    unittest.main()
