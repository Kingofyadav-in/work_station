# Jarvis Dashboard

Streamlit operator dashboard for the Jarvis Platform. It is the private control panel for commands, HI state, trusted-device status, system health, workflow, memory, conversation, and public website chat settings.

The dashboard calls the same Jarvis bridge used by the CLI. It does not maintain a separate command path.

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

## Authentication

When `APP_ENV=production`, `DASHBOARD_PASSWORD` must be set in `.env`.

```bash
APP_ENV=production
DASHBOARD_PASSWORD=change-this-dashboard-password
```

Session auth is persisted to `logs/dashboard_session.json` with a 24-hour TTL. Browser refresh does not re-prompt for the password within that window. Without `DASHBOARD_PASSWORD` in production mode, the dashboard locks before rendering any page.

## Manual Runtime

```bash
cd app
python3 -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## Page Architecture

| Page | File | Purpose |
|---|---|---|
| Home | `app.py` | Command console, state summary, alerts, quick status |
| Identity | `pages/1_Identity.py` | Profile, relationship, intro, identity commands |
| Device | `pages/2_Device.py` | Trusted-device registration and inventory tabs |
| System | `pages/3_System.py` | Host status, logs, doctor health, system commands |
| Work | `pages/4_Work.py` | Current focus, workflow tasks, task actions |
| Memory | `pages/5_Memory.py` | Search, filters, memory cards, public/private visibility |
| Security | `pages/6_Security.py` | Confirmation status, response mode, sensitive state controls |
| Conversation | `pages/7_Conversation.py` | AI conversation with provider/model selection |
| Public Jarvis | `pages/8_Public_Jarvis.py` | Website chat config, test chat, knowledge, recent questions |
| Public Inbox | `pages/9_Public_Inbox.py` | Website enquiries, access requests, and public chat review |
| Local Admins | `pages/10_Local_Admins.py` | Synced browser-local admin accounts, hashes, and latest activity |

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

## Networking

| Service | Bind |
|---|---|
| Streamlit dashboard | `127.0.0.1:8501` |
| API | `127.0.0.1:5050` unless explicitly configured |
| Public access | Nginx reverse proxy |

Do not expose Streamlit directly to the internet. Put Nginx, auth, and TLS in front of any public route.

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
