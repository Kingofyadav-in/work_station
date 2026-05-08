from __future__ import annotations

import html as _html
from datetime import datetime

import streamlit as st

from services.site_health import check_all
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
    "Live status of kingofyadav.in pages and all Jarvis API endpoints — response codes and latency at a glance.",
    eyebrow="Infrastructure",
)

# ── Run health checks ──────────────────────────────────────────────────────────
with st.spinner("Running health checks…"):
    data = check_all()

summary = data["summary"]
website = data["website"]
apis = data["apis"]

# ── Top stat row ───────────────────────────────────────────────────────────────
web_pct = f"{summary['website_ok']}/{summary['website_total']}"
api_pct = f"{summary['api_ok']}/{summary['api_total']}"
all_ok = summary["all_ok"]

c0, c1, c2, c3 = st.columns(4)
with c0:
    render_stat_card(
        "Overall",
        "All Clear" if all_ok else "Issues Detected",
        f"Website: {web_pct} · API: {api_pct}",
        tone="ok" if all_ok else "bad",
        pulse=all_ok,
    )
with c1:
    render_stat_card(
        "Website",
        web_pct,
        f"kingofyadav.in · avg {summary['avg_web_ms']} ms",
        tone="ok" if summary["website_ok"] == summary["website_total"] else "bad",
    )
with c2:
    render_stat_card(
        "API Endpoints",
        api_pct,
        f"localhost:5050 · avg {summary['avg_api_ms']} ms",
        tone="ok" if summary["api_ok"] == summary["api_total"] else "bad",
    )
with c3:
    render_stat_card(
        "Avg Latency",
        f"{summary['avg_web_ms']} ms",
        f"Website · API: {summary['avg_api_ms']} ms",
        tone="ok" if summary["avg_web_ms"] < 800 else "warn",
    )

# ── Helper to render a status table row ───────────────────────────────────────

def _status_color(ok: bool) -> str:
    return "var(--green)" if ok else "var(--red)"


def _status_icon(ok: bool, status: int) -> str:
    if ok:
        return "✓"
    return f"✗ {status}" if status else "✗ timeout"


def _ms_color(ms: int) -> str:
    if ms < 300:
        return "var(--green)"
    if ms < 800:
        return "var(--gold-light)"
    return "var(--red)"


def _render_endpoint_table(items: list[dict]) -> None:
    rows = []
    for item in items:
        ok = item["ok"]
        status = item.get("status", 0)
        ms = item.get("ms", 0)
        label = _html.escape(item["label"])
        path = _html.escape(item["path"])
        icon = _status_icon(ok, status)
        icon_color = _status_color(ok)
        ms_color = _ms_color(ms)
        error = _html.escape(item.get("error", "")[:80])
        rows.append(
            f'<div style="display:grid;grid-template-columns:1.5rem 1fr 5rem 5rem;'
            f'align-items:center;gap:0.75rem;padding:0.6rem 0.8rem;'
            f'border-bottom:1px solid var(--divider);">'
            f'<span style="color:{icon_color};font-weight:800;font-size:0.9rem;">{icon}</span>'
            f'<div><div style="font-weight:600;font-size:0.88rem;color:var(--text);">{label}</div>'
            f'<div style="color:var(--muted);font-size:0.72rem;font-family:monospace;">{path}'
            f'{(" — " + error) if error else ""}</div></div>'
            f'<span style="color:{icon_color};font-weight:700;font-size:0.82rem;text-align:right;">'
            f'{"OK" if ok else str(status) if status else "Timeout"}</span>'
            f'<span style="color:{ms_color};font-weight:700;font-size:0.82rem;text-align:right;">'
            f'{ms} ms</span>'
            f'</div>'
        )
    header = (
        '<div style="display:grid;grid-template-columns:1.5rem 1fr 5rem 5rem;'
        'gap:0.75rem;padding:0.5rem 0.8rem;border-bottom:2px solid var(--line-strong);">'
        '<span></span>'
        '<span style="color:var(--muted);font-size:0.67rem;text-transform:uppercase;'
        'letter-spacing:0.12em;font-weight:700;">Endpoint</span>'
        '<span style="color:var(--muted);font-size:0.67rem;text-transform:uppercase;'
        'letter-spacing:0.12em;font-weight:700;text-align:right;">Status</span>'
        '<span style="color:var(--muted);font-size:0.67rem;text-transform:uppercase;'
        'letter-spacing:0.12em;font-weight:700;text-align:right;">Latency</span>'
        '</div>'
    )
    st.markdown(
        f'<div style="background:var(--panel);border:1px solid var(--line);'
        f'border-radius:20px;overflow:hidden;">'
        f'{header}{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


# ── Content ────────────────────────────────────────────────────────────────────
left, right = st.columns([1.1, 0.9], gap="large")

with left:
    section_label(f"Website — kingofyadav.in  ({summary['website_ok']}/{summary['website_total']} up)")
    _render_endpoint_table(website)

    section_label("Quick Links")
    render_kv_grid([
        ("Website",      "https://kingofyadav.in"),
        ("Blog",         "https://kingofyadav.in/blog"),
        ("Services",     "https://kingofyadav.in/pages/services.html"),
        ("Contact",      "https://kingofyadav.in/pages/contact.html"),
        ("Collaboration","https://kingofyadav.in/pages/collaboration.html"),
        ("API Root",     "http://localhost:5050/api/"),
    ])

with right:
    section_label(f"Jarvis API — localhost:5050  ({summary['api_ok']}/{summary['api_total']} up)")
    _render_endpoint_table(apis)

    section_label("Failure Details")
    failed = [e for e in website + apis if not e["ok"]]
    if failed:
        for item in failed:
            st.markdown(
                f'<div class="jarvis-warn-banner">'
                f'<strong>{_html.escape(item["label"])}</strong><br/>'
                f'<code>{_html.escape(item["path"])}</code>'
                f'<span style="color:var(--muted);font-size:0.82rem;"> · {item["ms"]} ms</span><br/>'
                f'<span style="color:var(--muted);font-size:0.82rem;">'
                f'{_html.escape(item.get("error","unknown error"))}'
                f'</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            '<div class="jarvis-confirm-banner">'
            '<strong>All endpoints healthy</strong><br/>'
            '<span style="color:var(--muted);font-size:0.85rem;">'
            'No failures detected in this check cycle.</span>'
            '</div>',
            unsafe_allow_html=True,
        )

    section_label("Performance Summary")
    all_items = website + apis
    fastest = min(all_items, key=lambda x: x["ms"])
    slowest = max(all_items, key=lambda x: x["ms"])
    render_kv_grid([
        ("Fastest",          f"{fastest['label']} — {fastest['ms']} ms"),
        ("Slowest",          f"{slowest['label']} — {slowest['ms']} ms"),
        ("Web avg",          f"{summary['avg_web_ms']} ms"),
        ("API avg",          f"{summary['avg_api_ms']} ms"),
        ("Total checks",     str(summary['website_total'] + summary['api_total'])),
        ("Total passing",    str(summary['website_ok'] + summary['api_ok'])),
    ])

st.caption(
    f"Last checked: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
    f"Auto-refresh: every {refresh_interval}s · "
    f"Timeout: 8s per endpoint"
)

maybe_auto_refresh(True, refresh_interval)
