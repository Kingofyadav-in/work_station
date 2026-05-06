#!/usr/bin/env python3

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Callable

_ROOT_DIR = Path(__file__).resolve().parent.parent
_STATE_PATH = _ROOT_DIR / "Kingofyadav" / "state.json"

from ai_connector import ai_status, ask_ai, plan_with_ai
from behavior import get_risk_profile
from command_registry import format_help_text
from context import BASE_DIR, get_runtime_context, load_profile, log_activity, read_recent_logs
from device_registry import (
    auto_detect_and_register_device,
    format_device_report,
    format_device_section,
    register_current_device,
    verify_current_device,
)
from plugin_loader import execute_plugin_action, get_plugin_action_names
from profile_manager import (
    clear_pending_confirmation,
    get_session,
    load_profiles,
    reset_session,
    update_ai_field,
    update_hi_field,
)
from system_info import get_system_info


SAFE_COMMANDS = {
    "pwd": {"flags": set(), "allow_path": False},
    "whoami": {"flags": set(), "allow_path": False},
    "date": {"flags": set(), "allow_path": False},
    "uname": {"flags": {"-a", "-s", "-r", "-m"}, "allow_path": False},
    "ls": {"flags": {"-1", "-a", "-l", "-la", "-al"}, "allow_path": True},
}

_DESKTOP_ACTION_TIMEOUT = 5


