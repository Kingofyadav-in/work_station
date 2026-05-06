#!/usr/bin/env python3
from __future__ import annotations

import difflib
from typing import Any

from command_registry import build_exact_table
from plugin_loader import get_plugin_exact_table

try:
    from rapidfuzz import fuzz as _rfuzz
    from rapidfuzz import process as _rfprocess
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False

_FUZZY_CUTOFF_RAPIDFUZZ = 82   # token_sort_ratio score 0-100
_FUZZY_CUTOFF_DIFFLIB   = 0.74 # SequenceMatcher ratio 0-1


def normalize_intent(intent: str) -> str:
    return intent.strip().lower()


# ── exact-match table (derived from command_registry) ─────────────────────────
_EXACT: dict[str, tuple[str, Any]] = build_exact_table()


def _exact_table() -> dict[str, tuple[str, Any]]:
    return {**_EXACT, **get_plugin_exact_table()}

# ── prefix-match table ─────────────────────────────────────────────────────────
# Each entry: (prefix, action, value_validator_or_None)
# value_validator returns (action, payload) or raises ValueError with a message
def _require(value: str, label: str) -> str:
    if not value:
        raise ValueError(f"Empty {label}")
    return value


def _prefix_dispatch(prefix: str, action: str, payload_fn):
    return (prefix, action, payload_fn)


_PREFIX_RULES: list[tuple[str, str, Any]] = [
    _prefix_dispatch(
        "add memory ",
        "hi_memory_add",
        lambda v: {"entry": _require(v, "memory entry"), "source": "user"},
    ),
    _prefix_dispatch(
        "set current focus ",
        "hi_set_workflow_focus",
        lambda v: {"task": _require(v, "workflow focus")},
    ),
    _prefix_dispatch(
        "add task ",
        "hi_workflow_add_task",
        lambda v: {"title": _require(v, "task title")},
    ),
    _prefix_dispatch(
        "set task status ",
        "hi_workflow_set_task_status",
        lambda v: _parse_task_status(v),
    ),
    _prefix_dispatch(
        "block task ",
        "hi_workflow_add_blocker",
        lambda v: _parse_task_blocker(v),
    ),
    _prefix_dispatch(
        "set task due ",
        "hi_workflow_set_due",
        lambda v: _parse_task_due(v),
    ),
    _prefix_dispatch(
        "search memory ",
        "hi_memory_search",
        lambda v: {"query": _require(v, "search query")},
    ),
    _prefix_dispatch(
        "semantic memory ",
        "hi_memory_search",
        lambda v: {"query": _require(v, "semantic memory query")},
    ),
    _prefix_dispatch(
        "related memory ",
        "hi_memory_related",
        lambda v: {"memory_id": _require(v, "memory id")},
    ),
    _prefix_dispatch(
        "make memory public ",
        "hi_memory_visibility",
        lambda v: {"memory_id": _require(v, "memory id"), "visibility": "public"},
    ),
    _prefix_dispatch(
        "make memory private ",
        "hi_memory_visibility",
        lambda v: {"memory_id": _require(v, "memory id"), "visibility": "private"},
    ),
    _prefix_dispatch(
        "delete memory ",
        "hi_memory_delete",
        lambda v: {"memory_id": _require(v, "memory id")},
    ),
    _prefix_dispatch(
        "set my name ",
        "hi_set_profile_field",
        lambda v: {"field": "name", "value": _require(v, "human name")},
    ),
    _prefix_dispatch(
        "set my language ",
        "hi_set_profile_field",
        lambda v: {"field": "language", "value": _require(v, "human language")},
    ),
    _prefix_dispatch(
        "set my domain ",
        "hi_set_domain",
        lambda v: {
            "domain": _require(v, "human domain"),
            "website": f"https://{v}" if not v.startswith("http") else v,
        },
    ),
    _prefix_dispatch(
        "set my website ",
        "hi_set_profile_field",
        lambda v: {"field": "website", "value": _require(v, "website URL")},
    ),
    _prefix_dispatch(
        "set ai name ",
        "set_ai_name",
        lambda v: _require(v, "AI name"),
    ),
    _prefix_dispatch(
        "set intro mode ",
        "set_intro_mode",
        lambda v: _require(v, "intro mode"),
    ),
    _prefix_dispatch(
        "set command style ",
        "set_command_style",
        lambda v: _require(v, "command style"),
    ),
    _prefix_dispatch(
        "set mic device ",
        "set_mic_device",
        lambda v: _require(v, "microphone device"),
    ),
    _prefix_dispatch(
        "set wake phrase ",
        "set_wake_phrase",
        lambda v: _require(v, "wake phrase"),
    ),
    _prefix_dispatch(
        "register device ",
        "register_device",
        lambda v: _require(v, "device label"),
    ),
    _prefix_dispatch(
        "auto detect device ",
        "auto_detect_device",
        lambda v: _require(v, "device label"),
    ),
    _prefix_dispatch(
        "set response mode ",
        "hi_set_preference",
        lambda v: {"key": "response_mode", "value": _require(v, "response mode").lower()},
    ),
    _prefix_dispatch(
        "ask ",
        "ai",
        lambda v: _require(v, "AI prompt"),
    ),
    _prefix_dispatch(
        "ai ",
        "ai",
        lambda v: _require(v, "AI prompt"),
    ),
    _prefix_dispatch(
        "plan ",
        "plan",
        lambda v: _require(v, "planning prompt"),
    ),
    _prefix_dispatch(
        "run ",
        "shell",
        lambda v: _require(v, "shell command"),
    ),
]


