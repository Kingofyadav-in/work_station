#!/usr/bin/env python3
"""SQLite-backed message bus — drop-in replacement for the filesystem MessageBus.

Set JARVIS_BUS_BACKEND=sqlite to activate. Default is "filesystem".
The factory function get_bus(actor) returns the right backend automatically.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from message_bus import (
    ACTIVITY_LOG,
    BUS_LOG,
    DEADLETTER_DIR,
    LOG_DIR,
    MessageBus,
    _DL_ALERT_INTERVAL,
    _PROCESSED_KEEP,
    _REQUEST_TTL_SECONDS,
    _STALE_PROCESSING_SECONDS,
    new_request_id,
    utc_now_iso,
    write_log,
)

# bus_db keeps its own rate-limit timestamp so filesystem and SQLite buses
# don't share state when both are imported in the same process.
_last_dl_alert: float = 0.0
from validate_message import validate_message_dict

ROOT_DIR = Path(__file__).resolve().parent.parent
BUS_DIR = ROOT_DIR / "shared" / "bus"
DB_PATH = BUS_DIR / "bus.db"

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS messages (
    rowid      INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT    UNIQUE NOT NULL,
    intent     TEXT    NOT NULL,
    source     TEXT    NOT NULL,
    target     TEXT    NOT NULL,
    priority   TEXT    NOT NULL DEFAULT 'normal',
    status     TEXT    NOT NULL DEFAULT 'pending',
    ts         TEXT    NOT NULL,
    created_at REAL    NOT NULL,
    updated_at REAL    NOT NULL,
    payload    TEXT    NOT NULL DEFAULT '{}',
    meta       TEXT    NOT NULL DEFAULT '{}',
    reason     TEXT,
    version    TEXT    NOT NULL DEFAULT '1.0',
    full_json  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pending  ON messages (status, target, created_at);
CREATE INDEX IF NOT EXISTS idx_rid      ON messages (request_id);
CREATE INDEX IF NOT EXISTS idx_updated  ON messages (updated_at);
"""

_PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


class _DBPath:
    """Pseudo-path carrying a message so the bus and handler share one interface."""

    def __init__(self, request_id: str, msg: dict[str, Any]) -> None:
        self.request_id = request_id
        self.msg = msg
        self.name = f"db:{request_id}"
        self.suffix = ".json"

    def exists(self) -> bool:
        return True

    def __str__(self) -> str:
        return self.name

    def __bool__(self) -> bool:
        return True


