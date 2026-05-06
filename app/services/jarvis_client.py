from __future__ import annotations

import secrets
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
JARVIS_DIR = ROOT_DIR / "Jarvis"

if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

from command_registry import REGISTRY  # noqa: E402
from intent_parser import interpret_intent  # noqa: E402

import bridge  # noqa: E402
import router  # noqa: E402


_COMMAND_LOOKUP = {cmd.action: cmd for cmd in REGISTRY}


def preview_command(command: str) -> dict[str, Any]:
    action, payload = interpret_intent(command)
    cmd = _COMMAND_LOOKUP.get(action)
    route = "hi" if action in router.HI_INTENTS else "local"
    if action in {"unknown", "error"}:
        route = "n/a"
    return {
        "command": command,
        "parsed_action": action,
        "parsed_payload": payload,
        "route": route,
        "risk_tier": getattr(cmd, "risk_tier", "unknown"),
        "category": getattr(cmd, "category", "unknown"),
        "takes_payload": bool(getattr(cmd, "takes_payload", False)),
        "description": getattr(cmd, "description", ""),
        "needs_confirmation": bool(action == "shell" or getattr(cmd, "risk_tier", "") == "high"),
    }


def run_command(command: str) -> dict[str, Any]:
    trace_id = secrets.token_hex(4)
    started = time.perf_counter()
    preview = preview_command(command)
    result = bridge.process_intent(command)
    parsed_action = result.get("action", "")
    parsed_payload = result.get("payload", "")
    route = preview["route"]
    if parsed_action in {"unknown", "error"}:
        route = "n/a"

    return {
        "trace_id": trace_id,
        "command": command,
        "parsed_action": parsed_action,
        "parsed_payload": parsed_payload,
        "route": route,
        "preview": preview,
        "data": result,
        "formatted": bridge.format_result(result, as_json=False),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
        "ok": bool(result.get("ok")),
    }
