from __future__ import annotations

from datetime import datetime

import streamlit as st

from services.local_admin_registry import clear_local_admin_registry, get_local_admin_registry_state
from services.ui_helpers import (
    inject_theme,
    maybe_auto_refresh,
    render_hero,
    render_kv_grid,
    render_log_block,
    render_priority_level,
    render_stat_card,
    render_theme_toggle,
    section_label,
)


st.set_page_config(page_title="Local Admins", page_icon="J", layout="wide")

render_theme_toggle()
inject_theme()

state = get_local_admin_registry_state(limit=500)
items = state.get("items", [])
events = state.get("events", [])

render_hero(
    "Local Admins",
    "Synced browser accounts that have signed up or logged in through the website login page.",
    eyebrow="Auth Registry",
)

section_label("Priority")
c0, c1, c2, c3 = st.columns(4)
with c0:
    render_priority_level("medium" if items else "low", f"{state.get('count', 0)} synced session(s).")
with c1:
    render_stat_card("Sessions", state.get("count", 0), "Unique username/device records", tone="ok" if items else "warn")
with c2:
    render_stat_card("Active", state.get("active_count", 0), "Current active records")
with c3:
    latest = state.get("latest", {})
    render_stat_card("Latest", latest.get("action", "none"), latest.get("username", "none"))

left, right = st.columns([1.2, 0.8], gap="large")

with left:
    section_label("Current Users")
    confirm_reset = st.checkbox("Confirm registry reset", key="local_admin_reset_confirm")
    if st.button("Reset Registry", type="secondary", disabled=not confirm_reset):
        clear_local_admin_registry()
        st.success("Synced local admin registry cleared.")
        st.rerun()
    if items:
        for item in items[:100]:
            render_kv_grid([
                ("Username", item.get("username") or "none"),
                ("Action", item.get("action") or "none"),
                ("Session", item.get("session_key") or "none"),
                ("Last Seen", item.get("ts", "")[:19].replace("T", " ")),
                ("Created", item.get("created_at_label") or item.get("ts", "")[:19].replace("T", " ")),
                ("Hash Version", item.get("hash_version") or "legacy"),
                ("Hash Preview", item.get("password_hash_preview") or "none"),
                ("Hash Length", item.get("password_hash_length", 0)),
                ("Salt", "yes" if item.get("has_salt") else "no"),
                ("Device", item.get("device_id") or "none"),
            ])
            st.caption(" ")
    else:
        st.caption("No synced local admin users yet.")

with right:
    section_label("Latest Snapshot")
    latest = state.get("latest", {})
    if latest:
        render_kv_grid([
            ("Username", latest.get("username", "none")),
            ("Action", latest.get("action", "none")),
            ("Source", latest.get("source", "none")),
            ("Session", latest.get("session_key", "none")),
            ("Time", latest.get("ts", "")[:19].replace("T", " ")),
        ])
        render_log_block(latest.get("password_hash_preview", ""))
    else:
        st.caption("No registry snapshot available.")

    section_label("Event Log")
    if events:
        limit = st.slider("Show latest", 5, 50, 10, key="local_admin_events_limit")
        for item in events[:limit]:
            render_log_block(
                f"{item.get('ts', '')[:19].replace('T', ' ')} · {item.get('action', 'unknown')} · {item.get('username', 'none')} · {item.get('password_hash_preview', '')}"
            )
    else:
        st.caption("No auth events recorded yet.")

    st.caption(f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

maybe_auto_refresh(True, 8)
