from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import secrets
import time
from pathlib import Path

import streamlit as st

# ── Auth gate ─────────────────────────────────────────────────────────────────
# Session token persists in logs/dashboard_session.json so browser refresh
# does not force re-login. Token expires after SESSION_TTL_HOURS.

_ROOT_DIR_AUTH = Path(__file__).resolve().parent.parent
_SESSION_FILE  = _ROOT_DIR_AUTH / "logs" / "dashboard_session.json"
_SESSION_TTL_HOURS = 24


def _token_for_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()[:32]


def _save_session(token: str) -> None:
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(
        json.dumps({"token": token, "created_at": time.time()}),
        encoding="utf-8",
    )


def _load_session() -> str:
    try:
        data = json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
        age_hours = (time.time() - float(data["created_at"])) / 3600
        if age_hours < _SESSION_TTL_HOURS:
            return data["token"]
    except Exception:
        pass
    return ""


def _check_password() -> bool:
    _pw_env = os.getenv("DASHBOARD_PASSWORD", "").strip()
    if not _pw_env:
        if os.getenv("APP_ENV", "").strip().lower() == "production":
            st.set_page_config(page_title="Jarvis - Locked", page_icon="J", layout="centered")
            st.error("Dashboard is locked because DASHBOARD_PASSWORD is not set.")
            st.stop()
        return True

    expected_token = _token_for_password(_pw_env)

    def _verify(entered: str) -> bool:
        return hmac.compare_digest(
            hashlib.sha256(entered.encode()).hexdigest(),
            hashlib.sha256(_pw_env.encode()).hexdigest(),
        )

    # Restore auth from session file (survives browser refresh)
    if not st.session_state.get("_auth_ok"):
        if _load_session() == expected_token:
            st.session_state["_auth_ok"] = True

    if st.session_state.get("_auth_ok"):
        return True

    st.set_page_config(page_title="Jarvis — Login", page_icon="J", layout="centered")
    st.markdown("## Jarvis Control Panel")
    st.markdown("Enter your dashboard password to continue.")
    entered = st.text_input("Password", type="password", key="_login_input")
    if st.button("Login", type="primary"):
        if _verify(entered):
            st.session_state["_auth_ok"] = True
            _save_session(expected_token)   # persist so refresh skips login
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()
    return False

_check_password()

# ── End auth gate ─────────────────────────────────────────────────────────────

from services.automation_client import get_automation_status
from services.dashboard_db import get_latest_dashboard_state_snapshot
from services.jarvis_client import preview_command, run_command
from services.local_admin_registry import get_local_admin_registry_state
from services.public_intake import get_public_inbox_state
from services.model_selector import render_model_selector
from services.log_reader import read_bus_log
from services.state_reader import get_dashboard_state
from services.tts_client import speak_full_result, speak_result, tts_available
from services.ui_helpers import (
    ensure_history,
    inject_theme,
    maybe_auto_refresh,
    push_history,
    render_hero,
    render_command_preview,
    render_kv_grid,
    render_log_block,
    render_memory_cards,
    render_priority_level,
    render_result_with_confirmation,
    render_stat_card,
    render_live_strip,
    render_theme_toggle,
    render_tts_toggle,
    render_website_jarvis_hero,
    route_badge,
    section_label,
)


st.set_page_config(page_title="Jarvis", page_icon="J", layout="wide")

render_theme_toggle()
if tts_available():
    render_tts_toggle()
render_model_selector()
try:
    state = get_dashboard_state()
    local_admin_state = get_local_admin_registry_state(limit=200)
    public_inbox_state = get_public_inbox_state(limit=50)
    aut_state = get_automation_status()
except Exception as _e:
    st.error(f"Failed to load state: {_e}")
    st.stop()
ensure_history()
inject_theme()

# ── Derive service state (used by notification strip + stat row) ───────────────
listener_online   = state["listener"]["online"]
device_state      = state.get("device", {})
device_trusted    = bool(device_state.get("trusted"))
device_registered = bool(device_state.get("registered"))

# ── Notification strip ────────────────────────────────────────────────────────
_ROOT_DIR = Path(__file__).resolve().parent.parent
_DOCTOR_LATEST = _ROOT_DIR / "logs" / "doctor" / "latest.json"

