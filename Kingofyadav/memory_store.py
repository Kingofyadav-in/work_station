#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(__file__).resolve().parent / "memory.db"

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_\-]{1,}", re.I)
_local = threading.local()
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "for", "from", "has", "have",
    "i", "in", "is", "it", "me", "my", "of", "on", "or", "that", "the",
    "this", "to", "was", "were", "what", "when", "with", "you",
}

# Duplicate detection threshold — cosine similarity above this → treat as duplicate
_DUPLICATE_THRESHOLD = 0.88

# Retention policy: importance → max age in days (0 = never expire)
_RETENTION_DAYS: dict[int, int] = {1: 30, 2: 60, 3: 180, 4: 0, 5: 0}


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                text TEXT NOT NULL,
                event TEXT NOT NULL DEFAULT '',
                command TEXT NOT NULL DEFAULT '',
                tag TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'user',
                visibility TEXT NOT NULL DEFAULT 'private',
                importance INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                search_text TEXT NOT NULL,
                token_vector TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_tag ON memories(tag)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_visibility ON memories(visibility)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_connections (
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation TEXT NOT NULL DEFAULT 'related',
                score REAL NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (source_id, target_id, relation)
            )
            """
        )
        # Add updated_at column if upgrading from an older schema
        try:
            conn.execute("ALTER TABLE memory_connections ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists


def _stem(token: str) -> str:
    token = token.lower().strip("-_")
    for suffix in ("ing", "ers", "ies", "ed", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            if suffix == "ies":
                return token[:-3] + "y"
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    return [
        _stem(match.group(0))
        for match in _TOKEN_RE.finditer(text.lower())
        if match.group(0).lower() not in _STOPWORDS
    ]


def _token_vector(text: str) -> dict[str, float]:
    counts: dict[str, float] = {}
    for token in tokenize(text):
        counts[token] = counts.get(token, 0.0) + 1.0
    length = math.sqrt(sum(value * value for value in counts.values())) or 1.0
    return {token: value / length for token, value in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    small, large = (a, b) if len(a) <= len(b) else (b, a)
    return sum(value * large.get(token, 0.0) for token, value in small.items())


def _primary_text(entry: dict[str, Any]) -> str:
    return str(entry.get("text") or entry.get("event") or entry.get("command") or "").strip()


def _search_text(entry: dict[str, Any]) -> str:
    parts = [
        str(entry.get("type", "")),
        str(entry.get("text", "")),
        str(entry.get("event", "")),
        str(entry.get("command", "")),
        str(entry.get("tag", "")),
        str(entry.get("source", "")),
    ]
    return " ".join(part for part in parts if part).strip()


def memory_id(entry: dict[str, Any]) -> str:
    basis = "|".join([
        str(entry.get("created_at", "")),
        str(entry.get("type", "")),
        _primary_text(entry),
    ])
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def _normalize_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    importance = entry.get("importance", 3)
    try:
        importance_int = max(1, min(5, int(importance)))
    except (TypeError, ValueError):
        importance_int = 3
    visibility = str(entry.get("visibility", "private")).strip().lower()
    if visibility not in {"private", "public"}:
        visibility = "private"
    return {
        "source": str(entry.get("source", "user") or "user").strip() or "user",
        "visibility": visibility,
        "importance": importance_int,
    }


def find_duplicate(entry: dict[str, Any]) -> str | None:
    """Return the ID of an existing memory that is near-identical to entry, or None."""
    init_db()
    search_text = _search_text(entry)
    if not search_text.strip():
        return None
    new_vector = _token_vector(search_text)
    entry_id = str(entry.get("id") or "")
    with _connect() as conn:
        rows = conn.execute("SELECT id, token_vector FROM memories").fetchall()
    for row in rows:
        if entry_id and row["id"] == entry_id:
            continue
        existing_vector = json.loads(row["token_vector"] or "{}")
        if _cosine(new_vector, existing_vector) >= _DUPLICATE_THRESHOLD:
            return str(row["id"])
    return None


def upsert_memory(entry: dict[str, Any], *, check_duplicate: bool = False) -> str:
    """Insert or update a memory. Returns the canonical memory ID.

    When check_duplicate=True and a near-identical memory already exists,
    returns the existing ID without inserting (dedup behaviour).
    """
    init_db()
    if check_duplicate:
        dup_id = find_duplicate(entry)
        if dup_id:
            return dup_id
    entry_id = str(entry.get("id") or memory_id(entry))
    search_text = _search_text(entry)
    vector = _token_vector(search_text)
    metadata = _normalize_metadata(entry)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO memories (
                id, type, text, event, command, tag, source, visibility,
                importance, created_at, search_text, token_vector
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                type=excluded.type,
                text=excluded.text,
                event=excluded.event,
                command=excluded.command,
                tag=excluded.tag,
                source=excluded.source,
                visibility=excluded.visibility,
                importance=excluded.importance,
                created_at=excluded.created_at,
                search_text=excluded.search_text,
                token_vector=excluded.token_vector
            """,
            (
                entry_id,
                str(entry.get("type", "note") or "note"),
                str(entry.get("text", "") or ""),
                str(entry.get("event", "") or ""),
                str(entry.get("command", "") or ""),
                str(entry.get("tag", "") or ""),
                metadata["source"],
                metadata["visibility"],
                metadata["importance"],
                str(entry.get("created_at", "")),
                search_text,
                json.dumps(vector, sort_keys=True),
            ),
        )
    refresh_connections(entry_id)
    return entry_id