def _parse_task_status(value: str) -> dict[str, str]:
    parts = value.strip().split()
    if len(parts) < 2:
        raise ValueError("Task status needs: <task_id> <status>")
    return {"task_id": parts[0], "status": parts[1]}


def _parse_task_blocker(value: str) -> dict[str, str]:
    task_id, sep, blocker = value.strip().partition(" ")
    if not sep or not task_id.strip() or not blocker.strip():
        raise ValueError("Task blocker needs: <task_id> <blocker>")
    return {"task_id": task_id.strip(), "blocker": blocker.strip()}


def _parse_task_due(value: str) -> dict[str, str]:
    task_id, sep, due = value.strip().partition(" ")
    if not sep or not task_id.strip() or not due.strip():
        raise ValueError("Task due date needs: <task_id> <due>")
    return {"task_id": task_id.strip(), "due": due.strip()}


_EXACT_KEYS: list[str] = []  # populated after _EXACT is defined (see bottom of module)


def _fuzzy_match_intent(normalized: str) -> tuple[str, Any] | None:
    """Fuzzy-match against exact-match keys. Returns None if no confident match."""
    if not normalized:
        return None
    exact = _exact_table()
    exact_keys = [k for k in exact if k]
    if _HAS_RAPIDFUZZ:
        match = _rfprocess.extractOne(
            normalized,
            exact_keys,
            scorer=_rfuzz.token_sort_ratio,
            score_cutoff=_FUZZY_CUTOFF_RAPIDFUZZ,
        )
        if match:
            return exact[match[0]]
    else:
        matches = difflib.get_close_matches(normalized, exact_keys, n=1, cutoff=_FUZZY_CUTOFF_DIFFLIB)
        if matches:
            return exact[matches[0]]
    return None


def interpret_intent(intent: str) -> tuple[str, Any]:
    normalized = normalize_intent(intent)

    exact = _exact_table()
    if normalized in exact:
        return exact[normalized]

    for prefix, action, payload_fn in _PREFIX_RULES:
        if normalized.startswith(prefix):
            raw_value = intent.strip()[len(prefix):]
            try:
                payload = payload_fn(raw_value)
            except ValueError as exc:
                return "error", str(exc)
            return action, payload

    # Fuzzy fallback — catches typos and alternate phrasing before sending to AI
    fuzzy = _fuzzy_match_intent(normalized)
    if fuzzy is not None:
        return fuzzy

    return "ai", normalized


# Populate after _EXACT is fully defined
_EXACT_KEYS = [k for k in _EXACT if k]  # exclude empty-string key (identity default)