_alerts: list[tuple[str, str]] = []
if not listener_online:
    _alerts.append(("Kingofyadav listener is offline — HI state changes will not be applied.", "error"))
if not device_trusted and not device_registered:
    _alerts.append(("This device is not registered. Run 'register device' to enable trusted commands.", "warning"))
elif device_registered and not device_trusted:
    _alerts.append(("Device is registered but not yet trusted. Check the Device page.", "warning"))
if not state["health"].get("bus_active"):
    _alerts.append(("Message bus is inactive — no recent events detected.", "warning"))

try:
    _doctor = json.loads(_DOCTOR_LATEST.read_text(encoding="utf-8")) if _DOCTOR_LATEST.exists() else {}
    _critical = [c for c in _doctor.get("checks", []) if c.get("status") == "FAIL"]
    if _critical:
        _names = ", ".join(c.get("name", "") for c in _critical[:3])
        _more = f" (+{len(_critical) - 3} more)" if len(_critical) > 3 else ""
        _alerts.append((f"Doctor found {len(_critical)} critical issue(s): {_names}{_more}", "error"))
except Exception:
    pass

if not aut_state.get("daemon_alive"):
    _alerts.append(("Automation daemon is stopped. Go to Automation page to start it.", "warning"))
elif aut_state.get("stop_active"):
    _alerts.append(("Automation is paused (STOP file active).", "warning"))
if aut_state.get("pending_count", 0) > 0:
    _alerts.append((f"{aut_state['pending_count']} automation action(s) awaiting manual approval.", "warning"))

for _msg, _tone in _alerts:
    if _tone == "error":
        st.error(_msg, icon="🔴")
    else:
        st.warning(_msg, icon="⚠️")

render_hero(
    "Command Center",
    "Is everything ready and what can I do now? Health at a glance, last result, and quick actions — all without leaving this page.",
    eyebrow="Mission Control",
)
render_website_jarvis_hero(state.get("profile", {}))
render_live_strip(state)

# ── Top stat row — 4 key health indicators ────────────────────────────────────

home_priority = "high" if _alerts else "low"
home_priority_detail = "Resolve active alerts first." if _alerts else "All systems clear."

c0, c1, c2, c3, c4 = st.columns(5)
with c0:
    render_priority_level(home_priority, home_priority_detail)
with c1:
    render_stat_card(
        "Listener",
        "Online" if listener_online else "Offline",
        "Kingofyadav bridge",
        tone="ok" if listener_online else "bad",
        pulse=listener_online,
    )
with c2:
    render_stat_card(
        "Device",
        "Trusted" if device_trusted else "Unregistered",
        device_state.get("label") or "local device",
        tone="ok" if device_trusted else "warn",
    )
with c3:
    render_stat_card(
        "Focus",
        state["workflow"].get("current_focus") or "none",
        f"Mode: {state['preferences'].get('response_mode', 'unknown')}",
        tone="warn",
    )
with c4:
    _aut_alive = aut_state.get("daemon_alive", False)
    _aut_label = "Running" if _aut_alive and not aut_state.get("stop_active") else \
                 ("Paused" if _aut_alive else "Stopped")
    _aut_detail = f"{aut_state.get('enabled_count',0)}/{aut_state.get('rule_count',0)} rules"
    render_stat_card(
        "Automation",
        _aut_label,
        _aut_detail,
        tone="ok" if _aut_alive and not aut_state.get("stop_active") else "warn",
        pulse=_aut_alive and not aut_state.get("stop_active"),
    )

profile = state.get("profile", {})
_ventures = profile.get("ventures", [])
_channels = profile.get("public_channels", {})
_state_snapshot = get_latest_dashboard_state_snapshot()

section_label("Public Identity Snapshot")
id0, id1, id2, id3 = st.columns(4)
with id0:
    render_stat_card("Owner", profile.get("full_name") or profile.get("display_name") or "Amit Ku Yadav",
                     profile.get("location", "Bhagalpur, Bihar, India"), tone="ok")
with id1:
    render_stat_card("Website", profile.get("brand") or "kingofyadav.in",
                     profile.get("website", "https://kingofyadav.in"), tone="ok")
with id2:
    render_stat_card("Ventures", len(_ventures) if isinstance(_ventures, list) else 0,
                     "Active public work streams", tone="ok")
with id3:
    render_stat_card("Contact", profile.get("phone") or profile.get("email") or "available",
                     profile.get("email", "kingofyadav.in@gmail.com"), tone="ok")

