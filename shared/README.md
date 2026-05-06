# shared

Shared infrastructure for the Jarvis Platform. This package contains transport, validation, locking, diagnostics, and event journaling. It intentionally contains no product-specific business logic.

## Responsibilities

| Module | Responsibility |
|---|---|
| `message_bus.py` | Filesystem request/response bus with atomic claims |
| `bus_db.py` | SQLite WAL-backed bus with the same public interface |
| `validate_message.py` | Message schema validation |
| `intent_schema.json` | JSON Schema contract for bus messages |
| `event_journal.py` | Append-only audit event writer and query helpers |
| `file_lock.py` | `fcntl` exclusive lock context manager |
| `bus_health.py` | CLI diagnostics for pending, processed, dead-letter, and listener state |
| `identity.py` | Stable ID generation, fingerprinting, host info, and connectivity check |
| `listener_status.py` | PID-file helpers and process detection for the Kingofyadav listener |
| `local_admin_registry.py` | Append-only registry for browser-local admin sync snapshots |
| `public_intake.py` | Storage and retrieval for public enquiry and signup form submissions |

Runtime paths:

| Path | Purpose |
|---|---|
| `shared/bus/requests/` | Pending filesystem requests |
| `shared/bus/responses/` | Pending filesystem responses |
| `shared/bus/processed/` | Completed filesystem message archive |
| `shared/bus/deadletter/` | Invalid, expired, or failed filesystem messages |
| `shared/bus/bus.db` | SQLite backend database when enabled |
| `shared/events/YYYY-MM-DD.jsonl` | Audit events |
| `logs/bus.log` | Human-readable bus activity log |

## Bus Backends

### Filesystem Backend

Default backend. Each request and response is a JSON file. Writers use temp files and atomic `rename()`. Consumers claim work by renaming `.json` to `.processing`.

```python
from message_bus import MessageBus

bus = MessageBus(actor="Jarvis")
```

### SQLite Backend

Optional backend for WAL-backed queueing:

```bash
JARVIS_BUS_BACKEND=sqlite
```

Use the factory when writing new code:

```python
from bus_db import get_bus

bus = get_bus(actor="Jarvis")
```

The returned object supports the same methods used by `MessageBus`: `send_request`, `list_requests_for_me`, `read_message`, `send_response`, `mark_processed`, `move_to_deadletter`, `wait_for_response`, `reap_stale_responses`, and `alert_deadletter`.

## Message Lifecycle

```text
send_request()
   |
   v
pending request
   |
   v
listener claims request
   |
   v
handler processes typed intent
   |
   v
send_response()
   |
   v
caller claims response by request_id
   |
   v
processed archive or database status
```

## Message Schema

Every message must validate against `intent_schema.json`.

| Field | Type | Meaning |
|---|---|---|
| `version` | string | Protocol version, currently `"1.0"` |
| `intent` | string | Typed intent or typed response intent |
| `source` | string | Sender actor |
| `target` | string | Receiver actor |
| `payload` | object | `text` plus `args` |
| `timestamp` | string | UTC ISO 8601 timestamp |
| `request_id` | string | Correlation id |
| `priority` | string | `low`, `normal`, or `high` |
| `meta` | object | Free-form metadata |

Example request:

```json
{
  "version": "1.0",
  "intent": "hi_get_profile",
  "source": "Jarvis",
  "target": "Kingofyadav",
  "payload": {
    "text": "profile",
    "args": {
      "raw_payload": ""
    }
  },
  "timestamp": "2026-04-26T19:00:00+00:00",
  "request_id": "jarvis-abc123def456",
  "priority": "normal",
  "meta": {
    "origin": "router.py"
  }
}
```

Response intents append `_response` to the request intent and reuse the same `request_id`.

## Guarantees

| Guarantee | Mechanism |
|---|---|
| Atomic writes | Write temp file, then rename |
| Exactly-once filesystem claim | Rename request to `.processing` before read |
| Response isolation | Response keyed by `request_id` |
| Stale work recovery | Old `.processing` files return to pending |
| TTL cleanup | Expired requests move to dead-letter |
| Processed cap | Filesystem processed archive is trimmed |
| Cross-writer safety | `file_lock()` protects append/truncate operations |
| Audit query speed | `event_journal.py` builds an in-memory SQLite index for queries |

## Timeouts and Dead-letter

| Condition | Outcome |
|---|---|
| Request older than TTL | Dead-letter |
| Invalid schema | Dead-letter |
| Response target mismatch | Dead-letter |
| Invalid response | Dead-letter and return `None` |
| Stale `.processing` | Reclaimed for processing |
| Timeout waiting for response | Caller receives `None` and `TIMEOUT` is logged |

## Diagnostics

```bash
python3 shared/bus_health.py
python3 shared/bus_health.py --watch
python3 shared/bus_health.py --clear-dl
```

Useful log checks:

```bash
tail -f logs/bus.log
ls shared/bus/deadletter/
```

## Event Journal

Append an event:

```python
from event_journal import append_event

append_event(
    source="Kingofyadav",
    event_type="memory_added",
    payload={"entry": "documented bus behavior"},
)
```

Query events:

```python
from event_journal import query_events, recent_events, event_sources, event_types

recent = recent_events(hours=24, limit=50)
items = query_events(source="Kingofyadav", event_type="workflow_task_added", limit=20)
```

The API exposes the same event data through `/api/journal`.

## Development Rules

- Keep transport generic. Domain logic belongs in `Jarvis/`, `Kingofyadav/`, `app/`, or `web/`.
- Validate every bus message before publishing or processing.
- Include a `request_id` on all request/response pairs.
- Move bad data out of hot paths into dead-letter.
- Prefer `get_bus(actor)` in new code if backend flexibility matters.

## Tests

From the repo root:

```bash
python3 -m unittest discover -s shared/tests -v
```

Coverage includes atomic request claiming and response isolation by request id.
