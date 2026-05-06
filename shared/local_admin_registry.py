from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from file_lock import file_lock


ROOT_DIR = Path(__file__).resolve().parent.parent
REGISTRY_LOG = ROOT_DIR / "logs" / "local_admin_users.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any, *, max_chars: int = 4000) -> str:
    return str(value or "").strip()[:max_chars]


def _append_record(record: dict[str, Any]) -> dict[str, Any]:
    with file_lock(REGISTRY_LOG.with_suffix(REGISTRY_LOG.suffix + ".lock")):
        REGISTRY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with REGISTRY_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def _session_key(username: str, device_id: str = "", client_ip: str = "") -> str:
    username = _clean_text(username, max_chars=120).lower()
    device_id = _clean_text(device_id, max_chars=120)
    client_ip = _clean_text(client_ip, max_chars=120)
    anchor = device_id or client_ip or "unknown"
    return f"{username}::{anchor}"


def record_local_admin_user(
    *,
    username: str,
    password_hash: str,
    password_salt: str = "",
    hash_version: str = "legacy",
    action: str = "signup",
    source: str = "web",
    page: str = "",
    client_ip: str = "",
    device_id: str = "",
    user_agent: str = "",
) -> dict[str, Any]:
    password_hash = _clean_text(password_hash, max_chars=4000)
    record = {
        "ts": _utc_now(),
        "request_id": uuid.uuid4().hex[:12],
        "kind": "local_admin_user",
        "action": _clean_text(action, max_chars=24) or "signup",
        "source": _clean_text(source, max_chars=64) or "web",
        "username": _clean_text(username, max_chars=120).lower(),
        "session_key": _session_key(username, device_id=device_id, client_ip=client_ip),
        "hash_version": _clean_text(hash_version, max_chars=64) or "legacy",
        "password_hash": password_hash,
        "password_hash_preview": password_hash[:16] + ("…" if len(password_hash) > 16 else ""),
        "password_hash_length": len(password_hash),
        "password_salt": _clean_text(password_salt, max_chars=4000),
        "has_salt": bool(str(password_salt or "").strip()),
        "page": _clean_text(page, max_chars=500),
        "client": _clean_text(client_ip, max_chars=120),
        "device_id": _clean_text(device_id, max_chars=120),
        "user_agent": _clean_text(user_agent, max_chars=500),
        "status": "active",
    }
    return _append_record(record)


def read_local_admin_users(limit: int = 500) -> list[dict[str, Any]]:
    try:
        lines = REGISTRY_LOG.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if item.get("kind") != "local_admin_user":
            continue
        items.append(item)
    return items


def get_local_admin_users(limit: int = 500) -> dict[str, Any]:
    events = read_local_admin_users(limit=limit)
    latest_by_user: dict[str, dict[str, Any]] = {}
    for event in events:
        key = str(event.get("session_key") or "").strip()
        if not key:
            username = str(event.get("username") or "").strip()
            if not username:
                continue
            key = _session_key(username, device_id=str(event.get("device_id") or ""), client_ip=str(event.get("client") or ""))
        if not key:
            continue
        latest_by_user[key] = event

    users = list(latest_by_user.values())
    users.sort(key=lambda item: str(item.get("ts") or ""), reverse=True)

    active_count = sum(1 for item in users if item.get("status") == "active")
    return {
        "count": len(users),
        "active_count": active_count,
        "latest": users[0] if users else {},
        "items": users,
        "events": list(reversed(events)),
    }


def clear_local_admin_users() -> None:
    with file_lock(REGISTRY_LOG.with_suffix(REGISTRY_LOG.suffix + ".lock")):
        try:
            REGISTRY_LOG.unlink()
        except FileNotFoundError:
            pass
