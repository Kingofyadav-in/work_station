#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from memory import (
    add_memory,
    delete_memory_entry,
    export_memory_backup,
    get_graph_summary,
    get_knowledge_graph,
    get_memory_search_summary,
    get_memory_summary,
    get_related_memory_summary,
    import_memory_batch,
    link_memories,
    run_retention_policy,
    set_memory_visibility,
)
from preferences import get_preferences_summary, set_preference
from profile import get_hi_intro, get_profile_summary, get_relationship_summary, set_profile_field  # pyright: ignore[reportAttributeAccessIssue]
from workflow import add_task, add_task_blocker, get_workflow_summary, update_focus, update_task_due, update_task_status

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))
from event_journal import append_event  # noqa: E402


def _extract_payload(message: dict) -> Any:
    payload = message.get("payload", {})
    args = payload.get("args", {}) or {}
    return args.get("raw_payload", "")


def handle_request(message: dict) -> dict:
    intent = message.get("intent")
    raw_payload = _extract_payload(message)

    if intent == "hi_get_profile":
        return get_profile_summary(raw_payload)
    if intent == "hi_get_intro":
        return get_hi_intro(raw_payload)
    if intent == "hi_get_relationship":
        return get_relationship_summary(raw_payload)
    if intent == "hi_get_preferences":
        return get_preferences_summary(raw_payload)
    if intent == "hi_set_profile_field" and isinstance(raw_payload, dict):
        field = str(raw_payload.get("field", "")).strip()
        value = str(raw_payload.get("value", "")).strip()
        profile = set_profile_field(field, value)
        append_event("Kingofyadav", "profile_updated", {"field": field, "value": value})
        return {
            "text": f"Profile updated: {field}={profile.get(field, value)}",
            "args": {"module": "profile", "view": "update"},
        }
    if intent == "hi_set_preference" and isinstance(raw_payload, dict):
        key = str(raw_payload.get("key", "")).strip()
        value = str(raw_payload.get("value", "")).strip()
        set_preference(key, value)
        append_event("Kingofyadav", "preference_updated", {"key": key, "value": value})
        return {
            "text": f"Preference set: {key}={value}",
            "args": {"module": "preferences", "view": "update"},
        }
    if intent == "hi_get_memory":
        return get_memory_summary(raw_payload)
    if intent == "hi_memory_search":
        query = raw_payload.get("query", raw_payload) if isinstance(raw_payload, dict) else str(raw_payload)
        return get_memory_search_summary(str(query).strip())
    if intent == "hi_memory_related":
        memory_id = raw_payload.get("memory_id", raw_payload) if isinstance(raw_payload, dict) else str(raw_payload)
        return get_related_memory_summary(str(memory_id).strip())
    if intent == "hi_memory_visibility" and isinstance(raw_payload, dict):
        memory_id = str(raw_payload.get("memory_id", "")).strip()
        visibility = str(raw_payload.get("visibility", "")).strip()
        result = set_memory_visibility(memory_id, visibility)
        if not result.get("_error"):
            append_event("Kingofyadav", "memory_visibility_updated", {"memory_id": memory_id, "visibility": visibility})
        return result
    if intent == "hi_memory_add":
        entry = raw_payload.get("entry", raw_payload) if isinstance(raw_payload, dict) else raw_payload
        memory = add_memory(entry)
        append_event("Kingofyadav", "memory_added", {"entry": entry})
        return {
            "text": f"Memory stored. Total entries: {len(memory)}.",
            "args": {"module": "memory", "view": "append"},
        }
    if intent == "hi_memory_delete":
        memory_id = raw_payload.get("memory_id", raw_payload) if isinstance(raw_payload, dict) else str(raw_payload)
        result = delete_memory_entry(str(memory_id).strip())
        if not result.get("_error"):
            append_event("Kingofyadav", "memory_deleted", {"memory_id": memory_id})
        return result
    if intent == "hi_memory_graph":
        memory_id = raw_payload.get("memory_id", raw_payload) if isinstance(raw_payload, dict) else str(raw_payload)
        depth = int(raw_payload.get("depth", 2)) if isinstance(raw_payload, dict) else 2
        return get_knowledge_graph(str(memory_id).strip(), depth=depth)
    if intent == "hi_memory_link" and isinstance(raw_payload, dict):
        source_id = str(raw_payload.get("source_id", "")).strip()
        target_id = str(raw_payload.get("target_id", "")).strip()
        relation = str(raw_payload.get("relation", "related")).strip()
        result = link_memories(source_id, target_id, relation)
        if not result.get("_error"):
            append_event("Kingofyadav", "memory_linked", {"source_id": source_id, "target_id": target_id, "relation": relation})
        return result
    if intent == "hi_memory_graph_stats":
        return get_graph_summary()
    if intent == "hi_memory_retention":
        dry_run = bool(raw_payload.get("dry_run", False)) if isinstance(raw_payload, dict) else False
        result = run_retention_policy(dry_run=dry_run)
        if not dry_run:
            append_event("Kingofyadav", "memory_retention_applied", result.get("args", {}))
        return result
    if intent == "hi_memory_export":
        return export_memory_backup()
    if intent == "hi_memory_import" and isinstance(raw_payload, dict):
        entries = raw_payload.get("entries", [])
        if not isinstance(entries, list):
            return {"text": "Memory import failed: entries must be a list.", "_error": True}
        result = import_memory_batch(entries)
        append_event("Kingofyadav", "memory_imported", result.get("args", {}))
        return result
    if intent == "hi_get_workflow":
        return get_workflow_summary(raw_payload)
    if intent == "hi_set_workflow_focus" and isinstance(raw_payload, dict):
        task = str(raw_payload.get("task", "")).strip()
        workflow = update_focus(task)
        append_event("Kingofyadav", "workflow_updated", {"task": task})
        return {
            "text": f"Workflow updated: current_focus={workflow.get('current_focus', '') or 'none'}.",
            "args": {"module": "workflow", "view": "update"},
        }
    if intent == "hi_workflow_add_task" and isinstance(raw_payload, dict):
        title = str(raw_payload.get("title", "")).strip()
        due = str(raw_payload.get("due", "")).strip()
        try:
            estimate_minutes = int(raw_payload.get("estimate_minutes", 0) or 0)
        except (TypeError, ValueError):
            estimate_minutes = 0
        workflow = add_task(title, due=due, estimate_minutes=estimate_minutes)
        task = next((item for item in workflow.get("tasks", []) if item.get("title") == title), {})
        append_event("Kingofyadav", "workflow_task_added", {"title": title, "id": task.get("id", "")})
        return {
            "text": f"Workflow task added: {task.get('id', '')} {title}",
            "args": {"module": "workflow", "view": "task_add", "task": task},
        }
    if intent == "hi_workflow_set_task_status" and isinstance(raw_payload, dict):
        task_id = str(raw_payload.get("task_id", "")).strip()
        status = str(raw_payload.get("status", "")).strip()
        workflow = update_task_status(task_id, status)
        append_event("Kingofyadav", "workflow_task_status_updated", {"task_id": task_id, "status": status})
        return {
            "text": f"Workflow task status updated: {task_id} -> {status}",
            "args": {"module": "workflow", "view": "task_status", "workflow": workflow},
        }
    if intent == "hi_workflow_add_blocker" and isinstance(raw_payload, dict):
        task_id = str(raw_payload.get("task_id", "")).strip()
        blocker = str(raw_payload.get("blocker", "")).strip()
        workflow = add_task_blocker(task_id, blocker)
        append_event("Kingofyadav", "workflow_task_blocked", {"task_id": task_id, "blocker": blocker})
        return {
            "text": f"Workflow task blocker added: {task_id} -> {blocker}",
            "args": {"module": "workflow", "view": "task_blocker", "workflow": workflow},
        }
    if intent == "hi_workflow_set_due" and isinstance(raw_payload, dict):
        task_id = str(raw_payload.get("task_id", "")).strip()
        due = str(raw_payload.get("due", "")).strip()
        workflow = update_task_due(task_id, due)
        append_event("Kingofyadav", "workflow_task_due_updated", {"task_id": task_id, "due": due})
        return {
            "text": f"Workflow task due date updated: {task_id} -> {due}",
            "args": {"module": "workflow", "view": "task_due", "workflow": workflow},
        }
    if intent == "hi_set_domain" and isinstance(raw_payload, dict):
        domain = str(raw_payload.get("domain", "")).strip()
        website = str(raw_payload.get("website", "")).strip()
        if not domain and not website:
            return {
                "text": "Domain update failed: both domain and website are empty.",
                "args": {"status": "error", "module": "profile"},
                "_error": True,
            }
        if domain:
            set_profile_field("domain", domain)
            append_event("Kingofyadav", "profile_updated", {"field": "domain", "value": domain})
        if website:
            set_profile_field("website", website)
            append_event("Kingofyadav", "profile_updated", {"field": "website", "value": website})
        return {
            "text": f"Domain updated: domain={domain}, website={website}.",
            "args": {"module": "profile", "view": "update"},
        }

    return {
        "text": f"Unhandled intent: {intent}",
        "args": {"status": "unknown_intent", "layer": "HI", "intent": intent},
        "_error": True,
    }
