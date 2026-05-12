#!/usr/bin/env python3
"""
Automation skill — Jarvis interface to the Phase 4 automation daemon.

Commands (low risk):
  automation status          — daemon status + rule count
  automation rules           — list all rules with enabled/tier/trigger
  automation logs            — last 20 lines of automation.log
  automation pending         — show rules awaiting manual approval
  automation validate        — validate rules.json and report errors

Commands (medium risk):
  automation start           — start the daemon
  automation stop            — graceful stop (SIGTERM)
  automation enable          — remove STOP file; start daemon if not running
  automation disable         — create STOP file; pause all actions
  automation rule enable <id>  — enable a specific rule in rules.json
  automation rule disable <id> — disable a specific rule in rules.json
  automation approve <id>    — execute a pending high-risk approval
  automation deny <id>       — remove a pending approval without executing

Commands (high risk):
  automation emergency stop  — halt immediately: STOP file + SIGTERM
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PID_FILE     = _ROOT / "logs" / "automation.pid"
_RULES_FILE   = _ROOT / "automation" / "rules.json"
_LOG_FILE     = _ROOT / "logs" / "automation.log"
_STOP_FILE    = _ROOT / "logs" / "automation.STOP"
_AUDIT_FILE   = _ROOT / "logs" / "automation_audit.jsonl"
_FAILURE_FILE = _ROOT / "logs" / "automation_failures.jsonl"

ACTIONS = [
    # ── read-only ──────────────────────────────────────────────────────────
    {"action": "automation_status",
     "aliases": ["automation status", "automation health"],
     "description": "Show automation daemon status, stop state, and active rules.",
     "risk_tier": "low", "handler": "status"},

    {"action": "automation_rules",
     "aliases": ["automation rules", "show rules", "list rules"],
     "description": "List all rules with id, enabled, risk tier, trigger, and description.",
     "risk_tier": "low", "handler": "list_rules"},

    {"action": "automation_logs",
     "aliases": ["automation logs", "automation log"],
     "description": "Show the last 20 lines of automation.log.",
     "risk_tier": "low", "handler": "logs"},

    {"action": "automation_pending",
     "aliases": ["automation pending", "pending approvals", "show pending"],
     "description": "Show rules awaiting manual approval (high-risk).",
     "risk_tier": "low", "handler": "pending"},

    {"action": "automation_validate",
     "aliases": ["automation validate", "validate rules"],
     "description": "Validate rules.json and report schema errors.",
     "risk_tier": "low", "handler": "validate"},

    # ── medium risk ────────────────────────────────────────────────────────
    {"action": "automation_start",
     "aliases": ["start automation", "automation start"],
     "description": "Start the automation daemon.",
     "risk_tier": "medium", "handler": "start"},

    {"action": "automation_stop",
     "aliases": ["stop automation", "automation stop"],
     "description": "Gracefully stop the automation daemon (SIGTERM).",
     "risk_tier": "medium", "handler": "stop"},

    {"action": "automation_enable",
     "aliases": ["automation enable", "enable automation"],
     "description": "Remove STOP file and start daemon if not running.",
     "risk_tier": "medium", "handler": "enable"},

    {"action": "automation_disable",
     "aliases": ["automation disable", "disable automation"],
     "description": "Create STOP file — daemon stays alive but no actions execute.",
     "risk_tier": "medium", "handler": "disable"},

    {"action": "automation_rule_enable",
     "aliases": ["automation rule enable"],
     "description": "Enable a specific rule: automation rule enable <id>",
     "risk_tier": "medium", "handler": "rule_enable"},

    {"action": "automation_rule_disable",
     "aliases": ["automation rule disable"],
     "description": "Disable a specific rule: automation rule disable <id>",
     "risk_tier": "medium", "handler": "rule_disable"},

    {"action": "automation_approve",
     "aliases": ["automation approve"],
     "description": "Approve and execute a pending high-risk rule: automation approve <id>",
     "risk_tier": "medium", "handler": "approve"},

    {"action": "automation_deny",
     "aliases": ["automation deny"],
     "description": "Deny and remove a pending approval: automation deny <id>",
     "risk_tier": "medium", "handler": "deny"},

    # ── high risk ──────────────────────────────────────────────────────────
    {"action": "automation_emergency_stop",
     "aliases": ["automation emergency stop", "emergency stop automation"],
     "description": "Immediately halt all automation: STOP file + SIGTERM to daemon.",
     "risk_tier": "high", "handler": "emergency_stop"},
]


# ── PID helpers ────────────────────────────────────────────────────────────────

def _daemon_pid() -> int | None:
    try:
        return int(_PID_FILE.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def _daemon_alive() -> bool:
    pid = _daemon_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ── Read-only commands ─────────────────────────────────────────────────────────

def status(_payload: str = "") -> str:
    alive     = _daemon_alive()
    pid       = _daemon_pid()
    stopped   = _STOP_FILE.exists()
    dry_run   = os.getenv("AUTOMATION_DRY_RUN", "0") == "1"

    state_str = "running" if alive else "stopped"
    if alive and stopped:
        state_str = "running (PAUSED — STOP file active)"

    rule_count = enabled_count = 0
    if _RULES_FILE.exists():
        try:
            rules = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
            rule_count    = len(rules)
            enabled_count = sum(1 for r in rules if r.get("enabled", True))
        except (json.JSONDecodeError, OSError):
            pass

    lines = [
        f"Daemon:       {state_str}" + (f" (pid {pid})" if pid else ""),
        f"Rules total:  {rule_count}  (enabled: {enabled_count})",
        f"STOP file:    {'yes — automation paused' if stopped else 'no'}",
        f"Dry-run:      {'yes' if dry_run else 'no'}",
        f"Audit log:    {_AUDIT_FILE}",
        f"Pending:      {_pending_count()} awaiting approval",
    ]
    return "\n".join(lines)


def _pending_count() -> int:
    if not (_ROOT / "logs" / "automation_pending.json").exists():
        return 0
    try:
        return len(json.loads(
            (_ROOT / "logs" / "automation_pending.json").read_text(encoding="utf-8")
        ))
    except Exception:  # noqa: BLE001
        return 0


def list_rules(_payload: str = "") -> str:
    if not _RULES_FILE.exists():
        return "rules.json not found. Start the daemon once to create defaults."
    try:
        rules = json.loads(_RULES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"rules.json parse error: {exc}"
    if not rules:
        return "No rules defined."

    lines = [f"{'ID':<35} {'En':<4} {'Tier':<8} {'Trigger':<20} Description"]
    lines.append("-" * 95)
    for r in rules:
        trigger = r.get("trigger", {})
        t_str   = f"{trigger.get('type','?')}/{trigger.get('seconds', trigger.get('hour','?'))}"
        enabled = "yes" if r.get("enabled", True) else "no"
        tier    = r.get("risk_tier", "low")
        lines.append(f"{r.get('id',''):<35} {enabled:<4} {tier:<8} {t_str:<20} {r.get('description','')}")
    return "\n".join(lines)


def logs(_payload: str = "") -> str:
    if not _LOG_FILE.exists():
        return "No automation log yet."
    try:
        all_lines = _LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = all_lines[-20:]
        return "\n".join(tail) if tail else "Log file is empty."
    except OSError as exc:
        return f"Cannot read log: {exc}"


def pending(_payload: str = "") -> str:
    pfile = _ROOT / "logs" / "automation_pending.json"
    if not pfile.exists():
        return "No pending approvals."
    try:
        items = json.loads(pfile.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return "Could not read pending approvals."
    if not items:
        return "No pending approvals."
    lines = [f"{'Rule ID':<35} {'Action':<16} Queued at"]
    lines.append("-" * 70)
    for p in items:
        atype = p.get("action", {}).get("type", "?")
        lines.append(f"{p.get('rule_id',''):<35} {atype:<16} {p.get('ts','?')}")
    lines.append(f"\nUse: automation approve <id>  or  automation deny <id>")
    return "\n".join(lines)


def validate(_payload: str = "") -> str:
    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "automation"))
    from rules import load_all_rules, validate_rules  # noqa: PLC0415

    if not _RULES_FILE.exists():
        return "rules.json not found."
    try:
        rules = load_all_rules()
    except json.JSONDecodeError as exc:
        return f"rules.json is invalid JSON: {exc}"

    errors = validate_rules(rules)
    if not errors:
        return f"rules.json is valid — {len(rules)} rule(s) passed schema check."
    lines = [f"Validation errors ({sum(len(v) for v in errors.values())} total):"]
    for rid, errs in errors.items():
        for e in errs:
            lines.append(f"  {e}")
    return "\n".join(lines)


# ── Medium-risk commands ───────────────────────────────────────────────────────

def start(_payload: str = "") -> str:
    if _daemon_alive():
        return f"Automation daemon already running (pid {_daemon_pid()})."
    daemon_script = _ROOT / "automation" / "app.py"
    try:
        proc = subprocess.Popen(
            ["python3", str(daemon_script)],
            cwd=str(_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return f"Automation daemon started (pid {proc.pid})."
    except OSError as exc:
        return f"Failed to start automation daemon: {exc}"


def stop(_payload: str = "") -> str:
    pid = _daemon_pid()
    if pid is None or not _daemon_alive():
        return "Automation daemon is not running."
    try:
        os.kill(pid, signal.SIGTERM)
        return f"Sent SIGTERM to automation daemon (pid {pid})."
    except ProcessLookupError:
        return "Process already gone."
    except PermissionError:
        return f"Permission denied killing pid {pid}."


def enable(_payload: str = "") -> str:
    msgs = []
    if _STOP_FILE.exists():
        _STOP_FILE.unlink()
        msgs.append("STOP file removed — automation unpaused.")
    else:
        msgs.append("No STOP file was active.")
    if not _daemon_alive():
        msgs.append(start())
    else:
        msgs.append(f"Daemon already running (pid {_daemon_pid()}).")
    return "\n".join(msgs)


def disable(_payload: str = "") -> str:
    _STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STOP_FILE.write_text("disabled by operator", encoding="utf-8")
    state = f"running (pid {_daemon_pid()}) but paused" if _daemon_alive() else "not running"
    return f"STOP file created. Daemon is {state}. All rule executions suspended."


def rule_enable(payload: str = "") -> str:
    rule_id = payload.strip()
    if not rule_id:
        return "Usage: automation rule enable <rule_id>"
    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "automation"))
    from rules import set_rule_enabled  # noqa: PLC0415
    return set_rule_enabled(rule_id, True)


def rule_disable(payload: str = "") -> str:
    rule_id = payload.strip()
    if not rule_id:
        return "Usage: automation rule disable <rule_id>"
    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "automation"))
    from rules import set_rule_enabled  # noqa: PLC0415
    return set_rule_enabled(rule_id, False)


def approve(payload: str = "") -> str:
    rule_id = payload.strip()
    if not rule_id:
        return "Usage: automation approve <rule_id>"
    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "shared"))
    _sys.path.insert(0, str(_ROOT / "automation"))
    from scheduler import approve_pending  # noqa: PLC0415
    return approve_pending(rule_id)


def deny(payload: str = "") -> str:
    rule_id = payload.strip()
    if not rule_id:
        return "Usage: automation deny <rule_id>"
    import sys as _sys
    _sys.path.insert(0, str(_ROOT / "shared"))
    _sys.path.insert(0, str(_ROOT / "automation"))
    from scheduler import deny_pending  # noqa: PLC0415
    return deny_pending(rule_id)


# ── High-risk commands ─────────────────────────────────────────────────────────

def emergency_stop(_payload: str = "") -> str:
    """Create STOP file and send SIGTERM — immediate full halt."""
    _STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STOP_FILE.write_text("EMERGENCY STOP", encoding="utf-8")

    pid = _daemon_pid()
    killed = False
    if pid and _daemon_alive():
        try:
            os.kill(pid, signal.SIGTERM)
            killed = True
        except (ProcessLookupError, PermissionError):
            pass

    lines = [
        "EMERGENCY STOP activated.",
        "STOP file created — all rule executions halted.",
        f"Daemon pid {pid}: {'SIGTERM sent.' if killed else 'not running or already stopped.'}",
        "",
        "To resume: python3 Jarvis/bridge.py 'automation enable'",
    ]
    return "\n".join(lines)
