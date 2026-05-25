from __future__ import annotations

import html
import sys
from pathlib import Path

import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "app"))

from services.automation_client import (
    get_automation_audit,
    get_automation_failures,
    get_automation_log_tail,
    get_automation_pending,
    get_automation_rules,
    get_automation_status,
)
from services.dashboard_db import (
    get_recent_actions,
    get_recent_snapshots,
    log_action,
    save_automation_snapshot,
)
from services.jarvis_client import run_command
from services.model_selector import render_model_selector
from services.state_reader import get_dashboard_state
from services.ui_helpers import (
    ensure_history,
    inject_theme,
    maybe_auto_refresh,
    push_history,
    render_hero,
    render_kv_grid,
    render_log_block,
    render_priority_level,
    render_stat_card,
    render_theme_toggle,
    render_live_strip,
    section_label,
)

st.set_page_config(page_title="Automation", page_icon="J", layout="wide")

render_theme_toggle()
render_model_selector()
state = get_dashboard_state()
ensure_history()
inject_theme()

# ── Load live automation state ─────────────────────────────────────────────────
aut  = get_automation_status()
rules_data    = get_automation_rules()
pending_items = get_automation_pending()
audit_items   = get_automation_audit(n=20)
failure_items = get_automation_failures(n=10)

# Snapshot to DB every page load (for history/trend)
save_automation_snapshot(
    daemon_alive  = aut["daemon_alive"],
    stop_active   = aut["stop_active"],
    dry_run       = aut["dry_run"],
    rule_count    = aut["rule_count"],
    enabled_count = aut["enabled_count"],
    pending_count = aut["pending_count"],
    audit_count   = len(audit_items),
)

# ── Hero ───────────────────────────────────────────────────────────────────────
render_hero(
    "Automation Control",
    "Live automation daemon status, rules management, pending approvals, and audit trail.",
    eyebrow="Phase 4 — Autonomous Automation",
)
render_live_strip(state)

# ── Priority assessment ────────────────────────────────────────────────────────
_aut_alerts: list[tuple[str, str]] = []
if not aut["daemon_alive"]:
    _aut_alerts.append(("Automation daemon is not running.", "error"))
if aut["stop_active"]:
    _aut_alerts.append(("STOP file active — all rule executions are paused.", "warning"))
if aut["dry_run"]:
    _aut_alerts.append(("Dry-run mode is ON — actions are logged but not executed.", "warning"))
if aut["pending_count"] > 0:
    _aut_alerts.append((f"{aut['pending_count']} rule(s) awaiting manual approval.", "warning"))
if failure_items:
    _aut_alerts.append((f"{len(failure_items)} recent failure(s) in automation log.", "warning"))

for _msg, _tone in _aut_alerts:
    if _tone == "error":
        st.error(_msg, icon="🔴")
    else:
        st.warning(_msg, icon="⚠️")

aut_priority = "high" if any(t == "error" for _, t in _aut_alerts) else \
               ("medium" if _aut_alerts else "low")
aut_priority_detail = _aut_alerts[0][0] if _aut_alerts else "All automation systems clear."

# ── Stat row ──────────────────────────────────────────────────────────────────
c0, c1, c2, c3, c4 = st.columns(5)
with c0:
    render_priority_level(aut_priority, aut_priority_detail)
with c1:
    daemon_label = "Running" if aut["daemon_alive"] else "Stopped"
    daemon_detail = f"pid {aut['pid']}" if aut["pid"] else "not started"
    render_stat_card("Daemon", daemon_label, daemon_detail,
                     tone="ok" if aut["daemon_alive"] else "bad",
                     pulse=aut["daemon_alive"] and not aut["stop_active"])
with c2:
    stop_label = "Paused" if aut["stop_active"] else ("Active" if aut["daemon_alive"] else "Idle")
    render_stat_card("Status", stop_label,
                     "STOP file present" if aut["stop_active"] else "running normally",
                     tone="warn" if aut["stop_active"] else ("ok" if aut["daemon_alive"] else "bad"))
with c3:
    render_stat_card("Rules",
                     f"{aut['enabled_count']} / {aut['rule_count']}",
                     "enabled / total",
                     tone="ok" if aut["enabled_count"] > 0 else "warn")
with c4:
    render_stat_card("Pending",
                     str(aut["pending_count"]),
                     "awaiting approval",
                     tone="warn" if aut["pending_count"] > 0 else "ok")

