#!/usr/bin/env python3
from __future__ import annotations

import os
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from actions import execute_action
from behavior import apply_behavior_to_text, build_behavior_rules
from intent_parser import normalize_intent
from profile_manager import (
    bulk_update_session,
    clear_pending_confirmation,
    get_session,
    load_profiles,
    update_session_field,
)
from system_info import get_system_info

_HOSTNAME = socket.gethostname()

_ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(_ROOT_DIR / "shared"))
from event_journal import append_event  # noqa: E402
from message_bus import MessageBus  # noqa: E402

_KINGOFYADAV_PID = _ROOT_DIR / "logs" / "kingofyadav.pid"
_CONFIRM_TTL_SECONDS = 300  # 5 minutes


def _hi_listener_running() -> bool:
    try:
        pid = int(_KINGOFYADAV_PID.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True  # process exists but is owned by another user
    except ProcessLookupError:
        try:
            # In sandboxed or containerized shells, a host-side pid may be
            # invisible even though the listener is running. Trust only a
            # freshly written pid file; stale files still fail fast.
            age = datetime.now(timezone.utc).timestamp() - _KINGOFYADAV_PID.stat().st_mtime
            return age < 300
        except Exception:
            return False
    except (FileNotFoundError, ValueError):
        return False


# Keep this set in sync with Kingofyadav/handler.py handle_request().
# Any intent missing here routes locally instead of to the HI listener.
HI_INTENTS = {
    "hi_get_profile",
    "hi_get_intro",
    "hi_get_relationship",
    "hi_get_preferences",
    "hi_get_memory",
    "hi_memory_search",
    "hi_memory_related",
    "hi_memory_visibility",
    "hi_get_workflow",
    "hi_set_profile_field",
    "hi_set_preference",
    "hi_set_workflow_focus",
    "hi_workflow_add_task",
    "hi_workflow_set_task_status",
    "hi_workflow_add_blocker",
    "hi_workflow_set_due",
    "hi_memory_add",
    "hi_set_domain",
}


def send_hi_request(intent: str, raw_payload: Any = "", *, text: str = "") -> str:
    if not _hi_listener_running():
        return (
            "HI listener is offline.\n"
            f"Start it with: python3 {_ROOT_DIR / 'Kingofyadav' / 'app.py'}"
        )
    bus = MessageBus(actor="Jarvis")
    req = bus.send_request(
        intent=intent,
        target="Kingofyadav",
        payload={
            "text": text or intent,
            "args": {"raw_payload": raw_payload},
        },
        meta={"origin": "router.py"},
    )
    response = bus.wait_for_response(req["request_id"], timeout=10)
    if response is None:
        return "HI layer did not respond."
    payload = response.get("payload", {})
    return payload.get("text", str(payload))


def _record_action_event(action: str, command: str, route: str) -> None:
    append_event(
        source="Jarvis",
        event_type="action_completed",
        payload={"action": action, "command": command, "route": route},
    )


def _success_response(
    normalized: str,
    action: str,
    payload: Any,
    result: str,
    behavior: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": True,
        "intent": normalized,
        "action": action,
        "payload": payload,
        "result": result,
        "error": None,
        "behavior": behavior,
    }


def _error_response(
    normalized: str,
    action: str,
    payload: Any,
    error: str,
    behavior: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": False,
        "intent": normalized,
        "action": action,
        "payload": payload,
        "result": None,
        "error": error,
        "behavior": behavior,
    }


def process_intent(intent: str, action: str, payload: Any) -> dict[str, Any]:
    normalized = normalize_intent(intent)
    profiles = load_profiles()
    session = get_session()
    behavior = build_behavior_rules(profiles, session, intent, action=action, payload=str(payload))

    if action == "error":
        update_session_field("last_intent", normalized)
        update_session_field("last_command", intent)
        return _error_response(normalized, action, payload, str(payload), behavior)

    if action == "unknown":
        error_text = apply_behavior_to_text(
            text=f"Unknown intent: {payload}",
            ok=False,
            action=action,
            behavior=behavior,
        )
        update_session_field("last_intent", normalized)
        update_session_field("last_action", action)
        update_session_field("last_command", intent)
        return _error_response(normalized, action, payload, str(error_text), behavior)

    if action == "confirm":
        session = get_session()
        pending_action = session.get("pending_action", "")
        pending_payload = session.get("pending_payload", "")
        pending_command = session.get("pending_command", "")
        pending_since = session.get("pending_since", "")
        if not pending_action:
            return _error_response(normalized, action, "", "No pending action to confirm.", behavior)
        if pending_since:
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(pending_since)).total_seconds()
                if age > _CONFIRM_TTL_SECONDS:
                    clear_pending_confirmation()
                    return _error_response(normalized, action, "", "Pending confirmation expired (5 min). Re-run the command.", behavior)
            except Exception:
                pass
        action = pending_action
        payload = pending_payload
        intent = pending_command or intent
        normalized = normalize_intent(intent)
        clear_pending_confirmation()
        profiles = load_profiles()
        session = get_session()
        behavior = build_behavior_rules(profiles, session, intent, action=action, payload=str(payload))
    elif behavior["requires_confirmation"]:
        update_session_field("pending_action", action)
        update_session_field("pending_payload", payload)
        update_session_field("pending_command", intent)
        update_session_field("pending_since", datetime.now(timezone.utc).isoformat())
        update_session_field("last_intent", normalized)
        update_session_field("last_command", intent)
        update_session_field("last_risk_tier", behavior["risk_tier"])
        return _error_response(
            normalized,
            "confirmation_required",
            payload,
            (
                f"Confirmation required for {behavior['risk_tier']}-risk action. "
                "Run `confirm` to execute or `cancel` to discard."
            ),
            behavior,
        )

    try:
        route = "hi" if action in HI_INTENTS else "local"
        if route == "hi":
            result = send_hi_request(action, payload, text=intent)
            if result == "HI layer did not respond." or str(result).startswith("HI listener is offline."):
                update_session_field("last_intent", normalized)
                update_session_field("last_action", action)
                update_session_field("last_command", intent)
                update_session_field("last_risk_tier", behavior["risk_tier"])
                return _error_response(normalized, action, payload, result, behavior)
        else:
            result = execute_action(action, payload)

        result = apply_behavior_to_text(text=result, ok=True, action=action, behavior=behavior) or ""
        session_updates = {
            "last_intent": normalized,
            "last_action": action,
            "last_command": intent,
            "last_risk_tier": behavior["risk_tier"],
            "device_name": _HOSTNAME,
        }
        if result and not str(result).startswith("Refused:") and not str(result).startswith("Unknown action:"):
            session_updates["last_successful_action"] = action
        bulk_update_session(session_updates)
        _record_action_event(action, intent, route)
        return _success_response(normalized, action, payload, result, behavior)
    except Exception as exc:
        bulk_update_session({
            "last_intent": normalized,
            "last_action": action,
            "last_command": intent,
            "last_risk_tier": behavior["risk_tier"],
        })
        return _error_response(
            normalized,
            action,
            payload,
            str(apply_behavior_to_text(text=str(exc), ok=False, action=action, behavior=behavior)),
            behavior,
        )
