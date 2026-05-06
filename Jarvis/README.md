# Jarvis Bridge

Jarvis is the command bridge for the platform. It accepts user input from CLI, dashboard, voice, and API callers; turns natural language into a canonical action; applies risk behavior; and routes work either to local handlers or to the Kingofyadav HI layer.

## Runtime Flow

```text
input text
   |
   v
bridge.py
   |
   v
intent_parser.py  -> exact aliases, prefix commands, fuzzy fallback
   |
   v
router.py         -> risk profile, confirmation gate, route selection
   |
   +--> actions.py / ai_connector.py       local action
   |
   +--> shared.message_bus.MessageBus      HI intent
             |
             v
        Kingofyadav listener
```

Unknown phrases are routed to AI automatically, so conversational prompts still work even when they do not match a registered command.

## Key Files

| File | Responsibility |
|---|---|
| `bridge.py` | CLI entry point, JSON/text formatting, streaming option |
| `command_registry.py` | Single source of truth for commands, aliases, categories, and risk tiers |
| `intent_parser.py` | Exact, prefix, and fuzzy command parsing |
| `router.py` | Confirmation gate, local vs HI routing, event recording |
| `actions.py` | Local command handlers: status, device, shell, settings, apps, help |
| `ai_connector.py` | OpenAI, Anthropic, and Ollama calls; model config; prompt context; history |
| `behavior.py` | Risk metadata, repeated-command behavior, response shaping |
| `profile_manager.py` | AI profile and session persistence with HI overlay from `state.json` |
| `device_registry.py` | Trusted-device inventory and verification |
| `voice_input.py` | Speech recognition, wake phrase loop, text passthrough mode |
| `plugin_loader.py` | Drop-in command plugins from `Jarvis/skills/*.py` |
| `intro_app.py` | Tkinter desktop control surface |
| `tools/mic_test.py` | Microphone discovery and capture testing |

## Running Commands

From the repo root:

```bash
python3 Jarvis/bridge.py "status"
python3 Jarvis/bridge.py "profile"
python3 Jarvis/bridge.py "ask explain the bus architecture"
python3 Jarvis/bridge.py --json "status"
python3 Jarvis/bridge.py --no-stream "ask summarize my current focus"
```

From inside `Jarvis/`:

```bash
python3 bridge.py "commands"
python3 bridge.py "device report"
```

## Command Categories

Commands are declared in `command_registry.py`. Use this command for the live list:

```bash
python3 Jarvis/bridge.py "commands"
```

### Info

```bash
status
context
system info
system summary
logs
time
ai status
commands
```

### Device

```bash
register device primary laptop
device report
device inventory
hardware report
software report
network report
environment report
```

### Identity and HI State

```bash
who are you
who am i
identity
profiles
profile
human intro
relationship
hi summary
preferences
workflow
memory
domain
website status
```

### Memory

```bash
add memory <note>
search memory <query>
semantic memory <query>
related memory <memory_id>
make memory public <memory_id>
make memory private <memory_id>
```

### Workflow

```bash
set current focus <task>
add task <title>
set task status <task_id> <todo|doing|blocked|done|cancelled>
block task <task_id> <reason>
set task due <task_id> <date-or-text>
```

### Session and Preferences

```bash
show session
last command
last action
confirmation status
reset session
set response mode <adaptive|concise|detailed>
set ai name <name>
set intro mode <short|normal|formal>
set command style <natural|structured>
set mic device <index>
set wake phrase <phrase>
```

### AI

```bash
ask <question>
ai <question>
plan <topic>
```

### Apps and System Controls

```bash
open terminal
open chrome
open files
battery status
disk status
lock screen
volume up
volume down
mute
```

### Shell

```bash
run pwd
run whoami
run date
run uname -a
run ls -la
confirm
cancel
```

Shell execution is intentionally narrow. Commands outside the allowlist or paths outside the workspace are refused.

## HI Routing Contract

The router sends these actions to Kingofyadav through the message bus:

```text
hi_get_profile
hi_get_intro
hi_get_relationship
hi_get_preferences
hi_get_memory
hi_memory_search
hi_memory_related
hi_memory_visibility
hi_get_workflow
hi_set_profile_field
hi_set_preference
hi_set_workflow_focus
hi_workflow_add_task
hi_workflow_set_task_status
hi_workflow_add_blocker
hi_workflow_set_due
hi_memory_add
hi_set_domain
```

All other registered actions are handled locally by `actions.py` or plugins.

## Risk Model

| Tier | Examples | Behavior |
|---|---|---|
| `low` | Reads, status, AI, device reports | Runs immediately |
| `medium` | Profile, memory, workflow, session settings | Runs immediately and records state changes |
| `high` | Shell commands | Stored as pending until `confirm` |

Pending confirmations expire after 5 minutes. `cancel` clears the pending command.

## AI Connector

Provider config is read from environment and `logs/ai_model_config.json`. Ollama is the local-first default — no API key required.

| Provider | Environment |
|---|---|
| Ollama | `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT` |
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| Anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |

Every AI request includes:

- Runtime context from `context.py`.
- HI state from `Kingofyadav/state.json`.
- Recent memory and workflow focus.
- Recent activity log lines.
- Conversation history from `logs/ai_history.jsonl`.
- Response mode and command style.

## Voice

```bash
python3 Jarvis/voice_input.py --text "status"
python3 Jarvis/voice_input.py
python3 Jarvis/voice_input.py --loop
python3 Jarvis/voice_input.py --loop --no-wake-phrase
python3 Jarvis/voice_input.py --json
python3 Jarvis/voice_input.py --device-index 2
```

Find microphone devices:

```bash
python3 Jarvis/tools/mic_test.py
```

Voice needs `SpeechRecognition` and, for microphone capture, `pyaudio`. If those packages are unavailable, the rest of Jarvis continues to work.

## Plugins

Put local command plugins in `Jarvis/skills/*.py`. A plugin declares `ACTIONS`, aliases, a risk tier, and a handler. See [`skills/README.md`](skills/README.md).

## Session State

Jarvis stores session data in `profiles.json` under `session`:

| Field | Purpose |
|---|---|
| `last_command` | Raw last command |
| `last_intent` | Normalized command text |
| `last_action` | Canonical action name |
| `last_successful_action` | Last completed action |
| `last_risk_tier` | Risk tier for the last action |
| `pending_action` | High-risk action waiting for confirmation |
| `pending_payload` | Payload for pending action |
| `pending_command` | Original pending command text |
| `pending_since` | Pending timestamp |
| `device_name` | Current host |

HI identity fields are overlaid from `Kingofyadav/state.json` on load so profile data does not drift.

## Tests

From the repo root:

```bash
python3 -m unittest discover -s Jarvis/tests -t . -v
```

Coverage includes command parsing, route selection, risk behavior, shell safety, plugin loading, profile/session persistence, voice fallback logic, and event journal writes.
