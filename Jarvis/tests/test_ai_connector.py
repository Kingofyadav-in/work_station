#!/usr/bin/env python3

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_connector


class AIConnectorTests(unittest.TestCase):
    def test_missing_model_config_defaults_to_local_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_cfg = Path(tmpdir) / "ai_model_config.json"
            with patch.object(ai_connector, "_MODEL_CFG", fake_cfg), \
                 patch.dict(os.environ, {"OLLAMA_MODEL": "llama3.2:3b"}, clear=False):
                cfg = ai_connector.get_model_config()

        self.assertEqual(cfg["provider"], "ollama")
        self.assertEqual(cfg["model"], "llama3.2:3b")

    def test_ollama_model_sort_prefers_smaller_local_models(self) -> None:
        ordered = ai_connector.sort_ollama_models([
            "llama3:latest",
            "llama3.2:3b",
            "phi3:mini",
            "llama3.1:8b",
        ])

        self.assertEqual(ordered[0], "llama3.2:3b")
        self.assertLess(ordered.index("llama3.2:3b"), ordered.index("llama3.1:8b"))


if __name__ == "__main__":
    unittest.main()