def _run_desktop_action(command: list[str], success_message: str) -> str:
    try:
        subprocess.run(command, timeout=_DESKTOP_ACTION_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        return f"Command timed out after {_DESKTOP_ACTION_TIMEOUT}s: {command[0]}"
    except Exception as exc:
        return f"Command failed: {exc}"
    return success_message


def describe_identity() -> str:
    context = get_runtime_context(log_limit=5)
    profiles = context["profiles"]
    ai_profile = profiles["AI"]
    hi_profile = profiles["HI"]
    info = context["system"]
    return (
        "Jarvis Human Interface Bridge\n"
        "-----------------------------\n"
        f"AI: {ai_profile.get('name', 'unknown')} ({ai_profile.get('type', 'unknown')})\n"
        f"Human: {hi_profile.get('name', 'unknown')} ({hi_profile.get('type', 'unknown')})\n"
        f"Human Role: {hi_profile.get('role', 'unknown')}\n"
        f"AI Role: {ai_profile.get('role', 'unknown')}\n"
        f"Domain: {hi_profile.get('domain', 'unknown')}\n"
        f"Host: {info['hostname']}\n"
        f"Local IP: {info['local_ip']}\n"
        f"Connectivity: {info['connectivity']}"
    )


def get_status_report() -> str:
    info = get_system_info()
    return (
        "System Status\n"
        "-------------\n"
        f"Host: {info['hostname']}\n"
        f"Operating System: {info['operating_system']}\n"
        f"Time: {info['local_time']}\n"
        f"Connectivity: {info['connectivity']}\n"
        f"Available Memory: {info['available_memory']}"
    )

def get_time() -> str:
    return datetime.now().strftime("%I:%M %p")

def get_context_report() -> str:
    context = get_runtime_context(log_limit=5)
    profiles = context["profiles"]
    hi_profile = profiles["HI"]
    ai_profile = profiles["AI"]
    relationship = profiles["relationship"]
    system = context["system"]
    return (
        "Runtime Context\n"
        "---------------\n"
        f"Human: {hi_profile.get('name', 'unknown')}\n"
        f"AI: {ai_profile.get('name', 'unknown')}\n"
        f"Domain: {hi_profile.get('domain', 'unknown')}\n"
        f"Human Role: {relationship.get('human_role', 'unknown')}\n"
        f"AI Role: {relationship.get('ai_role', 'unknown')}\n"
        f"Host: {system['hostname']}\n"
        f"Connectivity: {system['connectivity']}\n"
        f"Current Directory: {system['current_directory']}"
    )


def get_ai_intro() -> str:
    profiles = load_profiles()
    ai_profile = profiles["AI"]
    hi_profile = profiles["HI"]
    mode = hi_profile.get("preferred_intro_mode", "normal")
    ai_name = ai_profile.get("name", "Jarvis")
    domain = hi_profile.get("domain", "unknown")
    if mode == "short":
        return f"I am {ai_name}, your AI assistant for {domain}."
    if mode == "formal":
        return (
            f"Greetings. I am {ai_name}, the Artificial Intelligence system assigned to assist "
            f"the human operator for {domain}. My function is to interpret intent, analyze context, "
            "and support safe execution under human control."
        )
    return ai_profile.get("intro", "Hello, I am Jarvis.")


def get_hi_intro() -> str:
    profiles = load_profiles()
    hi_profile = profiles["HI"]
    mode = hi_profile.get("preferred_intro_mode", "normal")
    hi_name = hi_profile.get("name", "unknown")
    domain = hi_profile.get("domain", "unknown")
    if mode == "short":
        return f"I am {hi_name}, the human operator for {domain}."
    if mode == "formal":
        return (
            f"I am {hi_name}, the primary human operator and decision maker for {domain}. "
            "I define objectives, authorize execution, and retain control over permissions and system boundaries."
        )
    return hi_profile.get("intro", "I am the primary user and controller of this system.")


def get_relationship_report() -> str:
    profiles = load_profiles()
    relationship = profiles["relationship"]
    hi_profile = profiles["HI"]
    ai_profile = profiles["AI"]
    return (
        "AI / HI Relationship Model\n"
        "--------------------------\n"
        f"HI ({hi_profile.get('name', 'unknown')}): {relationship.get('human_role', 'unknown')}\n"
        f"AI ({ai_profile.get('name', 'unknown')}): {relationship.get('ai_role', 'unknown')}\n"
        f"Bridge: {relationship.get('bridge_role', 'unknown')}\n"
        f"Voice Input: {relationship.get('voice_input_role', 'unknown')}"
    )


def who_am_i() -> str:
    hi = load_profiles().get("HI", {})
    name = hi.get("name", "User")
    full_name = hi.get("full_name", name)
    role = hi.get("role", "owner")
    language = hi.get("language", "unknown")

    return (
        f"You are {full_name}.\n"
        f"Short name: {name}\n"
        f"Role: {role}\n"
        f"Preferred language: {language}"
    )


def who_are_you() -> str:
    ai = load_profiles().get("AI", {})
    name = ai.get("name", "Jarvis")
    ai_type = ai.get("type", "Artificial Intelligence System")
    role = ai.get("role", "assistant")
    capabilities = ai.get("capabilities", [])
    caps = ", ".join(capabilities) if capabilities else "none"

    return (
        f"I am {name}.\n"
        f"Type: {ai_type}\n"
        f"Role: {role}\n"
        f"Capabilities: {caps}"
    )


def greet_user() -> str:
    hi = load_profiles().get("HI", {})
    name = hi.get("name", "User")
    return f"Hello {name}, how can I assist you today?"


def set_hi_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "Refused: empty human name."
    update_hi_field("name", cleaned)
    return f"HI name updated to {cleaned}"


def set_hi_language(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "Refused: empty human language."
    update_hi_field("language", cleaned)
    return f"HI language updated to {cleaned}"


def set_hi_domain(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "Refused: empty human domain."
    update_hi_field("domain", cleaned)
    return f"HI domain updated to {cleaned}"


def set_ai_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "Refused: empty AI name."
    update_ai_field("name", cleaned)
    return f"AI name updated to {cleaned}"


def set_intro_mode(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in {"short", "normal", "formal"}:
        return "Refused: intro mode must be one of short, normal, or formal."
    update_hi_field("preferred_intro_mode", cleaned)
    return f"Preferred intro mode updated to {cleaned}"


def set_command_style(value: str) -> str:
    cleaned = value.strip().lower()
    if not cleaned:
        return "Refused: empty command style."
    update_hi_field("preferred_command_style", cleaned)
    return f"Preferred command style updated to {cleaned}"


def set_mic_device(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "Refused: empty microphone device."
    try:
        device_index = int(cleaned)
    except ValueError:
        return "Refused: microphone device must be an integer."
    update_hi_field("preferred_mic_device", device_index)
    return f"Preferred microphone device updated to {device_index}"


def set_wake_phrase(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return "Refused: empty wake phrase."
    update_hi_field("wake_phrase", cleaned)
    return f"Wake phrase updated to {cleaned}"


def get_memory_report() -> str:
    import sys
    from pathlib import Path
    _ki_dir = Path(__file__).resolve().parent.parent / "Kingofyadav"
    if str(_ki_dir) not in sys.path:
        sys.path.insert(0, str(_ki_dir))
    from state_manager import load_state
    memory = load_state().get("memory", [])
    if not memory:
        return "Memory\n------\nNo memory entries yet."
    lines = ["Memory", "------", f"Total entries: {len(memory)}", ""]
    for m in reversed(memory[-10:]):
        ts = str(m.get("created_at", ""))[:10]
        tag = f" [{m['tag']}]" if m.get("tag") else ""
        imp = f" imp={m.get('importance', 3)}" if m.get("importance", 3) != 3 else ""
        vis = " [public]" if m.get("visibility") == "public" else ""
        entry_type = m.get("type", "note")
        text = str(m.get("text") or m.get("event") or m.get("command") or "").strip()
        lines.append(f"[{ts}] {entry_type}{tag}{imp}{vis}: {text[:120]}")
    return "\n".join(lines)


def get_preferences_report() -> str:
    hi_profile = load_profiles().get("HI", {})
    return (
        "Preferences\n"
        "-----------\n"
        f"Name: {hi_profile.get('name', 'unknown')}\n"
        f"Domain: {hi_profile.get('domain', 'unknown')}\n"
        f"Language: {hi_profile.get('language', 'unknown')}\n"
        f"Intro Mode: {hi_profile.get('preferred_intro_mode', 'unknown')}\n"
        f"Response Mode: {hi_profile.get('preferred_response_mode', 'unknown')}\n"
        f"Command Style: {hi_profile.get('preferred_command_style', 'unknown')}\n"
        f"Mic Device: {hi_profile.get('preferred_mic_device', 'unknown')}\n"
        f"Wake Phrase: {hi_profile.get('wake_phrase', 'unknown')}"
    )


def what_is_my_language() -> str:
    hi_profile = load_profiles().get("HI", {})
    return f"Your preferred language is {hi_profile.get('language', 'unknown')}."


def what_is_my_device() -> str:
    system = get_system_info()
    return f"Your device is {system['hostname']}."


def what_was_my_last_command() -> str:
    session = get_session()
    return f"Your last command was {session.get('last_command', 'unknown')}."


def what_was_my_last_action() -> str:
    session = get_session()
    return f"Your last action was {session.get('last_successful_action', 'unknown')}."


def show_session() -> str:
    return json.dumps(get_session(), indent=2, ensure_ascii=False)


def reset_session_state() -> str:
    reset_session()
    return "Session has been reset."


def get_system_summary() -> str:
    info = get_system_info()
    hi_profile = load_profiles().get("HI", {})
    return (
        "System Summary\n"
        "--------------\n"
        f"Human: {hi_profile.get('name', 'unknown')}\n"
        f"Domain: {hi_profile.get('domain', 'unknown')}\n"
        f"Device: {info['hostname']}\n"
        f"OS: {info['operating_system']}\n"
        f"Connectivity: {info['connectivity']}\n"
        f"Local Time: {info['local_time']}"
    )


def register_device(label: str = "") -> str:
    record = register_current_device(label or "primary")
    inv = record["inventory"]
    return (
        "Device registered as trusted.\n"
        f"Label: {record['label']}\n"
        f"Fingerprint: {inv['fingerprint']}\n"
        f"Host: {inv['identity']['hostname']}\n"
        f"OS: {inv['software']['operating_system']}\n"
        "Secret environment values were not stored."
    )


def auto_detect_device(label: str = "") -> str:
    result = auto_detect_and_register_device(label or "primary")
    record = result["record"]
    inv = record.get("inventory", {})
    action = result["action"]
    if action == "already_trusted":
        headline = "Device is already trusted."
    elif action == "refreshed":
        headline = "Device registry refreshed from auto-detect."
    elif action == "replaced":
        headline = "Device registry replaced from auto-detect."
    else:
        headline = "Device auto-detected and registered as trusted."
    return (
        f"{headline}\n"
        f"Label: {record.get('label', 'primary')}\n"
        f"Fingerprint: {inv.get('fingerprint', result['current_fingerprint'])}\n"
        f"Host: {inv.get('identity', {}).get('hostname', 'unknown')}\n"
        f"OS: {inv.get('software', {}).get('operating_system', 'unknown')}\n"
        "Secret environment values were not stored."
    )


def get_device_report() -> str:
    return format_device_report(detail=False)


def get_device_inventory_report() -> str:
    return format_device_report(detail=True)


def get_device_hardware_report() -> str:
    return format_device_section("hardware")


def get_device_software_report() -> str:
    return format_device_section("software")


def get_device_network_report() -> str:
    return format_device_section("network")


def get_device_environment_report() -> str:
    return format_device_section("environment")


def get_confirmation_status() -> str:
    session = get_session()
    pending_action = session.get("pending_action", "")
    if not pending_action:
        return "No pending confirmation."
    risk = get_risk_profile(pending_action, session.get("pending_payload", ""))
    return (
        "Pending Confirmation\n"
        "--------------------\n"
        f"Action: {pending_action}\n"
        f"Risk Tier: {risk['tier']}\n"
        f"Payload: {session.get('pending_payload', '(none)')}\n"
        f"Command: {session.get('pending_command', '(none)')}"
    )


def cancel_pending_action() -> str:
    clear_pending_confirmation()
    return "Pending action canceled."


def set_response_mode(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned not in {"adaptive", "concise", "detailed"}:
        return "Refused: response mode must be one of adaptive, concise, or detailed."
    update_hi_field("preferred_response_mode", cleaned)
    return f"Preferred response mode updated to {cleaned}"


def what_is_my_domain() -> str:
    hi = load_profiles().get("HI", {})
    domain = hi.get("domain", "not set")
    website = hi.get("website") or (f"https://{domain}" if domain != "not set" else "not set")
    email = hi.get("email", "not set")
    brand = hi.get("brand", "not set")
    company = hi.get("company", "not set")
    return (
        "Domain Identity\n"
        "---------------\n"
        f"Domain  : {domain}\n"
        f"Website : {website}\n"
        f"Brand   : {brand}\n"
        f"Company : {company}\n"
        f"Email   : {email}"
    )


def website_status() -> str:
    import time
    import re
    hi = load_profiles().get("HI", {})
    domain = hi.get("domain", "")
    website = hi.get("website") or (f"https://{domain}" if domain else "")
    brand = hi.get("brand", "")
    company = hi.get("company", "")
    if not website:
        return "No website configured. Set one with: set my domain <domain>"
    try:
        req = urllib.request.Request(website, headers={"User-Agent": "Jarvis/1.0"})
        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=8) as resp:
            code = resp.getcode()
            body = resp.read(4096).decode("utf-8", errors="ignore")
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        title_match = re.search(r"<title[^>]*>([^<]+)</title>", body, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "—"
        status = "Online" if 200 <= code < 400 else f"Unexpected ({code})"
        lines = [
            "Website Status",
            "--------------",
            f"URL          : {website}",
            f"Status       : {status}",
            f"HTTP         : {code}",
            f"Response     : {elapsed_ms} ms",
            f"Page title   : {title}",
        ]
        if brand:
            lines.append(f"Brand        : {brand}")
        if company:
            lines.append(f"Company      : {company}")
        return "\n".join(lines)
    except urllib.error.HTTPError as exc:
        return (
            "Website Status\n"
            "--------------\n"
            f"URL    : {website}\n"
            f"Status : HTTP Error\n"
            f"HTTP   : {exc.code}"
        )
    except urllib.error.URLError as exc:
        return (
            "Website Status\n"
            "--------------\n"
            f"URL    : {website}\n"
            f"Status : Unreachable\n"
            f"Reason : {exc.reason}"
        )
    except Exception as exc:
        return f"Website check failed: {exc}"


def hi_identity_summary() -> str:
    hi = load_profiles().get("HI", {})
    name = hi.get("full_name") or hi.get("name", "unknown")
    role = hi.get("role", "owner")
    domain = hi.get("domain", "not set")
    website = hi.get("website") or (f"https://{domain}" if domain != "not set" else "not set")
    email = hi.get("email", "not set")
    brand = hi.get("brand", "not set")
    company = hi.get("company", "not set")
    language = hi.get("language", "unknown")
    response_mode = hi.get("preferred_response_mode", "adaptive")
    return (
        "HI Identity Summary\n"
        "-------------------\n"
        f"Name          : {name}\n"
        f"Role          : {role}\n"
        f"Domain        : {domain}\n"
        f"Website       : {website}\n"
        f"Brand         : {brand}\n"
        f"Company       : {company}\n"
        f"Email         : {email}\n"
        f"Language      : {language}\n"
        f"Response mode : {response_mode}"
    )


def search_memory_entries(query: str) -> str:
    import sys
    from pathlib import Path
    _ki_dir = Path(__file__).resolve().parent.parent / "Kingofyadav"
    if str(_ki_dir) not in sys.path:
        sys.path.insert(0, str(_ki_dir))
    q = query.strip()
    if not q:
        return "Refused: empty search query."
    try:
        from memory_store import search_memories, sync_from_state
        from state_manager import load_state
        sync_from_state(load_state().get("memory", []))
        results = search_memories(q, limit=10)
    except Exception as exc:
        return f"Memory search failed: {exc}"
    if not results:
        return f"No memory entries matching '{query}'."
    lines = [f"Memory search '{query}' — {len(results)} result(s):", ""]
    for m in results:
        ts = str(m.get("created_at", ""))[:10]
        tag = f" [{m['tag']}]" if m.get("tag") else ""
        score = f" ({m['score']:.2f})" if "score" in m else ""
        text = str(m.get("text") or m.get("event") or m.get("command") or "").strip()
        entry_id = m.get("id", "")[:8]
        lines.append(f"[{ts}]{tag}{score} id:{entry_id} {text[:120]}")
    return "\n".join(lines)


def volume_up() -> str:
    return _run_desktop_action(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"], "Volume increased.")


def volume_down() -> str:
    return _run_desktop_action(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-10%"], "Volume decreased.")


def mute_volume() -> str:
    return _run_desktop_action(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], "Volume toggled.")


def lock_screen() -> str:
    return _run_desktop_action(["loginctl", "lock-session"], "Locking screen.")


def battery_status() -> str:
    try:
        result = subprocess.check_output(
            ["upower", "-i", "/org/freedesktop/UPower/devices/battery_BAT0"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        lines = [
            line.strip()
            for line in result.splitlines()
            if "percentage:" in line or "state:" in line or "time to" in line
        ]
        return "Battery Status\n--------------\n" + "\n".join(lines)
    except Exception:
        return "Battery information is not available."


def disk_status() -> str:
    result = subprocess.check_output(["df", "-h", "/"], text=True)
    return "Disk Status\n-----------\n" + result


def open_terminal() -> str:
    return _run_desktop_action(["gnome-terminal"], "Opening terminal.")


def open_chrome() -> str:
    for binary in ("google-chrome", "google-chrome-stable", "chromium-browser", "chromium"):
        if shutil.which(binary):
            return _run_desktop_action([binary], "Opening Chrome.")
    return "Chrome not found. Install google-chrome or chromium."


def open_files() -> str:
    return _run_desktop_action(["nautilus"], "Opening Files.")


def _path_allowed(token: str) -> bool:
    candidate = (BASE_DIR / token).resolve()
    try:
        candidate.relative_to(BASE_DIR)
        return True
    except ValueError:
        return False


def execute_shell_command(command: str) -> str:
    normalized = command.strip()
    if not normalized:
        return "Refused: empty command."

    try:
        tokens = shlex.split(normalized)
    except ValueError as exc:
        return f"Refused: invalid command syntax ({exc})."

    if not tokens:
        return "Refused: empty command."

    program = tokens[0]
    policy = SAFE_COMMANDS.get(program)
    if policy is None:
        return f"Refused: `{program}` is not in the safe allowlist."

    validated_tokens = [program]
    for token in tokens[1:]:
        if token.startswith("-"):
            if token not in policy["flags"]:
                return f"Refused: argument `{token}` is not allowed for `{program}`."
            validated_tokens.append(token)
            continue

        if not policy["allow_path"]:
            return f"Refused: `{program}` does not allow path arguments."
        if not _path_allowed(token):
            return f"Refused: path `{token}` is outside the Jarvis workspace."
        validated_tokens.append(token)

    completed = subprocess.run(
        validated_tokens,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return completed.stdout.strip() or completed.stderr.strip() or "Command completed with no output."


def show_commands() -> str:
    return format_help_text()


def _build_action_map(payload: str = "") -> dict[str, Callable[[], str]]:
    action_map: dict[str, Callable[[], str]] = {
        "time": get_time,
        "identity": describe_identity,
        "profile": lambda: json.dumps(load_profile(), indent=2),
        "profiles": lambda: json.dumps(load_profiles(), indent=2, ensure_ascii=False),
        "ai_intro": get_ai_intro,
        "hi_intro": get_hi_intro,
        "who_am_i": who_am_i,
        "who_are_you": who_are_you,
        "greet_user": greet_user,
        "relationship": get_relationship_report,
        "set_hi_name": lambda: set_hi_name(payload),
        "set_hi_language": lambda: set_hi_language(payload),
        "set_hi_domain": lambda: set_hi_domain(payload),
        "set_ai_name": lambda: set_ai_name(payload),
        "set_intro_mode": lambda: set_intro_mode(payload),
        "set_command_style": lambda: set_command_style(payload),
        "set_mic_device": lambda: set_mic_device(payload),
        "set_wake_phrase": lambda: set_wake_phrase(payload),
        "memory": get_memory_report,
        "preferences": get_preferences_report,
        "what_is_my_domain": what_is_my_domain,
        "website_status": website_status,
        "hi_identity_summary": hi_identity_summary,
        "what_is_my_language": what_is_my_language,
        "what_is_my_device": what_is_my_device,
        "what_was_my_last_command": what_was_my_last_command,
        "what_was_my_last_action": what_was_my_last_action,
        "show_session": show_session,
        "reset_session": reset_session_state,
        "system_summary": get_system_summary,
        "register_device": lambda: register_device(payload),
        "auto_detect_device": lambda: auto_detect_device(payload),
        "device_report": get_device_report,
        "device_inventory": get_device_inventory_report,
        "device_hardware": get_device_hardware_report,
        "device_software": get_device_software_report,
        "device_network": get_device_network_report,
        "device_environment": get_device_environment_report,
        "set_response_mode": lambda: set_response_mode(payload),
        "confirmation_status": get_confirmation_status,
        "cancel": cancel_pending_action,
        "status": get_status_report,
        "context": get_context_report,
        "ai_status": lambda: json.dumps(ai_status(), indent=2),
        "ai": lambda: ask_ai(payload),
        "plan": lambda: plan_with_ai(payload),
        "logs": lambda: read_recent_logs(20),
        "system_info": lambda: json.dumps(get_system_info(), indent=2),
        "shell": lambda: execute_shell_command(payload),
        "search_memory": lambda: search_memory_entries(payload),
        "commands": show_commands,
        "open_terminal": open_terminal,
        "open_chrome": open_chrome,
        "open_files": open_files,
        "battery_status": battery_status,
        "disk_status": disk_status,
        "lock_screen": lock_screen,
        "volume_up": volume_up,
        "volume_down": volume_down,
        "mute_volume": mute_volume,
    }
    for plugin_action in get_plugin_action_names():
        action_map[plugin_action] = lambda action=plugin_action: execute_plugin_action(action, payload) or f"Unknown plugin action: {action}"
    return action_map


def get_action_names() -> set[str]:
    """Return the set of all action names supported by execute_action."""
    return set(_build_action_map().keys())


def execute_action(action: str, payload: str = "") -> str:
    action_map = _build_action_map(payload)

    if action not in action_map:
        return f"Unknown action: {action}"

    result = action_map[action]()
    log_activity(action, payload or "requested")
    return result
