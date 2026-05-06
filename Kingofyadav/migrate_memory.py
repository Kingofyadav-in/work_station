#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from pathlib import Path

from validate_state import normalize_state
from memory_store import DB_PATH, sync_from_state


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
BACKUP_PATH = ROOT / "state.backup.json"


def main() -> int:
    if not STATE_PATH.exists():
        print(f"State file not found: {STATE_PATH}")
        return 1

    shutil.copy2(STATE_PATH, BACKUP_PATH)

    raw_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    normalized = normalize_state(raw_state)

    tmp_path = STATE_PATH.with_name(f"{STATE_PATH.name}.migration.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)
    tmp_path.replace(STATE_PATH)
    synced = sync_from_state(normalized.get("memory", []))

    print(f"Backup written to {BACKUP_PATH}")
    print(f"Migrated memory entries: {len(normalized.get('memory', []))}")
    print(f"SQLite memory entries synced: {synced} -> {DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
