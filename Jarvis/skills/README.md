# Jarvis Skills

> Drop-in command extension system — add a `.py` file to this directory, declare `ACTIONS`, and the command is live at next startup.

![Plugin system](https://img.shields.io/badge/plugins-auto--loaded-blue)
![Risk tiers](https://img.shields.io/badge/risk_tiers-low%20%7C%20medium%20%7C%20high-yellow)

Local plugin directory for Jarvis command extensions. Each `*.py` file in this directory can register one or more local actions. Plugins are loaded by `Jarvis/plugin_loader.py`, merged into intent parsing, included in help output, and executed by `actions.py`.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Plugin Contract](#plugin-contract)
- [Risk Tiers](#risk-tiers)
- [Examples](#examples)
  - [Minimal Plugin](#minimal-plugin)
  - [Plugin with Payload Parsing](#plugin-with-payload-parsing)
  - [Multi-Action Plugin](#multi-action-plugin)
  - [Workflow-Aware Plugin](#workflow-aware-plugin)
- [Testing Your Plugin](#testing-your-plugin)
- [Development Checklist](#development-checklist)
- [Plugin vs Core Command](#plugin-vs-core-command)
- [Payload Commands](#payload-commands)
- [Development Rules](#development-rules)
- [Related Docs](#related-docs)

---

## How It Works

1. At startup, `Jarvis/plugin_loader.py` scans every `*.py` file in this directory.
2. It imports each module and reads the `ACTIONS` list.
3. Each action's `aliases` are merged into the intent parser alongside built-in commands.
4. When a user input matches an alias, `actions.py` calls the declared `handler` function.
5. The handler receives the remaining payload text as a `str` and returns a `str` result.
6. The result is displayed or returned through whichever interface called it (CLI, dashboard, API, voice).

No registration file is needed — the file's presence is enough.

---

## Plugin Contract

A plugin exposes an `ACTIONS` list. Each action declares:

| Field | Required | Purpose |
|---|---|---|
| `action` | yes | Unique canonical action name (used in logs and routing) |
| `aliases` | yes | Exact phrases that trigger the action |
| `description` | yes | Help text shown in `commands` output |
| `risk_tier` | yes | `low`, `medium`, or `high` |
| `handler` | yes | Function name in the same module |

---

## Risk Tiers

| Tier | Meaning |
|---|---|
| `low` | Read-only or harmless local output |
| `medium` | Changes local state or preferences |
| `high` | Potentially destructive or external side effects; requires `confirm` |

High-risk plugin actions use the same pending-confirmation flow as built-in shell commands. The user must type `confirm` before the handler executes.

---

## Examples

### Minimal Plugin

```python
# Jarvis/skills/hello.py

ACTIONS = [
    {
        "action": "hello_world",
        "aliases": ["hello", "hello world"],
        "description": "Returns a greeting.",
        "risk_tier": "low",
        "handler": "run",
    }
]


def run(payload: str) -> str:
    return "Hello from the skills directory."
```

Run it:

```bash
python3 Jarvis/bridge.py "hello"
```

---

### Plugin with Payload Parsing

```python
# Jarvis/skills/note.py

ACTIONS = [
    {
        "action": "quick_note",
        "aliases": ["note"],
        "description": "Echo a quick note back to the screen.",
        "risk_tier": "low",
        "handler": "run",
    }
]


def run(payload: str) -> str:
    if not payload.strip():
        return "Usage: note <your text>"
    return f"Noted: {payload.strip()}"
```

```bash
python3 Jarvis/bridge.py "note remember to check deployment logs"
# → Noted: remember to check deployment logs
```

---

### Multi-Action Plugin

One file can register multiple distinct actions:

```python
# Jarvis/skills/timer.py

ACTIONS = [
    {
        "action": "timer_start",
        "aliases": ["start timer"],
        "description": "Record a start timestamp.",
        "risk_tier": "medium",
        "handler": "start",
    },
    {
        "action": "timer_stop",
        "aliases": ["stop timer"],
        "description": "Report elapsed time since start.",
        "risk_tier": "low",
        "handler": "stop",
    },
]

import time

_start: float = 0.0


def start(payload: str) -> str:
    global _start
    _start = time.time()
    return "Timer started."


def stop(payload: str) -> str:
    if _start == 0.0:
        return "Timer was not started."
    elapsed = time.time() - _start
    return f"Elapsed: {elapsed:.1f}s"
```

---

### Workflow-Aware Plugin

Read current HI state to enrich output:

```python
# Jarvis/skills/focus_summary.py

import json
from pathlib import Path

ACTIONS = [
    {
        "action": "focus_summary",
        "aliases": ["focus summary", "what am i doing"],
        "description": "Show current focus from workflow state.",
        "risk_tier": "low",
        "handler": "run",
    }
]

_STATE = Path("Kingofyadav/state.json")


def run(payload: str) -> str:
    try:
        state = json.loads(_STATE.read_text())
        focus = state.get("workflow", {}).get("current_focus", "not set")
        return f"Current focus: {focus}"
    except Exception as exc:
        return f"Could not read state: {exc}"
```

---

## Testing Your Plugin

```bash
# 1. Activate the virtual environment
source .venv/bin/activate

# 2. Run the command
python3 Jarvis/bridge.py "my command"

# 3. Verify it appears in the help list
python3 Jarvis/bridge.py "commands"

# 4. Run unit tests
python3 -m unittest Jarvis/tests/test_my_skill.py -v
```

Minimal test file pattern:

```python
# Jarvis/tests/test_my_skill.py
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from Jarvis.skills.my_skill import run


class TestMySkill(unittest.TestCase):
    def test_basic(self):
        result = run("")
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


if __name__ == "__main__":
    unittest.main()
```

---

## Development Checklist

Before shipping a skill as part of the product:

- [ ] Action name is unique — check `Jarvis/command_registry.py` and all other `skills/*.py`
- [ ] Handler always returns a plain `str` (never `None`, never raises uncaught exceptions)
- [ ] Risk tier matches what the handler actually does
- [ ] `SpeechRecognition pyaudio` — voice page shows error → install optional packages
- [ ] `python3 -m ruff check Jarvis/skills/my_skill.py` passes with no errors
- [ ] Test file added under `Jarvis/tests/test_<skill_name>.py`
- [ ] All test suites still pass: `python3 -m unittest discover -s Jarvis/tests -t . -v`

---

## Plugin vs Core Command

| Use a plugin when | Use a core command when |
|---|---|
| The command is personal / machine-specific | The command belongs to the platform itself |
| You want to iterate quickly without touching core files | It mutates HI state (profile, memory, workflow) |
| The command is experimental or local-only | It needs to appear in the official command registry |

HI state mutations must go through `Jarvis/command_registry.py`, `Jarvis/actions.py`, and `Kingofyadav/handler.py`. A skill cannot write directly to `state.json`.

---

## Payload Commands

Plugin aliases are exact-match triggers. The text after the matching alias is passed as `payload` to the handler.

Example: alias `"note"`, input `"note finish the docs today"` → `payload = "finish the docs today"`.

Keep plugin trigger phrases narrow and explicit to avoid conflicts with fuzzy matching on built-in commands.

---

## Development Rules

- Keep action names unique across all skills and the core registry.
- Keep handlers deterministic and fast — no blocking network calls in `low` risk plugins.
- Avoid network or filesystem side effects in `low` risk plugins.
- Use `medium` for state changes and `high` for anything that can delete, overwrite, execute, publish, or spend money.
- Return plain text from handlers.
- Add tests under `Jarvis/tests/` when a plugin becomes part of the product, not just a local experiment.

---

## Related Docs

- [Jarvis Bridge](../README.md)
- [Contributing Guide](../../CONTRIBUTING.md)
- [Root Platform README](../../README.md)
