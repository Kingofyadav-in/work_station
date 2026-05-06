#!/usr/bin/env python3

from __future__ import annotations

from typing import Any

from command_registry import HIGH_RISK_ACTIONS, LOW_RISK_ACTIONS, MEDIUM_RISK_ACTIONS
from plugin_loader import get_plugin_risk_tier
from system_info import get_system_info


def _normalize_intent(intent: str) -> str:
    return intent.strip().lower()


def get_risk_profile(action: str, payload: str = "") -> dict[str, Any]:
    plugin_risk = get_plugin_risk_tier(action)
    if plugin_risk == "high":
        return {
            "tier": "high",
            "requires_confirmation": True,
            "reason": "Plugin action declared high risk.",
        }
    if plugin_risk == "medium":
        return {
            "tier": "medium",
            "requires_confirmation": False,
            "reason": "Plugin action changes local or assistant state.",
        }
    if plugin_risk == "low":
        return {
            "tier": "low",
            "requires_confirmation": False,
            "reason": "Plugin action declared low risk.",
        }

    if action in HIGH_RISK_ACTIONS:
        return {
            "tier": "high",
            "requires_confirmation": True,
            "reason": "Local shell execution changes or queries the machine directly.",
        }

    if action in MEDIUM_RISK_ACTIONS:
        return {
            "tier": "medium",
            "requires_confirmation": False,
            "reason": "This action changes Jarvis state or preferences.",
        }

    return {
        "tier": "low",
        "requires_confirmation": False,
        "reason": "This action only reads state or returns information.",
    }


def build_behavior_rules(
    profiles: dict[str, Any],
    session: dict[str, Any],
    current_intent: str,
    *,
    action: str,
    payload: str = "",
) -> dict[str, Any]:
    hi_profile = profiles.get("HI", {})
    normalized_intent = _normalize_intent(current_intent)
    previous_action = session.get("last_action", "")
    previous_intent = _normalize_intent(session.get("last_intent", ""))
    response_mode = hi_profile.get("preferred_response_mode", "adaptive")
    if response_mode not in {"adaptive", "concise", "detailed"}:
        response_mode = "adaptive"

    repeated_status = action == "status" and previous_action == "status"
    repeated_unknown = action == "unknown" and previous_action == "unknown"
    repeated_greeting = action == "greet_user" and previous_action == "greet_user"
    same_intent_repeat = normalized_intent and normalized_intent == previous_intent
    risk = get_risk_profile(action, payload)

    return {
        "response_mode": response_mode,
        "command_style": hi_profile.get("preferred_command_style", "natural"),
        "intro_mode": hi_profile.get("preferred_intro_mode", "normal"),
        "risk_tier": risk["tier"],
        "requires_confirmation": risk["requires_confirmation"],
        "risk_reason": risk["reason"],
        "repeated_status": repeated_status,
        "repeated_unknown": repeated_unknown,
        "repeated_greeting": repeated_greeting,
        "same_intent_repeat": same_intent_repeat,
        "suggest_help": repeated_unknown,
        "prefer_short_output": response_mode == "concise" or (response_mode == "adaptive" and repeated_status),
        "prefer_detailed_output": response_mode == "detailed",
    }


def _short_status_text() -> str:
    info = get_system_info()
    return (
        f"System healthy on {info['hostname']} | "
        f"{info['connectivity']} | "
        f"{info['local_time']}"
    )


def apply_behavior_to_text(
    *,
    text: str | None,
    ok: bool,
    action: str,
    behavior: dict[str, Any],
) -> str | None:
    if text is None:
        return None

    if ok and action == "status" and behavior.get("prefer_short_output"):
        return _short_status_text()

    if ok and action == "greet_user" and behavior.get("repeated_greeting"):
        return "Hello again. Ready for the next command."

    if not ok and action == "unknown" and behavior.get("suggest_help"):
        return (
            f"{text}\n"
            "Suggestions: try `status`, `system summary`, `who am i`, `who are you`, or `show session`."
        )

    return text
