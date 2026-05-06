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

# ── CSS themes ─────────────────────────────────────────────────────────────────

_CSS_VARS_LIGHT = """
:root {
    --bg:           #ffffff;
    --bg-grad:      #ffffff;
    --panel:        #ffffff;
    --panel-strong: #ffffff;
    --panel-hover:  #f6f8f7;
    --line:         rgba(0,0,0,0.10);
    --line-strong:  rgba(0,0,0,0.16);
    --text:         #111111;
    --text-inv:     #ffffff;
    --muted:        #333333;
    --muted2:       #555555;
    --gold:         #046A38;
    --gold-light:   #FF671F;
    --teal:         #046A38;
    --teal-light:   #FF671F;
    --red:          #c92a2a;
    --green:        #046A38;
    --green-light:  #0b8a4c;
    --hero-bg:      rgba(255,255,255,0.88);
    --btn-bg:       #ffffff;
    --btn-bg-hover: #f4f7f5;
    --btn-text:     #111111;
    --input-bg:     #ffffff;
    --sidebar-link: #111111;
    --card-shadow:  0 10px 30px rgba(0,0,0,0.08);
    --hero-shadow:  0 10px 30px rgba(0,0,0,0.08);
    --accent1:      rgba(4,106,56,0.10);
    --accent2:      rgba(255,103,31,0.10);
    --pulse-color:  #046A38;
    --confirm-bg:   rgba(4,106,56,0.08);
    --confirm-border: rgba(4,106,56,0.28);
    --warn-bg:      rgba(255,103,31,0.08);
    --warn-border:  rgba(255,103,31,0.30);
    --danger-bg:    rgba(201,42,42,0.08);
    --danger-border: rgba(201,42,42,0.28);
    --divider:      rgba(0,0,0,0.08);
    --header-bg:    rgba(255,255,255,0.88);
    --header-text:  #111111;
    --sidebar-bg:   #ffffff;
    --sidebar-nav:  #f6f8f7;
    --sidebar-border: rgba(0,0,0,0.10);
}"""

_CSS_VARS_DARK = """
:root {
    --bg:           #000000;
    --bg-grad:      #000000;
    --panel:        #1c1c1e;
    --panel-strong: #202024;
    --panel-hover:  #252529;
    --line:         rgba(255,255,255,0.10);
    --line-strong:  rgba(255,255,255,0.12);
    --text:         #e5e5e5;
    --text-inv:     #000000;
    --muted:        #999999;
    --muted2:       #777777;
    --gold:         #046A38;
    --gold-light:   #FF671F;
    --teal:         #046A38;
    --teal-light:   #FF671F;
    --red:          #ff6b6b;
    --green:        #2ecc71;
    --green-light:  #4ad88a;
    --hero-bg:      rgba(28,28,30,0.72);
    --btn-bg:       #1c1c1e;
    --btn-bg-hover: #252529;
    --btn-text:     #e5e5e5;
    --input-bg:     #141416;
    --sidebar-link: #e5e5e5;
    --card-shadow:  0 10px 30px rgba(0,0,0,0.45);
    --hero-shadow:  0 10px 30px rgba(0,0,0,0.45);
    --accent1:      rgba(4,106,56,0.20);
    --accent2:      rgba(255,103,31,0.18);
    --pulse-color:  #2ecc71;
    --confirm-bg:   rgba(4,106,56,0.16);
    --confirm-border: rgba(4,106,56,0.38);
    --warn-bg:      rgba(255,103,31,0.14);
    --warn-border:  rgba(255,103,31,0.36);
    --danger-bg:    rgba(255,107,107,0.12);
    --danger-border: rgba(255,107,107,0.34);
    --divider:      rgba(255,255,255,0.08);
    --header-bg:    rgba(0,0,0,0.65);
    --header-text:  #e5e5e5;
    --sidebar-bg:   #000000;
    --sidebar-nav:  #0d0d0f;
    --sidebar-border: rgba(255,255,255,0.08);
}"""

