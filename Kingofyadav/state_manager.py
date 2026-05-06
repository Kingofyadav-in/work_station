#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

from validate_state import DEFAULT_STATE, normalize_state


STATE_PATH = Path(__file__).resolve().parent / "state.json"
ROOT_DIR = Path(__file__).resolve().parent.parent
LOCK_PATH = ROOT_DIR / "logs" / "state.json.lock"

if str(ROOT_DIR / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "shared"))

from file_lock import file_lock  # noqa: E402
from identity import (  # noqa: E402
    generate_id,
    get_hostname,
    get_system_username,
    make_fingerprint,
    now_utc,
)


def _ensure_hi_identity(state: dict[str, Any]) -> None:
    """Guarantee HI profile has stable id, fingerprint, host, username, and created_at.

    ID and host are generated once and never regenerated.
    Fingerprint is always recomputed from id + username + host (host-bound).
    """
    profile = state.setdefault("profile", {})
    if not profile.get("id"):
        profile["id"] = generate_id("hi")
    if not profile.get("created_at"):
        profile["created_at"] = now_utc()
    if not profile.get("host"):
        profile["host"] = get_hostname()
    if not profile.get("username"):
        profile["username"] = get_system_username()
    profile["fingerprint"] = make_fingerprint(
        profile["id"], profile.get("username", ""), profile.get("host", "")
    )


def _load_state_unlocked() -> dict[str, Any]:
    if STATE_PATH.exists():
        with STATE_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        had_id = bool(raw.get("profile", {}).get("id"))
        state = normalize_state(raw)
    else:
        had_id = False
        state = json.loads(json.dumps(DEFAULT_STATE))
    _ensure_hi_identity(state)
    if not had_id:
        _save_state_unlocked(state)
    return state


def load_state() -> dict[str, Any]:
    with file_lock(LOCK_PATH):
        return _load_state_unlocked()


def _save_state_unlocked(data: dict[str, Any]) -> None:
    merged = normalize_state(data)
    tmp_path = STATE_PATH.with_name(f"{STATE_PATH.name}.{uuid.uuid4().hex}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    tmp_path.replace(STATE_PATH)


def save_state(data: dict[str, Any]) -> None:
    with file_lock(LOCK_PATH):
        _save_state_unlocked(data)


def update_state(mutator) -> dict[str, Any]:
    with file_lock(LOCK_PATH):
        state = _load_state_unlocked()
        mutator(state)
        _save_state_unlocked(state)
        return normalize_state(state)
