from __future__ import annotations

import streamlit as st

from services.model_selector import render_model_selector
from services.public_jarvis import (
    analyze_topics,
    get_knowledge_status,
    load_config,
    read_recent_questions,
    save_config,
    test_public_message,
)
from services.ui_helpers import (
    inject_theme,
    render_hero,
    render_kv_grid,
    render_log_block,
    render_priority_level,
    render_question_card,
    render_stat_card,
    render_theme_toggle,
    section_label,
)

st.set_page_config(page_title="Public Jarvis", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
inject_theme()

render_hero(
    "Public Jarvis",
    "Control the website-facing Jarvis assistant. This page does not expose private command execution; "
    "it only manages public chat behavior.",
    eyebrow="Website AI",
)

cfg = load_config()

section_label("Priority")
pages = get_knowledge_status()
loaded = sum(1 for p in pages if p["available"])
p1, p2, p3 = st.columns(3)
with p1:
    render_priority_level("medium" if cfg.get("enabled") and not loaded else "low", "Knowledge pages missing." if cfg.get("enabled") and not loaded else "Public chat config loaded.")
with p2:
    render_stat_card("Public Chat", "On" if cfg.get("enabled") else "Off", "Website assistant")
with p3:
    render_stat_card("Knowledge", f"{loaded} / {len(pages)}", "Loaded source pages", tone="ok" if loaded else "warn")

tab_cfg, tab_test, tab_knowledge, tab_questions = st.tabs([
    "Config", "Test Chat", "Knowledge Sources", "Recent Questions"
])

# ── Tab 1: Config ─────────────────────────────────────────────────────────────
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

# ── Tab 2: Test Chat ──────────────────────────────────────────────────────────
with tab_test:
    section_label("Test Public Chat")
    st.caption(
        "Send a message using the public system prompt. "
        "No rate limiting applied here — admin only."
    )

    with st.form("public_test_chat"):
        test_msg = st.text_input(
            "Message",
            placeholder="What services does King Yadav offer?",
        )
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

# ── Tab 3: Knowledge Sources ──────────────────────────────────────────────────
with tab_knowledge:
    section_label("Site Knowledge Sources")
    st.caption(
        "These pages are read when the API builds context for public chat answers. "
            "Pages marked unavailable are skipped; the AI answers from remaining content."
    )

    total_chars = sum(p["chars"] for p in pages)

    meta1, meta2 = st.columns(2)
    meta1.metric("Pages loaded", f"{loaded} / {len(pages)}")
    meta2.metric("Total context chars", f"{total_chars:,}")

    rows = []
    for p in pages:
        status_icon = "✓" if p["available"] else "✗"
        rows.append({
            "Page":      p["name"],
            "Available": status_icon,
            "Chars":     p["chars"] if p["available"] else 0,
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if loaded == 0:
        st.warning(
            "No site pages found. Set `JARVIS_PUBLIC_SITE_ROOT` to the path of your "
            "static site root (e.g. `/home/kingofyadav/HI`). "
            "The AI will still respond using its training knowledge and the system prompt."
        )

# ── Tab 4: Recent Questions ───────────────────────────────────────────────────
with tab_questions:
    items = read_recent_questions(limit=100)

    if not items:
        st.info("No public questions logged yet.")
    else:
        left_q, right_q = st.columns([2, 1])

        with right_q:
            section_label("Topic Analysis")
            topics = analyze_topics(items)
            if topics:
                st.dataframe(
                    [{"Topic": word, "Count": count} for word, count in topics],
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("Not enough data for topic analysis.")

            section_label("Mode Breakdown")
            mode_counts: dict[str, int] = {}
            for item in items:
                mode = item.get("mode", "unknown")
                mode_counts[mode] = mode_counts.get(mode, 0) + 1
            render_kv_grid([(m, str(c)) for m, c in sorted(mode_counts.items())])

        with left_q:
            section_label(f"Recent Questions ({len(items)})")
            limit = st.slider("Show last N", 10, 100, 25, step=5)
            for item in items[:limit]:
                render_question_card(item)
