#!/usr/bin/env python3
"""
Scheduler and action dispatcher for the automation daemon.

Safety controls (Phase 4.1):
  Emergency stop  — create logs/automation.STOP to halt all execution immediately.
                    Delete the file (or run 'automation enable') to resume.
  Dry-run mode    — set AUTOMATION_DRY_RUN=1 to log what would execute without acting.
  Cooldown        — per-rule 'cooldown_seconds' prevents repeated firing after success.
  Retry           — per-rule 'max_retries' retries failed actions with exponential backoff.
  Approval gate   — rules with risk_tier 'high' queue to logs/automation_pending.json
                    and require 'automation approve <id>' before executing.
  Audit log       — every execution outcome written to logs/automation_audit.jsonl.
  Failure history — every failure written to logs/automation_failures.jsonl.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "shared"))

from notifier import notify  # noqa: E402

_log = logging.getLogger("automation.scheduler")

_STOP_FILE     = _ROOT / "logs" / "automation.STOP"
_AUDIT_FILE    = _ROOT / "logs" / "automation_audit.jsonl"
_FAILURE_FILE  = _ROOT / "logs" / "automation_failures.jsonl"
_PENDING_FILE  = _ROOT / "logs" / "automation_pending.json"

_RETRY_BASE_SECONDS = 30
_RETRY_CAP_SECONDS  = 300


# ── Safety helpers ─────────────────────────────────────────────────────────────

def is_emergency_stopped() -> bool:
    return _STOP_FILE.exists()


def set_emergency_stop(active: bool) -> None:
    if active:
        _STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STOP_FILE.write_text("emergency stop", encoding="utf-8")
    else:
        try:
            _STOP_FILE.unlink()
        except FileNotFoundError:
            pass


def is_dry_run() -> bool:
    return os.getenv("AUTOMATION_DRY_RUN", "0").strip() == "1"


# ── Audit + failure logging ────────────────────────────────────────────────────

def _append_jsonl(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def write_audit(rule_id: str, action_type: str, status: str, detail: str = "") -> None:
    _append_jsonl(_AUDIT_FILE, {
        "ts": datetime.now(timezone.utc).isoformat(),
        "rule_id": rule_id,
        "action_type": action_type,
        "status": status,
        "detail": detail,
    })
    try:
        from event_journal import append_event  # noqa: PLC0415
        append_event("automation_action", {"rule_id": rule_id, "action_type": action_type, "status": status})
    except Exception:  # noqa: BLE001
        pass


def write_failure(rule_id: str, action_type: str, error: str, retry: int) -> None:
    _append_jsonl(_FAILURE_FILE, {
        "ts": datetime.now(timezone.utc).isoformat(),
        "rule_id": rule_id,
        "action_type": action_type,
        "error": error,
        "retry": retry,
    })


# ── Pending approval store ─────────────────────────────────────────────────────

def _load_pending() -> list[dict[str, Any]]:
    if not _PENDING_FILE.exists():
        return []
    try:
        return json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_pending(items: list[dict[str, Any]]) -> None:
    _PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PENDING_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def add_pending_approval(rule: dict[str, Any]) -> None:
    items = _load_pending()
    rule_id = rule.get("id", "")
    if any(p["rule_id"] == rule_id for p in items):
        return  # already queued
    items.append({
        "rule_id": rule_id,
        "description": rule.get("description", ""),
        "action": rule.get("action", {}),
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    _save_pending(items)
    _log.info("[PENDING] high-risk rule '%s' queued for manual approval", rule_id)


def get_pending_approvals() -> list[dict[str, Any]]:
    return _load_pending()


def approve_pending(rule_id: str) -> str:
    items = _load_pending()
    entry = next((p for p in items if p["rule_id"] == rule_id), None)
    if not entry:
        return f"No pending approval for rule '{rule_id}'."
    rule_stub = {"id": rule_id, "action": entry["action"]}
    try:
        dispatch_action(rule_stub, _bypass_approval=True)
        write_audit(rule_id, entry["action"].get("type", ""), "approved")
        _log.info("[APPROVED] rule '%s' executed after manual approval", rule_id)
        msg = f"Rule '{rule_id}' approved and executed."
    except Exception as exc:  # noqa: BLE001
        write_failure(rule_id, entry["action"].get("type", ""), str(exc), 0)
        msg = f"Rule '{rule_id}' approved but action failed: {exc}"
    remaining = [p for p in items if p["rule_id"] != rule_id]
    _save_pending(remaining)
    return msg


def deny_pending(rule_id: str) -> str:
    items = _load_pending()
    if not any(p["rule_id"] == rule_id for p in items):
        return f"No pending approval for rule '{rule_id}'."
    remaining = [p for p in items if p["rule_id"] != rule_id]
    _save_pending(remaining)
    write_audit(rule_id, "", "denied")
    _log.info("[DENIED] rule '%s' denied by operator", rule_id)
    return f"Rule '{rule_id}' denied and removed from pending queue."


# ── Job ────────────────────────────────────────────────────────────────────────

class Job:
    def __init__(
        self,
        rule: dict[str, Any],
        handler: Callable[[dict[str, Any]], None],
        context_fn: Callable[[], dict[str, Any]],
    ) -> None:
        self.rule = rule
        self.handler = handler
        self.context_fn = context_fn

        trigger = rule.get("trigger", {})
        self._type            = trigger.get("type", "interval")
        self._interval        = int(trigger.get("seconds", 60))
        self._cron_hour       = int(trigger.get("hour", 0))
        self._cron_minute     = int(trigger.get("minute", 0))
        self._max_retries     = int(rule.get("max_retries", 0))
        self._cooldown        = int(rule.get("cooldown_seconds", 0))

        self._last_run:           float = time.monotonic() - self._interval  # due immediately
        self._last_success_time:  float = 0.0
        self._last_cron_day:      int   = -1
        self._retry_count:        int   = 0
        self._retry_at:           float = 0.0  # monotonic; 0 = no pending retry

    # ── timing ──────────────────────────────────────────────────────────────

    def is_due(self) -> bool:
        now = time.monotonic()

        # Pending retry supersedes normal schedule
        if self._retry_at > 0:
            return now >= self._retry_at

        # Cooldown: skip if last success was too recent
        if self._cooldown > 0 and self._last_success_time > 0:
            if (now - self._last_success_time) < self._cooldown:
                return False

        if self._type == "interval":
            return (now - self._last_run) >= self._interval
        if self._type == "cron":
            dt = datetime.now(timezone.utc)
            right_time = dt.hour == self._cron_hour and dt.minute == self._cron_minute
            new_day = dt.day != self._last_cron_day
            return right_time and new_day
        return False

    def mark_ran(self) -> None:
        self._last_run = time.monotonic()
        if self._type == "cron":
            self._last_cron_day = datetime.now(timezone.utc).day

    # ── execution ───────────────────────────────────────────────────────────

    def fire(self) -> None:
        from rules import evaluate_rule  # noqa: PLC0415

        rule_id    = self.rule.get("id", "?")
        action_type = self.rule.get("action", {}).get("type", "")
        self._retry_at = 0.0  # clear any pending retry flag

        # Emergency stop gate
        if is_emergency_stopped():
            _log.warning("[ESTOP] emergency stop active — skipping '%s'", rule_id)
            return

        # Condition evaluation
        try:
            context = self.context_fn()
        except Exception as exc:  # noqa: BLE001
            _log.error("[%s] context build failed: %s", rule_id, exc)
            return

        if not evaluate_rule(self.rule, context):
            self._retry_count = 0
            return

        # Dry-run gate
        if is_dry_run():
            _log.info("[DRY-RUN] would execute '%s' action=%s", rule_id, action_type)
            write_audit(rule_id, action_type, "dry_run", "AUTOMATION_DRY_RUN=1")
            self._last_success_time = time.monotonic()
            self._retry_count = 0
            return

        # Approval gate for high-risk rules
        if self.rule.get("risk_tier", "low") == "high":
            add_pending_approval(self.rule)
            write_audit(rule_id, action_type, "pending_approval")
            return

        # Execute
        try:
            self.handler(self.rule)
            write_audit(rule_id, action_type, "success")
            self._last_success_time = time.monotonic()
            self._retry_count = 0
        except Exception as exc:  # noqa: BLE001
            write_failure(rule_id, action_type, str(exc), self._retry_count)
            if self._retry_count < self._max_retries:
                backoff = min(_RETRY_BASE_SECONDS * (2 ** self._retry_count), _RETRY_CAP_SECONDS)
                self._retry_at = time.monotonic() + backoff
                self._retry_count += 1
                _log.warning(
                    "[%s] failed (retry %d/%d in %ds): %s",
                    rule_id, self._retry_count, self._max_retries, backoff, exc,
                )
            else:
                _log.error("[%s] exhausted retries — disabling rule: %s", rule_id, exc)
                write_audit(rule_id, action_type, "disabled_after_retries", str(exc))
                if self._max_retries > 0:
                    try:
                        from rules import set_rule_enabled  # noqa: PLC0415
                        set_rule_enabled(rule_id, False)
                    except Exception:  # noqa: BLE001
                        pass
                self._retry_count = 0


# ── Scheduler ─────────────────────────────────────────────────────────────────

class Scheduler:
    """Runs jobs serially in a single background thread."""

    def __init__(self, tick: float = 5.0) -> None:
        self._tick  = tick
        self._jobs: list[Job] = []
        self._stop  = threading.Event()
        self._thread: threading.Thread | None = None

    def add_job(self, job: Job) -> None:
        self._jobs.append(job)

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="automation-scheduler"
        )
        self._thread.start()
        _log.info("scheduler started with %d job(s)%s", len(self._jobs),
                  "  [DRY-RUN]" if is_dry_run() else "")

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            for job in self._jobs:
                if job.is_due():
                    job.mark_ran()
                    job.fire()
            self._stop.wait(timeout=self._tick)


# ── Action dispatcher ──────────────────────────────────────────────────────────

def dispatch_action(rule: dict[str, Any], *, _bypass_approval: bool = False) -> None:
    """
    Execute the action declared in a rule.
    Raises RuntimeError on failure so Job.fire() can trigger retry logic.
    """
    action  = rule.get("action", {})
    atype   = action.get("type", "notify")
    rule_id = rule.get("id", "")

    if atype == "notify":
        msg     = action.get("message", "automation trigger fired")
        channel = action.get("channel", "log")
        webhook = action.get("webhook_url", "")
        notify(msg, channel=channel, rule_id=rule_id, webhook_url=webhook)

    elif atype == "restart_service":
        _restart_service(rule_id, action.get("service", ""), action.get("script", ""))

    elif atype == "command":
        cmd = action.get("command", "")
        if cmd:
            _run_jarvis_command(rule_id, cmd)

    elif atype == "webhook":
        url = action.get("url", action.get("webhook_url", ""))
        msg = action.get("message", rule.get("description", ""))
        notify(msg, channel="webhook", rule_id=rule_id, webhook_url=url)


def _restart_service(rule_id: str, service: str, script: str) -> None:
    script_path = _ROOT / script
    if not script_path.exists():
        raise RuntimeError(f"restart script not found: {script_path}")
    result = subprocess.run(
        ["bash", str(script_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"script exited {result.returncode}: {result.stderr[:200]}")
    notify(f"Restarted {service}.", rule_id=rule_id)
    _log.info("[%s] restarted %s via %s", rule_id, service, script)


def _run_jarvis_command(rule_id: str, command: str) -> None:
    bridge = _ROOT / "Jarvis" / "bridge.py"
    try:
        result = subprocess.run(
            ["python3", str(bridge), command],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(_ROOT),
        )
        if result.returncode != 0:
            raise RuntimeError(f"bridge exited {result.returncode}: {result.stderr[:100]}")
        _log.info("[%s] command '%s' → %s", rule_id, command, result.stdout[:120])
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"command timed out: {command}")
