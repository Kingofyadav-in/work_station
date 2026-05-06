from __future__ import annotations

import hashlib
import hmac
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

from services.jarvis_client import preview_command, run_command
from services.local_admin_registry import get_local_admin_registry_state
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
render_live_strip(state)

# ── Priority + stat row ────────────────────────────────────────────────────────

home_priority = "high" if _alerts else "low"
home_priority_detail = "Resolve active alerts first." if _alerts else "No blocking alerts."

c0, c1, c2, c3, c4, c5, c6 = st.columns(7)
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
        "Current Focus",
        state["workflow"].get("current_focus") or "none",
        "Active workflow priority",
        tone="warn",
    )
with c4:
    render_stat_card(
        "Response Mode",
        state["preferences"].get("response_mode", "unknown"),
        "HI preference",
    )
with c5:
    render_stat_card("Memory", state["memory_count"], "Curated recall entries")
with c6:
    render_stat_card(
        "Sessions",
        local_admin_state.get("count", 0),
        "Synced username/device records",
        tone="ok" if local_admin_state.get("count", 0) else "warn",
    )

st.divider()

# ── Main layout ────────────────────────────────────────────────────────────────
left, right = st.columns([1.5, 1])

with left:
    # 1. Real User Profile
    profile = state.get("profile", {})
    section_label("User Profile")
    p1, p2, p3 = st.columns(3)
    with p1:
        render_stat_card(
            "Owner",
            profile.get("full_name") or profile.get("display_name") or profile.get("name", "unknown"),
            profile.get("auth_role", "primary owner"),
            tone="ok",
        )
    with p2:
        render_stat_card(
            "Domain",
            profile.get("domain", "unknown"),
            profile.get("email", "unknown"),
        )
    with p3:
        render_stat_card(
            "Language",
            profile.get("language", "unknown"),
            profile.get("system_role", "operator"),
        )

    # 2. Trusted Device
    section_label("Trusted Device")
    dv1, dv2, dv3 = st.columns([2, 1, 1])
    with dv1:
        render_stat_card(
            "Device",
            "Trusted" if device_trusted else "Needs Registration",
            device_state.get("label") or "primary-control-device",
            tone="ok" if device_trusted else "warn",
        )
    _pending = ""
    if dv2.button("Device Report", key="home_device_report", use_container_width=True):
        _pending = "device report"
    if dv3.button("Register Device", key="home_device_register", use_container_width=True):
        _pending = "register device primary-control-device"

    # 3. Health row is in the stat bar above

    # 4. Command Runner
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

    if _pending:
        _run(_pending)

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

    run_col, report_col, refresh_col = st.columns([1, 1, 1.2])
    if run_col.button("Run Command", type="primary", use_container_width=True):
        _run(str(cmd_input))
        st.rerun()
    if report_col.button("Device Report", key="home_qa_device", use_container_width=True):
        _run("device report")
        st.rerun()
    if refresh_col.button("Auto Detect Device", key="home_qa_device_auto", use_container_width=True):
        _run("auto detect device primary-control-device")
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

    # 6. Primary Actions
    section_label("Quick Actions")
    qa1, qa2, qa3 = st.columns(3)
    if qa1.button("Status",   key="home_qa_status",   use_container_width=True): _run("status")
    if qa2.button("Workflow", key="home_qa_workflow",  use_container_width=True): _run("workflow")
    if qa3.button("Profile",  key="home_qa_profile",   use_container_width=True): _run("profile")

    qa4, qa5, qa6 = st.columns(3)
    if qa4.button("Memory",   key="home_qa_memory",   use_container_width=True): _run("memory")
    if qa5.button("AI Status",key="home_qa_ai_status",use_container_width=True): _run("ai status")
    if qa6.button("Logs",     key="home_qa_logs",     use_container_width=True): _run("logs")

    # 7. Recent Activity
    st.divider()
    section_label("Recent Activity")
    bus_lines = read_bus_log(lines=10)
    render_log_block("\n".join(bus_lines) if bus_lines else "No bus log entries.")

with right:
    section_label("Operational Snapshot")
    st.markdown(
        f"HI layer: {route_badge('hi' if listener_online else 'n/a')}",
        unsafe_allow_html=True,
    )
    render_kv_grid([
        ("Host",         state["system"].get("hostname", "unknown")),
        ("Connectivity", state["system"].get("connectivity", "unknown")),
        ("OS",           state["system"].get("operating_system", "unknown")),
        ("Language",     profile.get("language", "unknown")),
        ("Mode",         state["preferences"].get("response_mode", "unknown")),
        ("Device",       "trusted" if device_trusted else "unregistered"),
        ("Focus",        state["workflow"].get("current_focus") or "none"),
        ("Last Event",   state["health"].get("last_event_type", "none")),
        ("Domain",       profile.get("domain", "unknown")),
        ("Email",        profile.get("email", "unknown")),
    ])

    section_label("Recent Memory")
    render_memory_cards(state["memory"][-4:])

maybe_auto_refresh(True, 4)
