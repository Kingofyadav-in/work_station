#!/usr/bin/env python3

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import memory
import memory_store
import state_manager


class MemoryTests(unittest.TestCase):
    def test_add_memory_persists_curated_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            db_path = Path(tmpdir) / "memory.db"
            with patch.object(state_manager, "STATE_PATH", path), patch.object(memory_store, "DB_PATH", db_path), patch.object(
                memory, "load_state", side_effect=state_manager.load_state
            ):
                stored = memory.add_memory("finished bus concurrency fix")
                entry = stored[-1]
                self.assertEqual(entry["type"], "note")
                self.assertEqual(entry["text"], "finished bus concurrency fix")
                self.assertIn("created_at", entry)
                texts = [e["text"] for e in memory.get_memory()]
                self.assertIn("finished bus concurrency fix", texts)

    def test_semantic_search_finds_related_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            db_path = Path(tmpdir) / "memory.db"
            with patch.object(state_manager, "STATE_PATH", path), patch.object(memory_store, "DB_PATH", db_path), patch.object(
                memory, "load_state", side_effect=state_manager.load_state
            ):
                memory.add_memory({"type": "note", "text": "finish API documentation for website launch", "tag": "website"})
                memory.add_memory({"type": "note", "text": "buy groceries after work", "tag": "personal"})

                results = memory.semantic_search_memory("website docs")

        self.assertGreaterEqual(len(results), 1)
        self.assertIn("API documentation", results[0]["text"])
        self.assertIn("score", results[0])

    def test_memory_visibility_updates_sqlite_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            db_path = Path(tmpdir) / "memory.db"
            with patch.object(state_manager, "STATE_PATH", path), patch.object(memory_store, "DB_PATH", db_path), patch.object(
                memory, "load_state", side_effect=state_manager.load_state
            ):
                stored = memory.add_memory("publishable project update")
                memory_id = memory_store.memory_id(stored[-1])
                result = memory.set_memory_visibility(memory_id, "public")
                public_items = memory_store.list_memories(visibility="public")

        self.assertFalse(result["_error"])
        self.assertEqual(public_items[0]["id"], memory_id)

    def test_memory_summary_reports_curated_entries(self) -> None:
        with patch(
            "memory.get_memory",
            return_value=[
                {"type": "note", "text": "one"},
                {"type": "note", "text": "two"},
                {"type": "note", "text": "three"},
                {"type": "note", "text": "four"},
            ],
        ):
            summary = memory.get_memory_summary()
        self.assertIn("4 stored event(s)", summary["text"])
        self.assertIn("'text': 'two'", summary["text"])
        self.assertIn("'text': 'four'", summary["text"])
