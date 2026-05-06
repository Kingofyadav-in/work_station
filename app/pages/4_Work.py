from __future__ import annotations

import streamlit as st

from services.jarvis_client import run_command
from services.model_selector import render_model_selector
from services.state_reader import get_dashboard_state
from services.tts_client import speak_full_result, speak_result, tts_available

from services.ui_helpers import (
    ensure_history,
    inject_theme,
    push_history,
    render_hero,
    render_history_with_actions,
    render_kv_grid,
    render_priority_level,
    render_result_with_confirmation,
    render_stat_card,
    render_theme_toggle,
    render_live_strip,
    section_label,
)


st.set_page_config(page_title="Work", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
state = get_dashboard_state()
ensure_history()
inject_theme()

render_hero(
    "Work / AI",
    "What are we working on? Current focus, plan a task, ask Jarvis, and check AI model status.",
    eyebrow="Work Surface",
)
render_live_strip(state)

workflow    = state.get("workflow", {})
preferences = state.get("preferences", {})

if "tts_speak_full_results" not in st.session_state:
    st.session_state["tts_speak_full_results"] = True
st.sidebar.toggle(
    "Speak full command results",
    key="tts_speak_full_results",
    help="When on, Jarvis reads the full command result after each action.",
)

# ── Priority, commands, result ─────────────────────────────────────────────────

open_tasks = [task for task in workflow.get("tasks", []) if task.get("status") not in {"done", "cancelled"}]
blocked_tasks = [task for task in open_tasks if task.get("blockers")]
work_priority = "high" if blocked_tasks else ("medium" if open_tasks else "low")
work_priority_detail = f"{len(blocked_tasks)} blocked task(s)." if blocked_tasks else f"{len(open_tasks)} open task(s)."

section_label("Priority")
p1, p2, p3 = st.columns(3)
with p1:
    render_priority_level(work_priority, work_priority_detail)
with p2:
    render_stat_card("Focus", workflow.get("current_focus") or "not set", f"Status: {workflow.get('status', 'unknown')}", tone="warn")
with p3:
    render_stat_card("Open Tasks", len(open_tasks), "Tracked unfinished work", tone="warn" if open_tasks else "ok")

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
    st.session_state["work_result"] = r
    st.session_state["work_last_cmd"] = cmd.strip()
    push_history(r)
    _tts(r)

section_label("Commands")

# Primary action buttons
b1, b2, b3, b4, b5 = st.columns(5)
if b1.button("Workflow",  key="work_workflow",  use_container_width=True): _run("workflow")
if b2.button("AI Status", key="work_ai_status", use_container_width=True): _run("ai status")
if b3.button("Logs",      key="work_logs",      use_container_width=True): _run("logs")
if b4.button("Context",   key="work_context",   use_container_width=True): _run("context")
if b5.button("Profiles",  key="work_profiles",  use_container_width=True): _run("profiles")

# Command runner
with st.form("work_cmd", clear_on_submit=False):
    cmd_col, btn_col = st.columns([5, 1])
    cmd = cmd_col.text_input(
        "Command",
        label_visibility="collapsed",
        key="work_cmd_input",
        placeholder="ask · plan · workflow · set current focus · ai status",
    )
    if btn_col.form_submit_button("Run", type="primary", use_container_width=True):
        _run(cmd)

result = st.session_state.get("work_result")
if result:
    render_result_with_confirmation(result, _run, key_prefix="work")

st.divider()

# ── Main content ───────────────────────────────────────────────────────────────
left, right = st.columns([1.4, 1])

with left:
    # Current Focus
    section_label("Current Focus")
    c1, c2 = st.columns([2, 1])
    with c1:
        render_stat_card(
            "Focus",
            workflow.get("current_focus") or "not set",
            f"Status: {workflow.get('status', 'unknown')}",
            tone="warn",
        )
    with c2:
        render_stat_card(
            "Response Mode",
            preferences.get("response_mode", "unknown"),
            "HI preference",
        )

    next_acts = workflow.get("next_actions", [])
    if next_acts:
        section_label("Next Actions")
        for act in next_acts:
            st.markdown(f"- {act}")

    section_label("Tracked Tasks")
    if open_tasks:
        for task in open_tasks[:8]:
            due = f" · due {task.get('due')}" if task.get("due") else ""
            estimate = f" · {task.get('estimate_minutes')}m" if task.get("estimate_minutes") else ""
            blockers = task.get("blockers") or []
            blocker_text = f" · blocked by {len(blockers)}" if blockers else ""
            st.markdown(f"**{task.get('title')}**  \n`{task.get('id')}` · {task.get('status')}{due}{estimate}{blocker_text}")
    else:
        st.caption("No open tracked tasks.")

    # Set Focus
    section_label("Set Focus")
    with st.form("work_focus_form", clear_on_submit=True):
        focus_val = st.text_input("New focus", placeholder="building Jarvis dashboard v2")
        if st.form_submit_button("Set Focus", type="primary"):
            if focus_val.strip():
                _run(f"set current focus {focus_val.strip()}")

    section_label("Add Task")
    with st.form("work_task_form", clear_on_submit=True):
        task_title = st.text_input("Task", placeholder="ship semantic memory search")
        if st.form_submit_button("Add Task", type="primary"):
            if task_title.strip():
                _run(f"add task {task_title.strip()}")

    # Plan Task
    section_label("Plan Task")
    with st.form("work_plan_form", clear_on_submit=True):
        plan_val = st.text_input("Plan topic", placeholder="refactor the dashboard pages")
        if st.form_submit_button("Plan", type="primary"):
            if plan_val.strip():
                _run(f"plan {plan_val.strip()}")

    # Ask Jarvis
    section_label("Ask Jarvis")
    with st.form("work_ask_form", clear_on_submit=True):
        ask_val = st.text_area(
            "Question",
            placeholder="what should I work on next based on my current focus and memory?",
            height=80,
        )
        ask_cols = st.columns([2, 2, 3])
        if ask_cols[0].form_submit_button("Ask", type="primary", use_container_width=True):
            if ask_val.strip():
                _run(f"ask {ask_val.strip()}")
        if ask_cols[1].form_submit_button("Next Priority", use_container_width=True):
            _run("ask what should I work on next based on my current focus and memory")

with right:
    section_label("Workflow State")
    render_kv_grid([
        ("Current Focus",  workflow.get("current_focus") or "none"),
        ("Status",         workflow.get("status", "unknown")),
        ("Next Actions",   len(workflow.get("next_actions", []))),
        ("Open Tasks",     len([task for task in workflow.get("tasks", []) if task.get("status") not in {"done", "cancelled"}])),
        ("Response Mode",  preferences.get("response_mode", "unknown")),
        ("Verbosity",      preferences.get("verbosity", "unknown")),
    ])
    st.caption(f"State snapshot: {state.get('fetched_at', 'n/a')[:19].replace('T', ' ')}")

    section_label("Voice Input")
    st.info("Voice conversation is available on the **Conversation** page in the sidebar.")

    # Command History
    render_history_with_actions("work", _run)
