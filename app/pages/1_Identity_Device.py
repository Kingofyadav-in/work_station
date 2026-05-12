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


st.set_page_config(page_title="Identity & Device", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
state = get_dashboard_state()
ensure_history()
inject_theme()

render_hero(
    "Identity & Device",
    "Who is the user and is this machine trusted? Profile, memory, preferences, and device trust — all in one place.",
    eyebrow="Identity Layer",
)
render_live_strip(state)

tab_identity, tab_device = st.tabs(["Identity", "Device"])


# ── IDENTITY ──────────────────────────────────────────────────────────────────
with tab_identity:
    profile     = state.get("profile", {})
    preferences = state.get("preferences", {})
    workflow    = state.get("workflow", {})
    memory      = state.get("memory", [])
    jarvis_sess = state.get("jarvis_session", {})

    ci0, ci1, ci2 = st.columns(3)
    with ci0:
        render_stat_card(
            "Profile",
            profile.get("display_name") or profile.get("full_name") or profile.get("name", "?"),
            "Loaded user identity",
            tone="ok",
        )
    with ci1:
        render_stat_card("Memory", len(memory), "Curated recall entries", tone="ok" if memory else "warn")
    with ci2:
        render_stat_card("Domain", profile.get("domain", "?"), profile.get("auth_role", "primary owner"))

    def _run_id(cmd: str) -> None:
        if not cmd.strip():
            return
        r = run_command(cmd.strip())
        st.session_state["identity_result"] = r
        push_history(r)

    section_label("Commands")
    ib1, ib2, ib3, ib4 = st.columns(4)
    if ib1.button("My Profile",   key="id_profile",      use_container_width=True): _run_id("profile")
    if ib2.button("Preferences",  key="id_prefs",        use_container_width=True): _run_id("preferences")
    if ib3.button("Relationship", key="id_relationship", use_container_width=True): _run_id("relationship")
    if ib4.button("Memory",       key="id_memory",       use_container_width=True): _run_id("memory")

    with st.form("identity_cmd", clear_on_submit=False):
        ic_col, ib_col = st.columns([5, 1])
        ic = ic_col.text_input("Command", label_visibility="collapsed",
                               placeholder="profile · preferences · relationship · memory")
        if ib_col.form_submit_button("Run", type="primary", use_container_width=True):
            _run_id(ic)

    id_result = st.session_state.get("identity_result")
    if id_result:
        render_result_with_confirmation(id_result, _run_id, key_prefix="identity")

    il, ir = st.columns([1.05, 0.95], gap="large")
    with il:
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
    with ir:
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
        for act in workflow.get("next_actions", []):
            st.markdown(f"- {act}")
        section_label(f"Memory ({len(memory)} entries)")
        render_memory_cards(memory[-5:])


# ── DEVICE ────────────────────────────────────────────────────────────────────
with tab_device:
    device            = state.get("device", {})
    device_trusted    = bool(device.get("trusted"))
    device_registered = bool(device.get("registered"))

    cd0, cd1, cd2, cd3 = st.columns(4)
    with cd0:
        render_priority_level(
            "low" if device_trusted else "medium",
            "Register or refresh trust before sensitive commands.",
        )
    with cd1:
        render_stat_card("Registered", "Yes" if device_registered else "No", "Device enrolled",
                         tone="ok" if device_registered else "warn")
    with cd2:
        render_stat_card("Trusted", "Yes" if device_trusted else "No", "Fingerprint match",
                         tone="ok" if device_trusted else "warn")
    with cd3:
        render_stat_card("Label", device.get("label") or "none",
                         (device.get("registered_at") or "never")[:10])

    def _run_dev(cmd: str) -> None:
        if not cmd.strip():
            return
        r = run_command(cmd.strip())
        st.session_state["device_result"] = r
        push_history(r)

    section_label("Commands")
    db1, db2, db3, db4 = st.columns(4)
    if db1.button("Device Report",   key="dev_report",   use_container_width=True): _run_dev("device report")
    if db2.button("Auto Detect",     key="dev_auto",     use_container_width=True): _run_dev("auto detect device primary-control-device")
    if db3.button("Register Device", key="dev_register", use_container_width=True): _run_dev("register device primary-control-device")
    if db4.button("Hardware",        key="dev_hw",       use_container_width=True): _run_dev("hardware report")

    db5, db6, db7, _ = st.columns(4)
    if db5.button("Software",    key="dev_sw",  use_container_width=True): _run_dev("software report")
    if db6.button("Network",     key="dev_net", use_container_width=True): _run_dev("network report")
    if db7.button("Environment", key="dev_env", use_container_width=True): _run_dev("env report")

    with st.form("device_cmd", clear_on_submit=False):
        dc_col, dbt_col = st.columns([5, 1])
        dc = dc_col.text_input("Command", label_visibility="collapsed",
                               placeholder="device report · hardware report · register device")
        if dbt_col.form_submit_button("Run", type="primary", use_container_width=True):
            _run_dev(dc)

    dev_result = st.session_state.get("device_result")
    if dev_result:
        render_result_with_confirmation(dev_result, _run_dev, key_prefix="device")

    if not device_trusted:
        if device_registered:
            st.info("This device is registered but the saved fingerprint is stale. "
                    "Click **Auto Detect** above to refresh the trusted-device registry.")
        else:
            st.info("This device is not yet registered. Click **Auto Detect** or "
                    "**Register Device** above to enroll it as a trusted control device.")

    section_label("Device Details")
    show_raw = st.sidebar.checkbox("Show raw device JSON", value=False)

    render_kv_grid([
        ("Registered",    "yes" if device_registered else "no"),
        ("Trusted",       "yes" if device_trusted else "no"),
        ("Label",         device.get("label") or "none"),
        ("Trust Match",   device.get("trust_match") or "none"),
        ("Fingerprint",   device.get("fingerprint") or "none"),
        ("Registered At", (device.get("registered_at") or "none")[:19].replace("T", " ")),
    ])
    if show_raw:
        render_json_block(device)

    with st.expander("Hardware", expanded=False):
        st.caption("Run **Hardware** button above to load current hardware details.")
    with st.expander("Software", expanded=False):
        st.caption("Run **Software** button above to load current software details.")
    with st.expander("Network", expanded=False):
        st.caption("Run **Network** button above to load current network details.")
    with st.expander("Environment", expanded=False):
        st.caption("Run **Environment** button above to load safe environment details.")
        st.caption("Secret values (API keys, tokens) are never stored or displayed.")
