#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any


DEFAULT_STATE: dict[str, Any] = {
    "profile": {
        "display_name": "King Yadav",
        "system_role": "primary human context",
        "owner_role": "human owner and decision-maker behind this workspace",
        "identity_summary": (
            "King Yadav is the primary human context for this system, "
            "with Jarvis acting as the local execution layer."
        ),
        "relationship": {
            "jarvis_role": "local execution and system operations",
            "hi_layer_role": "higher-level human interface layer",
        },
        "name": "kingofyadav",
        "domain": "AI systems",
        "language": "en",
    },
    "preferences": {
        "response_style": "structured",
        "local_execution": "preserve Jarvis local execution",
        "hi_routing": "route human-interface topics through Kingofyadav",
        "response_mode": "adaptive",
        "verbosity": "medium",
    },
    "memory": [],
    "workflow": {
        "current_focus": "",
        "status": "ready",
        "next_actions": [],
        "tasks": [],
    },
}


def _deepcopy_default() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_STATE))


_LEGACY_TS = "2026-01-01T00:00:00+00:00"  # placeholder for entries created before timestamps existed


def _extract_optional_fields(entry: dict) -> dict[str, Any]:
    """Pull supported metadata from an entry dict, returning only set values."""
    extras: dict[str, Any] = {}
    created_at = str(entry.get("created_at", "")).strip()
    if created_at:
        extras["created_at"] = created_at
    tag = str(entry.get("tag", "")).strip().lower()
    if tag:
        extras["tag"] = tag
    source = str(entry.get("source", "")).strip()
    if source:
        extras["source"] = source
    visibility = str(entry.get("visibility", "")).strip().lower()
    if visibility in {"private", "public"}:
        extras["visibility"] = visibility
    try:
        importance = int(entry.get("importance", ""))
        extras["importance"] = max(1, min(5, importance))
    except (TypeError, ValueError):
        pass
    return extras