def sync_from_state(entries: list[dict[str, Any]]) -> int:
    init_db()
    count = 0
    for entry in entries:
        if _primary_text(entry):
            upsert_memory(entry)
            count += 1
    return count


def _row_to_memory(row: sqlite3.Row, score: float | None = None) -> dict[str, Any]:
    item = {
        "id": row["id"],
        "type": row["type"],
        "text": row["text"],
        "event": row["event"],
        "command": row["command"],
        "tag": row["tag"],
        "source": row["source"],
        "visibility": row["visibility"],
        "importance": row["importance"],
        "created_at": row["created_at"],
    }
    if score is not None:
        item["score"] = round(score, 4)
    return item


def list_memories(limit: int = 50, *, visibility: str | None = None) -> list[dict[str, Any]]:
    init_db()
    limit = max(1, min(200, int(limit)))
    sql = "SELECT * FROM memories"
    params: list[Any] = []
    if visibility:
        sql += " WHERE visibility = ?"
        params.append(visibility)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        return [_row_to_memory(row) for row in conn.execute(sql, params)]


def search_memories(query: str, limit: int = 10) -> list[dict[str, Any]]:
    init_db()
    query = query.strip()
    if not query:
        return []
    query_vector = _token_vector(query)
    query_lower = query.lower()
    scored: list[tuple[float, sqlite3.Row]] = []
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM memories").fetchall()
    from datetime import datetime, timezone as _tz
    _now_ts = datetime.now(_tz.utc).timestamp()
    for row in rows:
        vector = json.loads(row["token_vector"] or "{}")
        score = _cosine(query_vector, vector)
        # exact phrase match
        row_text_lower = row["search_text"].lower()
        if query_lower in row_text_lower:
            score += 0.45
        # partial word match bonus
        for token in tokenize(query_lower):
            if token in row_text_lower:
                score += 0.08
        # tag match
        if row["tag"] and row["tag"].lower() in query_lower:
            score += 0.25
        # importance boost
        score += 0.04 * int(row["importance"])
        # recency boost (decay over ~30 days)
        try:
            created = datetime.fromisoformat(str(row["created_at"]).rstrip("Z").replace("Z", "+00:00"))
            age_days = (_now_ts - created.timestamp()) / 86400
            score += max(0.0, 0.1 * (1.0 - age_days / 30.0))
        except Exception:
            pass
        # public visibility boost
        if row["visibility"] == "public":
            score += 0.05
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda item: (item[0], item[1]["created_at"]), reverse=True)
    return [_row_to_memory(row, score) for score, row in scored[: max(1, min(25, limit))]]


