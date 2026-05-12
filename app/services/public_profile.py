from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


PUBLIC_PROFILE: dict[str, Any] = {
    "display_name": "Amit Ku Yadav",
    "full_name": "Amit Ku Yadav",
    "name": "Amit",
    "username": "kingofyadav",
    "domain": "Digital identity, business systems, AI workflows, and social impact",
    "website": "https://kingofyadav.in",
    "brand": "kingofyadav.in",
    "company": "HI Life OS",
    "email": "kingofyadav.in@gmail.com",
    "phone": "+91 95235 28114",
    "location": "Bhagalpur, Bihar, India",
    "language": "en-IN",
    "auth_role": "primary owner",
    "system_role": "Founder, digital systems builder, and primary human operator",
    "owner_role": "human owner and decision-maker behind HI Life OS and kingofyadav.in",
    "identity_summary": (
        "Amit Ku Yadav is a digital systems builder from Bhagalpur working across "
        "HI Life OS, public identity, business platforms, community coordination, "
        "and AI-assisted operations."
    ),
    "relationship": {
        "jarvis_role": "local execution, dashboard operations, automation, and private system control",
        "hi_layer_role": "human identity layer for public profile, ventures, people, records, and decisions",
    },
    "ventures": [
        "HI Life OS",
        "kingofyadav.in Platform",
        "Royal Heritage Resort",
        "National Youth Force",
        "Jhon Aamit LLP",
    ],
    "public_channels": {
        "website": "https://kingofyadav.in",
        "github": "https://github.com/kingofyadav",
        "instagram": "https://www.instagram.com/kingofyadav.in",
        "facebook": "https://www.facebook.com/kingofyadav.in",
    },
}


PUBLIC_PREFERENCES: dict[str, str] = {
    "response_style": "structured, direct, professional",
    "local_execution": "preserve Jarvis local execution",
    "hi_routing": "route identity, people, ventures, and public website context through HI Life OS",
    "response_mode": "operator",
    "verbosity": "medium",
    "language": "English with India context",
    "privacy": "private dashboard data stays local; public website data can be used as profile context",
}


PUBLIC_WORKFLOW: dict[str, Any] = {
    "current_focus": "restore HI Life OS dashboard data and keep kingofyadav.in public profile world-class",
    "status": "active",
    "next_actions": [
        "Verify identity, contact, ventures, and public profile facts on the dashboard.",
        "Back up private dashboard state after every major update.",
        "Keep website public pages aligned with current work and services.",
        "Use Jarvis to review daily focus, risks, and follow-ups.",
    ],
    "tasks": [
        {
            "id": "restore-dashboard-profile",
            "title": "Restore complete public identity profile in Jarvis dashboard",
            "status": "doing",
            "due": "",
            "estimate_minutes": 45,
            "blockers": [],
            "created_at": "2026-05-12T00:00:00+00:00",
            "updated_at": "2026-05-12T00:00:00+00:00",
        },
        {
            "id": "backup-hi-state",
            "title": "Create a repeatable backup and restore habit for HI state",
            "status": "todo",
            "due": "",
            "estimate_minutes": 30,
            "blockers": [],
            "created_at": "2026-05-12T00:00:00+00:00",
            "updated_at": "2026-05-12T00:00:00+00:00",
        },
        {
            "id": "public-proof-update",
            "title": "Keep ventures, services, and public proof updated on kingofyadav.in",
            "status": "todo",
            "due": "",
            "estimate_minutes": 60,
            "blockers": [],
            "created_at": "2026-05-12T00:00:00+00:00",
            "updated_at": "2026-05-12T00:00:00+00:00",
        },
    ],
}


PUBLIC_MEMORY: list[dict[str, Any]] = [
    {
        "type": "note",
        "text": "Amit Ku Yadav is based in Bhagalpur, Bihar, India and operates kingofyadav.in as a structured public identity platform.",
        "tag": "identity",
        "source": "public-site",
        "visibility": "public",
        "importance": 5,
        "created_at": "2026-05-12T00:00:00+00:00",
    },
    {
        "type": "note",
        "text": "Core work areas: digital identity systems, business platforms, AI-assisted workflows, public communication, and community initiatives.",
        "tag": "work",
        "source": "public-site",
        "visibility": "public",
        "importance": 5,
        "created_at": "2026-05-12T00:00:00+00:00",
    },
    {
        "type": "note",
        "text": "Active ventures include HI Life OS, kingofyadav.in Platform, Royal Heritage Resort, National Youth Force, and Jhon Aamit LLP.",
        "tag": "ventures",
        "source": "public-site",
        "visibility": "public",
        "importance": 5,
        "created_at": "2026-05-12T00:00:00+00:00",
    },
    {
        "type": "decision",
        "text": "When dashboard data is missing, use public website facts as the baseline and preserve any private user-saved data.",
        "tag": "dashboard",
        "source": "operator",
        "visibility": "private",
        "importance": 5,
        "created_at": "2026-05-12T00:00:00+00:00",
    },
]


def _is_placeholder_profile(profile: dict[str, Any]) -> bool:
    display = str(profile.get("display_name") or profile.get("full_name") or profile.get("name") or "").strip().lower()
    domain = str(profile.get("domain") or "").strip().lower()
    return display in {"", "?", "king yadav", "kingofyadav"} or domain in {"", "?", "ai systems"}


def _missing(value: Any) -> bool:
    return value in (None, "", "?", [], {})


def enrich_dashboard_state(raw_state: dict[str, Any] | None) -> dict[str, Any]:
    state = deepcopy(raw_state or {})

    profile = state.setdefault("profile", {})
    if not isinstance(profile, dict):
        profile = {}
        state["profile"] = profile
    force_public = _is_placeholder_profile(profile)
    for key, value in PUBLIC_PROFILE.items():
        if force_public or _missing(profile.get(key)):
            profile[key] = deepcopy(value)
    relationship = profile.setdefault("relationship", {})
    if not isinstance(relationship, dict):
        relationship = {}
        profile["relationship"] = relationship
    for key, value in PUBLIC_PROFILE["relationship"].items():
        if force_public or _missing(relationship.get(key)):
            relationship[key] = value

    preferences = state.setdefault("preferences", {})
    if not isinstance(preferences, dict):
        preferences = {}
        state["preferences"] = preferences
    for key, value in PUBLIC_PREFERENCES.items():
        if _missing(preferences.get(key)):
            preferences[key] = value

    workflow = state.setdefault("workflow", {})
    if not isinstance(workflow, dict):
        workflow = {}
        state["workflow"] = workflow
    if _missing(workflow.get("current_focus")):
        workflow["current_focus"] = PUBLIC_WORKFLOW["current_focus"]
    if _missing(workflow.get("status")):
        workflow["status"] = PUBLIC_WORKFLOW["status"]
    if not workflow.get("next_actions"):
        workflow["next_actions"] = deepcopy(PUBLIC_WORKFLOW["next_actions"])
    if not workflow.get("tasks"):
        workflow["tasks"] = deepcopy(PUBLIC_WORKFLOW["tasks"])

    memory = state.get("memory", [])
    if not isinstance(memory, list):
        memory = []
    if not memory:
        state["memory"] = deepcopy(PUBLIC_MEMORY)
    else:
        state["memory"] = memory

    state.setdefault("dashboard_seed", {})
    state["dashboard_seed"].update({
        "source": "kingofyadav.in public profile",
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "mode": "fallback_only",
    })
    return state