def normalize_memory_entry(entry: Any) -> dict[str, Any] | None:
    if isinstance(entry, str):
        text = entry.strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return normalize_memory_entry(parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        return {"type": "note", "text": text}

    if not isinstance(entry, dict):
        return None

    extras = _extract_optional_fields(entry)
    entry_type = str(entry.get("type", "")).strip().lower()

    if entry_type == "note":
        text = str(entry.get("text", "")).strip()
        if not text:
            return None
        return {"type": "note", "text": text, **extras}

    if entry_type == "event" or "event" in entry or "command" in entry:
        event = str(entry.get("event", "")).strip()
        command = str(entry.get("command", "")).strip()
        if not event and not command:
            text_fallback = str(entry.get("text", "")).strip()
            if not text_fallback:
                return None
            event = text_fallback
        return {"type": "event", "event": event, "command": command, **extras}

    if entry_type in {"decision", "reminder", "insight"}:
        text = str(entry.get("text", "")).strip()
        if not text:
            return None
        return {"type": entry_type, "text": text, **extras}

    text = str(entry.get("text", "")).strip()
    if text:
        return {"type": "note", "text": text, **extras}

    return None


def normalize_memory(memory: Any) -> list[dict[str, Any]]:
    if not isinstance(memory, list):
        return []

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entry in memory:
        item = normalize_memory_entry(entry)
        if item is None:
            continue
        # Backfill created_at for legacy entries that predate the timestamp field
        if "created_at" not in item:
            item["created_at"] = _LEGACY_TS
        # Deduplicate by (type, primary text content) regardless of entry type
        primary = item.get("text", "") or item.get("event", "") or ""
        marker = f"{item.get('type')}:{primary}"
        if marker in seen:
            continue
        seen.add(marker)
        normalized.append(item)

    return normalized


def normalize_state(data: dict[str, Any] | None) -> dict[str, Any]:
    state = _deepcopy_default()
    data = data or {}

    profile = data.get("profile", {})
    if isinstance(profile, dict):
        state["profile"].update(profile)
        relationship = profile.get("relationship", {})
        if isinstance(relationship, dict):
            state["profile"]["relationship"].update(relationship)
    state["profile"]["display_name"] = str(state["profile"].get("display_name", "") or DEFAULT_STATE["profile"]["display_name"])
    state["profile"]["system_role"] = str(state["profile"].get("system_role", "") or DEFAULT_STATE["profile"]["system_role"])
    state["profile"]["owner_role"] = str(state["profile"].get("owner_role", "") or DEFAULT_STATE["profile"]["owner_role"])
    state["profile"]["identity_summary"] = str(
        state["profile"].get("identity_summary", "") or DEFAULT_STATE["profile"]["identity_summary"]
    )
    state["profile"]["name"] = str(state["profile"].get("name", "") or DEFAULT_STATE["profile"]["name"])
    state["profile"]["domain"] = str(state["profile"].get("domain", "") or DEFAULT_STATE["profile"]["domain"])
    state["profile"]["language"] = str(state["profile"].get("language", "") or DEFAULT_STATE["profile"]["language"])
    for _opt_field in ("website", "email", "brand"):
        if _opt_field in (data.get("profile") or {}):
            state["profile"][_opt_field] = str(data["profile"][_opt_field])
    state["profile"]["relationship"]["jarvis_role"] = str(
        state["profile"]["relationship"].get("jarvis_role", "") or DEFAULT_STATE["profile"]["relationship"]["jarvis_role"]
    )
    state["profile"]["relationship"]["hi_layer_role"] = str(
        state["profile"]["relationship"].get("hi_layer_role", "")
        or DEFAULT_STATE["profile"]["relationship"]["hi_layer_role"]
    )

    preferences = data.get("preferences", {})
    if isinstance(preferences, dict):
        state["preferences"].update(preferences)
    for key, default in DEFAULT_STATE["preferences"].items():
        state["preferences"][key] = str(state["preferences"].get(key, "") or default)

    memory = data.get("memory", [])
    state["memory"] = normalize_memory(memory)

    workflow = data.get("workflow", {})
    if isinstance(workflow, dict):
        state["workflow"].update(workflow)
    state["workflow"]["current_focus"] = str(state["workflow"].get("current_focus", "") or "")
    state["workflow"]["status"] = str(state["workflow"].get("status", "") or DEFAULT_STATE["workflow"]["status"])
    next_actions = state["workflow"].get("next_actions", [])
    state["workflow"]["next_actions"] = next_actions if isinstance(next_actions, list) else []
    tasks = state["workflow"].get("tasks", [])
    state["workflow"]["tasks"] = normalize_workflow_tasks(tasks)

    return state


def normalize_workflow_task(task: Any) -> dict[str, Any] | None:
    if not isinstance(task, dict):
        return None
    title = str(task.get("title", "")).strip()
    if not title:
        return None
    status = str(task.get("status", "todo")).strip().lower()
    if status not in {"todo", "doing", "blocked", "done", "cancelled"}:
        status = "todo"
    task_id = str(task.get("id", "")).strip()
    if not task_id:
        task_id = title.lower().replace(" ", "-")[:40]
    blockers = task.get("blockers", [])
    if isinstance(blockers, str):
        blockers = [blockers] if blockers.strip() else []
    if not isinstance(blockers, list):
        blockers = []
    return {
        "id": task_id,
        "title": title,
        "status": status,
        "due": str(task.get("due", "") or "").strip(),
        "estimate_minutes": _coerce_minutes(task.get("estimate_minutes", 0)),
        "blockers": [str(item).strip() for item in blockers if str(item).strip()],
        "created_at": str(task.get("created_at", "") or _LEGACY_TS),
        "updated_at": str(task.get("updated_at", "") or task.get("created_at", "") or _LEGACY_TS),
    }


def _coerce_minutes(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def normalize_workflow_tasks(tasks: Any) -> list[dict[str, Any]]:
    if not isinstance(tasks, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for task in tasks:
        item = normalize_workflow_task(task)
        if item is None or item["id"] in seen:
            continue
        seen.add(item["id"])
        normalized.append(item)
    return normalized
