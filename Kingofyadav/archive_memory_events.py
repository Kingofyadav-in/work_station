#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

from validate_state import normalize_memory_entry, normalize_state


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
BACKUP_PATH = ROOT / "state.backup.json"
ARCHIVE_PATH = ROOT / "memory_event_archive.json"


def main() -> int:
    if not STATE_PATH.exists():
        print(f"State file not found: {STATE_PATH}")
        return 1

    shutil.copy2(STATE_PATH, BACKUP_PATH)

    raw_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    raw_memory = raw_state.get("memory", [])

    archived_events: list[dict] = []
    kept_notes: list[dict] = []
    seen_notes: set[str] = set()

    if isinstance(raw_memory, list):
        for entry in raw_memory:
            item = normalize_memory_entry(entry)
            if item is None:
                continue
            if item.get("type") == "event":
                archived_events.append(item)
                continue
            marker = json.dumps(item, sort_keys=True, ensure_ascii=False)
            if marker in seen_notes:
                continue
            seen_notes.add(marker)
            kept_notes.append(item)

    archive_payload = {
        "archived_from": str(STATE_PATH),
        "event_count": len(archived_events),
        "events": archived_events,
    }
    with ARCHIVE_PATH.open("w", encoding="utf-8") as f:
        json.dump(archive_payload, f, indent=2, ensure_ascii=False)

    raw_state["memory"] = kept_notes
    normalized = normalize_state(raw_state)
    tmp_path = STATE_PATH.with_name(f"{STATE_PATH.name}.archive.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)
    tmp_path.replace(STATE_PATH)

    print(f"Backup written to {BACKUP_PATH}")
    print(f"Archived event entries: {len(archived_events)}")
    print(f"Curated memory notes kept: {len(kept_notes)}")
    print(f"Archive written to {ARCHIVE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
