#!/usr/bin/env python3
"""
Jarvis bridge layer.

This is the single routing path for CLI, GUI, and voice input.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from intent_parser import interpret_intent, normalize_intent
from router import process_intent as route_intent, send_hi_request


def ask_hi_layer(text: str, args: dict | None = None) -> str:
    raw_payload = (args or {}).get("raw_payload", "")
    intent = text
    return send_hi_request(intent, raw_payload, text=text)


def process_intent(intent: str) -> dict[str, Any]:
    action, payload = interpret_intent(intent)
    return route_intent(intent, action, payload)


def _humanize_action(action: str) -> str:
    if not action:
        return "Command"
    return action.replace("_", " ").strip().capitalize()


def format_result(data: dict[str, Any], as_json: bool = False) -> str:
    if as_json:
        return json.dumps(data, indent=2, ensure_ascii=False)

    behavior = data.get("behavior", {})
    command_line = f"Command: {data.get('intent') or '(empty)'}"
    action_line = f"Action : {_humanize_action(str(data.get('action', '')))}"
    risk_line = f"Risk   : {behavior.get('risk_tier', 'unknown')}"
    mode_line = f"Mode   : {behavior.get('response_mode', 'unknown')}"

    if not data["ok"]:
        return (
            "Command failed.\n"
            f"{command_line}\n"
            f"{action_line}\n"
            f"{risk_line}\n"
            f"{mode_line}\n"
            f"Error  : {data['error']}"
        )

    return (
        "Command completed successfully.\n"
        f"{command_line}\n"
        f"{action_line}\n"
        f"{risk_line}\n"
        f"{mode_line}\n"
        f"Details: {data['payload'] or '(none)'}\n"
        f"Result : {data['result']}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Jarvis Human Interface bridge for intent routing and safe local execution."
    )
    parser.add_argument(
        "intent",
        nargs="*",
        help="Natural language request, for example: status, context, system info, profile, run ls",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON output",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        default=sys.stdout.isatty(),  # auto-enable when running in a real terminal
        help="Stream AI responses token-by-token (default: auto when in TTY)",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    intent_text = " ".join(args.intent).lower()

# Clean common voice-recognition filler words
    intent_text = intent_text.replace("are you", "")
    intent_text = intent_text.replace("can you", "")
    intent_text = intent_text.replace("could you", "")
    intent_text = intent_text.replace("please", "")
    intent_text = intent_text.replace("jarvis", "")
    intent_text = intent_text.strip()
    action, payload = interpret_intent(intent_text)

    # ── Streaming path for AI intents in CLI mode ──────────────────────────────
    if action == "ai" and isinstance(payload, str) and args.stream and not args.json:
        from ai_connector import ai_status, ask_ai_stream
        status = ai_status()
        if status["status"] == "ready":
            normalized = normalize_intent(intent_text)
            print(f"Intent : {normalized or '(empty)'}")
            print(f"Action : ai")
            print(f"Result : ", end="", flush=True)
            for chunk in ask_ai_stream(payload):
                print(chunk, end="", flush=True)
            print()
            return 0

    # ── Standard path (all other actions, or --json, or AI when streaming unavailable) ──
    data = process_intent(intent_text)
    print(format_result(data, as_json=args.json))
    return 0 if data["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
