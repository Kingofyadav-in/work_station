#!/usr/bin/env python3
"""
Automation state reader for the dashboard — Phase 4.2.

Reads automation state directly from files (same machine, no network hop).
All reads are best-effort; failures return safe empty defaults.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_AUT  = _ROOT / "automation"

_PID_FILE     = _ROOT / "logs" / "automation.pid"
_STOP_FILE    = _ROOT / "logs" / "automation.STOP"
_RULES_FILE   = _AUT  / "rules.json"
_PENDING_FILE = _ROOT / "logs" / "automation_pending.json"
_AUDIT_FILE   = _ROOT / "logs" / "automation_audit.jsonl"
_FAILURE_FILE = _ROOT / "logs" / "automation_failures.jsonl"
_LOG_FILE     = _ROOT / "logs" / "automation.log"


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {}


def _pid_alive(pid_path: Path) -> int | None:
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return pid
    except PermissionError:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _tail_jsonl(path: Path, n: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return [json.loads(l) for l in lines[-n:] if l.strip()]
    except Exception:
        return []


# ── Public API ─────────────────────────────────────────────────────────────────

def get_automation_status() -> dict[str, Any]:
    pid = _pid_alive(_PID_FILE)
    stop = _STOP_FILE.exists()
    dry  = os.getenv("AUTOMATION_DRY_RUN", "0") == "1"

    rules: list[dict] = _read_json(_RULES_FILE, default=[])
    rule_count    = len(rules)
    enabled_count = sum(1 for r in rules if r.get("enabled", True))

    pending: list = _read_json(_PENDING_FILE, default=[])

    audit_tail = _tail_jsonl(_AUDIT_FILE, 1)
    last_audit_ts = audit_tail[0].get("ts", "") if audit_tail else ""

    return {
        "daemon_alive":  pid is not None,
        "pid":           pid,
        "stop_active":   stop,
        "dry_run":       dry,
        "rule_count":    rule_count,
        "enabled_count": enabled_count,
        "pending_count": len(pending),
        "last_audit_ts": last_audit_ts,
        "ts":            datetime.now(timezone.utc).isoformat(),
    }


def get_automation_rules() -> list[dict[str, Any]]:
    return _read_json(_RULES_FILE, default=[])


def get_automation_pending() -> list[dict[str, Any]]:
    return _read_json(_PENDING_FILE, default=[])


def get_automation_audit(n: int = 30) -> list[dict[str, Any]]:
    return list(reversed(_tail_jsonl(_AUDIT_FILE, n)))


def get_automation_failures(n: int = 20) -> list[dict[str, Any]]:
    return list(reversed(_tail_jsonl(_FAILURE_FILE, n)))


def get_automation_log_tail(n: int = 30) -> list[str]:
    if not _LOG_FILE.exists():
        return []
    try:
        lines = _LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        return lines[-n:]
    except Exception:
        return []
