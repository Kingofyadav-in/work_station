# automation — Phase 4: Autonomous Automation

> Background automation daemon — watches health, monitors processes, fires rules-based triggers, and self-heals services without explicit commands.

![Phase](https://img.shields.io/badge/phase-4-orange)
![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Files](#files)
- [Start / Stop](#start--stop)
- [Rule Format](#rule-format)
  - [Trigger Types](#trigger-types)
  - [Condition Types](#condition-types)
  - [Action Types](#action-types)
- [Hardening Features](#hardening-features)
- [Rule Examples](#rule-examples)
- [Troubleshooting](#troubleshooting)
- [Tests](#tests)
- [Related Docs](#related-docs)

---

## Features

- **Interval and cron triggers** — fire every N seconds or once per day at a specific time
- **5 condition types** — health fail count, health warn count, process down, log pattern, state field match, or always
- **4 action types** — log notification, service restart, Jarvis command, outbound webhook
- **Dry-run mode** — test any rule without executing the action
- **Emergency stop** — halt all rules immediately with one command
- **Cooldown enforcement** — prevent a rule from re-firing within a configurable window
- **Approval gate** — store an action as pending until `confirm`
- **Retry + backoff** — configurable retry count and backoff interval per action
- **Webhook signing** — HMAC-signed payloads for outbound webhook actions
- **Audit trail** — every rule execution appended to `shared/events/YYYY-MM-DD.jsonl`
- **Failure history** — per-rule failure records with timestamps

---

## Architecture

```
Trigger (interval / cron / health_event / log_pattern / state_change)
        ↓
   Rules Engine (automation/rules.py)
        ↓  conditions pass?
   Action Dispatcher (automation/scheduler.py → dispatch_action)
        ↓
   ┌─────────────┬───────────────┬──────────────┬──────────┐
   │  notify log │ restart svc   │ run command  │ webhook  │
   └─────────────┴───────────────┴──────────────┴──────────┘
        ↓
   Audit journal (shared/event_journal.py)
```

---

## Files

| File | Responsibility |
|---|---|
| `app.py` | Daemon entry point — loads rules, starts scheduler, handles signals |
| `scheduler.py` | Interval and cron-style job runner (no external deps) |
| `rules.py` | Trigger → condition → action rules engine; loads `rules.json` |
| `monitor.py` | API health check, PID file checks, log tail, state snapshot |
| `notifier.py` | Notification dispatch (log / bus event / webhook) |
| `rules.json` | Rule definitions — created with defaults on first run |

---

## Start / Stop

```bash
# Via Jarvis command (recommended)
python3 Jarvis/bridge.py "start automation"
python3 Jarvis/bridge.py "automation status"
python3 Jarvis/bridge.py "automation rules"
python3 Jarvis/bridge.py "automation logs"
python3 Jarvis/bridge.py "stop automation"

# Direct
python3 automation/app.py

# systemd (production)
cp scripts/jarvis-automation.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now jarvis-automation
```

---

## Rule Format

Rules live in `automation/rules.json`. Edit and restart the daemon to pick up changes.

```json
{
  "id": "unique_rule_id",
  "description": "Human-readable label",
  "enabled": true,
  "trigger": {
    "type": "interval",
    "seconds": 300
  },
  "conditions": [
    { "type": "health_fail_count", "min": 1 }
  ],
  "action": {
    "type": "notify",
    "channel": "log",
    "message": "Health check: {health_fail_count} failure(s)."
  }
}
```

### Trigger Types

| Type | Fields | Description |
|---|---|---|
| `interval` | `seconds` | Fire every N seconds |
| `cron` | `hour`, `minute` | Fire once per day at HH:MM UTC |

### Condition Types

| Type | Fields | Passes when |
|---|---|---|
| `health_fail_count` | `min` | API health fail count ≥ min |
| `health_warn_count` | `min` | API health warn count ≥ min |
| `process_down` | `name` | Named service PID is gone |
| `log_pattern` | `pattern` | Regex matches a recent log line |
| `state_field_equals` | `field`, `value` | HI state field equals value |
| `always` | — | Always passes |

### Action Types

| Type | Fields | Effect |
|---|---|---|
| `notify` | `channel`, `message`, `webhook_url` | Log / bus event / HTTP POST |
| `restart_service` | `service`, `script` | Run a start script via bash |
| `command` | `command` | Run a Jarvis bridge command |
| `webhook` | `url`, `message` | HTTP POST JSON payload |

---

## Hardening Features

These features are available in every rule and do not require additional configuration files.

### Dry-run mode

Add `"dry_run": true` to any rule. The condition is evaluated but the action is logged rather than executed. Use this to validate new rules before enabling them in production.

```json
{
  "id": "test_restart_rule",
  "enabled": true,
  "dry_run": true,
  "trigger": { "type": "interval", "seconds": 60 },
  "conditions": [{ "type": "process_down", "name": "jarvis-api" }],
  "action": { "type": "restart_service", "service": "jarvis-api", "script": "scripts/start_api.sh" }
}
```

### Emergency stop

Stop all running rules immediately without waiting for the next trigger cycle:

```bash
python3 Jarvis/bridge.py "stop automation"
# or
systemctl --user stop jarvis-automation
```

### Cooldown

Prevent a rule from re-firing within a window after it last executed:

```json
"cooldown_seconds": 600
```

### Approval gate

Store the action as pending until an operator confirms:

```json
"require_approval": true
```

Then from the CLI or dashboard: `confirm`

### Retry + backoff

Retry a failed action up to N times with increasing delay:

```json
"action": {
  "type": "restart_service",
  "service": "jarvis-api",
  "script": "scripts/start_api.sh",
  "retry": { "max": 3, "backoff_seconds": 30 }
}
```

---

## Rule Examples

### Daily summary notification (cron trigger)

```json
{
  "id": "daily_summary",
  "description": "Send a daily log summary at 08:00 UTC.",
  "enabled": true,
  "trigger": {
    "type": "cron",
    "hour": 8,
    "minute": 0
  },
  "conditions": [
    { "type": "always" }
  ],
  "action": {
    "type": "notify",
    "channel": "log",
    "message": "Daily summary: {health_fail_count} fail(s), {health_warn_count} warn(s) at check time."
  }
}
```

### Log pattern watchdog

```json
{
  "id": "error_log_watchdog",
  "description": "Alert when ERROR appears in the activity log.",
  "enabled": true,
  "cooldown_seconds": 300,
  "trigger": {
    "type": "interval",
    "seconds": 60
  },
  "conditions": [
    { "type": "log_pattern", "pattern": "ERROR" }
  ],
  "action": {
    "type": "notify",
    "channel": "log",
    "message": "ERROR pattern detected in recent activity log."
  }
}
```

### Auto-restart API on process down

```json
{
  "id": "watchdog_restart_api",
  "description": "Restart jarvis-api if its PID is gone.",
  "enabled": true,
  "trigger": {
    "type": "interval",
    "seconds": 60
  },
  "conditions": [
    { "type": "process_down", "name": "jarvis-api" }
  ],
  "action": {
    "type": "restart_service",
    "service": "jarvis-api",
    "script": "scripts/start_api.sh",
    "retry": { "max": 2, "backoff_seconds": 15 }
  }
}
```

---

## Troubleshooting

### Rules not firing

The daemon is not running. Check status:

```bash
python3 Jarvis/bridge.py "automation status"
systemctl --user status jarvis-automation
```

Restart if needed:

```bash
python3 Jarvis/bridge.py "start automation"
```

---

### Rule fires but action fails

Check the automation log and dead-letter queue:

```bash
tail -f logs/automation.log
ls shared/bus/deadletter/
python3 shared/bus_health.py
```

---

### Dead-letter queue growing

Invalid messages or a listener crash is dropping requests. Fix the root cause first, then clear:

```bash
python3 shared/bus_health.py --clear-dl
```

---

### Webhook action not reaching endpoint

Verify the URL is reachable from the machine and check the log for HTTP error codes:

```bash
curl -X POST <your_webhook_url> -d '{"test":true}'
grep "webhook" logs/automation.log
```

---

## Tests

```bash
python3 -m unittest discover -s automation/tests -v
```

---

## Related Docs

- [Root Platform README](../README.md)
- [Jarvis Bridge](../Jarvis/README.md)
- [Shared Transport](../shared/README.md)
- [Contributing Guide](../CONTRIBUTING.md)
