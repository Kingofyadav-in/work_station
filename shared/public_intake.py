from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from file_lock import file_lock


ROOT_DIR = Path(__file__).resolve().parent.parent
INTAKE_LOG = ROOT_DIR / "logs" / "public_intake.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_hash(client_ip: str) -> str:
    client_ip = str(client_ip or "").strip()
    if not client_ip:
        return "unknown"
    return hashlib.sha256(client_ip.encode("utf-8")).hexdigest()[:16]


def _clean_text(value: Any, *, max_chars: int = 4000) -> str:
    return str(value or "").strip()[:max_chars]


def _append_record(record: dict[str, Any]) -> dict[str, Any]:
    with file_lock(INTAKE_LOG.with_suffix(INTAKE_LOG.suffix + ".lock")):
        INTAKE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with INTAKE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def submit_public_enquiry(
    *,
    name: str,
    email: str,
    subject: str,
    message: str,
    client_ip: str = "",
    page: str = "",
    source: str = "widget",
) -> dict[str, Any]:
    record = {
        "ts": _utc_now(),
        "request_id": uuid.uuid4().hex[:12],
        "kind": "enquiry",
        "status": "new",
        "source": source,
        "client": _client_hash(client_ip),
        "page": _clean_text(page, max_chars=500),
        "name": _clean_text(name, max_chars=120),
        "email": _clean_text(email, max_chars=160),
        "subject": _clean_text(subject, max_chars=160),
        "message": _clean_text(message, max_chars=4000),
    }
    return _append_record(record)


def submit_public_signup(
    *,
    name: str,
    email: str,
    handle: str = "",
    reason: str = "",
    message: str = "",
    client_ip: str = "",
    page: str = "",
    source: str = "widget",
) -> dict[str, Any]:
    record = {
        "ts": _utc_now(),
        "request_id": uuid.uuid4().hex[:12],
        "kind": "signup",
        "status": "new",
        "source": source,
        "client": _client_hash(client_ip),
        "page": _clean_text(page, max_chars=500),
        "name": _clean_text(name, max_chars=120),
        "email": _clean_text(email, max_chars=160),
        "handle": _clean_text(handle, max_chars=120),
        "reason": _clean_text(reason, max_chars=160),
        "message": _clean_text(message, max_chars=4000),
    }
    return _append_record(record)


def read_public_intake(limit: int = 100, *, kind: str | None = None) -> list[dict[str, Any]]:
    try:
        lines = INTAKE_LOG.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
    except Exception:
        return []
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            item = json.loads(line)
        except Exception:
            continue
        if kind and item.get("kind") != kind:
            continue
        items.append(item)
    return list(reversed(items))


def get_public_intake_summary(limit: int = 100) -> dict[str, Any]:
    items = read_public_intake(limit=limit)
    enquiries = [item for item in items if item.get("kind") == "enquiry"]
    signups = [item for item in items if item.get("kind") == "signup"]
    return {
        "count": len(items),
        "enquiry_count": len(enquiries),
        "signup_count": len(signups),
        "latest": items[0] if items else {},
        "items": items,
    }