sync0, sync1, sync2, sync3 = st.columns(4)
with sync0:
    render_stat_card("Machine Store", "Active" if _state_snapshot else "Ready",
                     "logs/dashboard.db", tone="ok" if _state_snapshot else "warn")
with sync1:
    render_stat_card("Dashboard Refresh", "Live",
                     f"{state.get('fetched_at', '')[:19].replace('T', ' ')} UTC", tone="ok", pulse=True)
with sync2:
    render_stat_card("Public API", "/api/public-state",
                     "Safe data for kingofyadav.in", tone="ok")
with sync3:
    render_stat_card("WebSocket", "/api/ws/public",
                     "Live public-safe stream", tone="ok")

snap_left, snap_right = st.columns([1.35, 1], gap="large")
with snap_left:
    render_kv_grid([
        ("Identity", profile.get("identity_summary", "Public identity loaded.")),
        ("Core Work", profile.get("domain", "Digital systems and public work")),
        ("Operating Role", profile.get("system_role", "Primary human operator")),
        ("Jarvis Role", profile.get("relationship", {}).get("jarvis_role", "local execution")),
    ])
with snap_right:
    if isinstance(_ventures, list) and _ventures:
        st.markdown("**Active Ventures**")
        for _venture in _ventures:
            st.markdown(f"- {html.escape(str(_venture))}")
    if isinstance(_channels, dict) and _channels:
        st.markdown("**Public Channels**")
        for _label, _url in _channels.items():
            st.markdown(f"- {html.escape(str(_label).title())}: {html.escape(str(_url))}")

# ── Main layout ────────────────────────────────────────────────────────────────
left, right = st.columns([1.5, 1])

with left:
    section_label("Command Runner")

    if "tts_speak_full_results" not in st.session_state:
        st.session_state["tts_speak_full_results"] = True
    st.sidebar.toggle(
        "Speak full command results",
        key="tts_speak_full_results",
        help="When on, Jarvis reads the full command result after each action.",
    )

    def _tts(r: dict) -> None:
        if st.session_state.get("tts_enabled", True) and tts_available():
            if st.session_state.get("tts_speak_full_results", True):
                speak_full_result(r)
            else:
                speak_result(r)

    def _run(cmd: str) -> None:
        if not cmd.strip():
            return
        r = run_command(cmd.strip())
        st.session_state["home_result"] = r
        st.session_state["home_last_cmd"] = cmd.strip()
        st.session_state["home_last_preview"] = r.get("preview", {})
        push_history(r)
        _tts(r)

    if "home_cmd_input" not in st.session_state:
        st.session_state["home_cmd_input"] = st.session_state.get("home_last_cmd", "")

    cmd_input = st.text_input(
        "Command",
        key="home_cmd_input",
        placeholder="profile · status · workflow · ask what should I work on next",
    )
    current_preview = None
    if str(cmd_input or "").strip():
        try:
            current_preview = preview_command(str(cmd_input))
            render_command_preview(current_preview)
        except Exception:
            current_preview = None

    run_col, dev_col, _ = st.columns([1.2, 1, 1])
    if run_col.button("Run Command", type="primary", use_container_width=True):
        _run(str(cmd_input))
        st.rerun()
    if dev_col.button("Device Report", key="home_qa_device", use_container_width=True):
        _run("device report")
        st.rerun()

    # 5. Last Result
    result = st.session_state.get("home_result")
    if result:
        def _on_confirm(cmd: str) -> None:
            r = run_command(cmd)
            st.session_state["home_result"] = r
            push_history(r)
            _tts(r)
        render_result_with_confirmation(result, _on_confirm, key_prefix="home")
        st.caption(
            f"Trace {result.get('trace_id', 'n/a')} · {result.get('duration_ms', 'n/a')} ms · "
            f"Route {result.get('route', 'n/a')} · Action {result.get('parsed_action', 'n/a')}"
        )

    section_label("Ask AI (Streaming)")
    if "stream_ai_input" not in st.session_state:
        st.session_state["stream_ai_input"] = ""
    stream_input = st.text_input(
        "Ask anything",
        key="stream_ai_input",
        placeholder="What should I work on today? · Explain my current workflow · Summarize my memory",
    )
    if st.button("Ask AI", key="home_stream_ai_btn", type="secondary", use_container_width=False):
        if str(stream_input or "").strip():
            from services.jarvis_client import run_ai_stream
            _ai_ctx = {
                "workflow_focus": state["workflow"].get("current_focus") or "",
                "memory_count": state.get("memory_count", 0),
                "domain": state.get("profile", {}).get("domain", ""),
                "response_mode": state["preferences"].get("response_mode", ""),
                "last_action": state["health"].get("last_event_type", ""),
            }
            with st.spinner(""):
                st.markdown("**Jarvis:**")
                st.write_stream(run_ai_stream(str(stream_input).strip(), context=_ai_ctx))

    section_label("Quick Actions")
    qa1, qa2, qa3, qa4 = st.columns(4)
    if qa1.button("Status",    key="home_qa_status",    use_container_width=True): _run("status")
    if qa2.button("Workflow",  key="home_qa_workflow",   use_container_width=True): _run("workflow")
    if qa3.button("Profile",   key="home_qa_profile",    use_container_width=True): _run("profile")
    if qa4.button("Memory",    key="home_qa_memory",    use_container_width=True): _run("memory")

    qa5, qa6, qa7, _ = st.columns(4)
    if qa5.button("AI Status", key="home_qa_ai_status", use_container_width=True): _run("ai status")
    if qa6.button("Logs",      key="home_qa_logs",      use_container_width=True): _run("logs")
    if qa7.button("Doctor",    key="home_qa_doctor",    use_container_width=True): _run("doctor")

    section_label("Recent Activity")
    bus_lines = read_bus_log(lines=10)
    render_log_block("\n".join(bus_lines) if bus_lines else "No bus log entries.")

