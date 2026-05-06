#!/usr/bin/env python3
from __future__ import annotations

from state_manager import load_state, update_state


def get_preferences() -> dict:
    return load_state()["preferences"]


def set_preference(key: str, value: str) -> dict:
    def _mutate(state: dict) -> None:
        state["preferences"][key] = value

    state = update_state(_mutate)
    return state["preferences"]


def get_preferences_summary(raw_payload: object = "") -> dict:
    preferences = get_preferences()
    detail = f" Request context: {raw_payload}." if raw_payload not in ("", None, {}) else ""
    return {
        "text": (
            "Preferences summary: "
            f"response_style={preferences.get('response_style', 'structured')}, "
            f"local_execution={preferences.get('local_execution', 'preserve Jarvis local execution')}, "
            f"hi_routing={preferences.get('hi_routing', 'route human-interface topics through Kingofyadav')}."
            f"{detail}"
        ),
        "args": {"module": "preferences", "view": "summary"},
    }