def refresh_connections(memory_id_value: str, limit: int = 5) -> None:
    """Recompute auto-similarity connections for a memory (bidirectional)."""
    init_db()
    now_iso = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        source = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id_value,)).fetchone()
        if source is None:
            return
        source_vector = json.loads(source["token_vector"] or "{}")
        scored: list[tuple[float, str]] = []
        for row in conn.execute("SELECT * FROM memories WHERE id != ?", (memory_id_value,)):
            score = _cosine(source_vector, json.loads(row["token_vector"] or "{}"))
            if source["tag"] and source["tag"] == row["tag"]:
                score += 0.15
            if score > 0:
                scored.append((score, row["id"]))
        scored.sort(reverse=True)
        conn.execute(
            "DELETE FROM memory_connections WHERE source_id = ? AND relation = 'related'",
            (memory_id_value,),
        )
        for score, target_id in scored[:limit]:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_connections (source_id, target_id, relation, score, updated_at)
                VALUES (?, ?, 'related', ?, ?)
                """,
                (memory_id_value, target_id, score, now_iso),
            )
            # Mirror connection so graph traversal works in both directions
            conn.execute(
                """
                INSERT OR IGNORE INTO memory_connections (source_id, target_id, relation, score, updated_at)
                VALUES (?, ?, 'related', ?, ?)
                """,
                (target_id, memory_id_value, score, now_iso),
            )


def add_typed_connection(
    source_id: str,
    target_id: str,
    relation: str,
    score: float = 1.0,
) -> bool:
    """Manually add a typed relationship between two memories."""
    init_db()
    relation = relation.strip().lower() or "related"
    score = max(0.0, min(1.0, float(score)))
    now_iso = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        exists = conn.execute(
            "SELECT 1 FROM memories WHERE id = ? OR id = ?", (source_id, target_id)
        ).fetchall()
        if len(exists) < 2:
            return False
        conn.execute(
            """
            INSERT OR REPLACE INTO memory_connections (source_id, target_id, relation, score, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (source_id, target_id, relation, score, now_iso),
        )
    return True


