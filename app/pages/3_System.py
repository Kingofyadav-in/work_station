from __future__ import annotations

import json

import streamlit as st

from services.jarvis_client import run_command
from services.log_reader import (
    get_last_bus_log_time,
    get_last_event,
    read_bus_log_filtered,
    read_event_objects,
)
from services.model_selector import render_model_selector
from services.state_reader import get_dashboard_state
from services.ui_helpers import (
    ensure_history,
    inject_theme,
    maybe_auto_refresh,
    push_history,
    refresh_timestamp,
    render_hero,
    render_log_block,
    render_live_strip,
    render_priority_level,
    render_result_with_confirmation,
    render_stat_card,
    render_theme_toggle,
    render_timeline,
    section_label,
)


st.set_page_config(page_title="System", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
refresh_interval = st.sidebar.slider("Refresh every (s)", min_value=2, max_value=10, value=3, key="sys_refresh_interval")
bus_line_count   = st.sidebar.slider("Bus log lines", min_value=10, max_value=100, value=30, key="sys_bus_line_count")

state = get_dashboard_state()
ensure_history()
inject_theme()

render_hero(
    "System",
    "Is the platform healthy? Listener status, bus traffic, event journal, disk, battery, and website reachability.",
    eyebrow="Platform Health",
)
render_live_strip(state)

# ── Priority, commands, result ─────────────────────────────────────────────────

listener_ok = state["health"]["kingofyadav_listener_healthy"]
bus_active  = state["health"]["bus_active"]
last_event  = get_last_event()
last_ts     = (last_event or {}).get("ts", "none")
last_ts_fmt = last_ts[:19].replace("T", " ") if last_ts != "none" else "none"
system_priority = "high" if not listener_ok else ("medium" if not bus_active else "low")
system_priority_detail = "Listener offline." if not listener_ok else ("Bus idle." if not bus_active else "Core services healthy.")

section_label("Priority")
p1, p2, p3 = st.columns(3)
with p1:
    render_priority_level(system_priority, system_priority_detail)
with p2:
    render_stat_card("Listener", "Healthy" if listener_ok else "Offline", "Kingofyadav service", tone="ok" if listener_ok else "bad", pulse=listener_ok)
with p3:
    render_stat_card("Bus Activity", "Active" if bus_active else "Idle", "Recent bus traffic", tone="ok" if bus_active else "warn")

section_label("Commands")

def _run(cmd: str) -> None:
    if not cmd.strip():
        return
    r = run_command(cmd.strip())
    st.session_state["system_result"] = r
    push_history(r)

# Primary action buttons
b1, b2, b3, b4, b5, b6 = st.columns(6)
if b1.button("Status",      key="sys_status",      use_container_width=True): _run("status")
if b2.button("Context",     key="sys_context",     use_container_width=True): _run("context")
if b3.button("System Info", key="sys_info",        use_container_width=True): _run("system info")
if b4.button("Disk",        key="sys_disk",        use_container_width=True): _run("disk")
if b5.button("Battery",     key="sys_battery",     use_container_width=True): _run("battery")
if b6.button("Website",     key="sys_website",     use_container_width=True): _run("website status")

# Command runner (compact)
with st.form("system_cmd", clear_on_submit=False):
    cmd_col, btn_col = st.columns([5, 1])
    cmd = cmd_col.text_input(
        "Command",
        label_visibility="collapsed",
        placeholder="status · context · system info · disk · battery · website status",
    )
    if btn_col.form_submit_button("Run", type="primary", use_container_width=True):
        _run(cmd)

result = st.session_state.get("system_result")
if result:
    render_result_with_confirmation(result, _run, key_prefix="system")

st.divider()

# ── Health badges ──────────────────────────────────────────────────────────────
s1, s2, s3, s4 = st.columns(4)
with s1:
    render_stat_card(
        "Listener",
        "Healthy" if listener_ok else "Offline",
        "Kingofyadav service",
        tone="ok" if listener_ok else "bad",
        pulse=listener_ok,
    )
with s2:
    render_stat_card(
        "Bus Activity",
        "Active" if bus_active else "Idle",
        "Recent bus traffic",
        tone="ok" if bus_active else "warn",
    )
with s3:
    render_stat_card(
        "Last Event",
        (last_event or {}).get("type", "none"),
        last_ts_fmt,
        tone="warn",
    )
with s4:
    render_stat_card(
        "Connectivity",
        state["system"].get("connectivity", "unknown"),
        state["system"].get("hostname", "unknown"),
    )

st.caption(
    f"Refreshed: {refresh_timestamp()} · Bus: {get_last_bus_log_time()} · "
    f"Event: {last_ts_fmt}"
)

# ── Live log + event timeline ──────────────────────────────────────────────────
section_label("Live Trace")
bus_col, event_col = st.columns([1.25, 0.95], gap="large")

with bus_col:
    filter_options = ["All", "REQUEST", "RESPONSE", "PROCESSED", "ERROR", "DEADLETTER", "TIMEOUT"]
    filter_value = st.selectbox("Filter", filter_options, index=0, label_visibility="collapsed")
    bus_lines = read_bus_log_filtered(
        lines=bus_line_count,
        keyword="" if filter_value == "All" else filter_value,
    )
    render_log_block("\n".join(bus_lines) if bus_lines else "No bus log lines matching filter.")

with event_col:
    events = read_event_objects(lines=12)
    if events:
        render_timeline([
            {
                "meta":  e.get("ts", "?")[:19].replace("T", " "),
                "title": e.get("type", "event"),
                "body":  json.dumps(e.get("payload", {}), ensure_ascii=False),
            }
            for e in events
        ])
    else:
        st.caption("No events yet.")

st.caption(
    f"Snapshot: {state.get('fetched_at', 'n/a')[:19].replace('T', ' ')} · "
    f"Last event: {state['health'].get('last_event_type', 'none')} · "
    f"Bus lines tracked: {len(state.get('recent_bus', []))}"
)

maybe_auto_refresh(True, refresh_interval)
