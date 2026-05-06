#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import archive_memory_events


class ArchiveMemoryEventsTests(unittest.TestCase):
    def test_archive_moves_events_and_keeps_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state_path = root / "state.json"
            backup_path = root / "state.backup.json"
            archive_path = root / "memory_event_archive.json"
            state_path.write_text(
                json.dumps(
                    {
                        "memory": [
                            {"event": "status", "command": "status"},
                            "finished bus concurrency fix",
                            {"type": "note", "text": "finished bus concurrency fix"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with patch.object(archive_memory_events, "STATE_PATH", state_path), patch.object(
                archive_memory_events, "BACKUP_PATH", backup_path
            ), patch.object(archive_memory_events, "ARCHIVE_PATH", archive_path):
                rc = archive_memory_events.main()
            self.assertEqual(rc, 0)
            archived = json.loads(archive_path.read_text(encoding="utf-8"))
            state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(archived["event_count"], 1)
        self.assertEqual(
            state["memory"],
            [{"type": "note", "text": "finished bus concurrency fix", "created_at": "2026-01-01T00:00:00+00:00"}],
        )
