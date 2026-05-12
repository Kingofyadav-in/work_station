#!/usr/bin/env python3
"""
Dashboard SQLite store — Phase 4.2.

Two tables:
  dashboard_actions  — every action taken from the dashboard (command, result, ts)
  automation_snapshots — periodic automation state captures for trend visibility

Database lives at logs/dashboard.db.
All operations are best-effort: failures never raise to the UI layer.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

_ROOT = Path(__file__).resolve().parents[2]
_DB_PATH = _ROOT / "logs" / "dashboard.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dashboard_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    action_type TEXT    NOT NULL,
    command     TEXT,
    result      TEXT,
    ok          INTEGER DEFAULT 1,
    source      TEXT    DEFAULT 'dashboard'
);
CREATE INDEX IF NOT EXISTS idx_actions_ts ON dashboard_actions(ts DESC);

CREATE TABLE IF NOT EXISTS automation_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,
    daemon_alive  INTEGER DEFAULT 0,
    stop_active   INTEGER DEFAULT 0,
    dry_run       INTEGER DEFAULT 0,
    rule_count    INTEGER DEFAULT 0,
    enabled_count INTEGER DEFAULT 0,
    pending_count INTEGER DEFAULT 0,
    audit_count   INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON automation_snapshots(ts DESC);
"""


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(str(_DB_PATH), timeout=5, check_same_thread=False)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _init() -> None:
    try:
        with _conn() as con:
            con.executescript(_SCHEMA)
    except Exception:
        pass


_init()


# ── Action log ─────────────────────────────────────────────────────────────────

def log_action(
    action_type: str,
    *,
    command: str = "",
    result: str = "",
    ok: bool = True,
    source: str = "dashboard",
) -> None:
    try:
        ts = datetime.now(timezone.utc).isoformat()
        with _conn() as con:
            con.execute(
                "INSERT INTO dashboard_actions (ts, action_type, command, result, ok, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ts, action_type, command, result[:500], int(ok), source),
            )
    except Exception:
        pass


def get_recent_actions(limit: int = 50) -> list[dict[str, Any]]:
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT ts, action_type, command, result, ok, source "
                "FROM dashboard_actions ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ── Automation snapshots ───────────────────────────────────────────────────────

def save_automation_snapshot(
    *,
    daemon_alive: bool,
    stop_active: bool,
    dry_run: bool,
    rule_count: int,
    enabled_count: int,
    pending_count: int,
    audit_count: int = 0,
) -> None:
    try:
        ts = datetime.now(timezone.utc).isoformat()
        with _conn() as con:
            con.execute(
                "INSERT INTO automation_snapshots "
                "(ts, daemon_alive, stop_active, dry_run, rule_count, enabled_count, pending_count, audit_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ts, int(daemon_alive), int(stop_active), int(dry_run),
                 rule_count, enabled_count, pending_count, audit_count),
            )
            # Keep only last 500 snapshots
            con.execute(
                "DELETE FROM automation_snapshots WHERE id NOT IN "
                "(SELECT id FROM automation_snapshots ORDER BY ts DESC LIMIT 500)"
            )
    except Exception:
        pass


def get_recent_snapshots(limit: int = 20) -> list[dict[str, Any]]:
    try:
        with _conn() as con:
            rows = con.execute(
                "SELECT ts, daemon_alive, stop_active, dry_run, rule_count, "
                "enabled_count, pending_count, audit_count "
                "FROM automation_snapshots ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
