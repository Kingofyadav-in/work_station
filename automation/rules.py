#!/usr/bin/env python3
"""
Rules engine for the automation daemon.

A rule schema:
  id              unique identifier (required)
  description     human-readable label (required)
  enabled         bool, default true
  risk_tier       "low" | "medium" | "high" — high requires manual approval
  max_retries     int, default 0 — retry failed actions up to N times
  cooldown_seconds  int, default 0 — min seconds between successful fires
  trigger         {type, ...} (required)
  conditions      list of condition objects (optional, default [])
  action          {type, ...} (required)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "shared"))

_RULES_FILE = Path(__file__).resolve().parent / "rules.json"

VALID_TRIGGER_TYPES = {"interval", "cron"}
VALID_ACTION_TYPES  = {"notify", "restart_service", "command", "webhook"}
VALID_RISK_TIERS    = {"low", "medium", "high"}
VALID_CONDITION_TYPES = {
    "health_fail_count", "health_warn_count", "process_down",
    "log_pattern", "state_field_equals", "always",
}


# ── Validation ─────────────────────────────────────────────────────────────────

def validate_rule(rule: dict[str, Any]) -> list[str]:
    """Return a list of error strings. Empty list means the rule is valid."""
    errors: list[str] = []
    rid = rule.get("id", "<no id>")

    if not rule.get("id"):
        errors.append("missing required field: id")
    if not rule.get("description"):
        errors.append(f"[{rid}] missing required field: description")

    trigger = rule.get("trigger")
    if not trigger or not isinstance(trigger, dict):
        errors.append(f"[{rid}] missing or invalid 'trigger'")
    else:
        ttype = trigger.get("type")
        if ttype not in VALID_TRIGGER_TYPES:
            errors.append(f"[{rid}] unknown trigger type '{ttype}'; valid: {sorted(VALID_TRIGGER_TYPES)}")
        if ttype == "interval" and not isinstance(trigger.get("seconds"), (int, float)):
            errors.append(f"[{rid}] interval trigger requires numeric 'seconds'")
        if ttype == "cron":
            if not isinstance(trigger.get("hour"), int):
                errors.append(f"[{rid}] cron trigger requires integer 'hour'")
            if not isinstance(trigger.get("minute"), int):
                errors.append(f"[{rid}] cron trigger requires integer 'minute'")

    action = rule.get("action")
    if not action or not isinstance(action, dict):
        errors.append(f"[{rid}] missing or invalid 'action'")
    else:
        atype = action.get("type")
        if atype not in VALID_ACTION_TYPES:
            errors.append(f"[{rid}] unknown action type '{atype}'; valid: {sorted(VALID_ACTION_TYPES)}")
        if atype == "restart_service":
            if not action.get("service"):
                errors.append(f"[{rid}] restart_service action requires 'service'")
            if not action.get("script"):
                errors.append(f"[{rid}] restart_service action requires 'script'")
        if atype in ("webhook", "notify") and action.get("channel") == "webhook" and not action.get("webhook_url"):
            errors.append(f"[{rid}] webhook action requires 'webhook_url'")

    risk = rule.get("risk_tier", "low")
    if risk not in VALID_RISK_TIERS:
        errors.append(f"[{rid}] unknown risk_tier '{risk}'; valid: {sorted(VALID_RISK_TIERS)}")

    for cond in rule.get("conditions", []):
        ctype = cond.get("type")
        if ctype not in VALID_CONDITION_TYPES:
            errors.append(f"[{rid}] unknown condition type '{ctype}'")

    max_retries = rule.get("max_retries", 0)
    if not isinstance(max_retries, int) or max_retries < 0:
        errors.append(f"[{rid}] max_retries must be a non-negative integer")

    cooldown = rule.get("cooldown_seconds", 0)
    if not isinstance(cooldown, (int, float)) or cooldown < 0:
        errors.append(f"[{rid}] cooldown_seconds must be non-negative")

    return errors


def validate_rules(rules: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Return {rule_id: [errors]} for all rules that have errors."""
    result: dict[str, list[str]] = {}
    ids_seen: set[str] = set()
    for rule in rules:
        rid = rule.get("id", "<no id>")
        errs = validate_rule(rule)
        if rid in ids_seen:
            errs.append(f"[{rid}] duplicate rule id")
        ids_seen.add(rid)
        if errs:
            result[rid] = errs
    return result


# ── Loading ────────────────────────────────────────────────────────────────────

