#!/usr/bin/env python3
"""
Notification dispatch for the automation daemon.

Channels:
  log      — append to automation.log (always available)
  bus      — post an event via the shared message bus
  webhook  — HTTP POST to an external URL

Webhook signing:
  Set AUTOMATION_WEBHOOK_SECRET to sign all outbound webhook payloads with
  HMAC-SHA256. The signature is sent as X-Jarvis-Signature: sha256=<hex>.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "shared"))

from event_journal import append_event  # noqa: E402

_LOG_PATH = _ROOT / "logs" / "automation.log"
_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(_LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_log = logging.getLogger("automation.notifier")


def notify(
    message: str,
    *,
    channel: str = "log",
    rule_id: str = "",
    extra: dict[str, Any] | None = None,
    webhook_url: str = "",
) -> None:
    """Dispatch a notification through the requested channel."""
    payload: dict[str, Any] = {
        "rule_id": rule_id,
        "message": message,
        "ts": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }

    if channel == "log" or channel not in ("bus", "webhook"):
        _log.info("[%s] %s", rule_id or "system", message)
        try:
            append_event("automation_notify", payload)
        except Exception:  # noqa: BLE001
            pass

    if channel == "bus":
        _notify_bus(message, payload)

    if channel == "webhook" and webhook_url:
        _notify_webhook(webhook_url, payload)


def _webhook_signature(data: bytes) -> str | None:
    """Return 'sha256=<hex>' if AUTOMATION_WEBHOOK_SECRET is set, else None."""
    secret = os.getenv("AUTOMATION_WEBHOOK_SECRET", "")
    if not secret:
        return None
    sig = hmac.new(secret.encode(), data, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


def _notify_bus(message: str, payload: dict[str, Any]) -> None:
    try:
        from message_bus import MessageBus  # noqa: PLC0415

        bus = MessageBus(str(_ROOT / "shared" / "bus"))
        bus.post(
            intent="automation_notify",
            payload={"message": message, **payload},
            source="automation",
        )
    except Exception as exc:  # noqa: BLE001
        _log.warning("bus notify failed: %s", exc)


def _notify_webhook(url: str, payload: dict[str, Any]) -> None:
    try:
        data = json.dumps(payload).encode()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        sig = _webhook_signature(data)
        if sig:
            headers["X-Jarvis-Signature"] = sig
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10):
            pass
    except (urllib.error.URLError, OSError) as exc:
        _log.warning("webhook notify failed (%s): %s", url, exc)
