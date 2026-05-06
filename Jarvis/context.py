#!/usr/bin/env python3
"""
Shared Jarvis runtime context.

This module centralizes profile data, activity logging, and the current
system snapshot so every interface uses the same state model.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from profile_manager import load_profiles
from system_info import get_system_info

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
PROFILE_PATH = BASE_DIR / "user_profile.json"
LOG_DIR = ROOT_DIR / "logs"
LOG_FILE = LOG_DIR / "activity.log"


def load_profile() -> dict[str, str]:
    if not PROFILE_PATH.exists():
        return {"username": "unknown", "full_name": "unknown", "language": "unknown"}

    with PROFILE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)

def ensure_log_dir() -> None:
    LOG_DIR.mkdir(exist_ok=True)


def log_activity(source: str, detail: str) -> None:
    ensure_log_dir()
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(f"{timestamp} | {source} | {detail}\n")


def read_recent_logs(limit: int = 10) -> str:
    if not LOG_FILE.exists():
        return "No logs yet."

    with LOG_FILE.open("r", encoding="utf-8") as file:
        lines = file.readlines()[-limit:]
    return "".join(lines).rstrip() or "No logs yet."


def get_runtime_context(log_limit: int = 10) -> dict[str, Any]:
    return {
        "profile": load_profile(),
        "profiles": load_profiles(),
        "system": get_system_info(),
        "recent_logs": read_recent_logs(log_limit),
    }
