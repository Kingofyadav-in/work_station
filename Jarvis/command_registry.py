#!/usr/bin/env python3
"""
Command Registry — single source of truth for every Jarvis intent.

Every action that the system can execute is declared here with its:
  - canonical action name
  - exact-match trigger phrases (aliases)
  - category, risk tier, description
  - payload metadata (for prefix-dispatched commands)

Downstream consumers:
  - intent_parser.py  → builds _EXACT from EXACT_TABLE
  - behavior.py       → derives LOW/MEDIUM/HIGH_RISK_ACTIONS
  - actions.py        → show_commands() formats this for CLI/voice
  - dashboard         → quick-action buttons and help panel
  - tests             → coverage: every registered action has a real handler
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from plugin_loader import format_plugin_help


@dataclass(frozen=True)
class Command:
    action: str
    aliases: tuple[str, ...]        # exact-match phrases; empty for payload-only
    category: str
    risk_tier: str                  # "low" | "medium" | "high"
    description: str
    takes_payload: bool = False
    payload_hint: str = ""          # e.g. "ask <question>" shown in help


# ── Registry ───────────────────────────────────────────────────────────────────

REGISTRY: tuple[Command, ...] = (
    # ── Info ──────────────────────────────────────────────────────────────────
    Command("status",       ("status", "system status", "health"),              "info",     "low",    "Show system health and connectivity."),
    Command("context",      ("context", "runtime context", "show context"),     "info",     "low",    "Show runtime context snapshot."),
    Command("system_info",  ("info", "system info", "system information"),      "info",     "low",    "Show detailed system information."),
    Command("system_summary", ("system summary",),                              "info",     "low",    "Full system summary."),
    Command("device_report", ("device report", "device status", "verify device", "trusted device"), "info", "low", "Show trusted-device registration status."),
    Command("device_inventory", ("device inventory", "full device inventory"), "info", "low", "Show hardware, software, network, and safe environment inventory."),
    Command("device_hardware", ("hardware report", "device hardware", "hardware details"), "info", "low", "Show trusted-device hardware details."),
    Command("device_software", ("software report", "device software", "software details"), "info", "low", "Show trusted-device software details."),
    Command("device_network", ("network report", "device network", "network details"), "info", "low", "Show trusted-device network details."),
    Command("device_environment", ("env report", "environment report", "device environment", "environment details"), "info", "low", "Show safe trusted-device environment details."),
    Command("auto_detect_device", ("auto detect device", "auto register device", "detect device"), "settings", "medium", "Auto-detect and register or refresh this trusted device.", takes_payload=True, payload_hint="auto detect device [label]"),
    Command("logs",         ("logs", "activity", "history"),                    "info",     "low",    "Show recent activity logs."),
    Command("ai_status",    ("ai status", "model status", "openai status"),     "info",     "low",    "Show AI provider and model status."),
    Command("time",         ("time", "what time is it", "current time", "tell me the time"), "info", "low", "Show current local time."),
    Command("commands",     ("commands", "help", "show commands", "list commands"), "info", "low",    "Show all available commands."),
    Command("doctor",        ("doctor", "health check", "system check", "run doctor"), "info", "low", "Show system health check report."),
    Command("inbox_summary", ("inbox", "public inbox", "inbox summary"),              "info", "low",  "Show public enquiry and signup counts."),
    Command("chat_stats",    ("chat stats", "public chat stats", "chat activity"),    "info", "low",  "Show public Jarvis chat statistics."),

    # ── Identity ───────────────────────────────────────────────────────────────
    Command("identity",         ("identity", "intro", ""),                      "identity", "low",    "Describe Jarvis identity."),
    Command("profiles",         ("profiles", "show profiles", "ai hi profiles"), "identity", "low",  "Show all profiles (AI + HI)."),
    Command("ai_intro",         ("jarvis introduce yourself", "ai intro", "introduce yourself"), "identity", "low", "Jarvis self-introduction."),
    Command("who_are_you",      ("who are you", "jarvis who are you"),          "identity", "low",    "Ask who Jarvis is."),
    Command("greet_user",       ("hello", "hi"),                                "identity", "low",    "Greet the user."),

    # ── HI State (read) ────────────────────────────────────────────────────────
    Command("who_am_i",             ("who am i", "identify"),                   "hi_state", "low",    "Show the human operator identity."),
    Command("hi_get_profile",       ("profile", "show profile"),                "hi_state", "low",    "Show full HI profile."),
    Command("hi_get_intro",         ("human intro", "user intro", "owner intro", "hi_intro"), "hi_state", "low", "HI self-introduction."),
    Command("hi_get_relationship",  ("relationship", "relationship model", "ai hi relationship"), "hi_state", "low", "Show HI-AI relationship model."),
    Command("hi_identity_summary",  ("hi summary", "my identity", "identity summary", "who is hi"), "hi_state", "low", "Full HI identity summary."),
    Command("hi_get_memory",        ("memory", "memory lite", "show memory"),   "hi_state", "low",    "Show HI memory entries."),
    Command("hi_get_preferences",   ("preferences", "show preferences"),        "hi_state", "low",    "Show HI preferences."),
    Command("hi_get_workflow",      ("workflow", "show workflow", "current focus"), "hi_state", "low", "Show HI workflow and current focus."),
    Command("what_is_my_domain",    ("what is my domain", "my domain", "show my domain", "domain"), "hi_state", "low", "Show HI domain."),
    Command("what_is_my_language",  ("what is my language", "my language"),     "hi_state", "low",    "Show HI language setting."),
    Command("what_is_my_device",    ("what is my device", "my device"),         "hi_state", "low",    "Show HI device info."),
    Command("website_status",       ("website status", "show website status", "check website", "site status"), "hi_state", "low", "Check HI website reachability."),

    # ── Session ────────────────────────────────────────────────────────────────
    Command("show_session",             ("show session", "session"),            "session",  "low",    "Show current session state."),
    Command("what_was_my_last_command", ("what was my last command", "last command"), "session", "low", "Show last command run."),
    Command("what_was_my_last_action",  ("what was my last action", "last action"),  "session", "low", "Show last action taken."),
    Command("confirmation_status",      ("confirmation status", "pending action"),    "session", "low", "Show pending confirmation."),
    Command("confirm",                  ("confirm", "confirm last action"),           "session", "low", "Confirm a pending high-risk action."),
    Command("cancel",                   ("cancel", "cancel pending action", "clear pending action"), "session", "medium", "Cancel a pending action."),
    Command("reset_session",            ("reset session",),                    "session",  "medium",  "Reset session state."),

    # ── AI ────────────────────────────────────────────────────────────────────
    Command("ai",           (),  "ai", "low",  "Ask AI a question.",    takes_payload=True, payload_hint="ask <question>"),
    Command("plan",         (),  "ai", "low",  "Plan with AI.",         takes_payload=True, payload_hint="plan <topic>"),

    # ── Apps ──────────────────────────────────────────────────────────────────
    Command("open_terminal", ("open terminal", "launch terminal"),              "apps",     "low",    "Open a terminal window."),
    Command("open_chrome",   ("open chrome", "launch chrome"),                  "apps",     "low",    "Open Chrome browser."),
    Command("open_files",    ("open files", "open file manager"),               "apps",     "low",    "Open file manager (Nautilus)."),

    # ── System ────────────────────────────────────────────────────────────────
    Command("battery_status", ("battery", "battery status", "show battery"),   "system",   "low",    "Show battery level and state."),
    Command("disk_status",    ("disk", "disk status", "show disk"),             "system",   "low",    "Show disk usage."),
    Command("lock_screen",    ("lock", "lock screen", "lock my screen"),        "system",   "low",    "Lock the screen."),
    Command("volume_up",      ("volume up", "increase volume"),                 "system",   "low",    "Increase system volume by 10%."),
    Command("volume_down",    ("volume down", "decrease volume"),               "system",   "low",    "Decrease system volume by 10%."),
    Command("mute_volume",    ("mute", "mute volume"),                          "system",   "low",    "Toggle system mute."),

    # ── Settings (HI write) ───────────────────────────────────────────────────
    Command("hi_set_profile_field", (), "settings", "medium", "Set an HI profile field.",    takes_payload=True, payload_hint="set my name <name>"),
    Command("hi_set_preference",    (), "settings", "medium", "Set an HI preference.",       takes_payload=True, payload_hint="set response mode <adaptive|concise|detailed>"),
    Command("hi_set_workflow_focus", (), "settings", "medium", "Set workflow current focus.", takes_payload=True, payload_hint="set current focus <task>"),
    Command("hi_workflow_add_task", (), "settings", "medium", "Add a workflow task with status, blockers, due date, and estimate metadata.", takes_payload=True, payload_hint="add task <title>"),
    Command("hi_workflow_set_task_status", (), "settings", "medium", "Update a workflow task status.", takes_payload=True, payload_hint="set task status <task_id> <todo|doing|blocked|done|cancelled>"),
    Command("hi_workflow_add_blocker", (), "settings", "medium", "Add a blocker to a workflow task.", takes_payload=True, payload_hint="block task <task_id> <blocker>"),
    Command("hi_workflow_set_due", (), "settings", "medium", "Set a workflow task due date.", takes_payload=True, payload_hint="set task due <task_id> <due>"),
    Command("hi_memory_add",        (), "settings", "medium", "Add a memory entry.",         takes_payload=True, payload_hint="add memory <note>"),
    Command("hi_set_domain",        (), "settings", "medium", "Set HI domain and website.",  takes_payload=True, payload_hint="set my domain <domain>"),
    Command("hi_memory_search",     (), "hi_state", "low",    "Semantic search across HI memory.", takes_payload=True, payload_hint="search memory <query>"),
    Command("hi_memory_related",    (), "hi_state", "low",    "Show memories related to a memory id.", takes_payload=True, payload_hint="related memory <id>"),
    Command("hi_memory_visibility", (), "settings", "medium", "Set memory public/private visibility.", takes_payload=True, payload_hint="make memory public <id>"),
    Command("hi_memory_delete",     (), "settings", "medium", "Delete a memory entry by id.", takes_payload=True, payload_hint="delete memory <id>"),
    Command("set_ai_name",          (), "settings", "medium", "Set the AI assistant name.",  takes_payload=True, payload_hint="set ai name <name>"),
    Command("set_intro_mode",       (), "settings", "medium", "Set intro verbosity mode.",   takes_payload=True, payload_hint="set intro mode <short|normal|formal>"),
    Command("set_command_style",    (), "settings", "medium", "Set preferred command style.", takes_payload=True, payload_hint="set command style <natural|structured>"),
    Command("set_mic_device",       (), "settings", "medium", "Set microphone device index.", takes_payload=True, payload_hint="set mic device <index>"),
    Command("set_wake_phrase",      (), "settings", "medium", "Set the voice wake phrase.",  takes_payload=True, payload_hint="set wake phrase <phrase>"),
    Command("register_device",      ("register device",), "settings", "medium", "Register this machine as a trusted Jarvis control device.", takes_payload=True, payload_hint="register device [label]"),

    # ── Shell ─────────────────────────────────────────────────────────────────
    Command("shell", (), "shell", "high", "Execute an allowlisted shell command (requires confirmation).", takes_payload=True, payload_hint="run <command>"),
)


# ── Derived lookup structures ─────────────────────────────────────────────────

def _build_risk_sets() -> tuple[set[str], set[str], set[str]]:
    low: set[str] = set()
    med: set[str] = set()
    hi: set[str] = set()
    for cmd in REGISTRY:
        if cmd.risk_tier == "high":
            hi.add(cmd.action)
        elif cmd.risk_tier == "medium":
            med.add(cmd.action)
        else:
            low.add(cmd.action)
    return low, med, hi


LOW_RISK_ACTIONS, MEDIUM_RISK_ACTIONS, HIGH_RISK_ACTIONS = _build_risk_sets()


def build_exact_table() -> dict[str, tuple[str, str]]:
    """Return the alias → (action, payload) mapping for intent_parser._EXACT."""
    table: dict[str, tuple[str, str]] = {}
    for cmd in REGISTRY:
        for alias in cmd.aliases:
            table[alias] = (cmd.action, "")
    return table


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_commands_by_category() -> dict[str, list[Command]]:
    result: dict[str, list[Command]] = {}
    for cmd in REGISTRY:
        result.setdefault(cmd.category, []).append(cmd)
    return result


def get_quick_actions(category: str) -> list[tuple[str, str]]:
    """Return (button_label, command_text) pairs for dashboard buttons."""
    pairs: list[tuple[str, str]] = []
    for cmd in REGISTRY:
        if cmd.category != category:
            continue
        if not cmd.aliases:
            continue
        first_alias = cmd.aliases[0]
        if not first_alias:
            continue
        label = first_alias.title()
        pairs.append((label, first_alias))
    return pairs


def get_all_quick_actions() -> dict[str, list[tuple[str, str]]]:
    """Return quick actions grouped by category for the dashboard."""
    result: dict[str, list[tuple[str, str]]] = {}
    for cat in ("info", "hi_state", "system", "apps"):
        actions = get_quick_actions(cat)
        if actions:
            result[cat] = actions
    return result


# ── Help text formatter ───────────────────────────────────────────────────────

_CATEGORY_LABELS: dict[str, str] = {
    "info":     "Info & Status",
    "identity": "Identity",
    "hi_state": "HI State",
    "session":  "Session",
    "ai":       "AI",
    "apps":     "Apps",
    "system":   "System",
    "settings": "Settings",
    "shell":    "Shell",
}

_RISK_NOTES: dict[str, str] = {
    "medium": " (changes state)",
    "high":   " (requires confirmation)",
}


def format_help_text(category: str | None = None) -> str:
    """Format a human-readable command reference."""
    by_cat = get_commands_by_category()
    lines: list[str] = ["Jarvis Commands", "═" * 50, ""]

    cat_order = ["info", "identity", "hi_state", "session", "ai", "apps", "system", "settings", "shell"]
    for cat in cat_order:
        cmds = by_cat.get(cat, [])
        if not cmds:
            continue
        if category and cat != category:
            continue

        label = _CATEGORY_LABELS.get(cat, cat.upper())
        risk_note = _RISK_NOTES.get(cmds[0].risk_tier, "") if cmds else ""
        lines.append(f"[{label.upper()}{risk_note}]")

        for cmd in cmds:
            if cmd.takes_payload:
                trigger = cmd.payload_hint or cmd.action
            elif cmd.aliases:
                trigger = cmd.aliases[0]
            else:
                continue
            if len(trigger) > 40:
                lines.append(f"  {trigger}")
                lines.append(f"    {'':<40} {cmd.description}")
            else:
                lines.append(f"  {trigger:<42} {cmd.description}")

        lines.append("")

    lines.append("Prefix commands: ask/ai <question>  ·  plan <topic>  ·  run <shell cmd>")
    plugin_help = format_plugin_help()
    if plugin_help:
        lines.append("")
        lines.append(plugin_help)
    lines.append("Unknown phrases are routed to AI automatically.")
    return "\n".join(lines)