_CSS_COMMON = """
/* ═══════════════════════════════════════════════════
   BASE & APP CONTAINER
═══════════════════════════════════════════════════ */

html, body, [class*="css"] {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

.stApp {
    background: var(--bg-grad) !important;
    color: var(--text) !important;
    min-height: 100vh;
}

.stApp,
.stApp p,
.stApp li,
.stApp label,
.stApp small,
.stApp summary,
.stApp figcaption,
.stApp [class*="css"] {
    color: var(--text);
}

.stApp svg {
    color: currentColor;
}

/* Main view container */
div[data-testid="stAppViewContainer"],
div[data-testid="stAppViewBlockContainer"] {
    background: transparent !important;
}
div[data-testid="stMain"],
div[data-testid="stMainBlockContainer"] {
    background: transparent !important;
}

/* Critical fix: header is fixed ~3.75rem tall — push content below it */
.block-container {
    padding-top: 5.25rem !important;
    padding-bottom: 3.25rem !important;
    max-width: 1360px;
}

/* Block wrappers — prevent white leaking through */
div[data-testid="stVerticalBlock"],
div[data-testid="stHorizontalBlock"],
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: transparent !important;
}

div[data-testid="stVerticalBlock"] {
    gap: 1.15rem !important;
}

div[data-testid="stHorizontalBlock"] {
    gap: 1.25rem !important;
}

/* ═══════════════════════════════════════════════════
   HIDE STREAMLIT CHROME
═══════════════════════════════════════════════════ */

[data-testid="stDecoration"],
#stDecoration,
div[data-testid="stDecoration"] {
    display: none !important;
}

footer,
footer[data-testid="footer"],
div[data-testid="stBottom"] {
    display: none !important;
}

/* ═══════════════════════════════════════════════════
   SCROLLBAR
═══════════════════════════════════════════════════ */

::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--line-strong); border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: var(--muted2); }

/* ═══════════════════════════════════════════════════
   HEADER (TOP BAR) — z-index 999999 ensures it always
   sits above hero banners and sticky content
═══════════════════════════════════════════════════ */

header[data-testid="stHeader"] {
    background: var(--header-bg) !important;
    border-bottom: 1px solid var(--line-strong) !important;
    backdrop-filter: blur(20px) saturate(1.6) !important;
    -webkit-backdrop-filter: blur(20px) saturate(1.6) !important;
    z-index: 999999 !important;
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    height: 3.75rem !important;
}

/* Header all text / icon elements */
header[data-testid="stHeader"] button,
header[data-testid="stHeader"] a,
header[data-testid="stHeader"] span,
header[data-testid="stHeader"] svg {
    color: var(--header-text) !important;
    fill: var(--header-text) !important;
}

/* Hamburger / sidebar toggle — all known Streamlit testids */
button[data-testid="collapsedControl"],
button[data-testid="baseButton-headerNoPadding"],
button[data-testid="stBaseButton-headerNoPadding"],
[data-testid="stSidebarNavToggleButton"],
[data-testid="stSidebarToggleButton"],
[data-testid="stSidebarCollapseButton"] {
    color: var(--header-text) !important;
    background: transparent !important;
    border: none !important;
    opacity: 1 !important;
}
button[data-testid="collapsedControl"] svg,
button[data-testid="baseButton-headerNoPadding"] svg,
button[data-testid="stBaseButton-headerNoPadding"] svg,
[data-testid="stSidebarNavToggleButton"] svg,
[data-testid="stSidebarToggleButton"] svg,
[data-testid="stSidebarCollapseButton"] svg {
    fill: var(--header-text) !important;
    color: var(--header-text) !important;
    stroke: var(--header-text) !important;
    opacity: 1 !important;
}

/* Toolbar / status widget */
div[data-testid="stToolbar"],
div[data-testid="stStatusWidget"] {
    color: var(--muted) !important;
}

/* ═══════════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════════ */

section[data-testid="stSidebar"] {
    background-color: var(--sidebar-bg) !important;
    border-right: 1px solid var(--sidebar-border) !important;
    min-width: 220px;
    z-index: 99998 !important;
}
div[data-testid="stSidebarContent"],
div[data-testid="stSidebarUserContent"],
div[data-testid="stSidebarCollapsedControl"],
div[data-testid="stSidebarHeader"] {
    background-color: var(--sidebar-bg) !important;
}

/* Catch-all: every text node Streamlit renders inside the sidebar */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] li,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4 {
    color: var(--text) !important;
}
section[data-testid="stSidebar"] .stMarkdown,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: var(--text) !important;
}
/* Sidebar SVG icons (slider thumb, toggle track, etc.) */
section[data-testid="stSidebar"] svg {
    fill: var(--text) !important;
}
/* Sidebar input fields */
section[data-testid="stSidebar"] input {
    background-color: var(--input-bg) !important;
    color: var(--text) !important;
    border-color: var(--line-strong) !important;
}
/* Sidebar slider track */
section[data-testid="stSidebar"] [data-testid="stSlider"] [data-baseweb="slider"] div {
    background: var(--gold) !important;
}

/* ── Sidebar navigation (page links) ── */

nav[data-testid="stSidebarNav"],
div[data-testid="stSidebarNav"] {
    padding: 0.5rem 0 !important;
    background-color: var(--sidebar-nav) !important;
    border-bottom: 1px solid var(--sidebar-border) !important;
}

/* Each page link item */
nav[data-testid="stSidebarNav"] ul,
div[data-testid="stSidebarNav"] ul {
    list-style: none !important;
    margin: 0 !important;
    padding: 0.25rem 0.5rem !important;
}

nav[data-testid="stSidebarNav"] ul li a,
div[data-testid="stSidebarNav"] ul li a,
a[data-testid="stSidebarNavLink"] {
    display: flex !important;
    align-items: center !important;
    padding: 0.45rem 0.8rem !important;
    margin: 0.1rem 0 !important;
    border-radius: 10px !important;
    color: var(--sidebar-link) !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    text-decoration: none !important;
    transition: background 0.15s, color 0.15s !important;
    background: transparent !important;
}

nav[data-testid="stSidebarNav"] ul li a:hover,
div[data-testid="stSidebarNav"] ul li a:hover,
a[data-testid="stSidebarNavLink"]:hover {
    background: var(--panel) !important;
    color: var(--gold) !important;
}

/* Active page link */
nav[data-testid="stSidebarNav"] ul li a[aria-current="page"],
div[data-testid="stSidebarNav"] ul li a[aria-current="page"],
a[data-testid="stSidebarNavLink"][aria-current="page"] {
    background: var(--accent1) !important;
    color: var(--gold) !important;
    font-weight: 700 !important;
}

/* Sidebar nav link icon/span text */
nav[data-testid="stSidebarNav"] ul li a span,
div[data-testid="stSidebarNav"] ul li a span,
a[data-testid="stSidebarNavLink"] span {
    color: inherit !important;
}

/* Sidebar content area (below nav) */
div[data-testid="stSidebarContent"],
div[data-testid="stSidebarUserContent"] {
    padding: 1rem 0.75rem !important;
}

/* Sidebar widgets */
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"],
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
    color: var(--text) !important;
    font-size: 0.87rem !important;
}
section[data-testid="stSidebar"] [data-testid="stToggle"] span,
section[data-testid="stSidebar"] [data-testid="stCheckbox"] span {
    color: var(--text) !important;
}
section[data-testid="stSidebar"] .stSlider [data-testid="stWidgetLabel"] {
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════════════
   TYPOGRAPHY & GLOBAL TEXT
═══════════════════════════════════════════════════ */

h1, h2, h3, h4 {
    color: var(--text) !important;
    font-weight: 800;
    letter-spacing: 0;
}

p, li, span, div {
    color: inherit;
}

main,
main p,
main li,
main span,
main label,
main small,
main div[data-testid="stMarkdownContainer"],
main div[data-testid="stMarkdownContainer"] * {
    color: var(--text);
}

/* Streamlit markdown */
[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] em,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4,
[data-testid="stMarkdownContainer"] code {
    color: var(--text) !important;
}
[data-testid="stMarkdownContainer"] :not(pre) > code {
    background: var(--panel-strong) !important;
    color: var(--text) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 6px !important;
    padding: 0.12rem 0.34rem !important;
    font-weight: 700 !important;
}

/* Caption */
.stCaptionContainer,
.stCaptionContainer p,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    color: var(--muted) !important;
    font-size: 0.82rem !important;
}

/* ═══════════════════════════════════════════════════
   FORM ELEMENTS
═══════════════════════════════════════════════════ */

/* Widget label (applies to all: input, slider, toggle, checkbox, select) */
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p,
label[data-baseweb="label"],
.stSlider label,
.stCheckbox label,
.stToggle label,
.stSelectbox label,
.stTextInput label,
.stTextArea label,
.stNumberInput label,
.stRadio label {
    color: var(--text) !important;
    font-size: 0.88rem !important;
    font-weight: 600 !important;
}

/* Text input */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stNumberInput"] input {
    background-color: var(--input-bg) !important;
    color: var(--text) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 12px !important;
    transition: border-color 0.15s !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: var(--gold) !important;
    box-shadow: 0 0 0 3px var(--accent1) !important;
}
div[data-testid="stTextInput"] input::placeholder,
div[data-testid="stTextArea"] textarea::placeholder {
    color: var(--muted2) !important;
}

/* Selectbox */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: var(--input-bg) !important;
    color: var(--text) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 12px !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div {
    color: var(--text) !important;
}
div[data-testid="stSelectbox"] [data-baseweb="select"] span,
div[data-testid="stSelectbox"] [data-baseweb="select"] svg,
div[data-testid="stMultiSelect"] [data-baseweb="select"] span,
div[data-testid="stMultiSelect"] [data-baseweb="select"] svg {
    color: var(--text) !important;
    fill: var(--text) !important;
}
/* Selectbox dropdown list */
ul[role="listbox"],
li[role="option"] {
    background-color: var(--panel-strong) !important;
    color: var(--text) !important;
}
li[role="option"] *,
[data-baseweb="menu"] *,
[data-baseweb="popover"] * {
    color: var(--text) !important;
}
li[role="option"]:hover {
    background-color: var(--panel-hover) !important;
}

/* Slider */
div[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stSlider"] div,
div[data-testid="stSlider"] [role="slider"] {
    background-color: var(--gold) !important;
}
div[data-testid="stSlider"] [data-baseweb="slider"] div[role="progressbar"] {
    background-color: var(--gold-light) !important;
}

/* Toggle */
div[data-testid="stToggle"] p,
div[data-testid="stToggle"] span {
    color: var(--text) !important;
}

/* Checkbox */
div[data-testid="stCheckbox"] p,
div[data-testid="stCheckbox"] span {
    color: var(--text) !important;
}

/* Radio */
div[data-testid="stRadio"] p,
div[data-testid="stRadio"] span {
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════════════
   BUTTONS
═══════════════════════════════════════════════════ */

div[data-testid="stButton"] button,
div[data-testid="stFormSubmitButton"] button {
    border-radius: 10px !important;
    border: 1px solid var(--line-strong) !important;
    background: var(--btn-bg) !important;
    color: var(--btn-text) !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    padding: 0.45rem 1.1rem !important;
    transition: background 0.15s ease, transform 0.1s ease, box-shadow 0.15s ease !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.08) !important;
    letter-spacing: 0.01em !important;
}
div[data-testid="stButton"] button *,
div[data-testid="stFormSubmitButton"] button * {
    color: inherit !important;
    fill: currentColor !important;
}
div[data-testid="stButton"] button:hover,
div[data-testid="stFormSubmitButton"] button:hover {
    background: var(--btn-bg-hover) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.12) !important;
}
div[data-testid="stButton"] button:active,
div[data-testid="stFormSubmitButton"] button:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
}

/* Primary button */
div[data-testid="stButton"] button[kind="primary"],
div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {
    background: linear-gradient(135deg, #046A38 0%, #FF671F 100%) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 10px 25px rgba(4,106,56,0.22), 0 8px 20px rgba(255,103,31,0.22) !important;
}
div[data-testid="stButton"] button[kind="primary"]:hover,
div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:hover {
    filter: brightness(1.08) !important;
    box-shadow: 0 4px 16px rgba(158,95,26,0.45) !important;
}

/* ═══════════════════════════════════════════════════
   NUMBER INPUT (step buttons)
═══════════════════════════════════════════════════ */

div[data-testid="stNumberInput"] button {
    background: var(--panel) !important;
    color: var(--text) !important;
    border: 1px solid var(--line-strong) !important;
}
div[data-testid="stNumberInput"] button:hover {
    background: var(--panel-hover) !important;
}
div[data-testid="stNumberInput"] button svg {
    fill: var(--text) !important;
}

/* ═══════════════════════════════════════════════════
   MULTISELECT
═══════════════════════════════════════════════════ */

div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background-color: var(--input-bg) !important;
    color: var(--text) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 12px !important;
}
div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: var(--accent1) !important;
    color: var(--text) !important;
    border: 1px solid var(--line-strong) !important;
}
div[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
    color: var(--text) !important;
}
div[data-testid="stMultiSelect"] [data-baseweb="tag"] [role="presentation"] svg {
    fill: var(--muted) !important;
}

/* ═══════════════════════════════════════════════════
   FORM CONTAINER
═══════════════════════════════════════════════════ */

/* ═══════════════════════════════════════════════════
   METRICS
═══════════════════════════════════════════════════ */

div[data-testid="stMetricLabel"],
div[data-testid="stMetricLabel"] p {
    color: var(--muted) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] div {
    color: var(--text) !important;
    font-size: 1.5rem !important;
    font-weight: 800 !important;
}

/* ═══════════════════════════════════════════════════
   ALERTS / INFO / WARNING / ERROR / SUCCESS
═══════════════════════════════════════════════════ */

div[data-testid="stAlert"] {
    border-radius: 14px !important;
    border: 1px solid var(--line-strong) !important;
    background: var(--panel) !important;
}
div[data-testid="stAlert"] p {
    color: var(--text) !important;
}
div[data-testid="stAlert"] *,
div[role="alert"][data-baseweb="notification"] * {
    color: var(--text) !important;
}
/* Info */
div[role="alert"][data-baseweb="notification"] {
    border-radius: 14px !important;
}

/* ═══════════════════════════════════════════════════
   CODE BLOCKS & JSON
═══════════════════════════════════════════════════ */

div[data-testid="stCodeBlock"] {
    border-radius: 14px !important;
    border: 1px solid var(--line) !important;
    background: var(--input-bg) !important;
    overflow: hidden !important;
}
div[data-testid="stCodeBlock"] > div,
div[data-testid="stCodeBlock"] pre,
div[data-testid="stCodeBlock"] code,
div[data-testid="stCodeBlock"] span {
    background: transparent !important;
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text) !important;
    font-size: 0.82rem !important;
}
div[data-testid="stCodeBlock"] button,
div[data-testid="stCodeBlock"] button svg {
    color: var(--muted) !important;
    fill: var(--muted) !important;
}

div[data-testid="stJson"] {
    background: var(--panel) !important;
    border: 1px solid var(--line) !important;
    border-radius: 14px !important;
    padding: 0.75rem !important;
}
div[data-testid="stJson"] *,
div[data-testid="stDataFrame"] *,
div[data-testid="stTable"] * {
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════════════
   EXPANDER
═══════════════════════════════════════════════════ */

/* ═══════════════════════════════════════════════════
   DIVIDER
═══════════════════════════════════════════════════ */

hr {
    border-color: var(--divider) !important;
    margin: 1rem 0 !important;
}

/* ═══════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════ */

div[data-testid="stTabs"] [role="tab"] {
    color: var(--muted) !important;
    font-weight: 600 !important;
    border-bottom: 2px solid transparent !important;
    transition: color 0.15s !important;
}
div[data-testid="stTabs"] [role="tablist"] {
    gap: 0.35rem !important;
    margin-bottom: 0.75rem !important;
}
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: var(--gold) !important;
    border-bottom-color: var(--gold) !important;
}

/* ═══════════════════════════════════════════════════
   DATAFRAME / TABLE
═══════════════════════════════════════════════════ */

div[data-testid="stDataFrame"],
div[data-testid="stDataFrame"] table {
    background: var(--panel) !important;
    color: var(--text) !important;
    border-radius: 14px !important;
    overflow: hidden !important;
}
div[data-testid="stDataFrame"] th {
    background: var(--panel-strong) !important;
    color: var(--muted) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
}

div[data-testid="stCodeBlock"] pre {
    max-height: 520px !important;
    overflow: auto !important;
}

/* ═══════════════════════════════════════════════════
   TOAST / SPINNER
═══════════════════════════════════════════════════ */

div[data-testid="stToast"] {
    background: var(--panel-strong) !important;
    border: 1px solid var(--line-strong) !important;
    border-radius: 14px !important;
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════════════
   CUSTOM JARVIS COMPONENTS
═══════════════════════════════════════════════════ */

/* Hero banner */
.jarvis-hero {
    border: 1px solid var(--line-strong);
    background: var(--hero-bg);
    border-radius: 20px;
    padding: 1.6rem 2rem 1.5rem;
    box-shadow: var(--hero-shadow);
    margin-bottom: 1.15rem;
    position: relative;
    overflow: hidden;
}
.jarvis-hero::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, var(--accent1), var(--accent2));
    pointer-events: none;
}
.jarvis-hero::after {
    content: "";
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--line-strong), transparent);
}
.jarvis-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.2em;
    font-size: 0.68rem;
    color: var(--gold);
    font-weight: 700;
    margin-bottom: 0.5rem;
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.jarvis-hero,
.jarvis-hero * {
    color: var(--text);
}
.jarvis-hero .jarvis-eyebrow {
    color: var(--gold);
}
.jarvis-eyebrow::before {
    content: "";
    display: inline-block;
    width: 20px;
    height: 1.5px;
    background: var(--gold);
    border-radius: 999px;
}
.jarvis-title {
    font-size: 1.9rem;
    line-height: 1.08;
    margin: 0 0 0.4rem;
    font-weight: 900;
    color: var(--text);
    position: relative;
    letter-spacing: 0;
}
.jarvis-subtitle {
    color: var(--muted);
    max-width: 68ch;
    font-size: 0.92rem;
    line-height: 1.6;
    position: relative;
}

/* Stat cards */
.jarvis-card {
    border: 1px solid var(--line);
    background: var(--panel);
    color: var(--text);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    margin: 0 0 1rem;
    box-shadow: var(--card-shadow);
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
.jarvis-card:hover {
    box-shadow: 0 8px 24px rgba(0,0,0,0.11);
    border-color: var(--line-strong);
}
.jarvis-card + .jarvis-card { margin-top: 0.35rem; }
.jarvis-card-title {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--muted);
    margin-bottom: 0.34rem;
    font-weight: 700;
}
.jarvis-card-value {
    font-size: 1.3rem;
    font-weight: 800;
    line-height: 1.15;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 0.35rem;
}
.jarvis-card-hint {
    margin-top: 0.35rem;
    color: var(--muted2);
    font-size: 0.8rem;
}
.jarvis-card-ok   { border-left: 3px solid var(--green); }
.jarvis-card-warn { border-left: 3px solid var(--gold-light);  }
.jarvis-card-bad  { border-left: 3px solid var(--red);   }

/* Live pulse dot */
.jarvis-pulse {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--pulse-color);
    animation: pulse-ring 2s ease-out infinite;
    margin-right: 7px;
    vertical-align: middle;
    flex-shrink: 0;
}
@keyframes pulse-ring {
    0%   { box-shadow: 0 0 0 0 rgba(74,200,120,0.6); }
    60%  { box-shadow: 0 0 0 7px rgba(74,200,120,0); }
    100% { box-shadow: 0 0 0 0 rgba(74,200,120,0); }
}

/* Section label */
.jarvis-section-label {
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.65rem;
    color: var(--muted);
    margin: 1.35rem 0 0.7rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
.jarvis-section-label::after {
    content: "";
    flex: 1;
    height: 1px;
    background: linear-gradient(90deg, var(--line-strong), transparent);
}

/* KV grid */
.jarvis-kv {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
    gap: 0.8rem;
    color: var(--text);
}
.jarvis-kv-item {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--panel);
    padding: 0.82rem 0.95rem;
    transition: background 0.15s;
}
.jarvis-kv-item:hover { background: var(--panel-hover); }
.jarvis-kv-label {
    font-size: 0.70rem;
    text-transform: uppercase;
    letter-spacing: 0.11em;
    color: var(--muted);
    margin-bottom: 0.28rem;
    font-weight: 600;
}
.jarvis-kv-value {
    font-size: 0.93rem;
    font-weight: 700;
    color: var(--text);
    word-break: break-word;
    line-height: 1.3;
}

/* Timeline */
.jarvis-timeline-item {
    border-left: 3px solid var(--teal);
    padding: 0.15rem 0 0.8rem 0.9rem;
    margin-left: 0.25rem;
    color: var(--text);
}
.jarvis-timeline-meta  { color: var(--muted2); font-size: 0.78rem; margin-bottom: 0.12rem; }
.jarvis-timeline-title { font-weight: 700; margin-bottom: 0.12rem; font-size: 0.9rem; }
.jarvis-timeline-body  { color: var(--muted); font-size: 0.86rem; word-break: break-all; }

/* Live strip */
.jarvis-live-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem 0.75rem;
    align-items: center;
    margin: 0.35rem 0 0.95rem;
    padding: 0.65rem 0.9rem;
    border: 1px solid var(--line-strong);
    border-radius: 14px;
    background: var(--panel);
    color: var(--text);
    font-size: 0.82rem;
    box-shadow: var(--card-shadow);
}
.jarvis-live-strip span {
    color: inherit;
    white-space: nowrap;
}

/* Command preview */
.jarvis-preview {
    border: 1px solid var(--line);
    border-radius: 14px;
    background: var(--panel);
    color: var(--text);
    padding: 0.8rem 0.95rem;
    margin: 0.6rem 0 0.8rem;
    display: grid;
    gap: 0.25rem;
    font-size: 0.84rem;
    box-shadow: var(--card-shadow);
}
.jarvis-preview strong {
    color: var(--text);
}

/* Memory cards */
.jarvis-memory-card {
    border: 1px solid var(--line);
    background: var(--panel);
    border-radius: 12px;
    padding: 0.6rem 0.85rem;
    margin-bottom: 0.45rem;
    font-size: 0.91rem;
    color: var(--text);
    transition: background 0.15s;
}
.jarvis-memory-card:hover { background: var(--panel-hover); }
.jarvis-memory-ts {
    font-size: 0.72rem;
    color: var(--muted2);
    margin-top: 0.2rem;
}

/* Banners */
.jarvis-warn-banner {
    border: 1px solid var(--warn-border);
    background: var(--warn-bg);
    border-radius: 16px;
    padding: 1rem 1.15rem;
    margin: 0.8rem 0;
    color: var(--text);
}
.jarvis-warn-banner *,
.jarvis-confirm-banner *,
.jarvis-danger-banner * {
    color: inherit;
}
.jarvis-confirm-banner {
    border: 1px solid var(--confirm-border);
    background: var(--confirm-bg);
    border-radius: 16px;
    padding: 1rem 1.15rem;
    margin: 0.8rem 0;
    color: var(--text);
}
.jarvis-danger-banner {
    border: 1px solid var(--danger-border);
    background: var(--danger-bg);
    border-radius: 16px;
    padding: 1rem 1.15rem;
    margin: 0.8rem 0;
    color: var(--text);
}

/* Pill badges (inline) */
.jarvis-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.2rem 0.65rem;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 700;
    border: 1px solid var(--line-strong);
    background: var(--panel);
    color: var(--text);
    letter-spacing: 0.01em;
}

.jarvis-log-block {
    display: block;
    width: 100%;
    max-height: 520px;
    overflow: auto;
    box-sizing: border-box;
    margin: 0;
    padding: 0.9rem 1rem;
    border: 1px solid var(--line-strong);
    border-radius: 14px;
    background: var(--input-bg);
    color: var(--text);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    font-size: 0.82rem;
    line-height: 1.55;
    white-space: pre-wrap;
    word-break: break-word;
    box-shadow: var(--card-shadow);
}

/* ═══════════════════════════════════════════════════
   CHAT MESSAGES  (st.chat_message)
═══════════════════════════════════════════════════ */

[data-testid="stChatMessage"] {
    background: var(--panel) !important;
    border: 1px solid var(--line) !important;
    border-radius: 16px !important;
    padding: 0.7rem 1rem !important;
    margin-bottom: 0.5rem !important;
    box-shadow: var(--card-shadow) !important;
    transition: box-shadow 0.15s ease !important;
}
[data-testid="stChatMessage"]:hover {
    border-color: var(--line-strong) !important;
    box-shadow: 0 6px 20px rgba(0,0,0,0.09) !important;
}
[data-testid="stChatMessageContent"] p,
[data-testid="stChatMessageContent"] li,
[data-testid="stChatMessageContent"] span {
    color: var(--text) !important;
}
[data-testid="stChatMessageAvatar"] {
    background: var(--accent1) !important;
    border: 1px solid var(--line-strong) !important;
}
[data-testid="stChatMessageAvatarUser"] {
    background: var(--accent2) !important;
}

/* ═══════════════════════════════════════════════════
   METRICS  (pro refinement)
═══════════════════════════════════════════════════ */

div[data-testid="stMetric"] {
    background: var(--panel) !important;
    border: 1px solid var(--line) !important;
    border-radius: 14px !important;
    padding: 0.85rem 1rem !important;
    box-shadow: var(--card-shadow) !important;
    transition: box-shadow 0.2s ease, transform 0.15s ease !important;
}
div[data-testid="stMetric"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(0,0,0,0.09) !important;
}

/* ═══════════════════════════════════════════════════
   FORM CONTAINER  (pro refinement)
═══════════════════════════════════════════════════ */

div[data-testid="stForm"] {
    background: var(--panel) !important;
    border: 1px solid var(--line) !important;
    border-radius: 16px !important;
    padding: 1.1rem 1.1rem 0.6rem !important;
    box-shadow: var(--card-shadow) !important;
}

/* ═══════════════════════════════════════════════════
   EXPANDER  (pro refinement)
═══════════════════════════════════════════════════ */

details[data-testid="stExpander"],
div[data-testid="stExpander"] {
    border: 1px solid var(--line) !important;
    border-radius: 14px !important;
    background: var(--panel) !important;
    overflow: hidden !important;
    transition: border-color 0.15s !important;
}
details[data-testid="stExpander"]:hover,
div[data-testid="stExpander"]:hover {
    border-color: var(--line-strong) !important;
}
details[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary {
    color: var(--text) !important;
    background: transparent !important;
    padding: 0.7rem 1rem !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
}
"""


