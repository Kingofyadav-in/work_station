from __future__ import annotations

import html as _html
from datetime import datetime

import streamlit as st

from services.local_admin_registry import clear_local_admin_registry, get_local_admin_registry_state
from services.state_reader import get_dashboard_state
from services.ui_helpers import (
    inject_theme,
    maybe_auto_refresh,
    render_hero,
    render_kv_grid,
    render_log_block,
    render_priority_level,
    render_stat_card,
    render_theme_toggle,
    render_timeline,
    section_label,
)


st.set_page_config(page_title="Admin", page_icon="J", layout="wide")

render_theme_toggle()
inject_theme()

admin_state = get_local_admin_registry_state(limit=500)
_profile  = get_dashboard_state().get("profile", {})
_channels = _profile.get("public_channels", {})
_ventures = _profile.get("ventures", [])
items  = admin_state.get("items", [])
events = admin_state.get("events", [])

render_hero(
    "Admin & Personal",
    "Synced web sessions and auth registry alongside personal identity, ventures, and contact details.",
    eyebrow="Admin Layer",
)

tab_admins, tab_personal = st.tabs(["Admins", "Personal"])


# ── ADMINS ────────────────────────────────────────────────────────────────────
with tab_admins:
    latest = admin_state.get("latest", {})
    ac0, ac1, ac2, ac3 = st.columns(4)
    with ac0:
        render_priority_level("medium" if items else "low",
                              f"{admin_state.get('count', 0)} synced session(s).")
    with ac1:
        render_stat_card("Sessions", admin_state.get("count", 0), "Unique username/device records",
                         tone="ok" if items else "warn")
    with ac2:
        render_stat_card("Active", admin_state.get("active_count", 0), "Current active records",
                         tone="ok" if admin_state.get("active_count") else "warn")
    with ac3:
        render_stat_card("Latest", latest.get("action", "none"), latest.get("username", "none"))

    al, ar = st.columns([1.2, 0.8], gap="large")
    with al:
        section_label("Current Users")
        confirm_reset = st.checkbox("Confirm registry reset", key="local_admin_reset_confirm")
        if st.button("Reset Registry", type="secondary", disabled=not confirm_reset):
            clear_local_admin_registry()
            st.success("Synced local admin registry cleared.")
            st.rerun()
        if items:
            for item in items[:100]:
                render_kv_grid([
                    ("Username",      item.get("username") or "none"),
                    ("Action",        item.get("action") or "none"),
                    ("Session",       item.get("session_key") or "none"),
                    ("Last Seen",     item.get("ts", "")[:19].replace("T", " ")),
                    ("Created",       item.get("created_at_label") or item.get("ts", "")[:19].replace("T", " ")),
                    ("Hash Version",  item.get("hash_version") or "legacy"),
                    ("Hash Preview",  item.get("password_hash_preview") or "none"),
                    ("Hash Length",   item.get("password_hash_length", 0)),
                    ("Salt",          "yes" if item.get("has_salt") else "no"),
                    ("Device",        item.get("device_id") or "none"),
                ])
                st.caption(" ")
        else:
            st.caption("No synced local admin users yet.")
    with ar:
        section_label("Latest Snapshot")
        if latest:
            render_kv_grid([
                ("Username", latest.get("username", "none")),
                ("Action",   latest.get("action", "none")),
                ("Source",   latest.get("source", "none")),
                ("Session",  latest.get("session_key", "none")),
                ("Time",     latest.get("ts", "")[:19].replace("T", " ")),
            ])
            render_log_block(latest.get("password_hash_preview", ""))
        else:
            st.caption("No registry snapshot available.")

        section_label("Event Log")
        if events:
            ev_limit = st.slider("Show latest", 5, 50, 10, key="local_admin_events_limit")
            for item in events[:ev_limit]:
                render_log_block(
                    f"{item.get('ts', '')[:19].replace('T', ' ')} · "
                    f"{item.get('action', 'unknown')} · "
                    f"{item.get('username', 'none')} · "
                    f"{item.get('password_hash_preview', '')}"
                )
        else:
            st.caption("No auth events recorded yet.")
        st.caption(f"Updated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# ── PERSONAL ──────────────────────────────────────────────────────────────────
with tab_personal:
    pc0, pc1, pc2, pc3 = st.columns(4)
    with pc0:
        render_stat_card("Full Name", _profile.get("full_name", "Amit Kumar Yadav"), "Primary identity", tone="ok")
    with pc1:
        render_stat_card("Location", _profile.get("location", "Bhagalpur, Bihar"), "India · Base of operations")
    with pc2:
        _v_count = str(len(_ventures)) + "+" if _ventures else "3+"
        _v_detail = " · ".join(_ventures[:3]) if _ventures else "Royal Heritage Resort · Jhon Aamit LLP · NGO"
        render_stat_card("Active Ventures", _v_count, _v_detail, tone="ok")
    with pc3:
        render_stat_card("Projects Led", "10+", "5+ years of work · 1 national NGO")

    pl, pr = st.columns([1.2, 0.8], gap="large")
    with pl:
        section_label("Contact & Identity")
        render_kv_grid([
            ("Full Name",    _profile.get("full_name",  "Amit Kumar Yadav")),
            ("Handle",       _profile.get("username",   "kingofyadav")),
            ("Born",         "25 December 1999"),
            ("Origin",       _profile.get("location",   "Bhagalpur, Bihar, India")),
            ("Phone",        _profile.get("phone",      "+91 95235 28114")),
            ("Website",      _profile.get("website",    "kingofyadav.in")),
            ("Brand",        _profile.get("brand",      "kingofyadav.in")),
            ("Company",      _profile.get("company",    "Jhon Aamit LLP")),
            ("Language",     "English · Hindi"),
            ("Domain",       _profile.get("domain",     "Digital Systems & Social Impact")),
        ])

        section_label("Professional Work")
        render_kv_grid([
            ("Title",      "Digital Systems Builder"),
            ("Role",       "Founder · Builder · Social Coordinator"),
            ("Years",      "5+ years"),
            ("Ventures",   "3 active businesses"),
            ("NGO",        "1 national-level NGO"),
            ("Projects",   "10+ projects led"),
            ("Core Work",  "Identity Systems · Business Systems · Social Impact"),
            ("Style",      "Long-term execution · Visible responsibility"),
        ])

        section_label("Services Offered")
        render_kv_grid([
            ("Web & Internet Building", "Full website and web application development"),
            ("Website Maintenance",     "Ongoing maintenance, security, performance monitoring"),
            ("Web Hosting",             "Reliable, fast, affordable hosting"),
            ("Machine Intelligence",    "AI, ML, and automation solutions"),
            ("Human Learning",          "Education and learning systems"),
            ("Individual Development",  "Guidance, learning paths, and growth systems"),
            ("Software Solutions",      "Custom software and application development"),
        ])

        section_label("Personal Journey")
        render_timeline([
            {"meta": "2026 — Ongoing",  "title": "action_completed",
             "body": "Expanding Jarvis platform, public digital systems, and AI-assisted workflows."},
            {"meta": "2024 — Present",  "title": "action_completed",
             "body": "Launched kingofyadav.in — structured digital identity covering personal, professional, and social dimensions."},
            {"meta": "2023 — Present",  "title": "workflow_updated",
             "body": "Public & social initiatives: youth, community, environment, and public coordination."},
            {"meta": "2021 — 2023",     "title": "profile_updated",
             "body": "Work across business and digital systems. Founded Royal Heritage Resort (hospitality venture)."},
            {"meta": "2019 — 2021",     "title": "memory_added",
             "body": "Ground-level learning: people, local issues, coordination, and consistent community presence."},
            {"meta": "2015 — 2019",     "title": "memory_added",
             "body": "Academic foundation in Bhagalpur. Began understanding real community challenges."},
            {"meta": "25 December 1999","title": "memory_added",
             "body": "Born in Bhagalpur, Bihar. Early years shaped by family discipline and cultural values."},
        ])

    with pr:
        section_label("Social Presence")
        _fb = _channels.get("facebook", "https://www.facebook.com/kingofyadav.in")
        _ig = _channels.get("instagram", "https://www.instagram.com/kingofyadav.in")
        _gh = _channels.get("github",   "https://github.com/kingofyadav")
        _ws = _channels.get("website",  "https://kingofyadav.in")
        st.markdown(
            f"""
<div style="display:grid;gap:0.75rem;">
<a href="{_fb}" target="_blank" style="display:flex;align-items:center;gap:0.85rem;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:0.9rem 1.1rem;text-decoration:none;color:var(--text);">
  <span style="font-size:1.3rem;">f</span>
  <div><div style="font-weight:700;font-size:0.92rem;">Facebook</div>
  <div style="color:var(--muted);font-size:0.78rem;">@kingofyadav.in · Public updates &amp; community</div></div>
</a>
<a href="{_ig}" target="_blank" style="display:flex;align-items:center;gap:0.85rem;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:0.9rem 1.1rem;text-decoration:none;color:var(--text);">
  <span style="font-size:1.3rem;">&#9432;</span>
  <div><div style="font-weight:700;font-size:0.92rem;">Instagram</div>
  <div style="color:var(--muted);font-size:0.78rem;">@kingofyadav.in · Visual updates &amp; field activity</div></div>
</a>
<a href="https://www.youtube.com/@kingofyadav-youtube" target="_blank" style="display:flex;align-items:center;gap:0.85rem;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:0.9rem 1.1rem;text-decoration:none;color:var(--text);">
  <span style="font-size:1.3rem;">&#9654;</span>
  <div><div style="font-weight:700;font-size:0.92rem;">YouTube</div>
  <div style="color:var(--muted);font-size:0.78rem;">@kingofyadav-youtube · Videos &amp; public messages</div></div>
</a>
<a href="{_gh}" target="_blank" style="display:flex;align-items:center;gap:0.85rem;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:0.9rem 1.1rem;text-decoration:none;color:var(--text);">
  <span style="font-size:1.3rem;">&lt;/&gt;</span>
  <div><div style="font-weight:700;font-size:0.92rem;">GitHub</div>
  <div style="color:var(--muted);font-size:0.78rem;">@kingofyadav · Code &amp; open projects</div></div>
</a>
<a href="{_ws}" target="_blank" style="display:flex;align-items:center;gap:0.85rem;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:0.9rem 1.1rem;text-decoration:none;color:var(--text);">
  <span style="font-size:1.3rem;">&#127760;</span>
  <div><div style="font-weight:700;font-size:0.92rem;">kingofyadav.in</div>
  <div style="color:var(--muted);font-size:0.78rem;">Official website · Identity &amp; portfolio</div></div>
</a>
</div>
""",
            unsafe_allow_html=True,
        )

        section_label("Active Ventures")
        render_kv_grid([
            ("Royal Heritage Resort", "Hospitality · Bhagalpur · Founded 2021"),
            ("Jhon Aamit LLP",        "Company · Digital systems & services"),
            ("National NGO",          "Social impact · Youth · Community"),
        ])

        section_label("Work Areas")
        render_kv_grid([
            ("Digital Identity",  "Websites, profiles, public presence"),
            ("Business Systems",  "Venture communication, service positioning"),
            ("Social Impact",     "Community, youth, public coordination"),
            ("AI & Automation",   "Jarvis platform, machine intelligence"),
            ("Web Hosting",       "Developer & business hosting"),
            ("Education",         "Learning systems & individual development"),
        ])

        section_label("Philosophy")
        st.markdown(
            """
<div class="jarvis-group">
  <div class="jarvis-group-label">Personal Standard</div>
  <div style="font-size:1.05rem;font-weight:700;color:var(--text);line-height:1.55;font-style:italic;">
    "Discipline creates stability. Stability creates progress. Progress creates trust."
  </div>
  <div style="color:var(--muted);font-size:0.85rem;margin-top:0.75rem;line-height:1.55;">
    I try to keep the work simple, visible, and useful enough that it can stand
    without loud explanation. Trust is built through work — not titles.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        section_label("Contact Details")
        st.markdown(
            """
<div class="jarvis-group">
  <div class="jarvis-group-label">Direct Contact</div>
  <div style="display:grid;gap:0.6rem;margin-top:0.5rem;">
    <div style="display:flex;align-items:center;gap:0.6rem;">
      <span style="color:var(--muted);font-size:0.78rem;width:60px;">Phone</span>
      <span style="font-weight:700;">+91 95235 28114</span>
    </div>
    <div style="display:flex;align-items:center;gap:0.6rem;">
      <span style="color:var(--muted);font-size:0.78rem;width:60px;">Web</span>
      <span style="font-weight:700;">kingofyadav.in</span>
    </div>
    <div style="display:flex;align-items:center;gap:0.6rem;">
      <span style="color:var(--muted);font-size:0.78rem;width:60px;">Location</span>
      <span style="font-weight:700;">Bhagalpur, Bihar, India</span>
    </div>
    <div style="display:flex;align-items:center;gap:0.6rem;">
      <span style="color:var(--muted);font-size:0.78rem;width:60px;">Languages</span>
      <span style="font-weight:700;">English · Hindi</span>
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )


maybe_auto_refresh(True, 8)
