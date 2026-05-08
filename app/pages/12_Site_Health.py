from __future__ import annotations

import html as _html
from datetime import datetime

import streamlit as st

from services.site_health import JARVIS_URL, WEBSITE_URL, check_all
from services.ui_helpers import (
    inject_theme,
    maybe_auto_refresh,
    render_hero,
    render_kv_grid,
    render_stat_card,
    render_theme_toggle,
    section_label,
)

st.set_page_config(page_title="Site Health", page_icon="J", layout="wide")

render_theme_toggle()
refresh_interval = st.sidebar.slider("Auto-refresh (s)", 10, 120, 30, key="health_refresh_interval")
inject_theme()

render_hero(
    "Site Health Monitor",
    "Live status of kingofyadav.in · jarvis.kingofyadav.in · and all local API endpoints — response codes and latency at a glance.",
    eyebrow="Infrastructure",
)

# ── Run health checks ──────────────────────────────────────────────────────────
with st.spinner("Running health checks…"):
    data = check_all()

summary = data["summary"]
website = data["website"]
jarvis  = data["jarvis"]
apis    = data["apis"]

# ── Top stat row ───────────────────────────────────────────────────────────────
all_ok = summary["all_ok"]

c0, c1, c2, c3 = st.columns(4)
with c0:
    render_stat_card(
        "Overall",
        "All Clear" if all_ok else "Issues Detected",
        f"Web {summary['website_ok']}/{summary['website_total']} · "
        f"Jarvis {summary['jarvis_ok']}/{summary['jarvis_total']} · "
        f"API {summary['api_ok']}/{summary['api_total']}",
        tone="ok" if all_ok else "bad",
        pulse=all_ok,
    )
with c1:
    render_stat_card(
        "kingofyadav.in",
        f"{summary['website_ok']}/{summary['website_total']}",
        f"avg {summary['avg_web_ms']} ms",
        tone="ok" if summary["website_ok"] == summary["website_total"] else "bad",
    )
with c2:
    render_stat_card(
        "jarvis.kingofyadav.in",
        f"{summary['jarvis_ok']}/{summary['jarvis_total']}",
        f"avg {summary['avg_jarvis_ms']} ms",
        tone="ok" if summary["jarvis_ok"] == summary["jarvis_total"] else "bad",
    )
with c3:
    render_stat_card(
        "Local API :5050",
        f"{summary['api_ok']}/{summary['api_total']}",
        f"avg {summary['avg_api_ms']} ms",
        tone="ok" if summary["api_ok"] == summary["api_total"] else "bad",
    )


# ── Shared table renderer ──────────────────────────────────────────────────────

def _ms_color(ms: int) -> str:
    if ms < 400:
        return "var(--green)"
    if ms < 1000:
        return "var(--gold-light)"
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


# ── Three columns of checks ────────────────────────────────────────────────────
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
            '<span style="color:var(--muted);font-size:0.85rem;">'
            'No failures in this check cycle.</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    section_label("Performance")
    all_items = website + jarvis + apis
    fastest = min(all_items, key=lambda x: x["ms"])
    slowest = max(all_items, key=lambda x: x["ms"])
    render_kv_grid([
        ("Fastest",         f"{fastest['label']} — {fastest['ms']} ms"),
        ("Slowest",         f"{slowest['label']} — {slowest['ms']} ms"),
        ("Web avg",         f"{summary['avg_web_ms']} ms"),
        ("Jarvis avg",      f"{summary['avg_jarvis_ms']} ms"),
        ("API avg",         f"{summary['avg_api_ms']} ms"),
        ("Total checks",    str(len(all_items))),
        ("Passing",         str(summary['website_ok'] + summary['jarvis_ok'] + summary['api_ok'])),
    ])

    section_label("Quick Links")
    render_kv_grid([
        ("Website",         WEBSITE_URL),
        ("Jarvis Dashboard", JARVIS_URL),
        ("Jarvis API",      JARVIS_URL + "/api/health"),
        ("Public Chat",     JARVIS_URL + "/api/public-state"),
        ("Intake Stats",    JARVIS_URL + "/api/intake-stats"),
    ])

st.caption(
    f"Last checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
    f"Auto-refresh: {refresh_interval}s · Timeout: 8s per endpoint"
)

maybe_auto_refresh(True, refresh_interval)
