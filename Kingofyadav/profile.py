#!/usr/bin/env python3
from __future__ import annotations

from state_manager import load_state, update_state


def _payload_detail(raw_payload: object) -> str:
    return f" Request context: {raw_payload}." if raw_payload not in ("", None, {}) else ""


def get_profile() -> dict:
    return load_state()["profile"]


def get_profile_summary(raw_payload: object = "") -> dict:
    profile = get_profile()
    detail = _payload_detail(raw_payload)
    return {
        "text": f"HI profile summary: {profile['identity_summary']}{detail}",
        "args": {"module": "profile", "view": "summary"},
    }


def set_profile_field(field: str, value: str) -> dict:
    def _mutate(state: dict) -> None:
        state["profile"][field] = value

    state = update_state(_mutate)
    return state["profile"]


def get_hi_intro(raw_payload: object = "") -> dict:
    profile = get_profile()
    detail = _payload_detail(raw_payload)
    return {
        "text": f"HI intro: {profile['display_name']} is the {profile['owner_role']}.{detail}",
        "args": {"module": "profile", "view": "hi_intro"},
    }


def get_relationship_summary(raw_payload: object = "") -> dict:
    profile = get_profile()
    relationship = profile.get("relationship", {})
    detail = _payload_detail(raw_payload)
    return {
        "text": (
            "Relationship model: Jarvis handles "
            f"{relationship.get('jarvis_role', 'local execution')}, while Kingofyadav provides the "
            f"{relationship.get('hi_layer_role', 'human interface layer')}.{detail}"
        ),
        "args": {"module": "profile", "view": "relationship"},
    }
