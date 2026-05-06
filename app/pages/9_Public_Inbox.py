from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from services.model_selector import render_model_selector
from services.public_intake import get_public_inbox_state
from services.public_jarvis import load_config, read_recent_questions
from services.ui_helpers import (
    ensure_history,
    inject_theme,
    maybe_auto_refresh,
    render_hero,
    render_kv_grid,
    render_log_block,
    render_priority_level,
    render_question_card,
    render_stat_card,
    render_theme_toggle,
    section_label,
)


st.set_page_config(page_title="Public Inbox", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
ensure_history()
inject_theme()

state = get_public_inbox_state(limit=200)
cfg = load_config()
public_questions = read_recent_questions(limit=100)

render_hero(
    "Public Inbox",
    "Website chat, enquiries, and access requests land here for review from the private dashboard.",
    eyebrow="Web Intake",
)

summary = state.get("summary", {})
items = summary.get("items", [])
enquiries = state.get("enquiries", [])
signups = state.get("signups", [])

section_label("Priority")
inbox_priority = "medium" if items else "low"
c0, c1, c2, c3, c4 = st.columns(5)
with c0:
    render_priority_level(inbox_priority, f"{summary.get('count', 0)} public submission(s).")
with c1:
    render_stat_card("Requests", summary.get("count", 0), "All public submissions", tone="ok" if items else "warn")
with c2:
    render_stat_card("Enquiries", summary.get("enquiry_count", 0), "Contact requests")
with c3:
    render_stat_card("Access", summary.get("signup_count", 0), "Signup / access requests")
with c4:
    render_stat_card("Chat", "On" if cfg.get("enabled") else "Off", "Public Jarvis chat")

left, right = st.columns([1.15, 0.85], gap="large")

with left:
    section_label("Recent Submissions")
    tab1, tab2 = st.tabs(["Enquiries", "Access Requests"])
    with tab1:
        if enquiries:
            for item in enquiries[:50]:
                st.markdown(
                    f"**{html.escape(str(item.get('name') or 'Unnamed'))}** · `{html.escape(str(item.get('email') or 'no email'))}`  \n"
                    f"{html.escape(str(item.get('subject') or 'No subject'))}  \n"
                    f"<span style='color:var(--muted);font-size:0.78rem;'>{html.escape(str(item.get('ts', '')[:19].replace('T', ' ')))}</span>",
                    unsafe_allow_html=True,
                )
                render_log_block(item.get("message", ""))
        else:
            st.caption("No enquiries yet.")
    with tab2:
        if signups:
            for item in signups[:50]:
                rows = [
                    ("Name", item.get("name") or "none"),
                    ("Email", item.get("email") or "none"),
                    ("Handle", item.get("handle") or "none"),
                    ("Reason", item.get("reason") or "none"),
                    ("Page", item.get("page") or "none"),
                    ("Time", item.get("ts", "")[:19].replace("T", " ")),
                ]
                render_kv_grid(rows)
                render_log_block(item.get("message", ""))
        else:
            st.caption("No access requests yet.")

with right:
    section_label("Public Chat")
    st.caption("Latest public questions from the website widget.")
    if public_questions:
        limit = st.slider("Show latest", 5, 50, 10, key="public_inbox_questions_limit")
        for item in public_questions[:limit]:
            render_question_card(item)
    else:
        st.caption("No public chat activity yet.")

    section_label("Inbox Summary")
    latest = summary.get("latest", {})
    if latest:
        render_kv_grid([
            ("Latest Kind", latest.get("kind", "none")),
            ("Latest Status", latest.get("status", "none")),
            ("Latest Client", latest.get("client", "none")),
            ("Latest Time", latest.get("ts", "")[:19].replace("T", " ")),
        ])
    else:
        st.caption("No intake records yet.")

    st.caption(f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

maybe_auto_refresh(True, 8)
