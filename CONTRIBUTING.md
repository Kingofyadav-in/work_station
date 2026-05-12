# Contributing to Jarvis Platform

## Quick orientation

Read the root `README.md` first — it has the architecture diagram, component map, and API reference.

The five main areas:

| Directory | What to touch |
|---|---|
| `Jarvis/` | New commands, intent parsing, AI connector, voice |
| `Kingofyadav/` | HI state mutations (profile, memory, workflow) |
| `shared/` | Bus, journal, schema — only touch if adding transport primitives |
| `automation/` | Scheduled jobs, rules, monitors, notifiers |
| `app/` | Dashboard pages and services |
| `web/` | FastAPI routes and WebSocket handlers |

---

## Adding a Jarvis skill (fastest path)

A skill is a plugin file in `Jarvis/skills/`. It is auto-loaded at startup.

**1. Create the file:**

```python
# Jarvis/skills/my_skill.py

ACTIONS = [
    {
        "action":      "my_skill_hello",
        "aliases":     ["my skill", "hello skill"],
        "description": "What this skill does.",
        "risk_tier":   "low",   # low | medium | high
        "handler":     "run",
    }
]

def run(payload: str) -> str:
    return "skill alive"
```

**2. Test it immediately:**

```bash
source .venv/bin/activate
python3 Jarvis/bridge.py "my skill"
```

**3. Add a test:**

```python
# Jarvis/tests/test_my_skill.py
import unittest, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))

from Jarvis.skills.my_skill import run

class TestMySkill(unittest.TestCase):
    def test_run(self):
        self.assertIn("alive", run(""))

if __name__ == "__main__":
    unittest.main()
```

**Risk tier rules:**

| Tier | Use when |
|---|---|
| `low` | Read-only output, no state change |
| `medium` | Changes local state or preferences |
| `high` | Deletes, overwrites, executes external commands, spends money — requires explicit `confirm` |

---

## Adding a core command

If the command is not a plugin (it belongs to the platform itself), register it in `Jarvis/command_registry.py` and add a handler in `Jarvis/actions.py`.

1. Add a `Command(...)` entry to `REGISTRY` in `command_registry.py`
2. Add a handler function in `actions.py` and wire it into `execute_action()`
3. If it mutates HI state, add the intent to `HI_INTENTS` in `router.py` and handle it in `Kingofyadav/handler.py`

---

## Running the test suites

```bash
source .venv/bin/activate

# All suites
python3 -m unittest discover -s Jarvis/tests   -t . -v
python3 -m unittest discover -s Kingofyadav/tests -v
python3 -m unittest discover -s shared/tests   -v
python3 -m unittest discover -s automation/tests -v

# Single file
python3 -m unittest Jarvis/tests/test_my_skill.py -v

# With coverage
python3 -m pytest Jarvis/tests/ --cov=Jarvis --cov-report=term-missing
```

---

## Adding an automation rule (Phase 4)

Rules live in `automation/rules.json`. Each rule has a trigger, optional conditions, and an action.

```json
{
  "id": "my_rule",
  "description": "What this rule does",
  "enabled": true,
  "trigger": {
    "type": "interval",
    "seconds": 300
  },
  "conditions": [
    {"type": "health_fail_count", "min": 1}
  ],
  "action": {
    "type": "notify",
    "channel": "log",
    "message": "Health check failed"
  }
}
```

Trigger types: `interval`, `cron`, `health_event`, `log_pattern`, `state_change`
Action types: `notify`, `command`, `restart_service`, `webhook`

---

## Code conventions

- No comments unless the WHY is non-obvious
- Return plain text from skill handlers
- Keep handlers fast and deterministic — no blocking network calls in `low` risk handlers
- Never edit `Kingofyadav/state.json` directly — use `state_manager.py`
- One writer per persistence file — check the table in README before adding a new writer
- All new modules go under the relevant top-level directory, not root

---

## Before submitting

```bash
bash scripts/doctor.sh
python3 -m ruff check .
python3 -m mypy Jarvis/ Kingofyadav/ shared/ automation/ --ignore-missing-imports
python3 -m unittest discover -s Jarvis/tests -t . -v
```
