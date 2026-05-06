#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory_store import delete_memory, related_memories, search_memories, set_visibility, sync_from_state, upsert_memory
from state_manager import load_state, update_state
from validate_state import normalize_memory_entry

_MEMORY_CAP = 200
_ARCHIVE_DIR = Path(__file__).resolve().parent.parent / "logs" / "memory_archive"


def _archive_overflow(state: dict) -> None:
    overflow = state["memory"][:-_MEMORY_CAP]
    state["memory"] = state["memory"][-_MEMORY_CAP:]
    _ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    archive_path = _ARCHIVE_DIR / f"archive_{ts}.jsonl"
    with archive_path.open("w", encoding="utf-8") as f:
        for item in overflow:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def add_memory(entry: object) -> list[dict[str, Any]]:
    item = normalize_memory_entry(entry)
    if item is None:
        return load_state()["memory"]

    def _mutate(state: dict) -> None:
        item["created_at"] = datetime.now(timezone.utc).isoformat()
        state["memory"].append(item)
        if len(state["memory"]) > _MEMORY_CAP:
            _archive_overflow(state)

    state = update_state(_mutate)
    upsert_memory(state["memory"][-1])
    return state["memory"]


def get_memory() -> list[dict[str, Any]]:
    memory = load_state()["memory"]
    sync_from_state(memory)
    return memory


def search_memory(query: str) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    return [
        m for m in get_memory()
        if q in str(m.get("text", "")).lower()
        or q in str(m.get("tag", "")).lower()
        or q in str(m.get("event", "")).lower()
        or q in str(m.get("command", "")).lower()
    ]


def semantic_search_memory(query: str, limit: int = 10) -> list[dict[str, Any]]:
    sync_from_state(load_state()["memory"])
    return search_memories(query, limit=limit)


def get_memory_search_summary(query: str) -> dict:
    results = semantic_search_memory(query)
    if not results:
        body = f"Memory search '{query}': no matches found."
    else:
        lines = []
        for m in results:
            ts = str(m.get("created_at", ""))[:10]
            tag = f" [{m['tag']}]" if m.get("tag") else ""
            score = f" score={m['score']}" if "score" in m else ""
            text = m.get("text") or m.get("event") or m.get("command") or str(m)
            lines.append(f"  [{ts}]{tag}{score} {text}")
        body = f"Semantic memory search '{query}': {len(results)} match(es).\n" + "\n".join(lines)
    return {
        "text": body,
        "args": {"module": "memory", "view": "semantic_search", "query": query, "count": len(results)},
    }


def get_related_memory_summary(memory_id: str) -> dict:
    sync_from_state(load_state()["memory"])
    results = related_memories(memory_id)
    if not results:
        body = f"Related memories for {memory_id}: no related entries found."
    else:
        lines = []
        for m in results:
            text = m.get("text") or m.get("event") or m.get("command") or str(m)
            lines.append(f"  {m.get('id')} score={m.get('score')} {text}")
        body = f"Related memories for {memory_id}: {len(results)} result(s).\n" + "\n".join(lines)
    return {
        "text": body,
        "args": {"module": "memory", "view": "related", "memory_id": memory_id, "count": len(results)},
    }


def set_memory_visibility(memory_id: str, visibility: str) -> dict:
    ok = set_visibility(memory_id, visibility)
    status = "updated" if ok else "not_found_or_invalid"
    return {
        "text": f"Memory visibility {status}: {memory_id} -> {visibility}",
        "args": {"module": "memory", "view": "visibility", "status": status},
        "_error": not ok,
    }


def delete_memory_entry(memory_id: str) -> dict:
    from state_manager import load_state, update_state
    mid = memory_id.strip()
    if not mid:
        return {"text": "Refused: empty memory id.", "_error": True}

    db_ok = delete_memory(mid)

    def _mutate(state: dict) -> None:
        state["memory"] = [
            m for m in state["memory"]
            if str(m.get("id", "")) != mid
        ]

    update_state(_mutate)
    if db_ok:
        return {"text": f"Memory {mid} deleted.", "args": {"module": "memory", "view": "delete", "id": mid}}
    return {"text": f"Memory {mid} not found.", "_error": True, "args": {"module": "memory", "view": "delete", "id": mid}}


def get_memory_summary(raw_payload: object = "") -> dict:
    memory = get_memory()
    recent = memory[-3:]
    detail = f" Request context: {raw_payload}." if raw_payload not in ("", None, {}) else ""
    return {
        "text": (
            f"Memory summary: {len(memory)} stored event(s). "
            f"Recent entries: {recent if recent else 'none'}."
            f"{detail}"
        ),
        "args": {"module": "memory", "view": "summary"},
    }
