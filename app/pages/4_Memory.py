from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

from services.jarvis_client import run_command
from services.model_selector import render_model_selector
from services.state_reader import get_dashboard_state
from services.ui_helpers import (
    ensure_history,
    inject_theme,
    maybe_auto_refresh,
    push_history,
    refresh_timestamp,
    render_hero,
    render_memory_cards,
    render_priority_level,
    render_result_with_confirmation,
    render_stat_card,
    render_theme_toggle,
    render_live_strip,
    section_label,
)


st.set_page_config(page_title="Memory", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()

# Load state first so sidebar can show real type options
state = get_dashboard_state()
ensure_history()
inject_theme()

memory: list[dict] = state.get("memory", [])
all_types = sorted({e.get("type", "note") for e in memory})

# ── Sidebar filters ────────────────────────────────────────────────────────────
with st.sidebar:
    section_label("Memory Filters")

    date_filter = st.selectbox(
        "Time range",
        ["All time", "Today", "Last 7 days", "Last 30 days"],
        key="mem_date_filter",
    )
    selected_type = st.selectbox(
        "Type",
        ["All types"] + all_types,
        key="mem_type_filter",
    )
    sort_order = st.radio(
        "Sort",
        ["Newest first", "Oldest first"],
        horizontal=True,
        key="mem_sort",
    )
    show_numbers = st.checkbox("Show entry numbers", value=False, key="mem_show_numbers")

    st.divider()
    live = st.checkbox("Live refresh", value=False, key="mem_live_refresh")
    if live:
        st.slider("Refresh every (s)", 5, 60, 15, key="mem_refresh_interval")
        st.caption(f"Updated: {refresh_timestamp()}")


# ── Filter + sort ──────────────────────────────────────────────────────────────

def _apply_filters(entries: list[dict]) -> list[dict]:
    now = datetime.now(timezone.utc)
    cutoff: datetime | None = None
    if date_filter == "Today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_filter == "Last 7 days":
        cutoff = now - timedelta(days=7)
    elif date_filter == "Last 30 days":
        cutoff = now - timedelta(days=30)

    out = []
    for e in entries:
        if cutoff:
            try:
                ts = datetime.fromisoformat(e.get("created_at", ""))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
            except (ValueError, TypeError):
                pass
        if selected_type != "All types" and e.get("type", "note") != selected_type:
            continue
        out.append(e)

    return out if sort_order == "Oldest first" else list(reversed(out))


filtered = _apply_filters(memory)

# ── Page header ────────────────────────────────────────────────────────────────
render_hero(
    "Memory",
    "What should Jarvis remember? Add notes, filter by date and type, and review curated memory.",
    eyebrow="Curated Memory",
)
render_live_strip(state)

# ── Stat row ──────────────────────────────────────────────────────────────────
last_ts = memory[-1].get("created_at", "none")[:19].replace("T", " ") if memory else "none"
c0, c1, c2, c3 = st.columns(4)
with c0:
    render_priority_level("medium" if not memory else "low", "Add memory when context is missing." if not memory else "Curated entries available.")
with c1:
    render_stat_card("Total", len(memory), "All entries", tone="ok" if memory else "warn")
with c2:
    render_stat_card("Showing", len(filtered), f"{date_filter} · {selected_type}", tone="ok" if filtered else "warn")
with c3:
    render_stat_card("Last Added", last_ts, f"{len(all_types)} type(s): {', '.join(all_types[:3])}")

st.caption(f"Snapshot: {state.get('fetched_at', 'n/a')[:19].replace('T', ' ')}")


# ── Commands, result ───────────────────────────────────────────────────────────

def _run(cmd: str) -> None:
    if not cmd.strip():
        return
    r = run_command(cmd.strip())
    st.session_state["memory_result"] = r
    push_history(r)


if "mem_panel" not in st.session_state:
    st.session_state["mem_panel"] = "show"

section_label("Commands")
b1, b2, b3 = st.columns(3)
if b1.button("Show Memory",   key="mem_show",       use_container_width=True):
    st.session_state["mem_panel"] = "show"
    _run("memory")
if b2.button("Add Memory",    key="mem_add_btn",    use_container_width=True):
    st.session_state["mem_panel"] = "add"
if b3.button("Search Memory", key="mem_search_btn", use_container_width=True):
    st.session_state["mem_panel"] = "search"

with st.form("memory_cmd", clear_on_submit=False):
    cmd_col, btn_col = st.columns([5, 1])
    cmd = cmd_col.text_input(
        "Command",
        label_visibility="collapsed",
        placeholder="memory · add memory <note> · search memory <query>",
    )
    if btn_col.form_submit_button("Run", type="primary", use_container_width=True):
        _run(cmd)

result = st.session_state.get("memory_result")
if result:
    render_result_with_confirmation(result, _run, key_prefix="memory")

# ── Main content ───────────────────────────────────────────────────────────────
left, right = st.columns([1.05, 0.95], gap="large")
_active = st.session_state.get("mem_panel", "show")

with left:
    section_label("Add Memory")
    if _active == "add":
        st.info("Fill in the fields and press Add Memory.")
    with st.form("memory_add_form", clear_on_submit=True):
        note = st.text_area(
            "Memory note",
            placeholder="finished X · decided Y · blocked by Z · learned that …",
            height=80,
        )
        fc1, fc2 = st.columns(2)
        mem_type = fc1.selectbox(
            "Type",
            ["note", "decision", "insight", "reminder", "event"],
            key="mem_add_type",
        )
        mem_tag = fc2.text_input("Tag", placeholder="jarvis · focus · venture", key="mem_add_tag")
        fc3, fc4 = st.columns(2)
        mem_importance = fc3.slider("Importance", 1, 5, 3, key="mem_add_importance")
        mem_visibility = fc4.radio("Visibility", ["private", "public"], horizontal=True, key="mem_add_visibility")
        if st.form_submit_button("Add Memory", type="primary"):
            if note.strip():
                entry = {
                    "type": mem_type,
                    "text": note.strip(),
                    "tag": mem_tag.strip().lower() if mem_tag.strip() else "",
                    "importance": mem_importance,
                    "visibility": mem_visibility,
                    "source": "user",
                }
                import json as _json
                _run(f"add memory {_json.dumps(entry)}")
                st.session_state["mem_panel"] = "show"
                st.success("Memory added.")

    section_label("Search Memory")
    if _active == "search":
        st.info("Enter a keyword and press Search.")
    with st.form("memory_search_form", clear_on_submit=False):
        query = st.text_input("Search query", placeholder="dashboard · focus · bug · jarvis")
        if st.form_submit_button("Search", type="primary"):
            if query.strip():
                _run(f"search memory {query.strip()}")

    section_label("Delete Memory")
    with st.form("memory_delete_form", clear_on_submit=True):
        del_id = st.text_input("Memory ID (8-char prefix shown on card)", placeholder="a3f1b2c4", key="mem_del_id")
        if st.form_submit_button("Delete", type="secondary"):
            if del_id.strip():
                _run(f"delete memory {del_id.strip()}")
                st.session_state["mem_panel"] = "show"

with right:
    label = f"Memory Entries ({len(filtered)} of {len(memory)})"
    section_label(label)
    if filtered:
        render_memory_cards(filtered, numbered=show_numbers)
    elif memory:
        st.info("No entries match the current filters. Try 'All time' or 'All types'.")
    else:
        st.info("No memory entries yet. Add a note using the form on the left.")

maybe_auto_refresh(live, st.session_state.get("mem_refresh_interval", 15))