class SQLiteMessageBus:
    """Same public interface as MessageBus, backed by SQLite WAL."""

    supports_filesystem_events: bool = False

    def __init__(self, actor: str, db_path: Path = DB_PATH) -> None:
        self.actor = actor
        self.db_path = db_path
        BUS_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ── internal ───────────────────────────────────────────────────────────────

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    # ── message building ───────────────────────────────────────────────────────

    def build_message(
        self,
        intent: str,
        target: str,
        payload: dict[str, Any],
        priority: str = "normal",
        request_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        msg = {
            "version": "1.0",
            "intent": intent,
            "source": self.actor,
            "target": target,
            "payload": payload,
            "timestamp": utc_now_iso(),
            "request_id": request_id or new_request_id(self.actor.lower()),
            "priority": priority,
            "meta": meta or {},
        }
        return validate_message_dict(msg)

    # ── sending ────────────────────────────────────────────────────────────────

    def send_request(
        self,
        intent: str,
        target: str,
        payload: dict[str, Any],
        priority: str = "normal",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        msg = self.build_message(intent, target, payload, priority=priority, meta=meta)
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO messages
                   (request_id, intent, source, target, priority, status,
                    ts, created_at, updated_at, payload, meta, version, full_json)
                   VALUES (?,?,?,?,?,'pending',?,?,?,?,?,?,?)""",
                (
                    msg["request_id"], msg["intent"], msg["source"], msg["target"],
                    msg.get("priority", "normal"), msg["timestamp"], now, now,
                    json.dumps(msg["payload"]), json.dumps(msg.get("meta", {})),
                    msg["version"], json.dumps(msg),
                ),
            )
        write_log(
            f"REQUEST source={msg['source']} target={msg['target']} "
            f"intent={msg['intent']} request_id={msg['request_id']}"
        )
        return msg

    def send_response(
        self,
        request_message: dict[str, Any],
        payload: dict[str, Any],
        status: str = "ok",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        msg = {
            "version": "1.0",
            "intent": f"{request_message['intent']}_response",
            "source": self.actor,
            "target": request_message["source"],
            "payload": payload,
            "timestamp": utc_now_iso(),
            "request_id": request_message["request_id"],
            "priority": request_message.get("priority", "normal"),
            "meta": {
                "status": status,
                "reply_to_intent": request_message["intent"],
                **(meta or {}),
            },
        }
        msg = validate_message_dict(msg)
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO messages
                   (request_id, intent, source, target, priority, status,
                    ts, created_at, updated_at, payload, meta, version, full_json)
                   VALUES (?,?,?,?,?,'response',?,?,?,?,?,?,?)""",
                (
                    msg["request_id"], msg["intent"], msg["source"], msg["target"],
                    msg.get("priority", "normal"), msg["timestamp"], now, now,
                    json.dumps(msg["payload"]), json.dumps(msg.get("meta", {})),
                    msg["version"], json.dumps(msg),
                ),
            )
        write_log(
            f"RESPONSE source={msg['source']} target={msg['target']} "
            f"intent={msg['intent']} request_id={msg['request_id']}"
        )
        return msg

    # ── receiving ──────────────────────────────────────────────────────────────

    def read_message(self, path: Any) -> dict[str, Any]:
        if isinstance(path, _DBPath):
            return validate_message_dict(path.msg)
        msg = json.loads(Path(path).read_text(encoding="utf-8"))
        return validate_message_dict(msg)

    def list_requests_for_me(self) -> list[_DBPath]:
        now = time.time()
        ttl_cutoff   = now - _REQUEST_TTL_SECONDS
        stale_cutoff = now - _STALE_PROCESSING_SECONDS

        with self._conn() as conn:
            # Reclaim messages stuck in processing
            conn.execute(
                "UPDATE messages SET status='pending', updated_at=? "
                "WHERE status='processing' AND target=? AND updated_at < ?",
                (now, self.actor, stale_cutoff),
            )
            # Expire TTL-busted pending messages
            expired = conn.execute(
                "SELECT request_id, intent FROM messages "
                "WHERE status='pending' AND target=? AND created_at < ?",
                (self.actor, ttl_cutoff),
            ).fetchall()
            for row in expired:
                conn.execute(
                    "UPDATE messages SET status='deadletter', reason='TTL expired', updated_at=? "
                    "WHERE request_id=?",
                    (now, row["request_id"]),
                )
                write_log(f"TTL_EXPIRED request_id={row['request_id']} intent={row['intent']}")

            # Claim pending messages, priority then age
            rows = conn.execute(
                """SELECT request_id, full_json FROM messages
                   WHERE status='pending' AND target=?
                   ORDER BY
                     CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
                     created_at ASC""",
                (self.actor,),
            ).fetchall()

            if rows:
                rids = [r["request_id"] for r in rows]
                conn.execute(
                    f"UPDATE messages SET status='processing', updated_at=? "
                    f"WHERE request_id IN ({','.join('?' * len(rids))})",
                    [now] + rids,
                )

        return [_DBPath(r["request_id"], json.loads(r["full_json"])) for r in rows]

    def mark_processed(self, path: Any) -> None:
        now = time.time()
        if isinstance(path, _DBPath):
            with self._conn() as conn:
                conn.execute(
                    "UPDATE messages SET status='processed', updated_at=? WHERE request_id=?",
                    (now, path.request_id),
                )
            write_log(f"PROCESSED request_id={path.request_id}")
            self._rotate_processed()
        else:
            import shutil
            from message_bus import PROCESSED_DIR
            target = PROCESSED_DIR / Path(path).name
            shutil.move(str(path), str(target))

    def move_to_deadletter(self, path: Any, reason: str) -> None:
        now = time.time()
        if isinstance(path, _DBPath):
            with self._conn() as conn:
                conn.execute(
                    "UPDATE messages SET status='deadletter', reason=?, updated_at=? "
                    "WHERE request_id=?",
                    (reason, now, path.request_id),
                )
            write_log(f"DEADLETTER request_id={path.request_id} reason={reason}")
        else:
            import shutil
            p = Path(path)
            target = DEADLETTER_DIR / p.name
            if p.exists():
                shutil.move(str(p), str(target))
            write_log(f"DEADLETTER file={p.name} reason={reason}")

    def wait_for_response(
        self,
        request_id: str,
        timeout: int = 15,
        poll_interval: float = 0.1,
    ) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT full_json FROM messages "
                    "WHERE request_id=? AND status='response' AND target=?",
                    (request_id, self.actor),
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE messages SET status='processed', updated_at=? WHERE request_id=?",
                        (time.time(), request_id),
                    )
                    return validate_message_dict(json.loads(row["full_json"]))
            time.sleep(poll_interval)
        write_log(f"TIMEOUT actor={self.actor} request_id={request_id} timeout={timeout}")
        return None

    def reap_stale_responses(self) -> int:
        return 0

    # ── health + alerting ──────────────────────────────────────────────────────

    def alert_deadletter(self) -> int:
        global _last_dl_alert
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as c, GROUP_CONCAT(request_id) as rids "
                    "FROM messages WHERE status='deadletter'"
                ).fetchone()
            count = row["c"] if row else 0
            if not count:
                return 0
            now = time.time()
            if now - _last_dl_alert < _DL_ALERT_INTERVAL:
                return count
            _last_dl_alert = now
            rids = (row["rids"] or "").split(",")[:5]
            write_log(f"DEADLETTER_ALERT count={count} request_ids={rids}")
            record = {
                "ts": utc_now_iso(),
                "source": "message_bus",
                "event": "deadletter_alert",
                "count": count,
            }
            try:
                with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception:
                pass
            print(f"[MessageBus/SQLite] WARNING: {count} dead-letter message(s).", flush=True)
            return count
        except Exception:
            return 0

    def get_health(self) -> dict[str, Any]:
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT status, COUNT(*) as c FROM messages GROUP BY status"
                ).fetchall()
            counts = {r["status"]: r["c"] for r in rows}
            return {
                "backend": "sqlite",
                "db_path": str(self.db_path),
                "pending":    counts.get("pending", 0),
                "processing": counts.get("processing", 0),
                "response":   counts.get("response", 0),
                "processed":  counts.get("processed", 0),
                "deadletter": counts.get("deadletter", 0),
            }
        except Exception as exc:
            return {"backend": "sqlite", "error": str(exc)}

    # ── maintenance ────────────────────────────────────────────────────────────

    def _rotate_processed(self) -> None:
        try:
            with self._conn() as conn:
                count = conn.execute(
                    "SELECT COUNT(*) as c FROM messages WHERE status='processed'"
                ).fetchone()["c"]
                if count > _PROCESSED_KEEP:
                    excess = count - _PROCESSED_KEEP
                    conn.execute(
                        "DELETE FROM messages WHERE rowid IN ("
                        "  SELECT rowid FROM messages WHERE status='processed'"
                        "  ORDER BY updated_at ASC LIMIT ?"
                        ")",
                        (excess,),
                    )
                    write_log(f"ROTATE_PROCESSED removed={excess}")
        except Exception:
            pass


# ── factory ────────────────────────────────────────────────────────────────────

def get_bus(actor: str) -> MessageBus | SQLiteMessageBus:
    """Return the right bus backend based on JARVIS_BUS_BACKEND env var.

    JARVIS_BUS_BACKEND=sqlite  → SQLiteMessageBus (WAL, queryable, priority ordering)
    JARVIS_BUS_BACKEND=filesystem (default) → original filesystem MessageBus
    """
    backend = os.getenv("JARVIS_BUS_BACKEND", "filesystem").strip().lower()
    if backend == "sqlite":
        return SQLiteMessageBus(actor)
    return MessageBus(actor)
