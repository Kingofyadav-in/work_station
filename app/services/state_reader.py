from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[2]
JARVIS_DIR = ROOT_DIR / "Jarvis"
KING_DIR = ROOT_DIR / "Kingofyadav"

if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

from device_registry import verify_current_device  # noqa: E402
from system_info import get_system_info  # noqa: E402

if str(ROOT_DIR / "app") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "app"))
if str(ROOT_DIR / "shared") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "shared"))

from services.log_reader import get_last_event, read_bus_log  # noqa: E402
from listener_status import pid_file_is_recent, resolve_listener_pid  # noqa: E402
from services.public_profile import enrich_dashboard_state  # noqa: E402
from services.dashboard_db import save_dashboard_state_snapshot  # noqa: E402


STATE_PATH = KING_DIR / "state.json"
PROFILES_PATH = JARVIS_DIR / "profiles.json"
BUS_LOG_PATH = ROOT_DIR / "logs" / "bus.log"
KING_PID_PATH = ROOT_DIR / "logs" / "kingofyadav.pid"


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    default = default or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def get_hi_state() -> dict[str, Any]:
    return _read_json(STATE_PATH, default={})


def get_profiles() -> dict[str, Any]:
    return _read_json(PROFILES_PATH, default={})


def get_listener_status() -> dict[str, Any]:
    pid = resolve_listener_pid(KING_PID_PATH)
    if pid is not None:
        return {"online": True, "pids": [str(pid)]}
    if pid_file_is_recent(KING_PID_PATH):
        return {"online": True, "pids": []}
    return {"online": False, "pids": []}


@st.cache_data(ttl=2.5, show_spinner=False)
def get_dashboard_state() -> dict[str, Any]:
    state = enrich_dashboard_state(get_hi_state())
    profiles = get_profiles()
    system = get_system_info()
    listener = get_listener_status()
    try:
        device = verify_current_device()
    except Exception:
        device = {}

    memory = state.get("memory", [])
    workflow = state.get("workflow", {})
    preferences = state.get("preferences", {})
    profile = state.get("profile", {})
    last_event = get_last_event()
    bus_lines = read_bus_log(lines=5)
    bus_active = bool(bus_lines)
    fetched_at = datetime.now(timezone.utc).isoformat()

    _result = {
        "fetched_at": fetched_at,
        "system": system,
        "listener": listener,
        "profile": profile,
        "preferences": preferences,
        "workflow": workflow,
        "memory": memory,
        "memory_count": len(memory),
        "jarvis_session": profiles.get("session", {}),
        "device": {
            "registered": bool(device.get("registered")),
            "trusted": bool(device.get("trusted")),
            "label": device.get("label", ""),
            "registered_at": device.get("registered_at", ""),
            "fingerprint": device.get("current_fingerprint", ""),
            "trust_match": device.get("trust_match", "none"),
        },
        "health": {
            "jarvis_route_available": True,
            "kingofyadav_listener_healthy": listener["online"],
            "bus_active": bus_active,
            "last_event_time": (last_event or {}).get("ts", "none"),
            "last_event_type": (last_event or {}).get("type", "none"),
            "current_focus": workflow.get("current_focus") or "none",
        },
        "recent_bus": bus_lines,
        "last_event": last_event or {},
    }
    save_dashboard_state_snapshot(_result)
    return _result


def get_automation_snapshot() -> dict:
    """Thin wrapper used by the main dashboard to include automation state."""
    try:
        sys.path.insert(0, str(ROOT_DIR / "app"))
        from services.automation_client import get_automation_status
        return get_automation_status()
    except Exception:
        return {"daemon_alive": False, "stop_active": False, "dry_run": False,
                "rule_count": 0, "enabled_count": 0, "pending_count": 0}
