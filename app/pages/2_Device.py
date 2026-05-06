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
    render_priority_level,
    render_result_with_confirmation,
    render_stat_card,
    render_theme_toggle,
    section_label,
)


st.set_page_config(page_title="Device", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
state = get_dashboard_state()
ensure_history()
inject_theme()

render_hero(
    "Device",
    "Is this machine trusted and what is inside it? Registration, fingerprint, hardware, software, network, and environment.",
    eyebrow="Trusted Device",
)
render_live_strip(state)

# ── Priority, commands, result ─────────────────────────────────────────────────

device = state.get("device", {})
device_trusted     = bool(device.get("trusted"))
device_registered  = bool(device.get("registered"))

section_label("Priority")
p1, p2, p3 = st.columns(3)
with p1:
    render_priority_level("low" if device_trusted else "medium", "Register or refresh trust before sensitive commands.")
with p2:
    render_stat_card("Registered", "Yes" if device_registered else "No", "Device enrolled", tone="ok" if device_registered else "warn")
with p3:
    render_stat_card("Trusted", "Yes" if device_trusted else "No", "Fingerprint match", tone="ok" if device_trusted else "warn")

section_label("Commands")

def _run(cmd: str) -> None:
    if not cmd.strip():
        return
    r = run_command(cmd.strip())
    st.session_state["device_result"] = r
    push_history(r)

# Primary action buttons
b1, b2, b3, b4, b5, b6, b7 = st.columns(7)
if b1.button("Device Report",  key="dev_report",   use_container_width=True): _run("device report")
if b2.button("Auto Detect",    key="dev_auto",     use_container_width=True): _run("auto detect device primary-control-device")
if b3.button("Register Device",key="dev_register", use_container_width=True): _run("register device primary-control-device")
if b4.button("Hardware",       key="dev_hw",       use_container_width=True): _run("hardware report")
if b5.button("Software",       key="dev_sw",       use_container_width=True): _run("software report")
if b6.button("Network",        key="dev_net",      use_container_width=True): _run("network report")
if b7.button("Environment",    key="dev_env",      use_container_width=True): _run("env report")

# Command runner (compact)
with st.form("device_cmd", clear_on_submit=False):
    cmd_col, btn_col = st.columns([5, 1])
    cmd = cmd_col.text_input(
        "Command",
        label_visibility="collapsed",
        placeholder="device report · hardware report · register device",
    )
    if btn_col.form_submit_button("Run", type="primary", use_container_width=True):
        _run(cmd)

result = st.session_state.get("device_result")
if result:
    render_result_with_confirmation(result, _run, key_prefix="device")

st.divider()

# ── Device trust status ────────────────────────────────────────────────────────
section_label("Trust Status")
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_stat_card(
        "Registered",
        "Yes" if device_registered else "No",
        "Device enrolled",
        tone="ok" if device_registered else "warn",
    )
with c2:
    render_stat_card(
        "Trusted",
        "Yes" if device_trusted else "No",
        "Fingerprint match",
        tone="ok" if device_trusted else "warn",
    )
with c3:
    render_stat_card(
        "Label",
        device.get("label") or "none",
        "Registered name",
    )
with c4:
    render_stat_card(
        "Registered At",
        (device.get("registered_at") or "never")[:19].replace("T", " "),
        "Enrollment timestamp",
    )

if not device_trusted:
    if device_registered:
        st.info(
            "This device is registered but the saved fingerprint is stale. Click **Auto Detect** above to refresh the trusted-device registry."
        )
    else:
        st.info(
            "This device is not yet registered. Click **Auto Detect** or **Register Device** above to enroll it as a trusted control device."
        )

# ── Detail panels ──────────────────────────────────────────────────────────────
section_label("Device Details")
show_raw = st.sidebar.checkbox("Show raw JSON", value=False)

t_summary, t_hw, t_sw, t_net, t_env = st.tabs([
    "Summary", "Hardware", "Software", "Network", "Environment"
])

with t_summary:
    render_kv_grid([
        ("Registered",     "yes" if device_registered else "no"),
        ("Trusted",        "yes" if device_trusted else "no"),
        ("Label",          device.get("label") or "none"),
        ("Trust Match",    device.get("trust_match") or "none"),
        ("Fingerprint",    device.get("fingerprint") or "none"),
        ("Registered At",  (device.get("registered_at") or "none")[:19].replace("T", " ")),
    ])
    if show_raw:
        render_json_block(device)

with t_hw:
    st.caption("Run **Hardware** button above to load current hardware details.")

with t_sw:
    st.caption("Run **Software** button above to load current software details.")

with t_net:
    st.caption("Run **Network** button above to load current network details.")

with t_env:
    st.caption("Run **Environment** button above to load safe environment details.")
    st.caption("Secret values (API keys, tokens) are never stored or displayed.")
