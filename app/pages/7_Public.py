from __future__ import annotations

import html as _html
from collections import defaultdict
from datetime import datetime

import streamlit as st

from services.model_selector import render_model_selector
from services.public_intake import get_public_inbox_state
from services.public_jarvis import (
    analyze_topics,
    get_knowledge_status,
    load_config,
    read_recent_questions,
    save_config,
    test_public_message,
)
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


st.set_page_config(page_title="Public", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
ensure_history()
inject_theme()

# ── Load shared data once ─────────────────────────────────────────────────────
cfg             = load_config()
pages           = get_knowledge_status()
loaded          = sum(1 for p in pages if p["available"])
inbox_state     = get_public_inbox_state(limit=500)
public_questions = read_recent_questions(limit=100)

render_hero(
    "Public",
    "Website-facing Jarvis assistant, public chat, enquiries, and access requests — manage your public presence from one place.",
    eyebrow="Public Layer",
)

# ── Shared stat row ───────────────────────────────────────────────────────────
summary  = inbox_state.get("summary", {})
items    = summary.get("items", [])
enquiries = inbox_state.get("enquiries", [])
signups   = inbox_state.get("signups", [])

ps0, ps1, ps2, ps3, ps4 = st.columns(5)
with ps0:
    render_stat_card("Public Chat", "On" if cfg.get("enabled") else "Off", "Website assistant",
                     tone="ok" if cfg.get("enabled") else "warn")
with ps1:
    render_stat_card("Knowledge", f"{loaded} / {len(pages)}", "Loaded source pages",
                     tone="ok" if loaded else "warn")
with ps2:
    render_stat_card("Requests", summary.get("count", 0), "All public submissions",
                     tone="ok" if items else "warn")
with ps3:
    render_stat_card("Enquiries", summary.get("enquiry_count", 0), "Contact requests")
with ps4:
    render_stat_card("Access", summary.get("signup_count", 0), "Signup requests")

# ── Flat tabs — no nesting ─────────────────────────────────────────────────────
tab_cfg, tab_test, tab_knowledge, tab_questions, tab_inbox = st.tabs([
    "Config", "Test Chat", "Knowledge", "Questions", "Inbox",
])


# ── CONFIG ────────────────────────────────────────────────────────────────────
with tab_cfg:
    left, right = st.columns([1.2, 1])
    with left:
        section_label("Controls")
        with st.form("public_jarvis_config"):
            enabled  = st.toggle("Enable public chat", value=cfg["enabled"])
            fallback = st.toggle("Use local fallback when AI provider is down", value=cfg["fallback"])
            rpm = st.slider("Rate limit per visitor per minute", min_value=1, max_value=120, value=int(cfg["rpm"]))
            provider = st.selectbox(
                "Public provider override",
                ["", "ollama", "anthropic", "openai"],
                index=(
                    ["", "ollama", "anthropic", "openai"].index(cfg.get("provider", ""))
                    if cfg.get("provider", "") in {"", "ollama", "anthropic", "openai"}
                    else 0
                ),
                help="Leave blank to use the global model selector.",
            )
            model  = st.text_input("Public model override", value=cfg.get("model", ""), placeholder="llama3.2:3b")
            prompt = st.text_area("Public system prompt", value=cfg.get("prompt", ""), height=160)
            submitted = st.form_submit_button("Save Public Jarvis Settings", type="primary")
        if submitted:
            save_config({
                "enabled": enabled, "fallback": fallback, "rpm": rpm,
                "provider": provider,
                "model": str(model or "").strip(),
                "prompt": str(prompt or "").strip(),
            })
            st.success("Public Jarvis settings saved. The API reads this file dynamically.")
            st.rerun()
    with right:
        section_label("Status")
        render_kv_grid([
            ("Enabled",          "Yes" if cfg["enabled"] else "No"),
            ("Fallback",         "Yes" if cfg["fallback"] else "No"),
            ("Rate Limit (rpm)", str(cfg["rpm"])),
            ("Provider",         cfg.get("provider") or "(global)"),
            ("Model",            cfg.get("model") or "(global)"),
        ])
        section_label("Embed Snippet")
        render_log_block(
            '<script src="/api-static/jarvis-widget.js" '
            'data-endpoint="/api/jarvis-chat" '
            'data-title="Jarvis AI" '
            'data-subtitle="Ask Jarvis about King Yadav and the website." '
            'defer></script>'
        )
        section_label("Security")
        st.caption("Injection guard: active — patterns like 'ignore previous instructions' are intercepted.")
        st.caption("Source citations: active — AI mentions which page an answer comes from.")
        st.caption("Rate limiting: per-IP sliding window, configurable above.")


# ── TEST CHAT ─────────────────────────────────────────────────────────────────
with tab_test:
    section_label("Test Public Chat")
    st.caption("Send a message using the public system prompt. No rate limiting applied here — admin only.")
    with st.form("public_test_chat"):
        test_msg = st.text_input("Message", placeholder="What services does King Yadav offer?")
        test_submitted = st.form_submit_button("Send", type="primary")
    if test_submitted and test_msg.strip():
        with st.spinner("Calling public AI..."):
            result = test_public_message(test_msg.strip())
        if result["ok"]:
            st.success(f"Provider: {result.get('provider')} · Model: {result.get('model')}")
            st.markdown(result["reply"])
        else:
            st.error(result["error"])
    with st.expander("Active system prompt", expanded=False):
        active_prompt = cfg.get("prompt") or "(using default — edit in Config tab)"
        render_log_block(active_prompt)


# ── KNOWLEDGE ─────────────────────────────────────────────────────────────────
with tab_knowledge:
    section_label("Site Knowledge Sources")
    st.caption(
        "These pages are read when the API builds context for public chat answers. "
        "Pages marked unavailable are skipped."
    )
    total_chars = sum(p["chars"] for p in pages)
    km1, km2 = st.columns(2)
    km1.metric("Pages loaded", f"{loaded} / {len(pages)}")
    km2.metric("Total context chars", f"{total_chars:,}")
    rows = [{"Page": p["name"], "Available": "✓" if p["available"] else "✗",
             "Chars": p["chars"] if p["available"] else 0} for p in pages]
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if loaded == 0:
        st.warning(
            "No site pages found. Set `JARVIS_PUBLIC_SITE_ROOT` to the path of your "
            "static site root. The AI will still respond using its training knowledge."
        )


# ── QUESTIONS ─────────────────────────────────────────────────────────────────
with tab_questions:
    q_items = read_recent_questions(limit=100)
    if not q_items:
        st.info("No public questions logged yet.")
    else:
        ql, qr = st.columns([2, 1])
        with qr:
            section_label("Topic Analysis")
            topics = analyze_topics(q_items)
            if topics:
                st.dataframe(
                    [{"Topic": word, "Count": count} for word, count in topics],
                    use_container_width=True, hide_index=True,
                )
            else:
                st.caption("Not enough data for topic analysis.")
            section_label("Mode Breakdown")
            mode_counts: dict[str, int] = {}
            for item in q_items:
                mode = item.get("mode", "unknown")
                mode_counts[mode] = mode_counts.get(mode, 0) + 1
            render_kv_grid([(m, str(c)) for m, c in sorted(mode_counts.items())])
        with ql:
            section_label(f"Recent Questions ({len(q_items)})")
            q_limit = st.slider("Show last N", 10, 100, 25, step=5, key="pub_q_limit")
            for item in q_items[:q_limit]:
                render_question_card(item)


# ── INBOX ─────────────────────────────────────────────────────────────────────
with tab_inbox:
    ic0, ic1, ic2, ic3 = st.columns(4)
    with ic0:
        render_priority_level("medium" if items else "low",
                              f"{summary.get('count', 0)} public submission(s).")
    with ic1:
        render_stat_card("Requests", summary.get("count", 0), "All public submissions",
                         tone="ok" if items else "warn")
    with ic2:
        render_stat_card("Enquiries", summary.get("enquiry_count", 0), "Contact requests")
    with ic3:
        render_stat_card("Access", summary.get("signup_count", 0), "Signup / access requests")

    if items:
        section_label("Daily Activity (last 30 days)")
        daily: dict[str, dict[str, int]] = defaultdict(lambda: {"enquiry": 0, "signup": 0})
        for item in items:
            day = str(item.get("ts", ""))[:10]
            if day:
                daily[day][item.get("kind", "other")] += 1
        sorted_days = sorted(daily.keys())[-30:]
        col_chart, _ = st.columns([3, 1])
        with col_chart:
            import pandas as pd
            df = pd.DataFrame(
                {"Enquiries": [daily[d]["enquiry"] for d in sorted_days],
                 "Signups":   [daily[d]["signup"]   for d in sorted_days]},
                index=sorted_days,
            )
            st.bar_chart(df, height=200)

    il, ir = st.columns([1.15, 0.85], gap="large")
    with il:
        section_label("Recent Submissions")
        search_q = st.text_input("Search", placeholder="name, email, subject…", key="inbox_search")

        def _matches(item: dict, q: str) -> bool:
            if not q:
                return True
            q = q.lower()
            return any(q in str(v).lower() for v in [
                item.get("name", ""), item.get("email", ""), item.get("subject", ""),
                item.get("message", ""), item.get("handle", ""), item.get("reason", ""),
            ])

        inbox_view = st.radio("View", ["Enquiries", "Access Requests"], horizontal=True, key="inbox_view_radio")

        if inbox_view == "Enquiries":
            filtered_enq = [e for e in enquiries if _matches(e, search_q)]
            if filtered_enq:
                st.caption(f"{len(filtered_enq)} enquiry(s){' matching search' if search_q else ''}.")
                for item in filtered_enq[:50]:
                    with st.container():
                        st.markdown(
                            f"**{_html.escape(str(item.get('name') or 'Unnamed'))}** "
                            f"· `{_html.escape(str(item.get('email') or 'no email'))}`  \n"
                            f"**{_html.escape(str(item.get('subject') or 'No subject'))}**  \n"
                            f"<span style='color:var(--muted);font-size:0.78rem;'>"
                            f"{_html.escape(str(item.get('ts', '')[:19].replace('T', ' ')))} "
                            f"· {_html.escape(str(item.get('source', '')))} "
                            f"· page: {_html.escape(str(item.get('page', '') or '—'))}"
                            f"</span>",
                            unsafe_allow_html=True,
                        )
                        if item.get("message"):
                            with st.expander("Message", expanded=False):
                                st.text(item["message"])
                        st.divider()
            else:
                st.caption("No enquiries matching search." if search_q else "No enquiries yet.")
        else:
            filtered_sig = [s for s in signups if _matches(s, search_q)]
            if filtered_sig:
                st.caption(f"{len(filtered_sig)} access request(s){' matching search' if search_q else ''}.")
                for item in filtered_sig[:50]:
                    render_kv_grid([
                        ("Name",   item.get("name") or "none"),
                        ("Email",  item.get("email") or "none"),
                        ("Handle", item.get("handle") or "none"),
                        ("Reason", item.get("reason") or "none"),
                        ("Page",   item.get("page") or "none"),
                        ("Source", item.get("source") or "none"),
                        ("Time",   item.get("ts", "")[:19].replace("T", " ")),
                    ])
                    if item.get("message"):
                        with st.expander("Message", expanded=False):
                            st.text(item["message"])
                    st.divider()
            else:
                st.caption("No access requests matching search." if search_q else "No access requests yet.")

    with ir:
        section_label("Public Chat")
        st.caption("Latest public questions from the website widget.")
        if public_questions:
            q_n = st.slider("Show latest", 5, 50, 10, key="public_inbox_questions_limit")
            for item in public_questions[:q_n]:
                render_question_card(item)
        else:
            st.caption("No public chat activity yet.")

        section_label("Inbox Summary")
        latest = summary.get("latest", {})
        if latest:
            render_kv_grid([
                ("Latest Kind",   latest.get("kind", "none")),
                ("Latest Status", latest.get("status", "none")),
                ("Latest Client", latest.get("client", "none")),
                ("Latest Time",   latest.get("ts", "")[:19].replace("T", " ")),
                ("Latest Name",   latest.get("name", "none")),
                ("Latest Page",   latest.get("page", "none") or "—"),
            ])
        else:
            st.caption("No intake records yet.")
        st.caption(f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


maybe_auto_refresh(True, 8)