with right:
    section_label("System Snapshot")
    st.markdown(
        f"HI layer: {route_badge('hi' if listener_online else 'n/a')}",
        unsafe_allow_html=True,
    )
    render_kv_grid([
        ("Owner",        profile.get("full_name") or profile.get("name", "unknown")),
        ("Domain",       profile.get("domain", "unknown")),
        ("Host",         state["system"].get("hostname", "unknown")),
        ("Connectivity", state["system"].get("connectivity", "unknown")),
        ("Mode",         state["preferences"].get("response_mode", "unknown")),
        ("Focus",        state["workflow"].get("current_focus") or "none"),
        ("Memory",       state["memory_count"]),
        ("Last Event",   state["health"].get("last_event_type", "none")),
    ])

    section_label("Users & Signups")
    _pub_signups = public_inbox_state.get("signups", [])
    _pub_enquiries = public_inbox_state.get("enquiries", [])
    _admin_users = local_admin_state.get("items", [])
    _session_count = local_admin_state.get("count", 0)
    _u1, _u2 = st.columns(2)
    with _u1:
        render_stat_card("Signups", len(_pub_signups), "Access requests from website", tone="ok" if _pub_signups else "warn")
    with _u2:
        render_stat_card("Active Sessions", local_admin_state.get("active_count", 0), "Login sessions synced", tone="ok" if _admin_users else "warn")
    if _pub_signups:
        st.caption("**Recent signups:**")
        for _s in _pub_signups[:5]:
            st.markdown(
                f"- **{html.escape(str(_s.get('name') or 'unnamed'))}** · `{html.escape(str(_s.get('email') or '—'))}` · "
                f"<span style='color:var(--muted);font-size:0.78rem;'>{str(_s.get('ts',''))[:10]}</span>",
                unsafe_allow_html=True,
            )
    elif _pub_enquiries:
        st.caption("**Recent enquiries:**")
        for _e in _pub_enquiries[:3]:
            st.markdown(
                f"- **{html.escape(str(_e.get('name') or 'unnamed'))}** — {html.escape(str(_e.get('subject') or '—'))}",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No public submissions yet. Check pages 9 & 10 for details.")
    if _admin_users:
        st.caption("**Latest web session:**")
        _latest_user = _admin_users[0]
        render_kv_grid([
            ("Username", _latest_user.get("username") or "—"),
            ("Action", _latest_user.get("action") or "—"),
            ("Last seen", str(_latest_user.get("ts", ""))[:16].replace("T", " ")),
        ])

    section_label("Recent Memory")
    render_memory_cards(state["memory"][-4:])

maybe_auto_refresh(True, 4)