# ── Main layout ────────────────────────────────────────────────────────────────
left, right = st.columns([1.6, 1])


# ──────────────────────── LEFT COLUMN ─────────────────────────────────────────

with left:

    # ── Daemon control ─────────────────────────────────────────────────────────
    section_label("Daemon Control")

    def _run_aut(cmd: str, label: str) -> None:
        r = run_command(cmd)
        log_action(label, command=cmd, result=r.get("formatted", ""), ok=r.get("ok", False))
        push_history(r)
        st.session_state["aut_last_result"] = r
        st.rerun()

    b1, b2, b3, b4, b5 = st.columns(5)
    if b1.button("Start",          key="aut_start",   use_container_width=True): _run_aut("automation start",   "start")
    if b2.button("Stop",           key="aut_stop",    use_container_width=True): _run_aut("automation stop",    "stop")
    if b3.button("Enable",         key="aut_enable",  use_container_width=True): _run_aut("automation enable",  "enable")
    if b4.button("Disable",        key="aut_disable", use_container_width=True): _run_aut("automation disable", "disable")
    if b5.button("Validate Rules", key="aut_validate",use_container_width=True): _run_aut("automation validate","validate")

    # Emergency stop — separated with visual weight
    st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)
    if st.button("Emergency Stop", key="aut_estop", type="secondary", use_container_width=False):
        _run_aut("automation emergency stop", "emergency_stop")

    if "aut_last_result" in st.session_state:
        _r = st.session_state["aut_last_result"]
        _txt = _r.get("formatted", "")
        if _txt:
            st.caption(_txt[:300])

    # ── Rules table ────────────────────────────────────────────────────────────
    section_label("Rules")

    if not rules_data:
        st.caption("No rules loaded. Start the daemon once to create defaults.")
    else:
        for rule in rules_data:
            rid       = rule.get("id", "")
            enabled   = rule.get("enabled", True)
            tier      = rule.get("risk_tier", "low")
            trigger   = rule.get("trigger", {})
            t_str     = f"{trigger.get('type','?')} / {trigger.get('seconds', trigger.get('hour','?'))}"
            desc      = rule.get("description", "")
            retries   = rule.get("max_retries", 0)
            cooldown  = rule.get("cooldown_seconds", 0)

            tier_color = {"low": "var(--green)", "medium": "var(--gold)", "high": "var(--red)"}.get(tier, "var(--muted)")
            en_badge   = (
                f"<span style='color:var(--green);font-size:0.75rem'>enabled</span>"
                if enabled else
                f"<span style='color:var(--red);font-size:0.75rem'>disabled</span>"
            )

            with st.container():
                rc1, rc2, rc3 = st.columns([3, 1, 1])
                with rc1:
                    st.markdown(
                        f"**{html.escape(rid)}** {en_badge} "
                        f"<span style='color:{tier_color};font-size:0.72rem'>[{tier}]</span> "
                        f"<span style='color:var(--muted);font-size:0.72rem'>{html.escape(t_str)}</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"{html.escape(desc)} · retries:{retries} · cooldown:{cooldown}s")
                with rc2:
                    if not enabled:
                        if st.button("Enable", key=f"en_{rid}", use_container_width=True):
                            _run_aut(f"automation rule enable {rid}", f"rule_enable_{rid}")
                    else:
                        if st.button("Disable", key=f"dis_{rid}", use_container_width=True):
                            _run_aut(f"automation rule disable {rid}", f"rule_disable_{rid}")
                with rc3:
                    if st.button("Run Now", key=f"run_{rid}", use_container_width=True,
                                 help="Trigger this rule once immediately"):
                        _run_aut(f"automation rule run {rid}", f"rule_run_{rid}")

    # ── Pending approvals ──────────────────────────────────────────────────────
    if pending_items:
        section_label(f"Pending Approvals ({len(pending_items)})")
        for p in pending_items:
            p_id  = p.get("rule_id", "")
            p_act = p.get("action", {}).get("type", "?")
            p_ts  = str(p.get("ts", ""))[:19].replace("T", " ")
            p_desc = html.escape(p.get("description", ""))

            with st.container():
                pc1, pc2, pc3 = st.columns([3, 1, 1])
                with pc1:
                    st.markdown(
                        f"**{html.escape(p_id)}** "
                        f"<span style='color:var(--red);font-size:0.72rem'>[high-risk · {p_act}]</span>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"{p_desc} · queued {p_ts}")
                with pc2:
                    if st.button("Approve", key=f"approve_{p_id}", use_container_width=True):
                        _run_aut(f"automation approve {p_id}", f"approve_{p_id}")
                with pc3:
                    if st.button("Deny", key=f"deny_{p_id}", use_container_width=True):
                        _run_aut(f"automation deny {p_id}", f"deny_{p_id}")

    # ── Audit trail ────────────────────────────────────────────────────────────
    section_label("Recent Audit Events")
    if not audit_items:
        st.caption("No audit events yet.")
    else:
        status_color = {
            "success": "var(--green)", "dry_run": "var(--gold)",
            "pending_approval": "var(--gold)", "approved": "var(--green)",
            "denied": "var(--red)", "disabled_after_retries": "var(--red)",
            "failed": "var(--red)",
        }
        for entry in audit_items[:15]:
            ts      = str(entry.get("ts", ""))[:19].replace("T", " ")
            eid     = html.escape(entry.get("rule_id", "—"))
            atype   = html.escape(entry.get("action_type", "—"))
            estatus = entry.get("status", "")
            ecolor  = status_color.get(estatus, "var(--muted)")
            detail  = html.escape(str(entry.get("detail", "")))[:80]
            st.markdown(
                f"<span style='color:var(--muted);font-size:0.72rem'>{ts}</span> "
                f"**{eid}** · {atype} · "
                f"<span style='color:{ecolor};font-size:0.78rem'>{estatus}</span>"
                + (f" <span style='color:var(--muted2);font-size:0.70rem'>— {detail}</span>" if detail else ""),
                unsafe_allow_html=True,
            )


# ──────────────────────── RIGHT COLUMN ────────────────────────────────────────

with right:

    # ── Live system info ────────────────────────────────────────────────────────
    section_label("Automation State")
    render_kv_grid([
        ("Daemon",        "running" if aut["daemon_alive"] else "stopped"),
        ("PID",           str(aut["pid"]) if aut["pid"] else "—"),
        ("STOP file",     "yes — paused" if aut["stop_active"] else "no"),
        ("Dry-run",       "yes" if aut["dry_run"] else "no"),
        ("Rules total",   aut["rule_count"]),
        ("Rules enabled", aut["enabled_count"]),
        ("Pending",       aut["pending_count"]),
        ("Last audit",    str(aut["last_audit_ts"])[:19].replace("T", " ") or "—"),
    ])

    # ── Recent failures ────────────────────────────────────────────────────────
    if failure_items:
        section_label(f"Recent Failures ({len(failure_items)})")
        for f in failure_items[:5]:
            f_ts    = str(f.get("ts", ""))[:19].replace("T", " ")
            f_id    = html.escape(f.get("rule_id", "—"))
            f_err   = html.escape(str(f.get("error", ""))[:80])
            f_retry = f.get("retry", 0)
            st.markdown(
                f"<span style='color:var(--muted);font-size:0.72rem'>{f_ts}</span> "
                f"**{f_id}** retry={f_retry}",
                unsafe_allow_html=True,
            )
            if f_err:
                st.caption(f_err)

    # ── Log tail ───────────────────────────────────────────────────────────────
    section_label("Daemon Log (last 20 lines)")
    log_lines = get_automation_log_tail(n=20)
    render_log_block("\n".join(log_lines) if log_lines else "No automation log yet.")

    # ── Dashboard action history ───────────────────────────────────────────────
    section_label("Dashboard Action History")
    db_actions = get_recent_actions(limit=15)
    if not db_actions:
        st.caption("No dashboard actions recorded yet.")
    else:
        for a in db_actions:
            a_ts  = str(a.get("ts", ""))[:19].replace("T", " ")
            a_cmd = html.escape(str(a.get("command", a.get("action_type", "—")))[:50])
            a_ok  = bool(a.get("ok", 1))
            ok_color = "var(--green)" if a_ok else "var(--red)"
            st.markdown(
                f"<span style='color:var(--muted);font-size:0.72rem'>{a_ts}</span> "
                f"<span style='color:{ok_color};font-size:0.75rem'>{'ok' if a_ok else 'fail'}</span> "
                f"{a_cmd}",
                unsafe_allow_html=True,
            )

_aut_refresh = st.sidebar.slider("Refresh every (s)", 5, 60, 10, key="aut_refresh_interval")
maybe_auto_refresh(True, _aut_refresh)
