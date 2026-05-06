# Jarvis Skills

Local plugin directory for Jarvis command extensions.

Each `*.py` file in this directory can register one or more local actions. Plugins are loaded by `Jarvis/plugin_loader.py`, merged into intent parsing, included in help output, and executed by `actions.py`.

## Plugin Contract

A plugin exposes an `ACTIONS` list. Each action declares:

| Field | Required | Purpose |
|---|---|---|
| `action` | yes | Unique canonical action name |
| `aliases` | yes | Exact phrases that trigger the action |
| `description` | yes | Help text |
| `risk_tier` | yes | `low`, `medium`, or `high` |
| `handler` | yes | Function name in the same module |

Minimal plugin:

```python
ACTIONS = [
    {
        "action": "demo_plugin_echo",
        "aliases": ["demo plugin"],
        "description": "Echo from a plugin.",
        "risk_tier": "low",
        "handler": "run",
    }
]


def run(payload: str) -> str:
    return "plugin alive"
```

Run it:

```bash
python3 Jarvis/bridge.py "demo plugin"
```

## Risk Tiers

| Tier | Meaning |
|---|---|
| `low` | Read-only or harmless local output |
| `medium` | Changes local state or preferences |
| `high` | Potentially destructive or external side effects; requires `confirm` |

High-risk plugin actions use the same pending-confirmation flow as shell commands.

## Payload Commands

Plugin aliases are exact-match triggers. If a plugin needs free-form payload text, use a specific alias and parse the payload inside the handler after Jarvis passes it through.

Keep plugin commands narrow and explicit. Core platform commands should be added to `Jarvis/command_registry.py` instead.

## Development Rules

- Keep action names unique.
- Keep handlers deterministic and fast.
- Avoid network or filesystem side effects in `low` risk plugins.
- Use `medium` for state changes and `high` for anything that can delete, overwrite, execute, publish, or spend money.
- Return plain text from handlers.
- Add tests under `Jarvis/tests/` when a plugin becomes part of the product, not just a local experiment.
