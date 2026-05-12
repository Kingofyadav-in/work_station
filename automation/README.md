# automation — Phase 4: Autonomous Automation

Background daemon that makes Jarvis work without explicit commands. It watches health, monitors processes, fires rules-based triggers, and self-heals services.

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

## Files

| File | Responsibility |
|---|---|
| `app.py` | Daemon entry point — loads rules, starts scheduler, handles signals |
| `scheduler.py` | Interval and cron-style job runner (no external deps) |
| `rules.py` | Trigger → condition → action rules engine; loads `rules.json` |
| `monitor.py` | API health check, PID file checks, log tail, state snapshot |
| `notifier.py` | Notification dispatch (log / bus event / webhook) |
| `rules.json` | Rule definitions — created with defaults on first run |

## Start / stop

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

## Rule format

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

### Trigger types

| Type | Fields | Description |
|---|---|---|
| `interval` | `seconds` | Fire every N seconds |
| `cron` | `hour`, `minute` | Fire once per day at HH:MM UTC |

### Condition types

| Type | Fields | Passes when |
|---|---|---|
| `health_fail_count` | `min` | API health fail count ≥ min |
| `health_warn_count` | `min` | API health warn count ≥ min |
| `process_down` | `name` | Named service PID is gone |
| `log_pattern` | `pattern` | Regex matches a recent log line |
| `state_field_equals` | `field`, `value` | HI state field equals value |
| `always` | — | Always passes |

### Action types

| Type | Fields | Effect |
|---|---|---|
| `notify` | `channel`, `message`, `webhook_url` | Log / bus event / HTTP POST |
| `restart_service` | `service`, `script` | Run a start script via bash |
| `command` | `command` | Run a Jarvis bridge command |
| `webhook` | `url`, `message` | HTTP POST JSON payload |

## Tests

```bash
python3 -m unittest discover -s automation/tests -v
```