def load_all_rules() -> list[dict[str, Any]]:
    """Return every rule regardless of enabled state."""
    if not _RULES_FILE.exists():
        return []
    with _RULES_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_rules() -> list[dict[str, Any]]:
    """Return only enabled rules (schema-valid subset)."""
    return [r for r in load_all_rules() if r.get("enabled", True)]


def reload_rules() -> list[dict[str, Any]]:
    return load_rules()


# ── Runtime enable/disable ─────────────────────────────────────────────────────

def set_rule_enabled(rule_id: str, enabled: bool) -> str:
    """Toggle a rule's enabled flag in rules.json. Returns status message."""
    rules = load_all_rules()
    for rule in rules:
        if rule.get("id") == rule_id:
            rule["enabled"] = enabled
            with _RULES_FILE.open("w", encoding="utf-8") as fh:
                json.dump(rules, fh, indent=2)
            state = "enabled" if enabled else "disabled"
            return f"Rule '{rule_id}' {state}. Restart the daemon to apply."
    return f"Rule '{rule_id}' not found in rules.json."


# ── Condition evaluation ───────────────────────────────────────────────────────

def _check_condition(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    ctype = condition.get("type", "")

    if ctype == "health_fail_count":
        return context.get("health_fail_count", 0) >= condition.get("min", 1)

    if ctype == "health_warn_count":
        return context.get("health_warn_count", 0) >= condition.get("min", 1)

    if ctype == "process_down":
        name = condition.get("name", "")
        return name in context.get("down_processes", [])

    if ctype == "log_pattern":
        pattern = condition.get("pattern", "")
        recent_logs = context.get("recent_log_lines", [])
        return any(re.search(pattern, line) for line in recent_logs)

    if ctype == "state_field_equals":
        field = condition.get("field", "")
        expected = condition.get("value")
        return context.get("state", {}).get(field) == expected

    if ctype == "always":
        return True

    return False


def evaluate_rule(rule: dict[str, Any], context: dict[str, Any]) -> bool:
    """Return True if all conditions pass (or there are no conditions)."""
    conditions = rule.get("conditions", [])
    return all(_check_condition(c, context) for c in conditions)


# ── Default rules file creation ────────────────────────────────────────────────

DEFAULT_RULES: list[dict[str, Any]] = [
    {
        "id": "health_check_every_5m",
        "description": "Run a health check every 5 minutes and notify on failures.",
        "enabled": True,
        "risk_tier": "low",
        "max_retries": 0,
        "cooldown_seconds": 0,
        "trigger": {"type": "interval", "seconds": 300},
        "conditions": [{"type": "health_fail_count", "min": 1}],
        "action": {"type": "notify", "channel": "log", "message": "Health check: {health_fail_count} failure(s) detected."},
    },
    {
        "id": "watchdog_restart_api",
        "description": "Restart jarvis-api if its PID file is stale or process is gone.",
        "enabled": True,
        "risk_tier": "medium",
        "max_retries": 2,
        "cooldown_seconds": 120,
        "trigger": {"type": "interval", "seconds": 60},
        "conditions": [{"type": "process_down", "name": "jarvis-api"}],
        "action": {"type": "restart_service", "service": "jarvis-api", "script": "scripts/start_api.sh"},
    },
    {
        "id": "watchdog_restart_kingofyadav",
        "description": "Restart kingofyadav listener if it goes down.",
        "enabled": True,
        "risk_tier": "medium",
        "max_retries": 2,
        "cooldown_seconds": 120,
        "trigger": {"type": "interval", "seconds": 60},
        "conditions": [{"type": "process_down", "name": "jarvis-kingofyadav"}],
        "action": {"type": "restart_service", "service": "jarvis-kingofyadav", "script": "scripts/start_all.sh"},
    },
    {
        "id": "daily_journal_summary",
        "description": "Log a daily summary of automation activity at midnight.",
        "enabled": True,
        "risk_tier": "low",
        "max_retries": 0,
        "cooldown_seconds": 0,
        "trigger": {"type": "cron", "hour": 0, "minute": 0},
        "conditions": [],
        "action": {"type": "notify", "channel": "log", "message": "Daily automation checkpoint: system running."},
    },
]


def create_default_rules_file() -> None:
    if not _RULES_FILE.exists():
        with _RULES_FILE.open("w", encoding="utf-8") as fh:
            json.dump(DEFAULT_RULES, fh, indent=2)
