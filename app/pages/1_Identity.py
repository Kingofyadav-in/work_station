from __future__ import annotations

import streamlit as st

from services.jarvis_client import run_command
from services.model_selector import render_model_selector
from services.state_reader import get_dashboard_state
from services.ui_helpers import (
    ensure_history,
    inject_theme,
    push_history,
    render_hero,
    render_json_block,
    render_kv_grid,
    render_live_strip,
    render_memory_cards,
    render_priority_level,
    render_result_with_confirmation,
    render_stat_card,
    render_theme_toggle,
    section_label,
)


st.set_page_config(page_title="Identity", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
state = get_dashboard_state()
ensure_history()
inject_theme()

render_hero(
    "Identity",
    "Who is the user and who is Jarvis? Profile, relationship model, preferences, and memory summary.",
    eyebrow="Identity Layer",
)
render_live_strip(state)

# ── Priority, commands, result ─────────────────────────────────────────────────

profile = state.get("profile", {})
preferences = state.get("preferences", {})
workflow = state.get("workflow", {})
memory = state.get("memory", [])
jarvis_sess = state.get("jarvis_session", {})

section_label("Priority")
p1, p2, p3 = st.columns(3)
with p1:
    render_priority_level("low", "Identity information is reference content.")
with p2:
    render_stat_card("Profile", profile.get("display_name") or profile.get("full_name") or profile.get("name", "?"), "Loaded user identity")
with p3:
    render_stat_card("Memory", len(memory), "Curated recall entries", tone="ok" if memory else "warn")

section_label("Commands")

def _run(cmd: str) -> None:
    if not cmd.strip():
        return
    r = run_command(cmd.strip())
    st.session_state["identity_result"] = r
    push_history(r)

# Primary action buttons
b1, b2, b3, b4, b5 = st.columns(5)
if b1.button("My Profile",    key="id_profile",      use_container_width=True): _run("profile")
if b2.button("My Identity",   key="id_identity",     use_container_width=True): _run("my identity")
if b3.button("Preferences",   key="id_prefs",        use_container_width=True): _run("preferences")
if b4.button("Relationship",  key="id_relationship", use_container_width=True): _run("relationship")
if b5.button("Memory",        key="id_memory",       use_container_width=True): _run("memory")

# Command runner (compact)
with st.form("identity_cmd", clear_on_submit=False):
    cmd_col, btn_col = st.columns([5, 1])
    cmd = cmd_col.text_input(
        "Command",
        label_visibility="collapsed",
        placeholder="profile · preferences · relationship · memory",
    )
    if btn_col.form_submit_button("Run", type="primary", use_container_width=True):
        _run(cmd)

result = st.session_state.get("identity_result")
if result:
    render_result_with_confirmation(result, _run, key_prefix="identity")

st.divider()

# ── Content ────────────────────────────────────────────────────────────────────
left, right = st.columns([1.05, 0.95], gap="large")

with left:
    section_label("User Profile")
    render_kv_grid([
        ("Display Name", profile.get("display_name") or profile.get("full_name") or profile.get("name", "?")),
        ("Short Name",   profile.get("name", "?")),
        ("Domain",       profile.get("domain", "?")),
        ("Website",      profile.get("website", "?")),
        ("Brand",        profile.get("brand", "?")),
        ("Company",      profile.get("company", "?")),
        ("Email",        profile.get("email", "?")),
        ("Language",     profile.get("language", "?")),
        ("System Role",  profile.get("system_role", "?")),
    ])

    section_label("Relationship Model")
    render_kv_grid([
        ("Human",     profile.get("name") or "unknown"),
        ("AI",        jarvis_sess.get("ai_name", "Jarvis")),
        ("Domain",    profile.get("domain", "unknown")),
        ("Auth Role", profile.get("auth_role", "primary owner")),
    ])

with right:
    section_label("Preferences")
    if preferences:
        render_kv_grid([(k, v or "—") for k, v in preferences.items()])
    else:
        st.caption("No preferences loaded.")

    section_label("Workflow State")
    render_kv_grid([
        ("Focus",        workflow.get("current_focus") or "none"),
        ("Status",       workflow.get("status", "unknown")),
        ("Next Actions", len(workflow.get("next_actions", []))),
    ])
    next_acts = workflow.get("next_actions", [])
    if next_acts:
        for act in next_acts:
            st.markdown(f"- {act}")

    section_label(f"Memory ({len(memory)} entries)")
    render_memory_cards(memory[-5:])
