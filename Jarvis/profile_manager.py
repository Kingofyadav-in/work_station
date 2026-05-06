#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any


PROFILE_PATH = Path(__file__).resolve().parent / "profiles.json"
_HI_STATE_PATH = Path(__file__).resolve().parent.parent / "Kingofyadav" / "state.json"
_ROOT_DIR = Path(__file__).resolve().parent.parent
_LOCK_PATH = _ROOT_DIR / "logs" / "profiles.json.lock"

if str(_ROOT_DIR / "shared") not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR / "shared"))

from file_lock import file_lock  # noqa: E402
from identity import generate_id, make_fingerprint, now_utc  # noqa: E402


def _overlay_hi_from_state(profiles: dict[str, Any]) -> dict[str, Any]:
    """Overlay HI identity fields from state.json so profiles.json never drifts."""
    try:
        state = json.loads(_HI_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return profiles
    hi = profiles.setdefault("HI", {})
    sp = state.get("profile", {})
    prefs = state.get("preferences", {})
    for field in ("name", "domain", "language"):
        if sp.get(field):
            hi[field] = sp[field]
    if prefs.get("response_mode"):
        hi["preferred_response_mode"] = prefs["response_mode"]
    return profiles

def _ensure_ai_identity(ai: dict[str, Any]) -> None:
    """Guarantee AI profile has stable id, fingerprint, mode, and created_at.

    ID is generated once and never regenerated.
    Fingerprint is always recomputed from id + name (reflects renames).
    """
    if not ai.get("id"):
        ai["id"] = generate_id("ai")
    if not ai.get("created_at"):
        ai["created_at"] = now_utc()
    if not ai.get("connectivity"):
        ai["connectivity"] = "online"
    ai["fingerprint"] = make_fingerprint(ai["id"], ai.get("name", "Jarvis"))


DEFAULT_PROFILES: dict[str, Any] = {
    "AI": {
        "name": "Jarvis",
        "connectivity": "online",
        "tts_voice": "en-US-AriaNeural",
        "tts_offline_voice": "en-gb-x-rp",
        "tts_speed": 1.0,
        "type": "Artificial Intelligence System",
        "role": "assistant",
        "capabilities": [
            "voice recognition",
            "task execution",
            "automation",
            "analysis",
            "context-aware responses",
        ],
        "mode": "assistant",
        "intro": (
            "Hello, I am Jarvis, your Artificial Intelligence assistant. "
            "I am designed to understand commands, process information, and execute tasks efficiently. "
            "My purpose is to assist you in managing systems, automating workflows, and providing intelligent responses based on data and context."
        ),
    },
    "HI": {
        "name": "Amit Kumar Yadav",
        "full_name": "Amit Kumar Yadav",
        "type": "Human Intelligence",
        "role": "owner",
        "permissions": ["full_access"],
        "language": "en",
        "domain": "kingofyadav.in",
        "preferred_intro_mode": "normal",
        "preferred_response_mode": "adaptive",
        "preferred_command_style": "natural",
        "trusted_device_name": "Jarvis",
        "preferred_mic_device": 5,
        "wake_phrase": "jarvis",
        "intro": (
            "I am the primary user and controller of this system. "
            "My role is to provide commands, make decisions, and define objectives. "
            "I rely on the AI to assist with execution, automation, and analysis. "
            "The AI should prioritize my instructions, maintain context, and operate within defined boundaries."
        ),
    },
    "relationship": {
        "human_role": "decision making",
        "ai_role": "execution and assistance",
        "bridge_role": "intent processing",
        "voice_input_role": "command capture",
    },
    "session": {
        "last_intent": "",
        "last_action": "",
        "last_command": "",
        "last_successful_action": "",
        "last_risk_tier": "",
        "pending_action": "",
        "pending_payload": "",
        "pending_command": "",
        "pending_since": "",
        "device_name": "",
    },
}


def _deepcopy_default() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_PROFILES))


def _merge_defaults(data: dict[str, Any]) -> dict[str, Any]:
    merged = _deepcopy_default()
    for section, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(section), dict):
            merged[section].update(value)
        else:
            merged[section] = value
    return merged


def _load_profiles_unlocked() -> dict[str, Any]:
    if PROFILE_PATH.exists():
        with PROFILE_PATH.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        had_id = bool(raw.get("AI", {}).get("id"))
        profiles = _overlay_hi_from_state(_merge_defaults(raw))
    else:
        had_id = False
        profiles = _overlay_hi_from_state(_deepcopy_default())
    _ensure_ai_identity(profiles.setdefault("AI", {}))
    if not had_id:
        _save_profiles_unlocked(profiles)
    return profiles


def load_profiles() -> dict[str, Any]:
    with file_lock(_LOCK_PATH):
        return _load_profiles_unlocked()


def _save_profiles_unlocked(data: dict[str, Any]) -> None:
    merged = _merge_defaults(data)
    tmp_path = PROFILE_PATH.with_name(f"{PROFILE_PATH.name}.{uuid.uuid4().hex}.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    tmp_path.replace(PROFILE_PATH)


def save_profiles(data: dict[str, Any]) -> None:
    with file_lock(_LOCK_PATH):
        _save_profiles_unlocked(data)


def update_hi_field(field: str, value: Any) -> None:
    with file_lock(_LOCK_PATH):
        data = _load_profiles_unlocked()
        data.setdefault("HI", {})
        data["HI"][field] = value
        _save_profiles_unlocked(data)


def update_ai_field(field: str, value: Any) -> None:
    with file_lock(_LOCK_PATH):
        data = _load_profiles_unlocked()
        data.setdefault("AI", {})
        data["AI"][field] = value
        _save_profiles_unlocked(data)


def update_session_field(field: str, value: Any) -> None:
    with file_lock(_LOCK_PATH):
        data = _load_profiles_unlocked()
        data.setdefault("session", {})
        data["session"][field] = value
        _save_profiles_unlocked(data)


def bulk_update_session(fields: dict[str, Any]) -> None:
    with file_lock(_LOCK_PATH):
        data = _load_profiles_unlocked()
        data.setdefault("session", {})
        data["session"].update(fields)
        _save_profiles_unlocked(data)


def clear_pending_confirmation() -> None:
    with file_lock(_LOCK_PATH):
        data = _load_profiles_unlocked()
        data.setdefault("session", {})
        data["session"]["pending_action"] = ""
        data["session"]["pending_payload"] = ""
        data["session"]["pending_command"] = ""
        data["session"]["pending_since"] = ""
        _save_profiles_unlocked(data)


def reset_session() -> None:
    with file_lock(_LOCK_PATH):
        data = _load_profiles_unlocked()
        data["session"] = _deepcopy_default()["session"]
        _save_profiles_unlocked(data)


def get_ai_profile() -> dict[str, Any]:
    return load_profiles().get("AI", {})


def get_hi_profile() -> dict[str, Any]:
    return load_profiles().get("HI", {})


def get_relationship() -> dict[str, Any]:
    return load_profiles().get("relationship", {})


def get_session() -> dict[str, Any]:
    return load_profiles().get("session", {})
