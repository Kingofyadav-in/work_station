#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

SKILLS_DIR = Path(__file__).resolve().parent / "skills"
_ACTION_RE = re.compile(r"^[a-z][a-z0-9_]{2,64}$")
_VALID_RISK = {"low", "medium", "high"}


@dataclass(frozen=True)
class PluginCommand:
    action: str
    aliases: tuple[str, ...]
    description: str
    risk_tier: str
    category: str
    payload_hint: str
    handler: Callable[[str], Any]
    source: Path


def _load_module(path: Path) -> ModuleType | None:
    module_name = f"jarvis_skill_{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _coerce_aliases(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        aliases = [value]
    elif isinstance(value, (list, tuple)):
        aliases = [str(item) for item in value]
    else:
        aliases = []
    return tuple(alias.strip().lower() for alias in aliases if alias and alias.strip())


def _handler_from(module: ModuleType, raw: dict[str, Any]) -> Callable[[str], Any] | None:
    handler = raw.get("handler")
    if callable(handler):
        return handler
    if isinstance(handler, str):
        candidate = getattr(module, handler, None)
        return candidate if callable(candidate) else None
    candidate = getattr(module, "run", None)
    return candidate if callable(candidate) else None


def _command_from(module: ModuleType, path: Path, raw: dict[str, Any]) -> PluginCommand | None:
    action = str(raw.get("action", "")).strip()
    if not _ACTION_RE.match(action):
        return None
    aliases = _coerce_aliases(raw.get("aliases", ()))
    if not aliases:
        return None
    risk_tier = str(raw.get("risk_tier", "low")).strip().lower()
    if risk_tier not in _VALID_RISK:
        risk_tier = "low"
    handler = _handler_from(module, raw)
    if handler is None:
        return None
    return PluginCommand(
        action=action,
        aliases=aliases,
        description=str(raw.get("description", "Plugin action")).strip() or "Plugin action",
        risk_tier=risk_tier,
        category=str(raw.get("category", "plugins")).strip() or "plugins",
        payload_hint=str(raw.get("payload_hint", aliases[0])).strip() or aliases[0],
        handler=handler,
        source=path,
    )


def load_plugin_commands() -> dict[str, PluginCommand]:
    commands: dict[str, PluginCommand] = {}
    if not SKILLS_DIR.exists():
        return commands
    for path in sorted(SKILLS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            module = _load_module(path)
            if module is None:
                continue
            raw_actions = getattr(module, "ACTIONS", [])
            if callable(raw_actions):
                raw_actions = raw_actions()
            if isinstance(raw_actions, dict):
                raw_actions = [raw_actions]
            for raw in raw_actions if isinstance(raw_actions, list) else []:
                if not isinstance(raw, dict):
                    continue
                command = _command_from(module, path, raw)
                if command is not None:
                    commands[command.action] = command
        except Exception:
            continue
    return commands


def get_plugin_exact_table() -> dict[str, tuple[str, str]]:
    table: dict[str, tuple[str, str]] = {}
    for command in load_plugin_commands().values():
        for alias in command.aliases:
            table[alias] = (command.action, "")
    return table


def get_plugin_risk_tier(action: str) -> str | None:
    command = load_plugin_commands().get(action)
    return command.risk_tier if command else None


def get_plugin_action_names() -> set[str]:
    return set(load_plugin_commands())


def execute_plugin_action(action: str, payload: str = "") -> str | None:
    command = load_plugin_commands().get(action)
    if command is None:
        return None
    return str(command.handler(payload))


def format_plugin_help() -> str:
    commands = list(load_plugin_commands().values())
    if not commands:
        return ""
    lines = ["[PLUGINS]"]
    for command in sorted(commands, key=lambda item: item.action):
        trigger = command.payload_hint or command.aliases[0]
        lines.append(f"  {trigger:<42} {command.description}")
    return "\n".join(lines)
