#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from state_manager import load_state, update_state

_VALID_STATUS = {"todo", "doing", "blocked", "done", "cancelled"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_id(title: str) -> str:
    digest = hashlib.sha256(title.strip().lower().encode("utf-8")).hexdigest()[:8]
    slug = "-".join(title.strip().lower().split())[:32] or "task"
    return f"{slug}-{digest}"


def _find_task(tasks: list[dict], task_id: str) -> dict | None:
    for task in tasks:
        if task.get("id") == task_id:
            return task
    return None


def get_workflow() -> dict:
    return load_state()["workflow"]


def update_focus(task: str) -> dict:
    def _mutate(state: dict) -> None:
        state["workflow"]["current_focus"] = task

    state = update_state(_mutate)
    return state["workflow"]


def add_task(
    title: str,
    *,
    due: str = "",
    estimate_minutes: int = 0,
    status: str = "todo",
    blockers: list[str] | None = None,
) -> dict:
    cleaned = title.strip()
    if not cleaned:
        return get_workflow()
    status = status.strip().lower()
    if status not in _VALID_STATUS:
        status = "todo"
    now = _utc_now()

    def _mutate(state: dict) -> None:
        tasks = state["workflow"].setdefault("tasks", [])
        task = {
            "id": _task_id(cleaned),
            "title": cleaned,
            "status": status,
            "due": due.strip(),
            "estimate_minutes": max(0, int(estimate_minutes or 0)),
            "blockers": blockers or [],
            "created_at": now,
            "updated_at": now,
        }
        existing = _find_task(tasks, task["id"])
        if existing:
            existing.update({**task, "created_at": existing.get("created_at", now)})
        else:
            tasks.append(task)
        if not state["workflow"].get("current_focus"):
            state["workflow"]["current_focus"] = cleaned

    state = update_state(_mutate)
    return state["workflow"]


def update_task_status(task_id: str, status: str) -> dict:
    cleaned_status = status.strip().lower()
    if cleaned_status not in _VALID_STATUS:
        return get_workflow()

    def _mutate(state: dict) -> None:
        task = _find_task(state["workflow"].setdefault("tasks", []), task_id.strip())
        if task:
            task["status"] = cleaned_status
            task["updated_at"] = _utc_now()

    state = update_state(_mutate)
    return state["workflow"]


def add_task_blocker(task_id: str, blocker: str) -> dict:
    cleaned = blocker.strip()
    if not cleaned:
        return get_workflow()

    def _mutate(state: dict) -> None:
        task = _find_task(state["workflow"].setdefault("tasks", []), task_id.strip())
        if task:
            blockers = task.setdefault("blockers", [])
            if cleaned not in blockers:
                blockers.append(cleaned)
            task["status"] = "blocked"
            task["updated_at"] = _utc_now()

    state = update_state(_mutate)
    return state["workflow"]


def update_task_due(task_id: str, due: str) -> dict:
    def _mutate(state: dict) -> None:
        task = _find_task(state["workflow"].setdefault("tasks", []), task_id.strip())
        if task:
            task["due"] = due.strip()
            task["updated_at"] = _utc_now()

    state = update_state(_mutate)
    return state["workflow"]


def _format_task(task: dict) -> str:
    due = f" due={task.get('due')}" if task.get("due") else ""
    estimate = f" estimate={task.get('estimate_minutes')}m" if task.get("estimate_minutes") else ""
    blockers = task.get("blockers") or []
    blocker_text = f" blockers={len(blockers)}" if blockers else ""
    return f"  {task.get('id')} [{task.get('status')}] {task.get('title')}{due}{estimate}{blocker_text}"


def get_workflow_summary(raw_payload: object = "") -> dict:
    workflow = get_workflow()
    tasks = workflow.get("tasks", [])
    open_tasks = [task for task in tasks if task.get("status") not in {"done", "cancelled"}]
    blocked_tasks = [task for task in tasks if task.get("status") == "blocked"]
    detail = f" Request context: {raw_payload}." if raw_payload not in ("", None, {}) else ""
    task_lines = "\n".join(_format_task(task) for task in open_tasks[:8])
    task_section = f"\nOpen tasks:\n{task_lines}" if task_lines else "\nOpen tasks: none"
    return {
        "text": (
            f"Workflow summary: status={workflow.get('status', 'ready')}, "
            f"current_focus={workflow.get('current_focus', '') or 'none'}, "
            f"tasks={len(tasks)}, open={len(open_tasks)}, blocked={len(blocked_tasks)}."
            f"{task_section}"
            f"{detail}"
        ),
        "args": {"module": "workflow", "view": "summary"},
    }
