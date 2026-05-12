#!/usr/bin/env python3
"""
Background health and process monitor for the automation daemon.

Provides a snapshot of:
  - API health (pass / warn / fail counts from /api/health/detail)
  - Process liveness (PID file checks for each Jarvis service)
  - Recent log lines (for log_pattern conditions)
  - HI state field snapshots (for state_change conditions)

All reads are best-effort — failures return a safe default so the rules engine
can still run.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "shared"))

_API_BASE = "http://127.0.0.1:5050"
_STATE_PATH = _ROOT / "Kingofyadav" / "state.json"
_LOG_LINES_MAX = 200

_PID_FILES: dict[str, Path] = {
    "jarvis-api":        _ROOT / "logs" / "api.pid",
    "jarvis-kingofyadav": _ROOT / "logs" / "kingofyadav.pid",
    "jarvis-dashboard":  _ROOT / "logs" / "dashboard.pid",
}

_LOG_FILES: list[Path] = [
    _ROOT / "logs" / "api.log",
    _ROOT / "logs" / "activity.log",
    _ROOT / "logs" / "automation.log",
]


def _pid_alive(pid_path: Path) -> bool:
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, FileNotFoundError, ValueError):
        return False


def check_processes() -> dict[str, bool]:
    """Return {service_name: is_alive} for each known service."""
    return {name: _pid_alive(path) for name, path in _PID_FILES.items()}


def check_api_health(token: str = "") -> dict[str, Any]:
    """
    Call /api/health/detail and return the summary dict.
    Returns {"pass": 0, "warn": 0, "fail": 0, "error": str} on failure.
    """
    try:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        req = urllib.request.Request(
            f"{_API_BASE}/api/health/detail",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
        return data.get("summary", {"pass": 0, "warn": 0, "fail": 0})
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {"pass": 0, "warn": 0, "fail": 0, "error": str(exc)}


def read_recent_log_lines(n: int = _LOG_LINES_MAX) -> list[str]:
    """Return the last n combined lines across all monitored log files."""
    lines: list[str] = []
    for log_path in _LOG_FILES:
        if not log_path.exists():
            continue
        try:
            with log_path.open(encoding="utf-8", errors="replace") as fh:
                lines.extend(fh.readlines()[-n:])
        except OSError:
            continue
    return [l.rstrip() for l in lines[-n:]]


def read_state_snapshot() -> dict[str, Any]:
    """Return a flat snapshot of select HI state fields."""
    try:
        with _STATE_PATH.open(encoding="utf-8") as fh:
            state = json.load(fh)
        return {
            "current_focus": state.get("current_focus", ""),
            "workflow_status": state.get("workflow", {}).get("status", ""),
            "memory_count": len(state.get("memories", [])),
        }
    except (OSError, json.JSONDecodeError):
        return {}


def build_context(token: str = "") -> dict[str, Any]:
    """
    Build the context dict passed to rules.evaluate_rule().

    Keys:
      health_fail_count   int
      health_warn_count   int
      health_pass_count   int
      health_error        str | None
      down_processes      list[str]
      recent_log_lines    list[str]
      state               dict
    """
    health = check_api_health(token)
    processes = check_processes()
    down = [name for name, alive in processes.items() if not alive]

    return {
        "health_fail_count": health.get("fail", 0),
        "health_warn_count": health.get("warn", 0),
        "health_pass_count": health.get("pass", 0),
        "health_error":      health.get("error"),
        "down_processes":    down,
        "recent_log_lines":  read_recent_log_lines(),
        "state":             read_state_snapshot(),
    }
