# Jarvis Platform

> Personal local AI control plane — command execution, human-interface state, workflow tracking, memory, voice input, private dashboard, and a public website chat layer for [kingofyadav.in](https://kingofyadav.in).

![Version](https://img.shields.io/badge/version-4.2-blue)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)
![Status](https://img.shields.io/badge/status-active-brightgreen)

**Local-first. Private by default. Zero cloud dependency.**

---

## Table of Contents

- [What Is Jarvis?](#what-is-jarvis)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [API Reference](#api-reference)
- [Command Surface](#command-surface)
- [Pro Usage Patterns](#pro-usage-patterns)
- [Runtime Options](#runtime-options)
- [AI Providers](#ai-providers)
- [Persistence](#persistence)
- [Security Model](#security-model)
- [Message Bus](#message-bus)
- [Logs](#logs)
- [Tests](#tests)
- [Operations Runbook](#operations-runbook)
- [Troubleshooting](#troubleshooting)
- [Core Principles](#core-principles)
- [Roadmap](#roadmap)
- [Related Docs](#related-docs)
- [Production Security Checklist](#production-security-checklist)

---

## What Is Jarvis?

Jarvis is a self-hosted AI control plane that runs on your own machine. It manages your identity state, workflow, memory, and device — and exposes a secure REST + WebSocket API so your website, scripts, and dashboards can all talk to a single source of truth.

Private state never leaves the machine. External AI providers (OpenAI, Anthropic) are optional fallbacks — the default is local Ollama.

---

## Key Features

- **Local-first AI** — Ollama runs on your hardware; OpenAI and Anthropic are opt-in fallbacks only
- **Unified command surface** — CLI, Streamlit dashboard, REST API, and voice all share one command router
- **Human-interface (HI) state layer** — durable, typed profile, preferences, memory, and workflow in a single locked store
- **Autonomous automation** — rules engine fires triggers, runs actions, self-heals services, and dispatches notifications without manual commands
- **Semantic memory** — curated notes stored in SQLite with token vectors, related-memory graph, and public/private visibility
- **Public website chat** — safe, isolated chat widget for [kingofyadav.in](https://kingofyadav.in) that never executes commands or exposes private state
- **Append-only audit journal** — every mutation and completed action written to timestamped JSONL for full observability
- **Production-ready** — systemd services, Docker Compose, Nginx reverse proxy, scoped API tokens, CORS, and rate limiting

---

## Architecture

```
                          User interfaces
         CLI        Streamlit dashboard      Voice       REST / WebSocket API
          |                  |                 |                  |
          +------------------+-----------------+------------------+
                             |
                             v
                      Jarvis bridge layer
        intent_parser.py → router.py → actions.py / ai_connector.py
                             |
              local actions  |  typed HI intents
                             v
                     shared message bus
           filesystem backend  ·  optional SQLite backend
                             |
                             v
                     Kingofyadav HI layer
         handler.py → profile / preferences / memory / workflow
                             |
           +-----------------+-------------------+
           v                 v                   v
    state.json          memory.db         events/*.jsonl
  current truth    semantic memory index   audit journal
```

### Component Map

| Area | Path | Responsibility |
|---|---|---|
| Bridge | `Jarvis/` | Intent parsing, routing, local actions, AI provider calls, voice, plugins |
| HI state | `Kingofyadav/` | Profile, preferences, memory, workflow, typed state mutations |
| Transport | `shared/` | Message bus, event journal, schema validation, locks, diagnostics |
| Dashboard | `app/` | Streamlit control panel, model selector, logs, memory, public chat controls |
| API | `web/` | FastAPI control plane, SSE, WebSocket, public-safe chat |
| Scripts | `scripts/` | Start/stop, systemd, health, deploy, watchdog |
| Runtime | `logs/`, `shared/events/` | Process logs, PID files, history, model config, audit events |

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | Older versions untested |
| Ollama | Latest | For local AI inference — `ollama pull llama3:latest` |
| `jq` | Any | For parsing CLI examples (`apt install jq`) |
| `watchdog` (Python) | Any | For low-latency inotify bus; installed via `requirements.txt` |
| systemd | Any | Optional, recommended for production autostart |
| Docker + Compose | Any | Optional, for containerized deployment |

---

## Quick Start

### 1. Configure

```bash
cp .env.example .env
```

Key variables in `.env`:

```bash
APP_ENV=production
DASHBOARD_PASSWORD=change-this                 # required in production

# Local AI — no API key needed
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3:latest
OLLAMA_NUM_CTX=2048
OLLAMA_NUM_PREDICT=96

# Online fallbacks — optional
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# API access
JARVIS_API_KEY=
ALLOWED_ORIGIN=https://kingofyadav.in

# Public website chat
JARVIS_PUBLIC_CHAT=1
JARVIS_PUBLIC_CHAT_PROVIDER=         # blank = follow global model selector
JARVIS_PUBLIC_CHAT_MODEL=
JARVIS_PUBLIC_CHAT_TIMEOUT=60
JARVIS_PUBLIC_CHAT_WORKERS=1
```

### 2. Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Start

```bash
# All services
bash scripts/start_all.sh

# API only
bash scripts/start_api.sh

# Dashboard only
bash scripts/start_dashboard.sh
```

### 4. Verify

```bash
curl -s http://127.0.0.1:5050/api/health
# → {"ok": true}

curl -s http://127.0.0.1:5050/api/health/detail | jq '.summary'
# → {"pass": 131, "warn": 2, "fail": 0}
```

---

## API Reference

Base URL: `http://127.0.0.1:5050`

### Health & Observability

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/health` | None | Liveness check |
| `GET` | `/api/health/detail` | Token | Full health report: critical, warnings, pass counts |
| `GET` | `/api/status` | Token | Host, OS, connectivity, listener state |
| `GET` | `/api/state` | Token | Full private HI + AI state snapshot |
| `GET` | `/api/live` | Token | Combined status + state in one call |
| `GET` | `/api/session` | Token | Current Jarvis session |
| `GET` | `/api/history` | Token | Last 50 executed commands |

### Streaming

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/events` | Token | SSE stream — live state push every 4 s |
| `WS` | `/api/ws/live` | Token | Authenticated WebSocket live stream |
| `WS` | `/api/ws/public` | None | Public WebSocket — safe profile + workflow |

### Journal

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/journal` | Token | Query audit events |

Query parameters: `?hours=24&source=Jarvis&type=action_completed&limit=100`

### Command Execution

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/command` | Token | Execute any Jarvis command |

```bash
curl -s -X POST http://127.0.0.1:5050/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "status"}'
```

Response includes: `ok`, `intent`, `action`, `result`, `error`, `behavior`, `risk_tier`, `ts`, `request_id`.

### Public Website Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/public-state` | None | Profile, focus, tasks, public memories |
| `POST` | `/api/jarvis-chat` | None | Website visitor chat |
| `POST` | `/api/public-enquiry` | None | Contact form submission |
| `POST` | `/api/public-signup` | None | Access request form |
| `GET` | `/api/public-chat/config` | Token | Chat provider + model config |
| `GET` | `/api/public-chat/history` | Token | Recent visitor questions |
| `GET` | `/api/public-chat/knowledge` | Token | Knowledge source load status |

### Admin

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/public-intake` | Token | Enquiry + signup inbox |
| `POST` | `/api/local-admin-sync` | Token | Sync browser-local admin snapshot |
| `GET` | `/api/local-admin-users` | Token | Synced local admin registry |
| `GET` | `/api/docs` | None | Interactive OpenAPI documentation |

---

## Command Surface

All commands work identically via CLI, dashboard, API, or voice.

### Identity & State

```bash
who are you          # Jarvis self-description
who am i             # Your HI profile
profile              # Full profile dump
hi summary           # Human-interface state summary
relationship         # Relationship model
preferences          # Current preferences
workflow             # Active workflow + tasks
memory               # Recent memories
domain               # Domain knowledge snapshot
website status       # Public website health
```

### Workflow

```bash
set current focus ship dashboard docs
add task write architecture readme
set task status <task_id> doing
block task <task_id> waiting for review
set task due <task_id> tomorrow
```

### Memory

```bash
add memory dashboard auth now uses DASHBOARD_PASSWORD
search memory dashboard auth
semantic memory dashboard auth
related memory <memory_id>
make memory public <memory_id>
make memory private <memory_id>
```

### Device & System

```bash
status
system info
hardware report
software report
network report
environment report
device report
device inventory
register device primary laptop
logs
```

### AI

```bash
ai status
ask explain the current architecture
plan upgrade the public website chat safely
```

### Safe Shell (confirmation required)

```bash
run pwd
run ls -la
confirmation status
confirm
cancel
```

Allowlisted commands: `pwd`, `whoami`, `date`, `uname`, `ls` with approved flags and workspace-safe paths. All others are rejected.

---

## Pro Usage Patterns

### Shell alias — run commands in one word

Add to `~/.bashrc`:

```bash
jarvis() {
  curl -s -X POST http://127.0.0.1:5050/api/command \
    -H "Content-Type: application/json" \
    -d "{\"command\":\"$*\"}" | jq -r '.result'
}
```

```bash
jarvis status
jarvis who am i
jarvis what should I work on next
```

### Morning health check

```bash
curl -s http://127.0.0.1:5050/api/health/detail \
  | jq '"[\(.summary.fail) fail · \(.summary.warn) warn · \(.summary.pass) pass] \(.critical | if length > 0 then .[0].detail else "all clear" end)"'
```

### Watch live state in terminal

```bash
watch -n 4 'curl -s http://127.0.0.1:5050/api/status | jq "{current_focus, memory_count, last_action, connectivity}"'
```

### Stream SSE live updates

```bash
curl -N http://127.0.0.1:5050/api/events | while read line; do
  echo "$line" | grep '^data:' | sed 's/^data: //' | jq '.status.time' 2>/dev/null
done
```

### Tail journal like a log

```bash
while true; do
  curl -s "http://127.0.0.1:5050/api/journal?hours=0.05&limit=5" \
    | jq -r '.events[] | "\(.ts)  \(.type)  \(.payload.action // "")"'
  sleep 3
done
```

### Snapshot state to file

```bash
curl -s http://127.0.0.1:5050/api/live | jq '.' \
  > ~/jarvis-snapshot-$(date +%F-%H%M).json
```

### Test the public chat

```bash
curl -s -X POST http://127.0.0.1:5050/api/jarvis-chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What services does King Yadav offer?"}' | jq -r '.reply'
```

### Audit what visitors are asking

```bash
curl -s http://127.0.0.1:5050/api/public-chat/history \
  | jq -r '.items[] | "\(.ts)  \(.message)"' | head -20
```

---

## Runtime Options

### systemd (recommended for production)

```bash
bash scripts/install-systemd.sh

systemctl --user start jarvis-kingofyadav jarvis-api jarvis-dashboard
systemctl --user status jarvis-kingofyadav jarvis-api jarvis-dashboard

# Autostart after login
loginctl enable-linger "$USER"
```

### Docker Compose

```bash
cp .env.example .env
docker compose up -d
```

| Service | URL |
|---|---|
| Dashboard | `http://127.0.0.1:8501` |
| API | `http://127.0.0.1:5050/api/health` |

### Direct scripts

```bash
bash scripts/start_all.sh
bash scripts/stop_all.sh
bash scripts/status.sh
bash scripts/watchdog.sh     # restart stopped services
```

---

## AI Providers

Model and provider selection are stored in `logs/ai_model_config.json` and switchable live from the dashboard sidebar.

| Provider | Environment variables | Notes |
|---|---|---|
| **Ollama** | `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT` | Local-first. No API key. Default: `llama3:latest` |
| **OpenAI** | `OPENAI_API_KEY`, `OPENAI_MODEL` | Online fallback. Default: `gpt-4o-mini` |
| **Anthropic** | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Online fallback. Default: `claude-sonnet-4-6` |

The public website chat and the private dashboard can use **different** providers. Set `JARVIS_PUBLIC_CHAT_PROVIDER` + `JARVIS_PUBLIC_CHAT_MODEL` to pin the public chat independently, or leave blank to follow the global selector.

Every AI prompt includes: runtime context, selected HI state, recent memory, workflow focus, response mode, and conversation history.

---

## Persistence

| Store | Writer | Purpose |
|---|---|---|
| `Kingofyadav/state.json` | `state_manager.py` | Current HI truth — do not edit directly |
| `Kingofyadav/memory.db` | `memory_store.py` | Searchable memory index, visibility, related-memory graph |
| `Jarvis/profiles.json` | `profile_manager.py` | AI profile and session state |
| `shared/events/YYYY-MM-DD.jsonl` | `event_journal.py` | Append-only audit journal |
| `logs/ai_history.jsonl` | `ai_connector.py` | AI conversation history |
| `logs/api_history.jsonl` | `web/api.py` | API command history |
| `logs/dashboard_history.jsonl` | `ui_helpers.py` | Dashboard command history |
| `logs/public_chat.jsonl` | `web/api.py` | Public visitor chat history |

> Never edit `state.json` directly. Use Jarvis commands or the HI state helpers — they enforce normalization, locking, and audit events.

---

## Security Model

| Layer | Control |
|---|---|
| Dashboard | `DASHBOARD_PASSWORD` required in production. Session cached 24 h in `logs/dashboard_session.json`. |
| API write access | Localhost trust or a scoped token in `JARVIS_API_KEY` / `logs/api_tokens.json`. |
| Public chat isolation | Chat does not call the command router and does not mutate private state. |
| Shell execution | High-risk actions stored as pending until explicit `confirm`. Allowlist enforced. |
| Network edge | Nginx is the only public entry point. API and dashboard bind to loopback. |
| Secrets | Never commit `.env`. Rotate keys immediately if they appear in logs or tool output. |

---

## Message Bus

Default backend: filesystem under `shared/bus/` — atomic writes, atomic claims, TTL expiry, dead-letter routing, processed-file rotation.

Optional SQLite backend (WAL-backed queueing, same interface):

```bash
JARVIS_BUS_BACKEND=sqlite
```

---

## Logs

| File | Content |
|---|---|
| `logs/api.log` | FastAPI process output |
| `logs/activity.log` | Bridge command activity |
| `logs/kingofyadav.log` | HI listener output |
| `logs/dashboard.log` | Streamlit output |
| `logs/bus.log` | Bus request / response / dead-letter events |
| `logs/public_chat.jsonl` | Public visitor chat history |
| `logs/doctor/latest.json` | Latest doctor report |
| `shared/events/YYYY-MM-DD.jsonl` | Append-only audit journal |

---

## Tests

```bash
# Run all test suites
python3 -m unittest discover -s Jarvis/tests -t . -v
python3 -m unittest discover -s Kingofyadav/tests -v
python3 -m unittest discover -s shared/tests -v
```

Coverage: command routing, risk behavior, shell safety, profile/session persistence, voice fallback, HI state normalization, workflow tasks, memory search/visibility, bus concurrency, response isolation.

---

## Operations Runbook

### Useful ops commands

| Command | Purpose |
|---|---|
| `bash scripts/status.sh` | Process status and recent bus log |
| `bash scripts/doctor.sh` | Full health report: Python, env, services, ports, files |
| `python3 shared/bus_health.py` | Bus queue and dead-letter summary |
| `bash scripts/watchdog.sh` | Restart stopped services by PID file |
| `bash scripts/deploy.sh` | Deployment helper for managed services |

---

## Troubleshooting

### Dashboard won't start

**Symptom:** Browser shows "Authentication required" with no password prompt, or Streamlit exits immediately.

**Fix:** In production mode (`APP_ENV=production`), `DASHBOARD_PASSWORD` must be set in `.env`. Without it, the dashboard locks before rendering.

```bash
grep DASHBOARD_PASSWORD .env   # must be non-empty
```

---

### API returns 401

**Symptom:** `{"detail": "Unauthorized"}` on private endpoints.

**Fix:** Set `JARVIS_API_KEY` in `.env`, or configure a scoped token in `logs/api_tokens.json`. Pass it as `Authorization: Bearer <token>` or `X-Api-Key: <token>`.

---

### Commands time out / "listener not running"

**Symptom:** `bridge.py` hangs or returns a bus timeout error.

**Fix:** The Kingofyadav listener is not running. Check for a stale or missing PID:

```bash
cat logs/kingofyadav.pid
ps aux | grep "Kingofyadav/app.py"
python3 Kingofyadav/app.py &
```

---

### Bus dead-letter queue growing

**Symptom:** `python3 shared/bus_health.py` shows many dead-letter entries.

**Fix:** Diagnose the root cause (invalid messages, listener crash), then clear:

```bash
python3 shared/bus_health.py --clear-dl
```

---

### Ollama responses are slow or time out

**Symptom:** `ask` commands take > 30 s or return a timeout error.

**Fix:** Reduce context window or switch to a smaller model:

```bash
OLLAMA_NUM_CTX=1024
OLLAMA_MODEL=phi3:mini
```

Or verify Ollama is running: `curl http://localhost:11434/api/tags`

---

### Voice not working

**Symptom:** Voice page shows an import error or mic not found.

**Fix:**

```bash
pip install SpeechRecognition pyaudio
python3 Jarvis/tools/mic_test.py       # lists detected microphone devices
python3 Jarvis/voice_input.py --text "status"   # test without mic
```

---

## Core Principles

| Principle | Enforcement |
|---|---|
| Local-first control | Dashboard and API bind to loopback; Nginx is the public edge |
| Typed state changes | HI mutations route through named intents — no generic text mutation |
| Single-writer persistence | `state.json`, `profiles.json`, event logs each have one dedicated writer |
| Auditable actions | Every completed action and HI mutation appends a JSONL event |
| Safe shell execution | Shell is allowlisted and requires explicit confirmation |
| Private / public split | Public chat never executes commands or exposes private memory |

---

## Roadmap

Phases are sequential. Later phases depend on earlier ones being stable.

| Phase | Name | Status | Summary |
|---|---|---|---|
| **0** | Foundation & Core Infrastructure | ✅ Complete | Bus, config, logging, state, auth, API, audit journal, scripts |
| **1** | Jarvis Core Intelligence | ✅ Complete | Intent parser, router, skills, AI connector (Ollama/OpenAI/Anthropic), voice input |
| **2** | Memory Engine | 🔄 Partial | SQLite semantic index, search, visibility done — long-term continuity and knowledge graph in progress |
| **3** | Voice Intelligence | 🔄 Partial | STT (SpeechRecognition) done — wake word, real-time conversation, multilingual not yet built |
| **4** | Autonomous Automation | ✅ Complete | Scheduler, rules engine, background monitors, self-healing watchdog, notification dispatch |
| **4.1** | Automation Hardening | ✅ Complete | Dry-run, emergency stop, cooldown, retry+backoff, approval gate, audit log, failure history, schema validation, webhook signing |
| **5** | Multi-Device Intelligence | 🔜 Next | Shared memory sync, cross-device session, device mesh, remote execution |
| **6** | HI Wallet Ecosystem | 🔄 Partial | Frontend prototype live at `kingofyadav.in/wallet/` — UPI bridge and backend ledger not yet built |
| **7** | Developer Ecosystem | ⬜ Planned | Plugin marketplace, SDK, third-party integrations |
| **8** | Jarvis OS | ⬜ Planned | Full AI operating environment — full autonomous life layer |

### Phase 4 — Autonomous Automation (current)

Goal: Jarvis works without explicit commands. Background agents monitor state, fire rules-based triggers, and self-heal services.

```
Trigger (time / health / event / state change)
        ↓
   Rules Engine (condition match)
        ↓
   Task Execution (action handler)
        ↓
   Feedback Loop (audit + notification)
```

Components under `automation/`:

| Module | Purpose |
|---|---|
| `scheduler.py` | Interval and cron-style job runner |
| `rules.py` | Trigger → condition → action rules engine |
| `monitor.py` | Health endpoint, log file, and process monitors |
| `notifier.py` | Notification dispatch (log, webhook, bus event) |
| `app.py` | Automation daemon entry point |

---

## Related Docs

| Component | README |
|---|---|
| Jarvis Bridge | [Jarvis/README.md](Jarvis/README.md) |
| HI State Layer | [Kingofyadav/README.md](Kingofyadav/README.md) |
| Streamlit Dashboard | [app/README.md](app/README.md) |
| FastAPI Web API | [web/README.md](web/README.md) |
| Automation Daemon | [automation/README.md](automation/README.md) |
| Shared Transport | [shared/README.md](shared/README.md) |
| Plugin Skills | [Jarvis/skills/README.md](Jarvis/skills/README.md) |
| Contributing Guide | [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## Production Security Checklist

Run before every public deployment:

```bash
bash scripts/doctor.sh
python3 shared/bus_health.py
curl -s http://127.0.0.1:5050/api/health/detail | jq '.summary'
```

**Secrets & credentials**

- [ ] `.env` is NOT committed — check `git status` and `.gitignore`
- [ ] `DASHBOARD_PASSWORD` is set to a strong value (not the example default)
- [ ] `JARVIS_API_KEY` or scoped tokens set if any non-localhost client will call the API
- [ ] API keys are only present for providers you actually use — remove unused keys
- [ ] `LIVE_CLASS_TOKEN` rotated if it has been shared or logged

**Network exposure**

- [ ] API and dashboard bind to loopback (`API_HOST=127.0.0.1`) — not `0.0.0.0`
- [ ] Nginx is the only public entry point; API and dashboard are never exposed directly
- [ ] HTTPS is enabled on the Nginx edge — no plaintext public traffic
- [ ] CORS `ALLOWED_ORIGIN` is set to your production domain(s) only
- [ ] `JARVIS_TRUSTED_PROXY_ADDRS` contains only known proxy IPs

**Public chat isolation**

- [ ] `JARVIS_PUBLIC_CHAT=1` only if you want the website widget live
- [ ] Public chat provider and rate limits reviewed (`JARVIS_PUBLIC_CHAT_RPM`)
- [ ] Public knowledge root (`JARVIS_PUBLIC_SITE_ROOT`) points to the correct directory

**State & persistence**

- [ ] `Kingofyadav/state.json` is not world-readable (`chmod 600`)
- [ ] `Kingofyadav/memory.db` is not world-readable
- [ ] `logs/` directory is excluded from any public file serving
- [ ] `shared/events/` audit journal is excluded from public access

**Runtime validation**

- [ ] `bash scripts/doctor.sh` shows zero critical failures
- [ ] `curl -s http://127.0.0.1:5050/api/health/detail | jq '.summary.fail'` returns `0`
- [ ] Automation daemon health check passes if Phase 4 is enabled

---

**Owner:** King Yadav · [kingofyadav.in](https://kingofyadav.in) · Jhon Aamit LLP · MIT License
