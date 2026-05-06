#!/usr/bin/env python3
"""
Bus health CLI — show pending/processed/deadletter/response counts at a glance.

Usage:
    python3 shared/bus_health.py
    python3 shared/bus_health.py --watch     # refresh every 2s
    python3 shared/bus_health.py --clear-dl  # move dead-letter files to /tmp for inspection
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from listener_status import pid_file_is_recent, resolve_listener_pid

ROOT_DIR = Path(__file__).resolve().parent.parent
BUS_DIR = ROOT_DIR / "shared" / "bus"
REQUESTS_DIR = BUS_DIR / "requests"
RESPONSES_DIR = BUS_DIR / "responses"
PROCESSED_DIR = BUS_DIR / "processed"
DEADLETTER_DIR = BUS_DIR / "deadletter"
BUS_LOG = ROOT_DIR / "logs" / "bus.log"
KING_PID = ROOT_DIR / "logs" / "kingofyadav.pid"


def _listener_alive() -> bool:
    pid = resolve_listener_pid(KING_PID)
    if pid is not None:
        return True
    return pid_file_is_recent(KING_PID)


def _count(directory: Path, pattern: str = "*") -> int:
    try:
        return sum(1 for _ in directory.glob(pattern))
    except Exception:
        return -1


def _last_bus_line() -> str:
    try:
        lines = BUS_LOG.read_text(encoding="utf-8").splitlines()
        if not lines:
            return "(no log)"
        obj = json.loads(lines[-1])
        return f"[{obj.get('ts', '?')[:19]}] {obj.get('msg', '?')}"
    except Exception:
        return "(unreadable)"


def _dl_summary() -> list[str]:
    try:
        files = sorted(DEADLETTER_DIR.glob("*"))
        return [f.name for f in files[:10]]
    except Exception:
        return []


def _age_seconds(path: Path) -> float:
    try:
        return time.time() - path.stat().st_mtime
    except Exception:
        return 0.0


def _oldest_pending() -> str:
    try:
        files = list(REQUESTS_DIR.glob("*.json"))
        if not files:
            return "none"
        oldest = min(files, key=lambda p: p.stat().st_mtime)
        age = _age_seconds(oldest)
        return f"{oldest.name[:40]}... ({age:.0f}s ago)"
    except Exception:
        return "unknown"


def render_health() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    listener = "ONLINE" if _listener_alive() else "OFFLINE"
    pending = _count(REQUESTS_DIR, "*.json")
    in_flight = _count(REQUESTS_DIR, "*.processing")
    responses = _count(RESPONSES_DIR, "*.json")
    processed = _count(PROCESSED_DIR, "*")
    deadletter = _count(DEADLETTER_DIR, "*")
    dl_files = _dl_summary()
    last_log = _last_bus_line()
    oldest = _oldest_pending()

    print(f"\n{'─' * 52}")
    print(f"  Bus Health            {now}")
    print(f"{'─' * 52}")
    print(f"  Listener      : {listener}")
    print(f"  Pending       : {pending}")
    print(f"  In-flight     : {in_flight}")
    print(f"  Awaiting resp : {responses}")
    print(f"  Processed     : {processed}")
    print(f"  Dead-letter   : {deadletter}{'  ← action needed' if deadletter else ''}")
    if dl_files:
        for name in dl_files:
            print(f"    • {name}")
    print(f"  Oldest pending: {oldest}")
    print(f"  Last bus log  : {last_log}")
    print(f"{'─' * 52}\n")


def clear_deadletter() -> None:
    import shutil
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="jarvis_dl_"))
    moved = 0
    for f in DEADLETTER_DIR.glob("*"):
        shutil.move(str(f), str(tmp / f.name))
        moved += 1
    print(f"Moved {moved} dead-letter file(s) to {tmp}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis bus health checker")
    parser.add_argument("--watch", action="store_true", help="Refresh every 2 seconds")
    parser.add_argument("--clear-dl", action="store_true", help="Move dead-letter files to /tmp")
    args = parser.parse_args()

    if args.clear_dl:
        clear_deadletter()
        return

    if args.watch:
        try:
            while True:
                os.system("clear")
                render_health()
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nStopped.")
    else:
        render_health()


if __name__ == "__main__":
    main()
