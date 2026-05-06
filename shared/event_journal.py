#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from file_lock import file_lock


ROOT_DIR = Path(__file__).resolve().parent.parent
EVENTS_DIR = ROOT_DIR / "shared" / "events"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_event(source: str, event_type: str, payload: dict[str, Any]) -> Path:
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    path = EVENTS_DIR / f"{datetime.now(timezone.utc).date().isoformat()}.jsonl"
    record = {
        "ts": utc_now_iso(),
        "source": source,
        "type": event_type,
        "payload": payload,
    }
    with file_lock(path.with_suffix(path.suffix + ".lock")):
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


# ── File-mtime cache ───────────────────────────────────────────────────────────

_EVENTS_CACHE: tuple[float, list[dict[str, Any]]] | None = None


def _file_signature() -> float:
    """Sum of all .jsonl file mtimes — changes whenever any file is written."""
    if not EVENTS_DIR.exists():
        return 0.0
    try:
        return sum(p.stat().st_mtime for p in EVENTS_DIR.glob("*.jsonl"))
    except Exception:
        return 0.0


def _load_events_cached() -> list[dict[str, Any]]:
    """Return all events, reloading from disk only when files have changed."""
    global _EVENTS_CACHE
    sig = _file_signature()
    if _EVENTS_CACHE is not None and _EVENTS_CACHE[0] == sig:
        return _EVENTS_CACHE[1]

    events: list[dict[str, Any]] = []
    files = sorted(EVENTS_DIR.glob("*.jsonl")) if EVENTS_DIR.exists() else []
    for path in files:
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    pass
        except Exception:
            pass
    _EVENTS_CACHE = (sig, events)
    return events


# ── Queryable journal ──────────────────────────────────────────────────────────

def _build_sqlite(events: list[dict[str, Any]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE events (ts TEXT, source TEXT, type TEXT, payload TEXT)")
    conn.executemany(
        "INSERT INTO events VALUES (?,?,?,?)",
        [
            (
                e.get("ts", ""),
                e.get("source", ""),
                e.get("type", ""),
                json.dumps(e.get("payload", {}), ensure_ascii=False),
            )
            for e in events
        ],
    )
    conn.commit()
    return conn


def query_events(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    source: str | None = None,
    event_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    events = _load_events_cached()
    if not events:
        return []

    conn = _build_sqlite(events)
    try:
        conditions: list[str] = []
        params: list[Any] = []
        if date_from:
            conditions.append("ts >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("ts <= ?")
            params.append(date_to)
        if source:
            conditions.append("source = ?")
            params.append(source)
        if event_type:
            conditions.append("type = ?")
            params.append(event_type)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT ts, source, type, payload FROM events {where} "
            f"ORDER BY ts DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [
            {
                "ts": r["ts"],
                "source": r["source"],
                "type": r["type"],
                "payload": json.loads(r["payload"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


def recent_events(hours: int = 24, limit: int = 100) -> list[dict[str, Any]]:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return query_events(date_from=cutoff, limit=limit)


def event_sources() -> list[str]:
    events = _load_events_cached()
    return sorted({e.get("source", "") for e in events if e.get("source")})


def event_types() -> list[str]:
    events = _load_events_cached()
    return sorted({e.get("type", "") for e in events if e.get("type")})