_CSS_DARK_OVERRIDES = """
/* ═══════════════════════════════════════════════════
   DARK MODE: eliminate light-theme bleed
   (Streamlit's base="light" in config.toml leaks
   into some internal elements — these rules win)
═══════════════════════════════════════════════════ */

/* Force app and all top-level wrappers dark */
.stApp,
.stApp > section,
.stApp > div:not([data-testid="stSidebar"]) {
    background: var(--bg) !important;
    background-color: var(--bg) !important;
    color: var(--text) !important;
}
.stApp {
    background: var(--bg-grad) !important;
}

/* All transparent containers must NOT inherit a white background */
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
div[data-testid="stVerticalBlock"],
div[data-testid="stHorizontalBlock"],
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: transparent !important;
    background-color: transparent !important;
}

/* BaseUI popover/dropdown */
[data-baseweb="popover"] > div,
[data-baseweb="popover-content"],
[data-baseweb="menu"],
[data-baseweb="list"],
ul[role="listbox"],
li[role="option"] {
    background-color: var(--panel-strong) !important;
    color: var(--text) !important;
    border-color: var(--line-strong) !important;
}
li[role="option"]:hover {
    background-color: var(--panel-hover) !important;
}

/* BaseUI tooltip */
[data-baseweb="tooltip"],
[data-baseweb="tooltip"] div {
    background-color: var(--panel-strong) !important;
    color: var(--text) !important;
}

/* BaseUI notification (info/warning/error boxes from Streamlit) */
[data-baseweb="notification"] {
    background-color: var(--panel) !important;
    border-color: var(--line-strong) !important;
}
[data-baseweb="notification"] p,
[data-baseweb="notification"] div {
    color: var(--text) !important;
}

/* Alert boxes */
div[data-testid="stAlert"] {
    background-color: var(--panel) !important;
}
div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span {
    color: var(--text) !important;
}

/* Spinner */
[data-testid="stSpinner"] > div {
    background: transparent !important;
    color: var(--gold-light) !important;
}

/* Code block */
div[data-testid="stCodeBlock"] {
    background-color: var(--input-bg) !important;
    border-color: var(--line-strong) !important;
}
div[data-testid="stCodeBlock"] > div,
div[data-testid="stCodeBlock"] pre,
div[data-testid="stCodeBlock"] code,
div[data-testid="stCodeBlock"] span {
    background-color: var(--input-bg) !important;
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text) !important;
}

/* JSON viewer */
div[data-testid="stJson"] {
    background-color: var(--input-bg) !important;
}

/* Links */
[data-testid="stMarkdownContainer"] a {
    color: var(--gold-light) !important;
}
[data-testid="stMarkdownContainer"] a:hover {
    color: var(--gold) !important;
}

/* Metric delta */
[data-testid="stMetricDelta"] > div,
[data-testid="stMetricDelta"] span {
    color: var(--green) !important;
}

/* Number input step buttons */
div[data-testid="stNumberInput"] button {
    background: var(--panel-strong) !important;
    border-color: var(--line-strong) !important;
    color: var(--text) !important;
}

/* Horizontal rule */
hr {
    border-color: var(--divider) !important;
}

/* Tabs in dark */
div[data-testid="stTabs"] [role="tablist"] {
    border-color: var(--divider) !important;
}

/* Expander in dark */
details[data-testid="stExpander"] summary:hover,
div[data-testid="stExpander"] summary:hover {
    background: var(--panel-hover) !important;
}

/* DataFrame / table in dark */
div[data-testid="stDataFrame"] td {
    color: var(--text) !important;
    border-color: var(--divider) !important;
}
"""


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


def render_theme_toggle() -> None:
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
    """Soft rerun after interval — preserves session_state, no page flash.
    Call at the BOTTOM of the page after all content is rendered.
    """
    import time  # noqa: PLC0415
    if not enabled or not st.session_state.get("live_updates_enabled", True):
        return
    time.sleep(max(1, interval_seconds))
    st.rerun()


def refresh_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
