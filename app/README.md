# Jarvis Dashboard

> Private operator control panel for the Jarvis Platform — commands, memory, workflow, voice, and public website chat controls in one place.

![Python](https://img.shields.io/badge/python-3.12-blue)
![Streamlit](https://img.shields.io/badge/streamlit-1.x-red)
![Port](https://img.shields.io/badge/port-8501-lightgrey)
![Auth](https://img.shields.io/badge/auth-password--protected-orange)

Streamlit operator dashboard for the Jarvis Platform. It is the private control panel for commands, HI state, trusted-device status, system health, workflow, memory, conversation, and public website chat settings.

The dashboard calls the same Jarvis bridge used by the CLI. It does not maintain a separate command path.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Start and Stop](#start-and-stop)
- [Authentication](#authentication)
- [Manual Runtime](#manual-runtime)
- [Page Architecture](#page-architecture)
- [Service Modules](#service-modules)
- [Data Flow](#data-flow)
- [Common Dashboard Commands](#common-dashboard-commands)
- [Public Jarvis Controls](#public-jarvis-controls)
- [Runtime Files](#runtime-files)
- [Networking](#networking)
- [Dependencies](#dependencies)
- [Operations](#operations)
- [Troubleshooting](#troubleshooting)
- [Related Docs](#related-docs)

---

## Features

- **Password-protected session** — production mode requires `DASHBOARD_PASSWORD`; session cached 24 h
- **10 specialized pages** — identity, health, work, memory, security, conversation, public chat, admin, automation
- **Live model selector** — switch AI provider and model without restarting; persisted to `logs/ai_model_config.json`
- **Voice conversation loop** — wake-phrase driven audio capture with TTS reply (neural + offline fallback)
- **Public chat management** — configure, monitor, and test the website visitor chat from the same panel
- **Docker / systemd compatible** — runs as a standalone service behind Nginx

---

## Prerequisites

- Python 3.12+ with the platform `requirements.txt` installed
- Jarvis Platform running (Kingofyadav listener + API)
- Optional: `SpeechRecognition` and `pyaudio` for the voice conversation page

---

## Start and Stop

From the repo root:

```bash
bash scripts/start_dashboard.sh
```

Open:

```text
http://127.0.0.1:8501
```

Stop:

```bash
bash scripts/stop_dashboard.sh
```

`scripts/start_dashboard.sh` loads `.env`, starts the Kingofyadav listener if needed, then starts Streamlit on `127.0.0.1:8501`.

---

## Authentication

When `APP_ENV=production`, `DASHBOARD_PASSWORD` must be set in `.env`.

```bash
APP_ENV=production
DASHBOARD_PASSWORD=change-this-dashboard-password
```

Session auth is persisted to `logs/dashboard_session.json` with a 24-hour TTL. Browser refresh does not re-prompt for the password within that window. Without `DASHBOARD_PASSWORD` in production mode, the dashboard locks before rendering any page.

---

## Manual Runtime

```bash
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

---

## Page Architecture

| Page | File | Purpose |
|---|---|---|
| Home | `app.py` | Command console, state summary, alerts, quick status |
| Identity & Device | `pages/1_Identity_Device.py` | Profile, device registration, hardware/software/network details |
| System Health | `pages/2_System_Health.py` | Listener status, bus log, doctor health, site health checks |
| Work | `pages/3_Work.py` | Current focus, workflow tasks, task actions, Ask AI |
| Memory | `pages/4_Memory.py` | Search, filters, memory cards, public/private visibility |
| Security | `pages/5_Security.py` | Confirmations, session controls, shell command queue |
| Conversation | `pages/6_Conversation.py` | Voice-driven AI conversation loop with wake phrase |
| Public | `pages/7_Public.py` | Chat config, knowledge sources, inbox, enquiries, signups |
| Admin | `pages/8_Admin.py` | Auth registry, personal identity, ventures, contact |
| Automation | `pages/9_Automation.py` | Rules, daemon control, pending approvals, audit trail |

---

## Service Modules

| Module | Responsibility |
|---|---|
| `services/jarvis_client.py` | Run a Jarvis command through `bridge.py` and return structured route metadata |
| `services/state_reader.py` | Read `state.json`, `profiles.json`, listener status, and health hints |
| `services/log_reader.py` | Read bus logs, event journal entries, processed ids |
| `services/ui_helpers.py` | Theme, cards, badges, history, rendering, auto-refresh |
| `services/model_selector.py` | Provider/model selector and active config persistence |
| `services/conversation_manager.py` | Voice-driven conversation loop state machine (thread-safe) |
| `services/voice_client.py` | Microphone capture wrapper with ALSA noise suppression |
| `services/tts_client.py` | TTS: edge-tts (online neural) with espeak-ng offline fallback; temp file cleanup; async-safe |
| `services/public_jarvis.py` | Public chat config, history, knowledge checks, test calls |
| `services/local_admin_registry.py` | Synced local-admin registry snapshots for the dashboard |

---

## Data Flow

```text
Streamlit input
    |
    v
services/jarvis_client.py
    |
    v
Jarvis/bridge.py
    |
    +--> local action result
    |
    +--> shared bus -> Kingofyadav -> response
    |
    v
dashboard result renderer
```

State panels read from disk through `state_reader.py`; command execution still goes through the bridge.

---

## Common Dashboard Commands

```bash
status
profile
workflow
add task write docs
set task status <task_id> doing
memory
search memory docs
make memory public <memory_id>
device report
register device primary laptop
ask summarize my current system
```

---

## Public Jarvis Controls

The Public Jarvis page manages `logs/public_chat_config.json` and reads `logs/public_chat.jsonl`.
The Public Inbox page reads `logs/public_intake.jsonl` for enquiries and access requests.

It controls:

- Enable/disable public chat.
- Public chat rate limit.
- Public model/provider behavior.
- System prompt for website-safe responses.
- Recent public questions.
- Knowledge status for configured public pages.

The public chat endpoint is implemented by `web/api.py` and `web/public_chat.py`, not by Streamlit.

---

## Runtime Files

| File | Purpose |
|---|---|
| `logs/dashboard.pid` | Dashboard PID |
| `logs/dashboard.log` | Streamlit stdout/stderr |
| `logs/dashboard_history.jsonl` | Dashboard command history |
| `logs/ai_model_config.json` | Active AI provider/model |
| `logs/ai_history.jsonl` | Conversation history |
| `logs/public_chat_config.json` | Public chat runtime config |
| `logs/public_chat.jsonl` | Public website chat history |
| `Kingofyadav/state.json` | HI state displayed by dashboard |
| `Jarvis/profiles.json` | AI/session profile displayed by dashboard |

---

## Networking

| Service | Bind |
|---|---|
| Streamlit dashboard | `127.0.0.1:8501` |
| API | `127.0.0.1:5050` unless explicitly configured |
| Public access | Nginx reverse proxy |

Do not expose Streamlit directly to the internet. Put Nginx, auth, and TLS in front of any public route.

---

## Dependencies

Installed from the repo root `requirements.txt`:

```text
streamlit
openai
anthropic
watchdog
rapidfuzz
fastapi
uvicorn
```

Optional voice dependencies:

```bash
pip install SpeechRecognition pyaudio
```

If microphone dependencies are missing, voice features are disabled while the rest of the dashboard remains available.

---

## Operations

```bash
bash scripts/status.sh
bash scripts/doctor.sh
tail -f logs/dashboard.log
tail -f logs/bus.log
```

When changing `.env`, restart the service:

```bash
systemctl --user restart jarvis-dashboard
```

---

## Troubleshooting

### "Authentication required" with no password prompt

`APP_ENV=production` is set but `DASHBOARD_PASSWORD` is blank or missing from `.env`. Set a strong password and restart:

```bash
grep DASHBOARD_PASSWORD .env
systemctl --user restart jarvis-dashboard
```

---

### Port 8501 already in use

A previous Streamlit process is still running. Find and stop it:

```bash
cat logs/dashboard.pid
kill $(cat logs/dashboard.pid)
bash scripts/start_dashboard.sh
```

---

### "Bridge not responding" or commands hang

The Kingofyadav listener is not running. Restart it:

```bash
python3 Kingofyadav/app.py &
# or
systemctl --user start jarvis-kingofyadav
```

---

### Voice page shows import error

Install the optional voice packages:

```bash
pip install SpeechRecognition pyaudio
```

Then test microphone detection:

```bash
python3 Jarvis/tools/mic_test.py
```

---

### Model selector shows no Ollama models

Ollama is not running or `OLLAMA_HOST` is wrong. Verify:

```bash
curl http://localhost:11434/api/tags
```

Start Ollama if needed, then refresh the model selector in the dashboard sidebar.

---

## Related Docs

- [Root Platform README](../README.md)
- [Jarvis Bridge](../Jarvis/README.md)
- [HI State Layer](../Kingofyadav/README.md)
- [FastAPI Web API](../web/README.md)
- [Automation Daemon](../automation/README.md)
- [Shared Transport](../shared/README.md)
