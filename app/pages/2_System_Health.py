from __future__ import annotations

import html as _html
import json
from datetime import datetime

import streamlit as st

from services.jarvis_client import run_command
from services.log_reader import (
    get_last_bus_log_time,
    get_last_event,
    read_bus_log_filtered,
    read_event_objects,
)
from services.model_selector import render_model_selector
from services.site_health import JARVIS_URL, WEBSITE_URL, check_all
from services.state_reader import get_dashboard_state
from services.ui_helpers import (
    ensure_history,
    inject_theme,
    maybe_auto_refresh,
    push_history,
    refresh_timestamp,
    render_hero,
    render_kv_grid,
    render_log_block,
    render_live_strip,
    render_priority_level,
    render_result_with_confirmation,
    render_stat_card,
    render_theme_toggle,
    render_timeline,
    section_label,
)


st.set_page_config(page_title="System & Health", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()

refresh_interval  = st.sidebar.slider("Refresh every (s)",     5, 60,  10, key="syshealth_refresh")
bus_line_count    = st.sidebar.slider("Bus log lines",          10, 100, 30, key="sys_bus_line_count")

state = get_dashboard_state()
ensure_history()
inject_theme()

render_hero(
    "System & Health",
    "Platform internals and live infrastructure — listener, bus, events, disk, battery, and all public endpoints at a glance.",
    eyebrow="Platform Health",
)
render_live_strip(state)

tab_system, tab_health = st.tabs(["System", "Site Health"])


# ── SYSTEM ────────────────────────────────────────────────────────────────────
with tab_system:
    listener_ok = state["health"]["kingofyadav_listener_healthy"]
    bus_active  = state["health"]["bus_active"]
    last_event  = get_last_event()
    last_ts     = (last_event or {}).get("ts", "none")
    last_ts_fmt = last_ts[:19].replace("T", " ") if last_ts != "none" else "none"
    sys_priority        = "high" if not listener_ok else ("medium" if not bus_active else "low")
    sys_priority_detail = ("Listener offline." if not listener_ok
                           else ("Bus idle." if not bus_active else "Core services healthy."))

    sc0, sc1, sc2, sc3 = st.columns(4)
    with sc0:
        render_priority_level(sys_priority, sys_priority_detail)
    with sc1:
        render_stat_card("Listener", "Healthy" if listener_ok else "Offline",
                         "Kingofyadav service", tone="ok" if listener_ok else "bad", pulse=listener_ok)
    with sc2:
        render_stat_card("Bus Activity", "Active" if bus_active else "Idle",
                         "Recent bus traffic", tone="ok" if bus_active else "warn")
    with sc3:
        render_stat_card("Last Event", (last_event or {}).get("type", "none"), last_ts_fmt, tone="warn")

    def _run_sys(cmd: str) -> None:
        if not cmd.strip():
            return
        r = run_command(cmd.strip())
        st.session_state["system_result"] = r
        push_history(r)

    section_label("Commands")
    sb1, sb2, sb3, sb4 = st.columns(4)
    if sb1.button("Status",      key="sys_status",  use_container_width=True): _run_sys("status")
    if sb2.button("Context",     key="sys_context", use_container_width=True): _run_sys("context")
    if sb3.button("System Info", key="sys_info",    use_container_width=True): _run_sys("system info")
    if sb4.button("Doctor",      key="sys_doctor",  use_container_width=True): _run_sys("doctor")

    sb5, sb6, sb7, _ = st.columns(4)
    if sb5.button("Disk",    key="sys_disk",    use_container_width=True): _run_sys("disk")
    if sb6.button("Battery", key="sys_battery", use_container_width=True): _run_sys("battery")
    if sb7.button("Website", key="sys_website", use_container_width=True): _run_sys("website status")

    with st.form("system_cmd", clear_on_submit=False):
        sc_col, sbt_col = st.columns([5, 1])
        sc = sc_col.text_input("Command", label_visibility="collapsed",
                               placeholder="status · context · system info · disk · battery")
        if sbt_col.form_submit_button("Run", type="primary", use_container_width=True):
            _run_sys(sc)

    sys_result = st.session_state.get("system_result")
    if sys_result:
        render_result_with_confirmation(sys_result, _run_sys, key_prefix="system")

    st.caption(f"Refreshed: {refresh_timestamp()} · Bus: {get_last_bus_log_time()} · Event: {last_ts_fmt}")

    section_label("Live Trace")
    bus_col, event_col = st.columns([1.25, 0.95], gap="large")

    with bus_col:
        filter_options = ["All", "REQUEST", "RESPONSE", "PROCESSED", "ERROR", "DEADLETTER", "TIMEOUT"]
        filter_value = st.selectbox("Filter", filter_options, index=0, label_visibility="collapsed")
        bus_lines = read_bus_log_filtered(
            lines=bus_line_count,
            keyword="" if filter_value == "All" else filter_value,
        )
        render_log_block("\n".join(bus_lines) if bus_lines else "No bus log lines matching filter.")

    with event_col:
        events = read_event_objects(lines=12)
        if events:
            render_timeline([
                {
                    "meta":  e.get("ts", "?")[:19].replace("T", " "),
                    "title": e.get("type", "event"),
                    "body":  json.dumps(e.get("payload", {}), ensure_ascii=False),
                }
                for e in events
            ])
        else:
            st.caption("No events yet.")

    st.caption(
        f"Snapshot: {state.get('fetched_at', 'n/a')[:19].replace('T', ' ')} · "
        f"Last event: {state['health'].get('last_event_type', 'none')} · "
        f"Bus lines tracked: {len(state.get('recent_bus', []))}"
    )


# ── SITE HEALTH ───────────────────────────────────────────────────────────────
with tab_health:
    with st.spinner("Running health checks…"):
        data = check_all()

    summary = data["summary"]
    website = data["website"]
    jarvis  = data["jarvis"]
    apis    = data["apis"]
    all_ok  = summary["all_ok"]

    hc0, hc1, hc2, hc3 = st.columns(4)
    with hc0:
        render_stat_card(
            "Overall",
            "All Clear" if all_ok else "Issues Detected",
            (f"Web {summary['website_ok']}/{summary['website_total']} · "
             f"Jarvis {summary['jarvis_ok']}/{summary['jarvis_total']} · "
             f"API {summary['api_ok']}/{summary['api_total']}"),
            tone="ok" if all_ok else "bad",
            pulse=all_ok,
        )
    with hc1:
        render_stat_card("kingofyadav.in",
                         f"{summary['website_ok']}/{summary['website_total']}",
                         f"avg {summary['avg_web_ms']} ms",
                         tone="ok" if summary["website_ok"] == summary["website_total"] else "bad")
    with hc2:
        render_stat_card("jarvis.kingofyadav.in",
                         f"{summary['jarvis_ok']}/{summary['jarvis_total']}",
                         f"avg {summary['avg_jarvis_ms']} ms",
                         tone="ok" if summary["jarvis_ok"] == summary["jarvis_total"] else "bad")
    with hc3:
        render_stat_card("Local API :5050",
                         f"{summary['api_ok']}/{summary['api_total']}",
                         f"avg {summary['avg_api_ms']} ms",
                         tone="ok" if summary["api_ok"] == summary["api_total"] else "bad")

    def _ms_color(ms: int) -> str:
        if ms < 400:   return "var(--green)"
        if ms < 1000:  return "var(--gold-light)"
        return "var(--red)"

    def _render_table(items: list[dict]) -> None:
        rows = []
        for item in items:
            ok     = item["ok"]
            status = item.get("status", 0)
            ms     = item.get("ms", 0)
            label  = _html.escape(item["label"])
            path   = _html.escape(item["path"])
            error  = _html.escape(item.get("error", "")[:80])
            icon_color = "var(--green)" if ok else "var(--red)"
            status_txt = "OK" if ok else (str(status) if status else "Timeout")
            if ok and status in (401, 403):
                status_txt = f"{status} auth"
            rows.append(
                f'<div style="display:grid;grid-template-columns:1.4rem 1fr 5.5rem 5rem;'
                f'align-items:center;gap:0.6rem;padding:0.55rem 0.9rem;'
                f'border-bottom:1px solid var(--divider);">'
                f'<span style="color:{icon_color};font-weight:800;font-size:0.9rem;">{"✓" if ok else "✗"}</span>'
                f'<div><div style="font-weight:600;font-size:0.87rem;color:var(--text);">{label}</div>'
                f'<div style="color:var(--muted);font-size:0.71rem;font-family:monospace;">{path}'
                f'{(" — " + error) if error and not ok else ""}</div></div>'
                f'<span style="color:{icon_color};font-weight:700;font-size:0.81rem;text-align:right;">'
                f'{status_txt}</span>'
                f'<span style="color:{_ms_color(ms)};font-weight:700;font-size:0.81rem;text-align:right;">'
                f'{ms} ms</span>'
                f'</div>'
            )
        header = (
            '<div style="display:grid;grid-template-columns:1.4rem 1fr 5.5rem 5rem;'
            'gap:0.6rem;padding:0.45rem 0.9rem;border-bottom:2px solid var(--line-strong);">'
            '<span></span>'
            '<span style="color:var(--muted);font-size:0.66rem;text-transform:uppercase;letter-spacing:0.13em;font-weight:700;">Endpoint</span>'
            '<span style="color:var(--muted);font-size:0.66rem;text-transform:uppercase;letter-spacing:0.13em;font-weight:700;text-align:right;">Status</span>'
            '<span style="color:var(--muted);font-size:0.66rem;text-transform:uppercase;letter-spacing:0.13em;font-weight:700;text-align:right;">Latency</span>'
            '</div>'
        )
        st.markdown(
            f'<div style="background:var(--panel);border:1px solid var(--line);'
            f'border-radius:20px;overflow:hidden;">'
            f'{header}{"".join(rows)}</div>',
            unsafe_allow_html=True,
        )

    col_web, col_jarvis = st.columns(2, gap="large")
    with col_web:
        section_label(f"kingofyadav.in — {summary['website_ok']}/{summary['website_total']} up · avg {summary['avg_web_ms']} ms")
        _render_table(website)
    with col_jarvis:
        section_label(f"jarvis.kingofyadav.in — {summary['jarvis_ok']}/{summary['jarvis_total']} up · avg {summary['avg_jarvis_ms']} ms")
        _render_table(jarvis)

    section_label(f"Local API localhost:5050 — {summary['api_ok']}/{summary['api_total']} up · avg {summary['avg_api_ms']} ms")
    api_col, detail_col = st.columns([1.1, 0.9], gap="large")
    with api_col:
        _render_table(apis)
    with detail_col:
        section_label("Failures")
        failed = [e for e in website + jarvis + apis if not e["ok"]]
        if failed:
            for item in failed:
                st.markdown(
                    f'<div class="jarvis-warn-banner">'
                    f'<strong>{_html.escape(item["label"])}</strong> · '
                    f'<code>{_html.escape(item["path"])}</code>'
                    f'<span style="color:var(--muted);font-size:0.82rem;"> · {item["ms"]} ms</span><br/>'
                    f'<span style="color:var(--muted);font-size:0.82rem;">'
                    f'{_html.escape(item.get("error", "unknown"))}'
                    f'</span></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                '<div class="jarvis-confirm-banner">'
                '<strong>All endpoints healthy</strong><br/>'
                '<span style="color:var(--muted);font-size:0.85rem;">No failures in this check cycle.</span>'
                '</div>',
                unsafe_allow_html=True,
            )

        section_label("Performance")
        all_items = website + jarvis + apis
        fastest = min(all_items, key=lambda x: x["ms"])
        slowest = max(all_items, key=lambda x: x["ms"])
        render_kv_grid([
            ("Fastest",      f"{fastest['label']} — {fastest['ms']} ms"),
            ("Slowest",      f"{slowest['label']} — {slowest['ms']} ms"),
            ("Web avg",      f"{summary['avg_web_ms']} ms"),
            ("Jarvis avg",   f"{summary['avg_jarvis_ms']} ms"),
            ("API avg",      f"{summary['avg_api_ms']} ms"),
            ("Total checks", str(len(all_items))),
            ("Passing",      str(summary['website_ok'] + summary['jarvis_ok'] + summary['api_ok'])),
        ])

        section_label("Quick Links")
        render_kv_grid([
            ("Website",          WEBSITE_URL),
            ("Jarvis Dashboard", JARVIS_URL),
            ("Jarvis API",       JARVIS_URL + "/api/health"),
            ("Public Chat",      JARVIS_URL + "/api/public-state"),
            ("Intake Stats",     JARVIS_URL + "/api/intake-stats"),
        ])

    st.caption(
        f"Last checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
        f"Auto-refresh: {refresh_interval}s · Timeout: 8s per endpoint"
    )


maybe_auto_refresh(True, refresh_interval)
