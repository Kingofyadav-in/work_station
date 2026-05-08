from __future__ import annotations

import html as _html

import streamlit as st

from services.ui_helpers import (
    inject_theme,
    render_hero,
    render_kv_grid,
    render_stat_card,
    render_theme_toggle,
    render_timeline,
    section_label,
)

st.set_page_config(page_title="Personal", page_icon="J", layout="wide")

render_theme_toggle()
inject_theme()

render_hero(
    "Amit Kumar Yadav",
    "Digital systems builder from Bhagalpur — building trusted public identity systems across ventures, community work, and digital infrastructure.",
    eyebrow="Personal Profile",
)

# ── Top identity stat row ──────────────────────────────────────────────────────
c0, c1, c2, c3 = st.columns(4)
with c0:
    render_stat_card("Full Name", "Amit Kumar Yadav", "Primary identity", tone="ok")
with c1:
    render_stat_card("Location", "Bhagalpur, Bihar", "India · Base of operations")
with c2:
    render_stat_card("Active Ventures", "3+", "Royal Heritage Resort · Jhon Aamit LLP · NGO", tone="ok")
with c3:
    render_stat_card("Projects Led", "10+", "5+ years of work · 1 national NGO")

# ── Main content ───────────────────────────────────────────────────────────────
left, right = st.columns([1.2, 0.8], gap="large")

with left:
    section_label("Contact & Identity")
    render_kv_grid([
        ("Full Name",    "Amit Kumar Yadav"),
        ("Handle",       "kingofyadav"),
        ("Born",         "25 December 1999"),
        ("Origin",       "Bhagalpur, Bihar, India"),
        ("Phone",        "+91 95235 28114"),
        ("Website",      "kingofyadav.in"),
        ("Brand",        "kingofyadav.in"),
        ("Company",      "Jhon Aamit LLP"),
        ("Language",     "English · Hindi"),
        ("Domain",       "Digital Systems & Social Impact"),
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
    _services = [
        ("Web & Internet Building", "Full website and web application development"),
        ("Website Maintenance",     "Ongoing maintenance, security, performance monitoring"),
        ("Web Hosting",             "Reliable, fast, affordable hosting"),
        ("Machine Intelligence",    "AI, ML, and automation solutions"),
        ("Human Learning",          "Education and learning systems"),
        ("Individual Development",  "Guidance, learning paths, and growth systems"),
        ("Software Solutions",      "Custom software and application development"),
    ]
    render_kv_grid([(s[0], s[1]) for s in _services])

    section_label("Personal Journey")
    render_timeline([
        {
            "meta":  "2026 — Ongoing",
            "title": "action_completed",
            "body":  "Expanding Jarvis platform, public digital systems, and AI-assisted workflows.",
        },
        {
            "meta":  "2024 — Present",
            "title": "action_completed",
            "body":  "Launched kingofyadav.in — structured digital identity covering personal, professional, and social dimensions.",
        },
        {
            "meta":  "2023 — Present",
            "title": "workflow_updated",
            "body":  "Public & social initiatives: youth, community, environment, and public coordination.",
        },
        {
            "meta":  "2021 — 2023",
            "title": "profile_updated",
            "body":  "Work across business and digital systems. Founded Royal Heritage Resort (hospitality venture).",
        },
        {
            "meta":  "2019 — 2021",
            "title": "memory_added",
            "body":  "Ground-level learning: people, local issues, coordination, and consistent community presence.",
        },
        {
            "meta":  "2015 — 2019",
            "title": "memory_added",
            "body":  "Academic foundation in Bhagalpur. Began understanding real community challenges.",
        },
        {
            "meta":  "25 December 1999",
            "title": "memory_added",
            "body":  "Born in Bhagalpur, Bihar. Early years shaped by family discipline and cultural values.",
        },
    ])

with right:
    section_label("Social Presence")
    st.markdown(
        """
<div style="display:grid;gap:0.75rem;">

<a href="https://www.facebook.com/kingofyadav.in" target="_blank" style="
  display:flex;align-items:center;gap:0.85rem;
  background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:0.9rem 1.1rem;text-decoration:none;
  transition:border-color 0.15s,transform 0.15s;color:var(--text);">
  <span style="font-size:1.3rem;">f</span>
  <div>
    <div style="font-weight:700;font-size:0.92rem;">Facebook</div>
    <div style="color:var(--muted);font-size:0.78rem;">@kingofyadav.in · Public updates &amp; community</div>
  </div>
</a>

<a href="https://www.instagram.com/kingofyadav.in" target="_blank" style="
  display:flex;align-items:center;gap:0.85rem;
  background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:0.9rem 1.1rem;text-decoration:none;
  transition:border-color 0.15s,transform 0.15s;color:var(--text);">
  <span style="font-size:1.3rem;">&#9432;</span>
  <div>
    <div style="font-weight:700;font-size:0.92rem;">Instagram</div>
    <div style="color:var(--muted);font-size:0.78rem;">@kingofyadav.in · Visual updates &amp; field activity</div>
  </div>
</a>

<a href="https://www.youtube.com/@kingofyadav-youtube" target="_blank" style="
  display:flex;align-items:center;gap:0.85rem;
  background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:0.9rem 1.1rem;text-decoration:none;
  transition:border-color 0.15s,transform 0.15s;color:var(--text);">
  <span style="font-size:1.3rem;">&#9654;</span>
  <div>
    <div style="font-weight:700;font-size:0.92rem;">YouTube</div>
    <div style="color:var(--muted);font-size:0.78rem;">@kingofyadav-youtube · Videos &amp; public messages</div>
  </div>
</a>

<a href="https://github.com/kingofyadav" target="_blank" style="
  display:flex;align-items:center;gap:0.85rem;
  background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:0.9rem 1.1rem;text-decoration:none;
  transition:border-color 0.15s,transform 0.15s;color:var(--text);">
  <span style="font-size:1.3rem;">&lt;/&gt;</span>
  <div>
    <div style="font-weight:700;font-size:0.92rem;">GitHub</div>
    <div style="color:var(--muted);font-size:0.78rem;">@kingofyadav · Code &amp; open projects</div>
  </div>
</a>

<a href="https://kingofyadav.in" target="_blank" style="
  display:flex;align-items:center;gap:0.85rem;
  background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:0.9rem 1.1rem;text-decoration:none;
  transition:border-color 0.15s,transform 0.15s;color:var(--text);">
  <span style="font-size:1.3rem;">&#127760;</span>
  <div>
    <div style="font-weight:700;font-size:0.92rem;">kingofyadav.in</div>
    <div style="color:var(--muted);font-size:0.78rem;">Official website · Identity &amp; portfolio</div>
  </div>
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
