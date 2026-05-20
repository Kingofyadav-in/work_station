from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

ROOT_DIR = Path(__file__).resolve().parents[2]
_HISTORY_PATH = ROOT_DIR / "logs" / "dashboard_history.jsonl"
_HISTORY_KEEP = 50

# ── CSS themes — loaded from app/static/ ───────────────────────────────────────

_STATIC_DIR = ROOT_DIR / "app" / "static"


def _load_css(filename: str) -> str:
    path = _STATIC_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


_CSS_VARS_LIGHT = _load_css("dashboard-vars-light.css")
_CSS_VARS_DARK = _load_css("dashboard-vars-dark.css")
_CSS_COMMON = _load_css("dashboard-common.css")
_CSS_DARK_OVERRIDES = _load_css("dashboard-dark-overrides.css")


def _theme_mode() -> str:
    mode = st.session_state.get("theme_mode")
    if mode in {"System", "Dark", "Light"}:
        return mode
    if st.session_state.get("dark_mode"):
        return "Dark"
    return "System"


def inject_theme() -> None:
    mode = _theme_mode()
    if mode == "Dark":
        css_vars = _CSS_VARS_DARK
        dark_block = _CSS_DARK_OVERRIDES
    elif mode == "Light":
        css_vars = _CSS_VARS_LIGHT
        dark_block = ""
    else:
        css_vars = _CSS_VARS_LIGHT
        dark_block = f"@media (prefers-color-scheme: dark) {{\n{_CSS_VARS_DARK}\n{_CSS_DARK_OVERRIDES}\n}}"
    st.markdown(
        f"<style>{css_vars}\n{_CSS_COMMON}\n{dark_block}</style>",
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    from datetime import datetime as _dt
    st.sidebar.markdown(
        '<div class="jarvis-sidebar-brand">'
        '<div class="jarvis-sidebar-logo">J</div>'
        '<div class="jarvis-sidebar-meta">'
        '<div class="jarvis-sidebar-wordmark">Jarvis</div>'
        '<div class="jarvis-sidebar-tagline">Command Panel</div>'
        '</div>'
        '<div class="jarvis-sidebar-online">'
        '<div class="jarvis-sidebar-dot"></div>'
        '<div class="jarvis-sidebar-online-label">Live</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_theme_toggle() -> None:
    render_sidebar_brand()

    st.sidebar.markdown(
        '<div class="jarvis-sidebar-sep">'
        '<span class="jarvis-sidebar-sep-label">Settings</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    mode = _theme_mode()
    if "theme_mode" not in st.session_state:
        st.session_state["theme_mode"] = mode
    st.session_state["dark_mode"] = mode == "Dark"
    selected = st.sidebar.selectbox(
        "Theme",
        options=("System", "Dark", "Light"),
        index=("System", "Dark", "Light").index(mode),
        key="theme_mode",
    )
    st.session_state["dark_mode"] = selected == "Dark"
    if "live_updates_enabled" not in st.session_state:
        st.session_state["live_updates_enabled"] = True
    st.sidebar.toggle(
        "Live updates",
        key="live_updates_enabled",
        help="Master switch for every auto-refresh timer in the dashboard.",
    )

    from datetime import datetime as _dt
    _version = "v" + (ROOT_DIR / "VERSION").read_text(encoding="utf-8").strip() if (ROOT_DIR / "VERSION").exists() else "v?"
    st.sidebar.markdown(
        '<div class="jarvis-sidebar-footer">'
        f'<span class="jarvis-sidebar-footer-text">Jarvis&nbsp;&nbsp;{_version}</span>'
        f'<span class="jarvis-sidebar-footer-ts">{_dt.now().strftime("%H:%M")}</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_tts_toggle() -> None:
    if "tts_enabled" not in st.session_state:
        st.session_state["tts_enabled"] = True
    st.sidebar.toggle(
        "Audio confirmation",
        key="tts_enabled",
    )


# ── Layout helpers ─────────────────────────────────────────────────────────────

def render_hero(title: str, subtitle: str, *, eyebrow: str = "Jarvis Console") -> None:
    st.markdown(
        (
            '<div class="jarvis-hero">'
            f'<div class="jarvis-eyebrow">{html.escape(eyebrow)}</div>'
            f'<div class="jarvis-title">{html.escape(title)}</div>'
            f'<div class="jarvis-subtitle">{html.escape(subtitle)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_website_jarvis_hero(profile: dict[str, Any] | None = None) -> None:
    profile = profile or {}
    site_url = str(profile.get("website") or "https://kingofyadav.in")
    owner = str(profile.get("full_name") or profile.get("display_name") or "Amit Ku Yadav")
    location = str(profile.get("location") or "Bhagalpur, Bihar, India")
    brand = str(profile.get("brand") or "kingofyadav.in")
    ventures = profile.get("ventures", [])
    venture_count = len(ventures) if isinstance(ventures, list) else 0
    st.markdown(
        (
            '<div class="jarvis-site-hero">'
            '<div>'
            '<div class="jarvis-site-kicker">Live Website AI Layer</div>'
            f'<div class="jarvis-site-title">Jarvis AI for {html.escape(brand)}</div>'
            '<div class="jarvis-site-copy">'
            f'{html.escape(owner)} public website, HI Life OS identity, ventures, public questions, '
            'and dashboard operations in one command surface. Use this panel to jump from local control '
            'to the live website and public AI workflow.'
            '</div>'
            '<div class="jarvis-site-actions">'
            f'<a class="jarvis-site-action primary" href="{html.escape(site_url)}" target="_blank" rel="noopener noreferrer">Open Live Website</a>'
            '<a class="jarvis-site-action" href="/Public" target="_self">Public AI</a>'
            '<a class="jarvis-site-action" href="/Identity_Device" target="_self">Identity</a>'
            '<a class="jarvis-site-action" href="/System_Health" target="_self">System Health</a>'
            '</div>'
            '</div>'
            '<div class="jarvis-site-panel">'
            f'<div class="jarvis-site-panel-row"><span>Owner</span><strong>{html.escape(owner)}</strong></div>'
            f'<div class="jarvis-site-panel-row"><span>Location</span><strong>{html.escape(location)}</strong></div>'
            f'<div class="jarvis-site-panel-row"><span>Ventures</span><strong>{venture_count}</strong></div>'
            '<div class="jarvis-site-panel-row"><span>Status</span><strong>Live dashboard linked</strong></div>'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def section_label(text: str) -> None:
    st.markdown(
        f'<div class="jarvis-section-label">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


def render_stat_card(label: str, value: Any, hint: str = "", *, tone: str = "neutral", pulse: bool = False) -> None:
    tone_class = {"ok": "jarvis-card-ok", "warn": "jarvis-card-warn", "bad": "jarvis-card-bad"}.get(tone, "")
    pulse_html = '<span class="jarvis-pulse"></span>' if pulse else ""
    st.markdown(
        (
            f'<div class="jarvis-card {tone_class}">'
            f'<div class="jarvis-card-title">{html.escape(str(label))}</div>'
            f'<div class="jarvis-card-value">{pulse_html}{html.escape(str(value))}</div>'
            f'<div class="jarvis-card-hint">{html.escape(str(hint))}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _priority_tone(level: str) -> str:
    value = str(level or "").strip().lower()
    if value in {"high", "critical", "blocked", "error"}:
        return "bad"
    if value in {"medium", "normal", "warning", "pending"}:
        return "warn"
    if value in {"low", "ok", "clear", "healthy"}:
        return "ok"
    return "neutral"


def render_priority_level(level: Any, detail: Any = "", *, label: str = "Priority Level") -> None:
    render_stat_card(label, str(level or "normal").title(), str(detail or "Current page priority"), tone=_priority_tone(str(level)))


def render_kv_grid(items: list[tuple[str, Any]]) -> None:
    cells = []
    for label, value in items:
        cells.append(
            '<div class="jarvis-kv-item">'
            f'<div class="jarvis-kv-label">{html.escape(str(label))}</div>'
            f'<div class="jarvis-kv-value">{html.escape(str(value))}</div>'
            "</div>"
        )
    st.markdown(f'<div class="jarvis-kv">{"".join(cells)}</div>', unsafe_allow_html=True)


_TIMELINE_COLORS = {
    "profile_updated": "#ab6c2c",
    "preference_updated": "#205f5a",
    "memory_added": "#276749",
    "workflow_updated": "#7b4e9e",
    "action_completed": "#1e5fa0",
}


def render_timeline(items: list[dict[str, Any]]) -> None:
    if not items:
        st.info("No activity yet.")
        return
    blocks = []
    for item in items:
        meta  = item.get("meta", "")
        title = item.get("title", "")
        body  = item.get("body", "")
        color = _TIMELINE_COLORS.get(str(title), "var(--teal)")
        blocks.append(
            f'<div class="jarvis-timeline-item" style="border-color:{color}">'
            f'<div class="jarvis-timeline-meta">{html.escape(str(meta))}</div>'
            f'<div class="jarvis-timeline-title" style="color:{color}">{html.escape(str(title))}</div>'
            f'<div class="jarvis-timeline-body">{html.escape(str(body))}</div>'
            "</div>"
        )
    st.markdown("".join(blocks), unsafe_allow_html=True)


_MEMORY_TYPE_COLORS: dict[str, str] = {
    "note":     "var(--teal)",
    "decision": "#7048e8",
    "event":    "#1971c2",
    "reminder": "#e67700",
    "insight":  "#2b8a3e",
}


def render_memory_cards(memory: list[dict[str, Any]], *, numbered: bool = False) -> None:
    if not memory:
        st.caption("No memory entries.")
        return
    for idx, entry in enumerate(memory):
        text = entry.get("text") or entry.get("event") or str(entry)
        ts = entry.get("created_at", "")
        ts_short = ts[:19].replace("T", " ") if ts else ""
        entry_type = str(entry.get("type", "note"))
        badge_color = _MEMORY_TYPE_COLORS.get(entry_type, "var(--muted)")

        # type badge
        badge = (
            f"<span style='background:{badge_color};color:#fff;font-size:0.68rem;"
            f"font-weight:700;padding:0.1rem 0.45rem;border-radius:999px;"
            f"margin-right:0.4rem;vertical-align:middle;'>{html.escape(entry_type)}</span>"
        )

        # tag badge
        tag = entry.get("tag", "")
        tag_html = (
            f"<span style='background:var(--panel);border:1px solid var(--line);color:var(--muted);"
            f"font-size:0.65rem;padding:0.1rem 0.4rem;border-radius:999px;"
            f"margin-right:0.3rem;vertical-align:middle;'>{html.escape(str(tag))}</span>"
            if tag else ""
        )

        # visibility badge
        vis = entry.get("visibility", "private")
        vis_color = "#2b8a3e" if vis == "public" else "#6c757d"
        vis_label = "public" if vis == "public" else "private"
        vis_html = (
            f"<span style='background:{vis_color};color:#fff;font-size:0.62rem;"
            f"padding:0.1rem 0.4rem;border-radius:999px;margin-right:0.3rem;"
            f"vertical-align:middle;'>{vis_label}</span>"
        )

        # importance dots (1–5)
        importance = int(entry.get("importance", 3))
        dots = "●" * importance + "○" * (5 - importance)
        imp_html = (
            f"<span style='color:{badge_color};font-size:0.62rem;letter-spacing:1px;"
            f"vertical-align:middle;margin-right:0.4rem;' title='importance {importance}/5'>{dots}</span>"
        )

        # short ID
        entry_id = str(entry.get("id", ""))
        id_html = (
            f"<span style='color:var(--muted);font-size:0.6rem;font-family:monospace;"
            f"vertical-align:middle;' title='id: {html.escape(entry_id)}'>{html.escape(entry_id[:8])}</span>"
            if entry_id else ""
        )

        num_html = (
            f"<span style='color:var(--muted);font-size:0.72rem;margin-right:0.4rem;'>#{idx + 1}</span>"
            if numbered else ""
        )
        ts_html = (
            f'<div class="jarvis-memory-ts">{html.escape(ts_short)}</div>' if ts_short else ""
        )
        st.markdown(
            f'<div class="jarvis-memory-card">'
            f'<div style="margin-bottom:0.35rem;display:flex;flex-wrap:wrap;align-items:center;gap:0.1rem;">'
            f'{num_html}{badge}{tag_html}{vis_html}{imp_html}{id_html}'
            f'</div>'
            f'{html.escape(str(text))}{ts_html}'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_log_block(text: str) -> None:
    st.markdown(
        f'<pre class="jarvis-log-block">{html.escape(text)}</pre>',
        unsafe_allow_html=True,
    )


def render_json_block(value: Any) -> None:
    try:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    except TypeError:
        text = str(value)
    render_log_block(text)


# ── Route / health badges ──────────────────────────────────────────────────────

_ROUTE_COLORS = {"hi": "#0b7285", "local": "#2b8a3e", "n/a": "#6c757d"}


def route_badge(route: str) -> str:
    color = _ROUTE_COLORS.get(route, "#6c757d")
    return (
        f"<span style='background:{color};color:white;padding:0.2rem 0.5rem;"
        f"border-radius:999px;font-size:0.78rem;font-weight:700;'>{html.escape(route)}</span>"
    )


def health_badge(label: str, ok: bool) -> str:
    color = "#2b8a3e" if ok else "#c92a2a"
    value = "OK" if ok else "Down"
    return (
        f"<div style='border:1px solid var(--line);border-radius:12px;padding:0.6rem 0.8rem;margin-bottom:0.5rem;"
        f"background:var(--panel);'>"
        f"<div style='font-size:0.78rem;color:var(--muted);'>{html.escape(label)}</div>"
        f"<div style='font-weight:700;color:{color};'>{value}</div>"
        "</div>"
    )


def _humanize(text: Any) -> str:
    value = str(text or "").replace("_", " ").strip()
    return value[:1].upper() + value[1:] if value else ""


def render_live_strip(state: dict[str, Any]) -> None:
    device = state.get("device", {})
    health = state.get("health", {})
    system = state.get("system", {})
    fetched_at = str(state.get("fetched_at", ""))[:19].replace("T", " ")
    st.markdown(
        (
            '<div class="jarvis-live-strip">'
            f"<span><strong>Live</strong> {html.escape(fetched_at or 'n/a')}</span>"
            f"<span>Listener {html.escape('online' if state.get('listener', {}).get('online') else 'offline')}</span>"
            f"<span>Bus {html.escape('active' if health.get('bus_active') else 'idle')}</span>"
            f"<span>Focus {html.escape(str(health.get('current_focus', 'none')))}</span>"
            f"<span>Device {html.escape(str(device.get('trust_match', 'none')))}</span>"
            f"<span>Host {html.escape(str(system.get('hostname', 'unknown')))}</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_command_preview(preview: dict[str, Any]) -> None:
    if not preview:
        return
    st.markdown(
        (
            '<div class="jarvis-preview">'
            f"<div><strong>Preview</strong> {html.escape(str(preview.get('command', '')))}</div>"
            f"<div>Action: {html.escape(_humanize(preview.get('parsed_action', '')))}</div>"
            f"<div>Route: {html.escape(str(preview.get('route', 'n/a')))}</div>"
            f"<div>Risk: {html.escape(str(preview.get('risk_tier', 'unknown')))}</div>"
            f"<div>Payload: {html.escape(str(preview.get('parsed_payload', '')) or '(none)')}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


# ── Command result rendering ───────────────────────────────────────────────────

def _is_confirmation_required(result: dict[str, Any]) -> bool:
    data = result.get("data", {})
    return data.get("action") == "confirmation_required"


def render_result(result: dict[str, Any]) -> None:
    data = result["data"]
    route = result["route"]
    tone = "ok" if data.get("ok") else "bad"
    summary = "Command completed successfully." if data.get("ok") else "Command failed."
    value = "Success" if data.get("ok") else "Failed"
    if result.get("duration_ms") is not None:
        value = f"{value} · {result['duration_ms']} ms"
    render_stat_card("Execution", value, summary, tone=tone)

    st.markdown(f"Route: {route_badge(route)}", unsafe_allow_html=True)
    meta1, meta2, meta3 = st.columns(3)
    meta1.metric("Intent", data.get("intent", ""))
    meta2.metric("Action", _humanize(data.get("action", "")))
    meta3.metric("Time", result.get("timestamp", ""))
    if result.get("trace_id"):
        st.caption(f"Trace ID: {result['trace_id']}")

    st.markdown("**Payload**")
    _render_value(data.get("payload"))

    if data.get("ok"):
        st.markdown("**Result**")
        render_log_block(str(data.get("result", "")))
    else:
        st.markdown("**Error**")
        render_log_block(str(data.get("error", "")))

    with st.expander("Structured Result", expanded=False):
        render_json_block(data)


def render_result_with_confirmation(
    result: dict[str, Any],
    run_fn,
    *,
    key_prefix: str = "confirm",
) -> None:
    """Render result. If it's a confirmation_required response, show Confirm/Cancel buttons."""
    if _is_confirmation_required(result):
        data = result["data"]
        error_text = data.get("error", "Confirmation required.")
        st.markdown(
            f'<div class="jarvis-warn-banner">'
            f"<strong>Confirmation Required</strong><br/>{html.escape(str(error_text))}"
            "</div>",
            unsafe_allow_html=True,
        )
        c1, c2, _ = st.columns([1, 1, 3])
        if c1.button("Confirm", key=f"{key_prefix}_yes", type="primary", use_container_width=True):
            run_fn("confirm")
            st.rerun()
        if c2.button("Cancel", key=f"{key_prefix}_no", use_container_width=True):
            run_fn("cancel")
            st.rerun()
    else:
        render_result(result)


def _render_value(value: Any) -> None:
    if isinstance(value, (dict, list)):
        render_json_block(value)
        return
    if value in ("", None):
        st.caption("(none)")
        return
    render_log_block(str(value))


# ── Persistent command history ─────────────────────────────────────────────────

def _load_disk_history() -> list[dict[str, Any]]:
    try:
        if not _HISTORY_PATH.exists():
            return []
        items = []
        for line in _HISTORY_PATH.read_text(encoding="utf-8").splitlines()[-_HISTORY_KEEP:]:
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return list(reversed(items))
    except Exception:
        return []


def _save_to_disk_history(entry: dict[str, Any]) -> None:
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        lines = _HISTORY_PATH.read_text(encoding="utf-8").splitlines()
        if len(lines) > _HISTORY_KEEP:
            _HISTORY_PATH.write_text(
                "\n".join(lines[-_HISTORY_KEEP:]) + "\n", encoding="utf-8"
            )
    except Exception:
        pass


def ensure_history() -> None:
    if "command_history" not in st.session_state:
        st.session_state["command_history"] = _load_disk_history()


def push_history(entry: dict[str, Any]) -> None:
    ensure_history()
    item = {
        "timestamp": entry.get("timestamp", datetime.now().strftime("%H:%M:%S")),
        "command": entry.get("command", ""),
        "route": entry.get("route", "n/a"),
        "ok": entry.get("ok", False),
        "action": entry.get("parsed_action", ""),
        "trace_id": entry.get("trace_id", ""),
        "duration_ms": entry.get("duration_ms", ""),
    }
    st.session_state["command_history"].insert(0, item)
    st.session_state["command_history"] = st.session_state["command_history"][:_HISTORY_KEEP]
    _save_to_disk_history(item)


# ── History rendering ──────────────────────────────────────────────────────────

def render_question_card(item: dict[str, Any]) -> None:
    ts = str(item.get("ts", ""))[:19].replace("T", " ")
    mode = html.escape(str(item.get("mode", "unknown")))
    provider = html.escape(str(item.get("provider", "") or "n/a"))
    model = html.escape(str(item.get("model", "") or "n/a"))
    message = html.escape(str(item.get("message", "")))
    st.markdown(
        f'<div class="jarvis-memory-card">'
        f'<div style="display:flex;gap:0.45rem;align-items:center;flex-wrap:wrap;margin-bottom:0.35rem;">'
        f'<span class="jarvis-pill">{mode}</span>'
        f'<span class="jarvis-pill">{provider}</span>'
        f'<span class="jarvis-pill">{model}</span>'
        f'<span style="color:var(--muted2);font-size:0.71rem;margin-left:auto;">{html.escape(ts)}</span>'
        f'</div>'
        f'<div style="font-size:0.91rem;color:var(--text);line-height:1.45;">{message}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_history() -> None:
    ensure_history()
    st.subheader("Recent Command History")
    history = st.session_state["command_history"]
    if not history:
        st.info("No commands run yet.")
        return
    for item in history:
        status = "OK" if item["ok"] else "Error"
        st.markdown(
            f"**{item['timestamp']}**  `{html.escape(item['command'])}`  "
            f"{route_badge(item['route'])}  `{status}`  `{item['action']}`",
            unsafe_allow_html=True,
        )
        if item.get("trace_id") or item.get("duration_ms"):
            st.caption(f"Trace {item.get('trace_id', 'n/a')} · {item.get('duration_ms', 'n/a')} ms")


def render_history_with_actions(key_prefix: str, run_command_fn) -> None:
    ensure_history()
    section_label("Recent Command History")
    history = st.session_state["command_history"]
    if not history:
        st.info("No commands run yet.")
        return

    for index, item in enumerate(history):
        status_color = "var(--green)" if item["ok"] else "var(--red)"
        status_label = "OK" if item["ok"] else "Err"
        info_col, replay_col, fill_col = st.columns([6, 1, 1])
        info_col.markdown(
            f"<span style='color:var(--muted);font-size:0.82rem;'>{item['timestamp']}</span>  "
            f"`{html.escape(item['command'])}`  "
            f"{route_badge(item['route'])}  "
            f"<span style='color:{status_color};font-weight:700;font-size:0.82rem;'>{status_label}</span>  "
            f"<span style='color:var(--muted);font-size:0.80rem;'>`{_humanize(item['action'])}`</span>",
            unsafe_allow_html=True,
        )
        if item.get("trace_id") or item.get("duration_ms"):
            info_col.caption(f"Trace {item.get('trace_id', 'n/a')} · {item.get('duration_ms', 'n/a')} ms")
        if replay_col.button("Run", key=f"{key_prefix}_replay_{index}", use_container_width=True):
            run_command_fn(item["command"])
            st.rerun()
        if fill_col.button("Fill", key=f"{key_prefix}_use_{index}", use_container_width=True):
            st.session_state["command_input_pending"] = item["command"]
            st.rerun()


# ── Auto-refresh ───────────────────────────────────────────────────────────────

def maybe_auto_refresh(enabled: bool, interval_seconds: int) -> None:
    """Non-blocking auto-refresh via streamlit-autorefresh JS timer.

    Uses a JavaScript setTimeout so the Streamlit server thread is never
    blocked. Call at the BOTTOM of the page after all content is rendered.
    """
    if not enabled or not st.session_state.get("live_updates_enabled", True):
        return
    ms = max(5_000, interval_seconds * 1_000)
    try:
        from streamlit_autorefresh import st_autorefresh  # noqa: PLC0415
        st_autorefresh(interval=ms, key="jarvis_auto_refresh")
    except ImportError:
        # Graceful fallback: inject a JS timer that reloads the parent frame.
        # Avoids blocking the server thread entirely — no time.sleep().
        components.html(
            f"<script>setTimeout(function(){{window.parent.location.reload();}},{ms});</script>",
            height=0,
        )


def refresh_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
