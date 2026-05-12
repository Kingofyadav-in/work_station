from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from services.conversation_manager import (
    clear_conversation,
    get_state,
    is_running,
    start_conversation,
    stop_conversation,
)
from services.model_selector import render_model_selector
from services.state_reader import get_dashboard_state
from services.ui_helpers import (
    inject_theme,
    maybe_auto_refresh,
    render_hero,
    render_live_strip,
    render_priority_level,
    render_stat_card,
    render_theme_toggle,
    section_label,
)
from services.voice_client import voice_available
from services.voice_client import get_voice_status

st.set_page_config(page_title="Conversation", page_icon="J", layout="wide")

_WAKE = "jarvis"

render_theme_toggle()
render_model_selector()
state = get_dashboard_state()

# ── Load state ────────────────────────────────────────────────────────────────
conv_state = get_state()
status     = conv_state["status"]
# Bug 5 fix: exclude "error" from running so auto-refresh pauses on errors
running    = is_running() and status not in ("stopped", "idle", "error")

# ── Sidebar settings ──────────────────────────────────────────────────────────
with st.sidebar:
    section_label("Conversation Settings")
    # Bug 1 fix: add key= to all sliders so values survive soft reruns
    listen_timeout = st.slider("Listen timeout (s)", 3, 20, 8,  key="conv_listen_timeout")
    phrase_limit   = st.slider("Phrase limit (s)",   3, 20, 10, key="conv_phrase_limit")
    if "conv_require_wake" not in st.session_state:
        st.session_state["conv_require_wake"] = False
    require_wake   = st.toggle(
        f"Require wake phrase ('{_WAKE}' …)",
        key="conv_require_wake",
        help="When on, Jarvis only processes speech that starts with the wake phrase.",
    )
    st.divider()
    refresh_rate = st.slider("Refresh rate (s)", 1, 5, 2, key="conv_refresh_rate")
    st.divider()
    st.caption(f"Status: **{status}**")
    st.caption(f"Messages: **{len(conv_state['conversation'])}**")

inject_theme()

render_hero(
    "Continuous Conversation",
    "Speak naturally — Jarvis listens continuously, processes your words, and responds in full detail.",
    eyebrow="Audio Mode",
)
render_live_strip(state)

# ── Live status bar ───────────────────────────────────────────────────────────
_STATUS_CFG: dict[str, tuple[str, str, str]] = {
    "idle":       ("#8095b0", "Ready",       "Press Start to begin."),
    "starting":   ("#FF671F", "Starting",    "Initializing microphone..."),
    "listening":  ("#3a9e62", "Listening",   "Speak now — Jarvis is listening."),
    "processing": ("#FF671F", "Processing",  "Analyzing your request..."),
    "speaking":   ("#2a9e96", "Speaking",    "Jarvis is responding."),
    "stopped":    ("#8095b0", "Stopped",     "Conversation ended. Press Start to restart."),
    "error":      ("#e05555", "Error",       conv_state.get("error", "Unknown error")),
}

color, label, hint = _STATUS_CFG.get(status, ("#8095b0", status, ""))
pulse_css = "animation:pulse-ring 2s ease-out infinite;" if status == "listening" else ""

st.markdown(
    f'<div style="display:flex;align-items:center;gap:0.85rem;padding:0.75rem 1rem;'
    f'background:var(--panel);border:1px solid var(--line);border-radius:14px;margin-bottom:1.2rem;">'
    f'<div style="width:12px;height:12px;border-radius:50%;background:{color};{pulse_css}flex-shrink:0;"></div>'
    f'<span style="font-weight:700;color:{color};font-size:0.97rem;">{label}</span>'
    f'<span style="color:var(--muted);font-size:0.88rem;">&nbsp;·&nbsp;{hint}</span>'
    f'</div>',
    unsafe_allow_html=True,
)

if status == "error" and conv_state.get("error"):
    st.error(conv_state["error"])

# ── Mic warning — before controls so user sees it before clicking Start ───────
_voice_ok = voice_available()
if not _voice_ok:
    st.warning(
        "Microphone not detected — check that `speech_recognition` and `pyaudio` are installed "
        "and a microphone is connected."
    )

voice_state = get_voice_status()
st.caption(f"Voice status: {voice_state.get('status', 'unknown')} · {voice_state.get('message', '')}")

# ── Status + controls ─────────────────────────────────────────────────────────
conv_priority = "high" if status == "error" else ("medium" if running else "low")
p1, p2, p3 = st.columns(3)
with p1:
    render_priority_level(conv_priority, hint if status != "error" else conv_state.get("error", "Conversation error."))
with p2:
    render_stat_card("Status", label, f"{len(conv_state['conversation'])} message(s)", tone="bad" if status == "error" else ("warn" if running else "ok"))
with p3:
    render_stat_card("Microphone", "Ready" if _voice_ok else "Missing", voice_state.get("message", ""), tone="ok" if _voice_ok else "warn")

section_label("Controls")

# Bug 3 fix: button label reflects actual running status
_STATUS_LABELS = {
    "starting":   "Starting…",
    "listening":  "Listening…",
    "processing": "Processing…",
    "speaking":   "Speaking…",
}
start_label = _STATUS_LABELS.get(status, "Running…") if running else "Start Conversation"

c1, c2, c3, _ = st.columns([1.2, 1, 1, 2.8])

if c1.button(
    start_label,
    type="primary",
    disabled=running or not _voice_ok,
    use_container_width=True,
):
    start_conversation(
        timeout=listen_timeout,
        phrase_time_limit=phrase_limit,
        require_wake_phrase=require_wake,
    )
    st.rerun()

if c2.button("Stop", disabled=not running, use_container_width=True):
    stop_conversation()
    st.rerun()

if c3.button("Reset", use_container_width=True, help="Force-stop and clear all conversation history"):
    stop_conversation()
    clear_conversation()
    st.rerun()

# ── Conversation display ──────────────────────────────────────────────────────
section_label("Conversation")
conversation = conv_state["conversation"]

if not conversation:
    st.markdown(
        '<div style="text-align:center;padding:3rem 1rem;color:var(--muted);font-size:0.93rem;">'
        "No messages yet. Press <strong>Start Conversation</strong> and speak to Jarvis."
        "</div>",
        unsafe_allow_html=True,
    )
else:
    for msg in conversation:
        role = msg["role"]
        text = msg["text"]
        ts   = msg["ts"]

        if role == "user":
            with st.chat_message("user"):
                st.write(text)
                st.caption(f"You · {ts}")
        elif role == "jarvis":
            with st.chat_message("assistant"):
                st.markdown(text)
                st.caption(f"Jarvis · {ts}")
        else:
            st.caption(f"  {text}")

    # Bug 8 fix: auto-scroll to bottom when new messages arrive
    components.html(
        "<script>window.parent.scrollTo(0, window.parent.document.body.scrollHeight);</script>",
        height=0,
    )

# ── Bug 2 fix: soft auto-refresh at BOTTOM (preserves session_state, no flash)
# maybe_auto_refresh sleeps then calls st.rerun() — content is already rendered above.
maybe_auto_refresh(running, refresh_rate)
