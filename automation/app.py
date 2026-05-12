#!/usr/bin/env python3
"""
Automation daemon — Phase 4 entry point.

Start:   python3 automation/app.py
Stop:    send SIGTERM or SIGINT, or 'automation emergency stop'
Pause:   touch logs/automation.STOP (daemon stays alive; no actions execute)
Resume:  rm logs/automation.STOP
Status:  python3 Jarvis/bridge.py "automation status"

Dry-run: AUTOMATION_DRY_RUN=1 python3 automation/app.py
         All actions are logged but not executed.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

_PID_FILE = _ROOT / "logs" / "automation.pid"
_LOG_FILE = _ROOT / "logs" / "automation.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_log = logging.getLogger("automation.app")


def _write_pid() -> None:
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    try:
        _PID_FILE.unlink()
    except FileNotFoundError:
        pass


def _handle_signal(signum: int, _frame: object) -> None:
    _log.info("received signal %d — shutting down", signum)
    _remove_pid()
    sys.exit(0)


def main() -> None:
    from monitor import build_context
    from rules import create_default_rules_file, load_rules, validate_rules
    from scheduler import Job, Scheduler, dispatch_action, is_dry_run

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    _write_pid()

    dry = "  [DRY-RUN — no actions will execute]" if is_dry_run() else ""
    _log.info("automation daemon starting (pid %d)%s", os.getpid(), dry)

    create_default_rules_file()

    # Validate rules.json before scheduling
    from rules import load_all_rules
    all_rules = load_all_rules()
    errors = validate_rules(all_rules)
    if errors:
        for rid, errs in errors.items():
            for e in errs:
                _log.warning("rules.json validation: %s", e)

    token = os.getenv("JARVIS_API_KEY", "")
    rules = load_rules()
    if not rules:
        _log.warning("no enabled rules found in rules.json — daemon idle")

    scheduler = Scheduler(tick=5.0)
    for rule in rules:
        job = Job(rule, dispatch_action, lambda t=token: build_context(t))
        scheduler.add_job(job)

    scheduler.start()
    _log.info("%d rule(s) loaded and scheduled", len(rules))

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.stop()
        _remove_pid()
        _log.info("automation daemon stopped")


if __name__ == "__main__":
    main()