def related_memories(memory_id_value: str, limit: int = 5) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT m.*, c.score, c.relation
            FROM memory_connections c
            JOIN memories m ON m.id = c.target_id
            WHERE c.source_id = ?
            ORDER BY c.score DESC
            LIMIT ?
            """,
            (memory_id_value, max(1, min(25, limit))),
        ).fetchall()
    result = []
    for row in rows:
        item = _row_to_memory(row, float(row["score"]))
        item["relation"] = row["relation"]
        result.append(item)
    return result


def knowledge_graph_query(
    root_id: str,
    depth: int = 2,
    limit: int = 20,
    relation_filter: str | None = None,
) -> dict[str, Any]:
    """BFS traversal of the knowledge graph from root_id.

    Returns a dict with:
      nodes: list of memory dicts (id, text, type, ...)
      edges: list of {source, target, relation, score}
      root:  the root memory id
    """
    init_db()
    depth = max(1, min(4, depth))
    limit = max(1, min(100, limit))

    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])

    with _connect() as conn:
        while queue and len(nodes) < limit:
            current_id, current_depth = queue.popleft()
            if current_id in visited:
                continue
            visited.add(current_id)

            row = conn.execute("SELECT * FROM memories WHERE id = ?", (current_id,)).fetchone()
            if row is None:
                continue
            nodes[current_id] = _row_to_memory(row)

            if current_depth >= depth:
                continue

            sql = "SELECT * FROM memory_connections WHERE source_id = ?"
            params: list[Any] = [current_id]
            if relation_filter:
                sql += " AND relation = ?"
                params.append(relation_filter)
            sql += " ORDER BY score DESC LIMIT 10"

            for conn_row in conn.execute(sql, params):
                target_id = conn_row["target_id"]
                edges.append({
                    "source": current_id,
                    "target": target_id,
                    "relation": conn_row["relation"],
                    "score": round(float(conn_row["score"]), 4),
                })
                if target_id not in visited:
                    queue.append((target_id, current_depth + 1))

    return {
        "root": root_id,
        "nodes": list(nodes.values()),
        "edges": edges,
        "depth": depth,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def apply_retention_policy(dry_run: bool = False) -> dict[str, Any]:
    """Archive and delete memories that exceed their importance-based TTL.

    Importance 1 → 30 days, 2 → 60 days, 3 → 180 days, 4-5 → never.
    Returns stats: {checked, expired, archived}.
    """
    init_db()
    now = datetime.now(timezone.utc)
    expired_ids: list[str] = []
    archive_entries: list[dict] = []

    with _connect() as conn:
        rows = conn.execute("SELECT * FROM memories").fetchall()
    for row in rows:
        max_days = _RETENTION_DAYS.get(int(row["importance"]), 180)
        if max_days == 0:
            continue
        try:
            created = datetime.fromisoformat(
                str(row["created_at"]).rstrip("Z").replace("Z", "+00:00")
            )
        except Exception:
            continue
        age_days = (now - created).days
        if age_days > max_days:
            expired_ids.append(row["id"])
            archive_entries.append(_row_to_memory(row))

    if not dry_run and expired_ids:
        archive_dir = ROOT_DIR / "logs" / "memory_archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        ts = now.strftime("%Y%m%dT%H%M%S")
        archive_path = archive_dir / f"retention_{ts}.jsonl"
        with archive_path.open("w", encoding="utf-8") as f:
            for entry in archive_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        with _connect() as conn:
            for mid in expired_ids:
                conn.execute(
                    "DELETE FROM memory_connections WHERE source_id = ? OR target_id = ?",
                    (mid, mid),
                )
                conn.execute("DELETE FROM memories WHERE id = ?", (mid,))

    return {
        "checked": len(archive_entries.__class__(archive_entries)),  # noqa: use len
        "total_checked": len(list(rows)),
        "expired": len(expired_ids),
        "archived": len(expired_ids) if not dry_run else 0,
        "dry_run": dry_run,
    }


def export_memories(
    limit: int = 1000,
    visibility: str | None = None,
) -> list[dict[str, Any]]:
    """Export all memories as a list of dicts (for backup / migration)."""
    return list_memories(limit=limit, visibility=visibility)


def import_memories(entries: list[dict[str, Any]], *, check_duplicate: bool = True) -> dict[str, int]:
    """Bulk-import memories. Returns {imported, skipped}."""
    imported = 0
    skipped = 0
    for entry in entries:
        if not _primary_text(entry):
            skipped += 1
            continue
        result_id = upsert_memory(entry, check_duplicate=check_duplicate)
        orig_id = str(entry.get("id") or memory_id(entry))
        if check_duplicate and result_id != orig_id:
            skipped += 1
        else:
            imported += 1
    return {"imported": imported, "skipped": skipped}


def get_graph_stats() -> dict[str, Any]:
    """Return basic knowledge graph statistics."""
    init_db()
    with _connect() as conn:
        total_memories = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        total_connections = conn.execute("SELECT COUNT(*) FROM memory_connections").fetchone()[0]
        relation_counts = conn.execute(
            "SELECT relation, COUNT(*) as cnt FROM memory_connections GROUP BY relation ORDER BY cnt DESC"
        ).fetchall()
        top_connected = conn.execute(
            """
            SELECT source_id, COUNT(*) as cnt
            FROM memory_connections
            GROUP BY source_id
            ORDER BY cnt DESC
            LIMIT 5
            """
        ).fetchall()
    return {
        "total_memories": total_memories,
        "total_connections": total_connections,
        "relation_types": {row["relation"]: row["cnt"] for row in relation_counts},
        "top_connected": [{"id": row["source_id"], "connections": row["cnt"]} for row in top_connected],
    }


def set_visibility(memory_id_value: str, visibility: str) -> bool:
    visibility = visibility.strip().lower()
    if visibility not in {"private", "public"}:
        return False
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE memories SET visibility = ? WHERE id = ?",
            (visibility, memory_id_value),
        )
        return cur.rowcount > 0


def delete_memory(memory_id_value: str) -> bool:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM memory_connections WHERE source_id = ? OR target_id = ?", (memory_id_value, memory_id_value))
        cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id_value,))
        return cur.rowcount > 0
