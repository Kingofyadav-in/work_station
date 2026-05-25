# Kingofyadav HI Layer

> The human-interface state layer — owns the durable truth for the operator: profile, preferences, workflow, curated memory, and audit events.

![Python](https://img.shields.io/badge/python-3.12-blue)
![SQLite](https://img.shields.io/badge/storage-SQLite-lightblue)
![Single writer](https://img.shields.io/badge/state-single--writer-important)

Kingofyadav is the Human Interface (HI) state layer for Jarvis. It owns the durable truth for the human operator: profile, preferences, workflow, curated memory, memory visibility, and audit events.

The listener receives typed requests from Jarvis through the shared bus, dispatches them to domain modules, writes state atomically, and records mutations in the event journal.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Files](#files)
- [Starting the Listener](#starting-the-listener)
- [Listener Backends](#listener-backends)
- [Intent Contract](#intent-contract)
  - [Reads](#reads)
  - [Mutations](#mutations)
- [State Model](#state-model)
- [Memory System](#memory-system)
- [Workflow System](#workflow-system)
- [Audit Journal](#audit-journal)
- [Operational Rules](#operational-rules)
- [Troubleshooting](#troubleshooting)
- [Tests](#tests)
- [Related Docs](#related-docs)

---

## Features

- **Typed intent dispatch** — every mutation routes through a named intent, never a generic text string
- **Atomic state load/save** — `fcntl` exclusive lock prevents concurrent writes to `state.json`
- **SQLite semantic memory index** — token vectors, related-memory graph, public/private visibility metadata
- **Overflow protection with archive** — memory cap enforced before trim; archived entries preserved in the journal
- **Append-only audit journal** — every successful mutation writes a JSONL event to `shared/events/`
- **inotify + adaptive polling fallback** — low-latency request handling via `watchdog`; graceful fallback when unavailable
- **Two bus backends** — filesystem (default) or SQLite WAL for high-volume message throughput

---

## Architecture

```text
shared bus request
      |
      v
app.py                  listener loop
      |
      v
handler.py              typed intent dispatch
      |
      +--> profile.py       identity, intro, relationship
      +--> preferences.py   response mode and preference values
      +--> workflow.py      focus, tasks, status, blockers, due dates
      +--> memory.py        memory summaries, search, visibility
              |
              v
        memory_store.py     SQLite semantic index and related memory
      |
      v
state_manager.py        locked atomic state load/save
      |
      v
state.json              current HI truth
shared/events/*.jsonl   append-only audit trail
```

---

## Files

| File | Responsibility |
|---|---|
| `app.py` | Persistent listener, PID management, watchdog/polling dispatch |
| `handler.py` | Maps HI intent names to domain module functions |
| `profile.py` | Profile summaries and profile field updates |
| `preferences.py` | Preference summaries and updates |
| `workflow.py` | Focus, task creation, status, blockers, due metadata |
| `memory.py` | Memory append, summary, search, related memory, visibility |
| `memory_store.py` | SQLite memory index, token vectors, related-memory graph |
| `state_manager.py` | Atomic normalized `state.json` load/save with locks |
| `validate_state.py` | Defaults, normalization, dedupe, schema repair |
| `archive_memory_events.py` | Archive legacy event entries from memory |
| `migrate_memory.py` | One-time legacy memory migration helper |
| `state.json` | Persistent profile, preferences, memory, workflow |
| `memory.db` | Searchable memory metadata and relationships |

---

## Starting the Listener

From the repo root:

```bash
python3 Kingofyadav/app.py
```

Usually started through another service:

```bash
bash scripts/start_dashboard.sh
systemctl --user start jarvis-kingofyadav
```

Verify it is running:

```bash
cat logs/kingofyadav.pid
ps aux | grep "Kingofyadav/app.py"
```

Quick functional test:

```bash
python3 Kingofyadav/app.py &
python3 Jarvis/bridge.py "profile"
```

The listener writes `logs/kingofyadav.pid`. Jarvis checks that PID before sending HI requests and fails fast if the listener is offline.

---

## Listener Backends

The default bus backend is filesystem-based. The listener prefers inotify via `watchdog` for low-latency request handling and falls back to adaptive polling when watchdog is unavailable.

The shared layer also supports SQLite:

```bash
JARVIS_BUS_BACKEND=sqlite
```

SQLite mode uses `shared/bus/bus.db` with WAL and the same public bus interface.

---

## Intent Contract

### Reads

| Intent | Purpose |
|---|---|
| `hi_get_profile` | Full profile summary |
| `hi_get_intro` | Human-readable intro |
| `hi_get_relationship` | HI/Jarvis relationship model |
| `hi_get_preferences` | Preferences and response mode |
| `hi_get_memory` | Memory summary and recent entries |
| `hi_memory_search` | Semantic memory search |
| `hi_memory_related` | Related memories for one memory id |
| `hi_get_workflow` | Focus, status, open tasks, blockers, due dates |

### Mutations

| Intent | Payload | Effect |
|---|---|---|
| `hi_set_profile_field` | `field`, `value` | Update profile field |
| `hi_set_domain` | `domain`, optional `website` | Set domain and website together |
| `hi_set_preference` | `key`, `value` | Update preference |
| `hi_set_workflow_focus` | `task` | Update current focus |
| `hi_workflow_add_task` | `title`, optional `due`, `estimate_minutes` | Add tracked task |
| `hi_workflow_set_task_status` | `task_id`, `status` | Change task status |
| `hi_workflow_add_blocker` | `task_id`, `blocker` | Mark/add blocker |
| `hi_workflow_set_due` | `task_id`, `due` | Update due date/text |
| `hi_memory_add` | `entry` | Append curated memory |
| `hi_memory_visibility` | `memory_id`, `visibility` | Set `public` or `private` metadata |

Every successful mutation appends an event to `shared/events/YYYY-MM-DD.jsonl`.

---

## State Model

`state.json` is normalized on every load and save.

```json
{
  "profile": {
    "name": "kingofyadav",
    "display_name": "King Yadav",
    "domain": "AI systems",
    "website": "https://kingofyadav.in",
    "email": "you@example.com",
    "language": "english",
    "system_role": "primary human context",
    "owner_role": "human owner and decision-maker behind this workspace"
  },
  "preferences": {
    "response_style": "structured",
    "response_mode": "adaptive",
    "verbosity": "medium"
  },
  "memory": [
    {
      "type": "note",
      "text": "finished dashboard auth setup",
      "created_at": "2026-04-26T19:00:00+00:00"
    }
  ],
  "workflow": {
    "current_focus": "documentation upgrade",
    "status": "ready",
    "next_actions": [],
    "tasks": []
  }
}
```

### Normalization Rules

- Missing sections are filled from defaults.
- Memory entries are converted to typed dictionaries.
- Memory entries are deduplicated by type and primary text.
- Missing memory timestamps receive a UTC timestamp or legacy sentinel.
- Workflow task status, due text, blockers, and estimates are normalized.
- Optional profile fields are preserved when present.

---

## Memory System

Curated memory is stored in `state.json` and indexed into `memory.db`.

| Capability | Implementation |
|---|---|
| Add memory | `hi_memory_add` → `memory.add_memory()` |
| Full-text/semantic search | Token vectors in `memory_store.py` |
| Related memories | Stored connection metadata refreshed from similarity |
| Public/private metadata | `hi_memory_visibility` updates SQLite metadata |
| Overflow protection | Memory cap with archive before trim |

CLI examples:

```bash
python3 Jarvis/bridge.py "add memory completed README architecture pass"
python3 Jarvis/bridge.py "search memory architecture"
python3 Jarvis/bridge.py "related memory <memory_id>"
python3 Jarvis/bridge.py "make memory public <memory_id>"
```

---

## Workflow System

Workflow state has a current focus plus tracked tasks.

Task fields include:

| Field | Purpose |
|---|---|
| `id` | Stable short task identifier |
| `title` | Task title |
| `status` | `todo`, `doing`, `blocked`, `done`, or `cancelled` |
| `blockers` | List of blockers |
| `due` | Date or human due text |
| `estimate_minutes` | Optional estimate |
| `created_at` | UTC timestamp |
| `updated_at` | UTC timestamp |

---

## Audit Journal

Events are append-only JSONL files under `shared/events/`.

Example:

```json
{"ts":"2026-04-26T19:00:00+00:00","source":"Kingofyadav","type":"workflow_task_added","payload":{"title":"write docs","id":"task-a1b2c3"}}
```

Use API `/api/journal` or `shared/event_journal.py` helpers to query events by time, source, and type.

---

## Operational Rules

- Do not edit `state.json` directly.
- Use command intents or `state_manager.update_state()`.
- Keep mutation logic in domain modules, not in `handler.py`.
- Add a test for every new intent or normalization rule.
- Keep `Jarvis/router.py` `HI_INTENTS` synchronized with `handler.py`.

---

## Troubleshooting

### HI requests time out

The listener is not running. Check the PID file:

```bash
cat logs/kingofyadav.pid
ps aux | grep "Kingofyadav/app.py"
systemctl --user start jarvis-kingofyadav
```

---

### state.json schema error on load

The file may have been edited directly or corrupted. Run the repair tool:

```bash
python3 Kingofyadav/validate_state.py
```

---

### Memory search returns nothing

The SQLite index may need rebuilding after a migration. Run the migration helper:

```bash
python3 Kingofyadav/migrate_memory.py
```

---

### Bus dead-letter has HI requests

The listener crashed and left requests unhandled. Restart the listener, then clear dead-letter:

```bash
systemctl --user restart jarvis-kingofyadav
python3 shared/bus_health.py --clear-dl
```

---

### State changes not persisting

Never edit `state.json` directly — it will be overwritten on the next save. Use the intent API or `state_manager.update_state()` instead.

---

## Tests

From the repo root:

```bash
python3 -m unittest discover -s Kingofyadav/tests -v
```

Coverage includes handler routing, profile/preference mutations, memory append/search/visibility, workflow task updates, state normalization, and archive behavior.

---

## Related Docs

- [Root Platform README](../README.md)
- [Jarvis Bridge](../Jarvis/README.md)
- [Shared Transport](../shared/README.md)
- [FastAPI Web API](../web/README.md)
- [Contributing Guide](../CONTRIBUTING.md)
