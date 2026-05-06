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
    render_kv_grid,
    render_priority_level,
    render_result_with_confirmation,
    render_stat_card,
    render_theme_toggle,
    render_live_strip,
    section_label,
)


st.set_page_config(page_title="Security", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
state = get_dashboard_state()
ensure_history()
inject_theme()

render_hero(
    "Security / Actions",
    "What needs approval or caution? Pending confirmations, guarded shell commands, screen lock, and session control.",
    eyebrow="Security Layer",
)
render_live_strip(state)

jarvis_session = state.get("jarvis_session", {})
pending_action = jarvis_session.get("pending_action", "")

# ── Priority, commands, result ─────────────────────────────────────────────────

def _run(cmd: str) -> None:
    if not cmd.strip():
        return
    r = run_command(cmd.strip())
    st.session_state["security_result"] = r
    push_history(r)

section_label("Priority")
p1, p2, p3 = st.columns(3)
with p1:
    render_priority_level("high" if pending_action else "low", "Confirmation is waiting." if pending_action else "No pending confirmation.")
with p2:
    render_stat_card("Pending Action", pending_action or "none", "Confirmation queue", tone="bad" if pending_action else "ok")
with p3:
    render_stat_card("Last Risk Tier", jarvis_session.get("last_risk_tier") or "none", "Last command behavior", tone="warn")

# ── Pending confirmation (prominent, top of page) ──────────────────────────────
if pending_action:
    st.markdown(
        f'<div class="jarvis-danger-banner">'
        f"<strong>Pending Confirmation Required</strong><br/>"
        f"Action: <code>{pending_action}</code><br/>"
        f"<span style='color:var(--muted);font-size:0.88rem;'>Run <code>confirm</code> to execute or <code>cancel</code> to discard.</span>"
        "</div>",
        unsafe_allow_html=True,
    )
    conf1, conf2, _ = st.columns([1, 1, 4])
    if conf1.button("Confirm Action", type="primary", key="sec_confirm_top", use_container_width=True):
        _run("confirm")
        st.rerun()
    if conf2.button("Cancel Action", key="sec_cancel_top", use_container_width=True):
        _run("cancel")
        st.rerun()
    st.divider()
else:
    st.success("No pending confirmation. All clear.")
    st.write("")

section_label("Commands")

# Primary action buttons
b1, b2, b3, b4, b5 = st.columns(5)
if b1.button("Pending Action", key="sec_pending", use_container_width=True): _run("confirmation status")
if b2.button("Lock Screen",    key="sec_lock",    use_container_width=True): _run("lock screen")
if b3.button("Cancel Pending", key="sec_cancel",  use_container_width=True): _run("cancel")
if b4.button("Reset Session",  key="sec_reset",   use_container_width=True): _run("reset session")
if b5.button("Show Session",   key="sec_session", use_container_width=True): _run("show session")

# Command runner (compact)
with st.form("security_cmd", clear_on_submit=False):
    cmd_col, btn_col = st.columns([5, 1])
    cmd = cmd_col.text_input(
        "Command",
        label_visibility="collapsed",
        placeholder="confirmation status · confirm · cancel · run pwd · lock screen",
    )
    if btn_col.form_submit_button("Run", type="primary", use_container_width=True):
        _run(cmd)

result = st.session_state.get("security_result")
if result:
    render_result_with_confirmation(result, _run, key_prefix="security")

st.divider()

# ── Main content ───────────────────────────────────────────────────────────────
left, right = st.columns([1.05, 0.95], gap="large")

with left:
    section_label("Shell Command")
    st.caption(
        "Only allowlisted commands are permitted: "
        "`pwd` · `whoami` · `date` · `uname [-a/-s/-r/-m]` · `ls [-1/-a/-l/-la]`  "
        "All shell commands require `confirm` before execution."
    )
    with st.form("security_shell_form", clear_on_submit=True):
        shell_cmd = st.text_input(
            "Shell command",
            placeholder="ls · pwd · whoami · date · uname -a",
        )
        if st.form_submit_button("Queue Shell Command", type="primary"):
            if shell_cmd.strip():
                _run(f"run {shell_cmd.strip()}")

    section_label("Volume Controls")
    v1, v2, v3 = st.columns(3)
    if v1.button("Volume Up",   key="sec_vol_up",   use_container_width=True): _run("volume up")
    if v2.button("Volume Down", key="sec_vol_down", use_container_width=True): _run("volume down")
    if v3.button("Mute",        key="sec_vol_mute", use_container_width=True): _run("mute volume")

with right:
    section_label("Session State")
    session_pairs = [
        (k, str(v) or "—")
        for k, v in jarvis_session.items()
        if not k.startswith("pending") and v not in (None, "")
    ]
    if session_pairs:
        render_kv_grid(session_pairs)
    else:
        st.caption("Session state is empty.")

    section_label("Pending State")
    render_kv_grid([
        ("Pending Action",  jarvis_session.get("pending_action") or "none"),
        ("Pending Since",   (jarvis_session.get("pending_since") or "none")[:19].replace("T", " ")),
        ("Last Risk Tier",  jarvis_session.get("last_risk_tier") or "none"),
        ("Last Command",    jarvis_session.get("last_command") or "none"),
    ])

    section_label("Danger Zone")
    st.caption("These actions modify or clear session state. Use with care.")
    st.warning("Use the buttons at the top of this page to lock the screen or reset the session.")
