#!/usr/bin/env python3
"""Jarvis Control Plane API — FastAPI + uvicorn."""
from __future__ import annotations

import asyncio
import copy
import json
import os
import socket
import platform
import sys
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, AsyncGenerator
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

_WEB_DIR = Path(__file__).resolve().parent
if str(_WEB_DIR) not in sys.path:
    sys.path.insert(0, str(_WEB_DIR))

import public_chat as _public_chat
_ORIGINAL_PUBLIC_CHAT_CONFIG = _public_chat._public_chat_config

ROOT_DIR        = Path(__file__).resolve().parent.parent
STATE_PATH      = ROOT_DIR / "Kingofyadav" / "state.json"
PROFILES_PATH   = ROOT_DIR / "Jarvis" / "profiles.json"
KING_PID        = ROOT_DIR / "logs" / "kingofyadav.pid"
HISTORY_PATH    = ROOT_DIR / "logs" / "api_history.jsonl"
PUBLIC_CHAT_LOG    = ROOT_DIR / "logs" / "public_chat.jsonl"
PUBLIC_CHAT_CONFIG = ROOT_DIR / "logs" / "public_chat_config.json"
API_TOKENS_PATH    = ROOT_DIR / "logs" / "api_tokens.json"
LIVE_CLASS_STATE_PATH = ROOT_DIR / "logs" / "live_class_state.json"
PUBLIC_SITE_ROOT   = Path(os.getenv("JARVIS_PUBLIC_SITE_ROOT", str(ROOT_DIR.parent / "HI")))

_API_KEY        = os.getenv("JARVIS_API_KEY", "").strip()
_ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "https://kingofyadav.in")
_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        ",".join(
            [
                _ALLOWED_ORIGIN,
                "http://localhost:8081",
                "http://127.0.0.1:8081",
                "http://localhost:8080",
                "http://127.0.0.1:8080",
            ]
        ),
    ).split(",")
    if origin.strip()
]
_TRUSTED_PROXY_ADDRS = {
    item.strip()
    for item in os.getenv("JARVIS_TRUSTED_PROXY_ADDRS", "127.0.0.1,::1").split(",")
    if item.strip()
}

_KNOWLEDGE_PAGES = _public_chat._KNOWLEDGE_PAGES
_SITE_KNOWLEDGE_CACHE = _public_chat._SITE_KNOWLEDGE_CACHE

_env_int = _public_chat._env_int

_LOCALHOST_ADDRS = {"127.0.0.1", "::1", "localhost"}
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = _env_int("API_PORT", 5050, minimum=1, maximum=65535)
_MAX_BODY_BYTES = 65_536
_RATE_LIMIT_RPM = 60
_HISTORY_KEEP   = 50
_SSE_MAX_SECS   = 1800
_PUBLIC_INTAKE_RPM = _env_int("JARVIS_PUBLIC_INTAKE_RPM", 12, minimum=1, maximum=120)
_LOCAL_ADMIN_SYNC_RPM = _env_int("JARVIS_LOCAL_ADMIN_SYNC_RPM", 30, minimum=1, maximum=240)

_CMD_HISTORY: deque[dict] = deque(maxlen=_HISTORY_KEEP)
_RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)
_TOKEN_CACHE: tuple[float, list[dict[str, Any]]] = (0.0, [])
_LIVE_CLASS_LOCK = Lock()
_LIVE_CLASS_STATE: dict[str, Any] | None = None
_LIVE_CLASS_TOKEN = os.getenv("LIVE_CLASS_TOKEN", "").strip()
_LIVE_CLASS_SUBSCRIBERS: set[asyncio.Queue] = set()


# ── Jarvis router import (graceful fallback) ───────────────────────────────────
_JARVIS_DIR = ROOT_DIR / "Jarvis"
_SHARED_DIR = ROOT_DIR / "shared"
for _p in (str(_SHARED_DIR), str(_JARVIS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from file_lock import file_lock      # noqa: E402
from listener_status import pid_file_is_recent, resolve_listener_pid  # noqa: E402
from event_journal import (          # noqa: E402
    event_sources,
    event_types,
    query_events,
    recent_events,
)
from public_intake import (          # noqa: E402
    get_public_intake_summary,
    submit_public_enquiry,
    submit_public_signup,
)
from local_admin_registry import (   # noqa: E402
    get_local_admin_users,
    record_local_admin_user,
)

_JARVIS_OK = False
_JARVIS_ERR = ""
try:
    from intent_parser import interpret_intent      # noqa: E402
    from router import process_intent               # noqa: E402
    from ai_connector import (                      # noqa: E402
        _call_model as call_public_model,
        ai_status,
        get_active_model,
        get_active_provider,
        provider_status,
    )
    from device_registry import verify_current_device  # noqa: E402
    _JARVIS_OK = True
except Exception as _e:
    _JARVIS_ERR = str(_e)


# ── public_chat module sync ────────────────────────────────────────────────────

def _sync_public_chat_module() -> None:
    _public_chat.PUBLIC_CHAT_LOG    = PUBLIC_CHAT_LOG
    _public_chat.PUBLIC_CHAT_CONFIG = PUBLIC_CHAT_CONFIG
    _public_chat.PUBLIC_SITE_ROOT   = PUBLIC_SITE_ROOT
    _public_chat.STATE_PATH         = STATE_PATH
    _public_chat._JARVIS_OK         = _JARVIS_OK
    _public_chat._JARVIS_ERR        = _JARVIS_ERR
    if _JARVIS_OK:
        _public_chat.call_public_model  = call_public_model
        _public_chat.ai_status          = ai_status
        _public_chat.get_active_model   = get_active_model
        _public_chat.get_active_provider = get_active_provider
        _public_chat.provider_status    = provider_status
    _public_chat._KNOWLEDGE_PAGES       = _KNOWLEDGE_PAGES
    _public_chat._SITE_KNOWLEDGE_CACHE  = _SITE_KNOWLEDGE_CACHE
    config_func = globals().get("_public_chat_config")
    _public_chat._public_chat_config = (
        config_func if config_func is not _DEFAULT_PUBLIC_CHAT_CONFIG
        else _ORIGINAL_PUBLIC_CHAT_CONFIG
    )


# ── helpers ────────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request_id() -> str:
    return uuid.uuid4().hex[:12]


def _origin_allowed(origin: str, referer: str) -> bool:
    check = (origin or referer).strip()
    if not check:
        return True
    try:
        parsed = urlparse(check)
    except Exception:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False

    allowed_origins = set(_ALLOWED_ORIGINS)
    allowed_origins.add(_ALLOWED_ORIGIN)
    normalized = f"{parsed.scheme}://{parsed.netloc}"
    if normalized in allowed_origins:
        return True
    return (parsed.hostname or "").lower() in _LOCALHOST_ADDRS


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _public_chat_config() -> dict[str, Any]:
    _sync_public_chat_module()
    return _public_chat._public_chat_config()


def get_public_chat_config() -> dict[str, Any]:
    _sync_public_chat_module()
    return _public_chat.get_public_chat_config()


def get_public_chat_history(limit: int = 50) -> dict[str, Any]:
    _sync_public_chat_module()
    return _public_chat.get_public_chat_history(limit)


class LocalAdminSyncBody(BaseModel):
    username: str
    password_hash: str = Field(alias="passwordHash")
    password_salt: str = Field(default="", alias="passwordSalt")
    hash_version: str = Field(default="legacy", alias="hashVersion")
    action: str = "signup"
    source: str = "web"
    page: str = ""
    device_id: str = Field(default="", alias="deviceId")
    user_agent: str = Field(default="", alias="userAgent")


_DEFAULT_PUBLIC_CHAT_CONFIG = _public_chat_config


def _listener_alive() -> bool:
    pid = resolve_listener_pid(KING_PID)
    if pid is not None:
        return True
    return pid_file_is_recent(KING_PID)


def _connectivity() -> str:
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=2):
            pass
        return "Connected"
    except Exception:
        return "Offline"


def _rate_check(ip: str, *, limit_rpm: int = _RATE_LIMIT_RPM) -> bool:
    now = time.time()
    window_start = now - 60.0
    bucket = [t for t in _RATE_BUCKETS[ip] if t > window_start]
    if len(bucket) >= limit_rpm:
        _RATE_BUCKETS[ip] = bucket
        return False
    bucket.append(now)
    _RATE_BUCKETS[ip] = bucket
    if len(_RATE_BUCKETS) > 10_000:
        dead = [k for k, v in _RATE_BUCKETS.items() if not v]
        for k in dead:
            del _RATE_BUCKETS[k]
    return True


# ── persistent history ─────────────────────────────────────────────────────────

def _load_history() -> None:
    try:
        if not HISTORY_PATH.exists():
            return
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines()[-_HISTORY_KEEP:]:
            try:
                _CMD_HISTORY.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass


def _save_history_entry(record: dict[str, Any]) -> None:
    try:
        with file_lock(HISTORY_PATH.with_suffix(HISTORY_PATH.suffix + ".lock")):
            HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with HISTORY_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            lines = HISTORY_PATH.read_text(encoding="utf-8").splitlines()
            if len(lines) > _HISTORY_KEEP:
                HISTORY_PATH.write_text(
                    "\n".join(lines[-_HISTORY_KEEP:]) + "\n", encoding="utf-8"
                )
    except Exception:
        pass


# ── data builders ──────────────────────────────────────────────────────────────

_DOCTOR_REPORT = ROOT_DIR / "logs" / "doctor" / "latest.json"


def get_health() -> dict:
    return {
        "ok": True,
        "ts": _utc_now(),
        "listener_online": _listener_alive(),
        "jarvis_ok": _JARVIS_OK,
    }


def get_health_detail() -> dict:
    report = _read_json(_DOCTOR_REPORT)
    if not report:
        return {
            "ok": True,
            "available": False,
            "message": "No doctor report found — run: bash scripts/doctor.sh",
        }
    summary = report.get("summary", {})
    checks: list[dict] = report.get("checks", [])
    critical = [c for c in checks if c.get("status") == "FAIL"]
    warnings = [c for c in checks if c.get("status") == "WARN"]
    return {
        "ok": True,
        "available": True,
        "timestamp_utc": report.get("timestamp_utc", ""),
        "summary": summary,
        "critical": critical,
        "warnings": warnings[:20],
        "warning_count": len(warnings),
        "ts": _utc_now(),
    }


def get_status() -> dict:
    state    = _read_json(STATE_PATH)
    profiles = _read_json(PROFILES_PATH)
    session  = profiles.get("session", {})
    try:
        device = verify_current_device()
    except Exception:
        device = {}
    return {
        "hostname":           socket.gethostname(),
        "os":                 platform.system() + " " + platform.release(),
        "time":               datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "connectivity":       _connectivity(),
        "listener_online":    _listener_alive(),
        "jarvis_online":      _JARVIS_OK,
        "current_focus":      state.get("workflow", {}).get("current_focus") or "none",
        "memory_count":       len(state.get("memory", [])),
        "last_command":       session.get("last_command", "none"),
        "last_action":        session.get("last_action", "none"),
        "last_risk_tier":     session.get("last_risk_tier", "none"),
        "device_registered":  bool(device.get("registered")),
        "device_trusted":     bool(device.get("trusted")),
        "device_fingerprint": device.get("current_fingerprint", ""),
        "device_trust_match": device.get("trust_match", "none"),
    }


def get_state() -> dict:
    state    = _read_json(STATE_PATH)
    profiles = _read_json(PROFILES_PATH)
    ai       = profiles.get("AI", {})
    hi_prof  = state.get("profile", {})
    memory   = state.get("memory", [])
    try:
        device = verify_current_device()
    except Exception:
        device = {}
    return {
        "hi": {
            "display_name": hi_prof.get("display_name", ""),
            "name":         hi_prof.get("name", ""),
            "domain":       hi_prof.get("domain", ""),
            "website":      hi_prof.get("website", ""),
            "email":        hi_prof.get("email", ""),
            "brand":        hi_prof.get("brand", ""),
            "company":      hi_prof.get("company", ""),
            "language":     hi_prof.get("language", ""),
            "role":         profiles.get("HI", {}).get("role", "owner"),
        },
        "ai": {
            "name":         ai.get("name", "Jarvis"),
            "type":         ai.get("type", ""),
            "role":         ai.get("role", ""),
            "mode":         ai.get("mode", "assistant"),
            "capabilities": ai.get("capabilities", []),
        },
        "preferences":  state.get("preferences", {}),
        "workflow":     state.get("workflow", {}),
        "memory":       memory[-5:],
        "memory_count": len(memory),
        "device": {
            "registered":    bool(device.get("registered")),
            "trusted":       bool(device.get("trusted")),
            "label":         device.get("label", ""),
            "registered_at": device.get("registered_at", ""),
            "fingerprint":   device.get("current_fingerprint", ""),
            "trust_match":   device.get("trust_match", "none"),
        },
    }


def get_public_state() -> dict:
    state = _read_json(STATE_PATH)
    profile = state.get("profile", {})
    workflow = state.get("workflow", {})
    memory = state.get("memory", [])
    chat_cfg = get_public_chat_config()
    knowledge = get_knowledge_status()
    intake = get_public_intake_summary(limit=100)
    public_memories = [
        {
            "type": item.get("type", "note"),
            "text": item.get("text", "") or item.get("event", ""),
            "tag": item.get("tag", ""),
            "importance": item.get("importance", 3),
            "created_at": item.get("created_at", ""),
        }
        for item in memory
        if isinstance(item, dict) and item.get("visibility") == "public"
    ][-12:]
    open_tasks = [
        {
            "title": task.get("title", ""),
            "status": task.get("status", ""),
            "due": task.get("due", ""),
        }
        for task in workflow.get("tasks", [])
        if isinstance(task, dict) and task.get("status") not in {"done", "cancelled"}
    ][:8]
    knowledge_loaded = int(knowledge.get("loaded_pages", 0))
    knowledge_total = len(knowledge.get("pages", []))
    chat_enabled = bool(chat_cfg.get("enabled"))
    public_memory_count = len(public_memories)
    intake_count = int(intake.get("count", 0))
    enquiry_count = int(intake.get("enquiry_count", 0))
    signup_count = int(intake.get("signup_count", 0))
    provider = chat_cfg.get("active_provider") or chat_cfg.get("provider") or ""
    model = chat_cfg.get("active_model") or chat_cfg.get("model") or ""
    model_bits = " / ".join(bit for bit in (provider, model) if bit)
    status_bits = [
        f"Public chat {'on' if chat_enabled else 'off'}",
    ]
    if model_bits:
        status_bits.append(model_bits)
    status_bits.extend([
        f"Knowledge {knowledge_loaded}/{knowledge_total} pages",
        f"{public_memory_count} public memories",
        f"{intake_count} public requests",
    ])
    return {
        "profile": {
            "display_name": profile.get("display_name", ""),
            "public_name": profile.get("public_name", profile.get("name", "")),
            "domain": profile.get("domain", ""),
            "website": profile.get("website", "https://kingofyadav.in"),
            "brand": profile.get("brand", ""),
            "company": profile.get("company", ""),
            "language": profile.get("language", ""),
        },
        "workflow": {
            "current_focus": workflow.get("current_focus", ""),
            "status": workflow.get("status", ""),
            "open_tasks": open_tasks,
        },
        "web": {
            "public_chat_enabled": chat_enabled,
            "fallback_enabled": bool(chat_cfg.get("fallback")),
            "rate_limit_rpm": chat_cfg.get("rpm", 12),
            "provider": provider,
            "model": model,
            "knowledge_loaded": knowledge_loaded,
            "knowledge_total": knowledge_total,
            "knowledge_chars": knowledge.get("total_chars", 0),
            "intake_count": intake_count,
            "enquiry_count": enquiry_count,
            "signup_count": signup_count,
            "status_line": " · ".join(status_bits),
        },
        "public_memories": public_memories,
        "public_memory_count": public_memory_count,
        "ts": _utc_now(),
    }


def get_session() -> dict:
    return _read_json(PROFILES_PATH).get("session", {})


def get_live() -> dict:
    return {"status": get_status(), "state": get_state()}


def get_history() -> dict:
    return {"history": list(_CMD_HISTORY)}


def _live_class_now_ms() -> int:
    return int(time.time() * 1000)


def _live_class_default_state() -> dict[str, Any]:
    now = _live_class_now_ms()
    return {
        "revision": 1,
        "theme": "dark",
        "title": "Live Future Class",
        "subtitle": "How computers, AI, and human intelligence can help people.",
        "status": "Waiting for teacher",
        "teacher": "Amit Ku Yadav",
        "room": "Future Computer Class",
        "focusId": "welcome",
        "viewers": {},
        "blocks": [
            {
                "id": "welcome",
                "type": "text",
                "text": "Welcome. This board updates live from the teacher terminal.",
                "createdAt": now,
            }
        ],
        "updatedAt": now,
    }


def _live_class_sanitize_text(value: Any, limit: int) -> str:
    return str(value or "").replace("\r", "").strip()[:limit]


def _live_class_next_id() -> str:
    return uuid.uuid4().hex[:14]


def _live_class_mask_ip(ip: str) -> str:
    if not ip or ip == "unknown":
        return "unknown"
    if ":" in ip:
        return ":".join(ip.split(":")[:3]) + ":..."
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.x"
    return ip[:8] + "..."


def _live_class_cleanup_viewers(state: dict[str, Any]) -> None:
    now = _live_class_now_ms()
    viewers = state.get("viewers") or {}
    if not isinstance(viewers, dict):
        viewers = {}
    expired = [
        viewer_id
        for viewer_id, viewer in viewers.items()
        if now - int(viewer.get("lastSeen", 0) or 0) > 70_000
    ]
    for viewer_id in expired:
        viewers.pop(viewer_id, None)
    state["viewers"] = viewers


def _live_class_public_state(state: dict[str, Any]) -> dict[str, Any]:
    _live_class_cleanup_viewers(state)
    viewers = sorted(
        (
            {
                "id": viewer.get("id", ""),
                "name": viewer.get("name", "Guest Learner"),
                "device": viewer.get("device", "Browser"),
                "ip": viewer.get("ip", "IP hidden"),
                "joinedAt": viewer.get("joinedAt", 0),
                "lastSeen": viewer.get("lastSeen", 0),
            }
            for viewer in (state.get("viewers") or {}).values()
            if isinstance(viewer, dict)
        ),
        key=lambda item: item.get("lastSeen", 0),
        reverse=True,
    )[:80]
    public_state = copy.deepcopy(state)
    public_state["viewers"] = viewers
    return public_state


def _live_class_load_state() -> dict[str, Any]:
    global _LIVE_CLASS_STATE
    if _LIVE_CLASS_STATE is not None:
        return _LIVE_CLASS_STATE
    state = _read_json(LIVE_CLASS_STATE_PATH)
    if not isinstance(state, dict) or not state:
        state = _live_class_default_state()
    else:
        fresh = _live_class_default_state()
        for key in ("theme", "title", "subtitle", "status", "teacher", "room", "focusId"):
            if isinstance(state.get(key), str) and state.get(key):
                fresh[key] = _live_class_sanitize_text(state.get(key), 5000 if key in {"title", "subtitle", "status", "teacher", "room"} else 120)
        try:
            fresh["revision"] = max(1, int(state.get("revision", 1)))
        except (TypeError, ValueError):
            fresh["revision"] = 1
        try:
            fresh["updatedAt"] = int(state.get("updatedAt", fresh["updatedAt"]))
        except (TypeError, ValueError):
            pass
        blocks = state.get("blocks")
        if isinstance(blocks, list):
            fresh["blocks"] = [
                block
                for block in blocks
                if isinstance(block, dict) and block.get("type")
            ][-80:]
        viewers = state.get("viewers")
        fresh["viewers"] = viewers if isinstance(viewers, dict) else {}
        state = fresh
    _LIVE_CLASS_STATE = state
    _live_class_cleanup_viewers(_LIVE_CLASS_STATE)
    return _LIVE_CLASS_STATE


def _live_class_save_state(state: dict[str, Any]) -> None:
    try:
        with file_lock(LIVE_CLASS_STATE_PATH.with_suffix(LIVE_CLASS_STATE_PATH.suffix + ".lock")):
            LIVE_CLASS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            LIVE_CLASS_STATE_PATH.write_text(
                json.dumps(state, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
    except Exception:
        pass


def _live_class_broadcast(state: dict[str, Any]) -> None:
    """Push updated state to all WebSocket subscribers (fire-and-forget)."""
    payload = json.dumps(_live_class_public_state(state), ensure_ascii=False, default=str)
    dead: list[asyncio.Queue] = []
    for q in _LIVE_CLASS_SUBSCRIBERS:
        try:
            q.put_nowait(payload)
        except Exception:
            dead.append(q)
    for q in dead:
        _LIVE_CLASS_SUBSCRIBERS.discard(q)


def _live_class_token_from_request(request: Request, body: dict[str, Any]) -> str:
    auth = str(request.headers.get("authorization", ""))
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return str(request.headers.get("x-live-class-token", "") or body.get("token", "")).strip()


def _live_class_apply_action(state: dict[str, Any], body: dict[str, Any], request: Request) -> dict[str, Any]:
    action = _live_class_sanitize_text(body.get("action", ""), 40).lower()
    value = _live_class_sanitize_text(body.get("value", body.get("text", "")), 12_000)

    if action == "state":
        return state

    if action == "title":
        state["title"] = value or state.get("title", "Live Future Class")
        if body.get("subtitle") is not None:
            state["subtitle"] = _live_class_sanitize_text(body.get("subtitle"), 500)
    elif action == "subtitle":
        state["subtitle"] = value
    elif action == "teacher":
        state["teacher"] = value or state.get("teacher", "Teacher")
    elif action == "room":
        state["room"] = value or state.get("room", "Future Class")
    elif action == "status":
        state["status"] = value or "Live"
    elif action == "theme":
        state["theme"] = "light" if value == "light" else "dark"
    elif action in {"write", "text", "w"}:
        _live_class_add_block(state, "text", value)
    elif action in {"heading", "h"}:
        _live_class_add_block(state, "heading", value)
    elif action == "code":
        _live_class_add_block(state, "code", value, {"language": _live_class_sanitize_text(body.get("language", "text"), 40)})
    elif action == "list":
        _live_class_add_block(state, "list", value)
    elif action == "quote":
        _live_class_add_block(state, "quote", value)
    elif action == "homework":
        _live_class_add_block(state, "homework", value)
    elif action == "link":
        _live_class_add_block(
            state,
            "link",
            _live_class_sanitize_text(body.get("label", value), 500),
            {"url": _live_class_sanitize_text(body.get("url", value), 2000)},
        )
    elif action == "image":
        _live_class_add_block(
            state,
            "image",
            _live_class_sanitize_text(body.get("caption", ""), 500),
            {"url": _live_class_sanitize_text(body.get("url", value), 2000)},
        )
    elif action == "divider":
        _live_class_add_block(state, "divider", "")
    elif action == "focus":
        try:
            index = int(value)
        except (TypeError, ValueError):
            index = 0
        target = state["blocks"][index - 1] if 1 <= index <= len(state["blocks"]) else next(
            (block for block in state["blocks"] if block.get("id") == value),
            None,
        )
        if target:
            state["focusId"] = target.get("id", state.get("focusId", ""))
    elif action == "undo":
        if state["blocks"]:
            state["blocks"].pop()
        state["focusId"] = state["blocks"][-1]["id"] if state["blocks"] else ""
    elif action == "clear":
        state["blocks"] = []
        state["focusId"] = ""
    elif action == "reset":
        state = _live_class_default_state()
        state["updatedAt"] = _live_class_now_ms()
        return state
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

    state["revision"] = int(state.get("revision", 1)) + 1
    state["updatedAt"] = _live_class_now_ms()
    if action != "status":
        state["status"] = "Live now"
    return state


def _live_class_add_block(state: dict[str, Any], block_type: str, text: str, extra: dict[str, Any] | None = None) -> None:
    block = {
        "id": _live_class_next_id(),
        "type": block_type,
        "text": _live_class_sanitize_text(text, 12_000 if block_type == "code" else 5_000),
        "createdAt": _live_class_now_ms(),
    }
    if extra:
        block.update(extra)
    if not block["text"] and block_type != "divider":
        return
    state["blocks"].append(block)
    state["focusId"] = block["id"]
    if len(state["blocks"]) > 80:
        state["blocks"] = state["blocks"][-80:]


def _live_class_join_viewer(state: dict[str, Any], body: dict[str, Any], request: Request) -> dict[str, Any]:
    now = _live_class_now_ms()
    device_id = _live_class_sanitize_text(body.get("deviceId", _live_class_next_id()), 120)
    device_id = "".join(ch for ch in device_id if ch.isalnum() or ch in "_.:-")[:120] or _live_class_next_id()
    name = _live_class_sanitize_text(body.get("name", "Guest Learner"), 80) or "Guest Learner"
    device = _live_class_sanitize_text(body.get("device", "Browser"), 120)
    ip = _client_ip(request)

    viewers = state.setdefault("viewers", {})
    if not isinstance(viewers, dict):
        viewers = {}
        state["viewers"] = viewers
    viewers[device_id] = {
        "id": device_id,
        "name": name,
        "device": device,
        "ip": _live_class_mask_ip(ip),
        "joinedAt": viewers.get(device_id, {}).get("joinedAt", now),
        "lastSeen": now,
    }
    state["updatedAt"] = now
    return state


def get_live_class_state() -> dict[str, Any]:
    with _LIVE_CLASS_LOCK:
        state = _live_class_load_state()
        _live_class_cleanup_viewers(state)
        return _live_class_public_state(state)


def update_live_class_state(body: dict[str, Any], request: Request) -> dict[str, Any]:
    with _LIVE_CLASS_LOCK:
        state = _live_class_load_state()
        action = _live_class_sanitize_text(body.get("action", ""), 40).lower()
        if action == "state":
            _live_class_cleanup_viewers(state)
            return _live_class_public_state(state)
        if action == "join":
            updated = _live_class_join_viewer(state, body, request)
            _live_class_save_state(updated)
            _live_class_broadcast(updated)
            return _live_class_public_state(updated)

        expected = _LIVE_CLASS_TOKEN or _API_KEY
        if not expected:
            raise HTTPException(status_code=503, detail="LIVE_CLASS_TOKEN is not configured on the server.")
        if _live_class_token_from_request(request, body) != expected:
            raise HTTPException(status_code=401, detail="Unauthorized live class command.")

        updated = _live_class_apply_action(state, body, request)
        _live_class_save_state(updated)
        _live_class_broadcast(updated)
        return _live_class_public_state(updated)


def _is_injection_attempt(message: str) -> bool:
    return _public_chat._is_injection_attempt(message)


def _public_site_knowledge() -> str:
    global _SITE_KNOWLEDGE_CACHE
    _sync_public_chat_module()
    knowledge = _public_chat._public_site_knowledge()
    _SITE_KNOWLEDGE_CACHE = _public_chat._SITE_KNOWLEDGE_CACHE
    return knowledge


def get_knowledge_status() -> dict[str, Any]:
    _sync_public_chat_module()
    return _public_chat.get_knowledge_status()


def run_command(command: str) -> dict:
    rid = _request_id()
    if not _JARVIS_OK:
        return {
            "ok": False,
            "request_id": rid,
            "command": command,
            "error": f"Jarvis router unavailable: {_JARVIS_ERR}",
            "ts": _utc_now(),
        }
    action, payload = interpret_intent(command)
    result = process_intent(command, action, payload)
    record = {
        "ts":         _utc_now(),
        "request_id": rid,
        "command":    command,
        "action":     action,
        "ok":         result.get("ok", False),
        "result":     result.get("result") or result.get("error", ""),
        "risk":       result.get("behavior", {}).get("risk_tier", ""),
    }
    _CMD_HISTORY.append(record)
    _save_history_entry(record)
    return {**result, "command": command, "ts": record["ts"], "request_id": rid}


def run_public_chat(
    message: str, *, client_ip: str = "", history: list[dict[str, str]] | None = None
) -> dict:
    _sync_public_chat_module()
    return _public_chat.run_public_chat(message, client_ip=client_ip, history=history)


def get_index() -> dict:
    return {
        "name": "Jarvis API",
        "version": "2.1",
        "endpoints": {
            "GET /api/health":               "liveness check (no auth required)",
            "GET /api/health/detail":        "latest doctor report: critical findings, warnings, summary",
            "GET /api/status":               "system status snapshot",
            "GET /api/state":                "full HI + AI state",
            "GET /api/public-state":         "public-safe profile, focus, tasks, and public memories",
            "GET /api/session":              "current Jarvis session",
            "GET /api/history":              "last 50 executed commands",
            "GET /api/live":                 "combined status + state",
            "GET /api/live-class":           "public live classroom state",
            "GET /api/events":               "SSE stream — live state push every 4 s",
            "GET /api/journal":              "query event journal: ?hours=24&source=Jarvis&type=action_completed&limit=100",
            "WS /api/ws/live":               "authenticated WebSocket live status + state stream",
            "WS /api/ws/public":             "public WebSocket public-state stream",
            "WS /api/ws/live-class":         "public WebSocket live class push stream",
            "GET /api/docs":                 "interactive OpenAPI documentation",
            "POST /api/command":             'execute a command: {"command": "status"}',
            "POST /api/jarvis-chat":         'public-safe website chat: {"message": "hello"}',
            "POST /api/public-enquiry":      'public enquiry form: {"name":"...","email":"...","subject":"...","message":"..."}',
            "POST /api/public-signup":       'public access request: {"name":"...","email":"...","handle":"...","reason":"..."}',
            "GET /api/public-intake":        "protected public enquiry/access request inbox",
            "POST /api/local-admin-sync":     'sync browser-local admin snapshot: {"username":"...","passwordHash":"..."}',
            "GET /api/local-admin-users":     "protected synced local admin registry",
            "GET /api/public-chat/config":   "protected public Jarvis config snapshot",
            "GET /api/public-chat/history":  "protected recent public Jarvis questions",
            "GET /api/public-chat/knowledge":"protected site knowledge source status",
        },
        "public_chat_enabled": _public_chat_config()["enabled"],
    }


# ── FastAPI app ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_history()
    if not _API_KEY:
        print(
            f"[Jarvis API] WARNING: JARVIS_API_KEY not set — "
            f"binding to {API_HOST} (localhost-only mode)."
        )
    else:
        print(f"[Jarvis API] API key configured — binding on {API_HOST}:{API_PORT}")
    if _JARVIS_OK:
        print("[Jarvis API] Jarvis router loaded — command execution enabled")
    else:
        print(f"[Jarvis API] WARNING: Jarvis router unavailable ({_JARVIS_ERR})")
    yield


app = FastAPI(
    title="Jarvis API",
    version="2.1",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Api-Key"],
    expose_headers=["Vary", "X-Request-ID"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    request_id = (request.headers.get("X-Request-ID") or "").strip() or _request_id()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    return response


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > _MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"error": f"request body too large (max {_MAX_BODY_BYTES} bytes)"},
                    headers={
                        "X-Request-ID": (request.headers.get("X-Request-ID") or "").strip() or _request_id(),
                        "X-Content-Type-Options": "nosniff",
                        "X-Frame-Options": "DENY",
                        "X-XSS-Protection": "0",
                    },
                )
        except ValueError:
            pass
    return await call_next(request)


# ── auth helpers ───────────────────────────────────────────────────────────────

def _client_ip(request: Request) -> str:
    peer_ip = request.client.host if request.client else "unknown"
    if peer_ip in _TRUSTED_PROXY_ADDRS:
        forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        if forwarded_for:
            return forwarded_for
        real_ip = request.headers.get("x-real-ip", "").strip()
        if real_ip:
            return real_ip
    return peer_ip


def _parse_ts(value: str) -> datetime | None:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _load_tokens() -> list[dict[str, Any]]:
    global _TOKEN_CACHE
    now = time.time()
    cached_at, cached = _TOKEN_CACHE
    if cached and now - cached_at < 30:
        return cached
    raw = os.getenv("JARVIS_API_TOKENS", "").strip()
    data: Any = []
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = []
    elif API_TOKENS_PATH.exists():
        data = _read_json(API_TOKENS_PATH).get("tokens", [])
    if isinstance(data, dict):
        data = data.get("tokens", [])
    tokens = [item for item in data if isinstance(item, dict) and str(item.get("token", "")).strip()]
    _TOKEN_CACHE = (now, tokens)
    return tokens


def _token_auth(raw_token: str) -> dict[str, Any] | None:
    for item in _load_tokens():
        if str(item.get("token", "")).strip() != raw_token:
            continue
        expires_at = str(item.get("expires_at", "")).strip()
        if expires_at:
            parsed = _parse_ts(expires_at)
            if parsed is None or parsed < datetime.now(timezone.utc):
                return None
        scopes = item.get("scopes", ["read"])
        if isinstance(scopes, str):
            scopes = [scopes]
        if not isinstance(scopes, list):
            scopes = ["read"]
        try:
            rpm = max(1, min(600, int(item.get("rpm", _RATE_LIMIT_RPM))))
        except (TypeError, ValueError):
            rpm = _RATE_LIMIT_RPM
        return {
            "name": str(item.get("name", "")),
            "scopes": {str(scope).strip() for scope in scopes if str(scope).strip()},
            "rpm": rpm,
        }
    return None


def _auth_context(request: Request) -> dict[str, Any]:
    ip = _client_ip(request)
    if not _API_KEY and ip in _LOCALHOST_ADDRS:
        return {"ip": ip, "scopes": {"full"}, "rpm": _RATE_LIMIT_RPM, "name": "localhost"}
    auth = request.headers.get("authorization", "")
    x_key = request.headers.get("x-api-key", "")
    bearer = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
    if _API_KEY and ((auth == f"Bearer {_API_KEY}") or (x_key == _API_KEY)):
        return {"ip": ip, "scopes": {"full"}, "rpm": _RATE_LIMIT_RPM, "name": "legacy-api-key"}
    token = bearer or x_key
    if token:
        token_ctx = _token_auth(token)
        if token_ctx:
            return {"ip": ip, **token_ctx}
    raise HTTPException(status_code=401, detail="unauthorized")


def _has_scope(ctx: dict[str, Any], required: str) -> bool:
    scopes = ctx.get("scopes", set())
    return "full" in scopes or required in scopes


def _require_scope(request: Request, scope: str) -> dict[str, Any]:
    ctx = _auth_context(request)
    if not _has_scope(ctx, scope):
        raise HTTPException(status_code=403, detail=f"missing scope: {scope}")
    return ctx


def _require_auth(request: Request) -> str:
    """Return client IP if authorized, raise 401 otherwise."""
    return str(_auth_context(request)["ip"])


def _require_read_auth(request: Request) -> dict[str, Any]:
    return _require_scope(request, "read")


def _require_command_auth(request: Request) -> dict[str, Any]:
    return _require_scope(request, "command")


def _query_or_header_token(websocket: WebSocket) -> str:
    auth = websocket.headers.get("authorization", "")
    bearer = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
    return (
        websocket.query_params.get("token", "")
        or websocket.headers.get("x-api-key", "")
        or bearer
    ).strip()


def _websocket_auth(websocket: WebSocket, scope: str) -> dict[str, Any] | None:
    peer_ip = websocket.client.host if websocket.client else "unknown"
    if not _API_KEY and peer_ip in _LOCALHOST_ADDRS:
        return {"ip": peer_ip, "scopes": {"full"}, "rpm": _RATE_LIMIT_RPM, "name": "localhost"}
    token = _query_or_header_token(websocket)
    if _API_KEY and token == _API_KEY:
        return {"ip": peer_ip, "scopes": {"full"}, "rpm": _RATE_LIMIT_RPM, "name": "legacy-api-key"}
    token_ctx = _token_auth(token) if token else None
    if token_ctx and _has_scope(token_ctx, scope):
        return {"ip": peer_ip, **token_ctx}
    return None


# ── GET routes ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return RedirectResponse(url="/api/")


@app.get("/api/")
async def index():
    return get_index()


@app.get("/api/health")
async def health():
    return get_health()


@app.get("/api/health/detail")
async def health_detail(ctx: dict[str, Any] = Depends(_require_read_auth)):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_health_detail)


@app.get("/api/status")
async def status(ctx: dict[str, Any] = Depends(_require_read_auth)):
    return get_status()


@app.get("/api/state")
async def state(ctx: dict[str, Any] = Depends(_require_read_auth)):
    return get_state()


@app.get("/api/public-state")
async def public_state():
    return get_public_state()


@app.get("/api/session")
async def session(ctx: dict[str, Any] = Depends(_require_read_auth)):
    return get_session()


@app.get("/api/history")
async def history(ctx: dict[str, Any] = Depends(_require_read_auth)):
    return get_history()


@app.get("/api/live")
async def live(ctx: dict[str, Any] = Depends(_require_read_auth)):
    return get_live()


@app.get("/api/public-chat/config")
async def public_chat_config_route(ctx: dict[str, Any] = Depends(_require_read_auth)):
    return get_public_chat_config()


@app.get("/api/public-chat/history")
async def public_chat_history_route(ctx: dict[str, Any] = Depends(_require_read_auth)):
    return get_public_chat_history()


@app.get("/api/public-chat/knowledge")
async def knowledge_route(ctx: dict[str, Any] = Depends(_require_read_auth)):
    return get_knowledge_status()


@app.get("/api/live-class")
async def live_class_get_route():
    return get_live_class_state()


@app.post("/api/live-class")
async def live_class_post_route(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    return update_live_class_state(body, request)


@app.get("/api/events")
async def events(request: Request, ctx: dict[str, Any] = Depends(_require_read_auth)):
    loop = asyncio.get_running_loop()

    async def generate() -> AsyncGenerator[str, None]:
        last_payload = None
        deadline = time.monotonic() + _SSE_MAX_SECS
        while time.monotonic() < deadline:
            try:
                # get_live() calls _connectivity() which does a blocking socket call —
                # run it in the thread pool so we don't stall the event loop.
                current = await loop.run_in_executor(None, get_live)
                current_json = json.dumps(current, ensure_ascii=False, default=str)
                if current_json != last_payload:
                    yield f"data: {current_json}\n\n"
                    last_payload = current_json
            except Exception:
                pass
            await asyncio.sleep(4)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/api/journal")
async def journal(
    request: Request,
    hours: int = 24,
    date_from: str | None = None,
    date_to: str | None = None,
    source: str | None = None,
    type: str | None = None,
    limit: int = 100,
    ctx: dict[str, Any] = Depends(_require_read_auth),
):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    resolved_from = date_from or (
        datetime.now(timezone.utc) - timedelta(hours=max(1, hours))
    ).isoformat()
    loop = asyncio.get_running_loop()
    events = await loop.run_in_executor(
        None,
        lambda: query_events(
            date_from=resolved_from,
            date_to=date_to,
            source=source,
            event_type=type,
            limit=limit,
        ),
    )
    sources, types = await asyncio.gather(
        loop.run_in_executor(None, event_sources),
        loop.run_in_executor(None, event_types),
    )
    return {
        "ok": True,
        "count": len(events),
        "events": events,
        "sources": sources,
        "types": types,
        "query": {
            "hours": hours,
            "date_from": resolved_from,
            "date_to": date_to,
            "source": source,
            "type": type,
            "limit": limit,
        },
        "ts": _utc_now(),
    }


async def _send_live_websocket(websocket: WebSocket, builder, interval: float) -> None:
    await websocket.accept()
    last_payload = ""
    loop = asyncio.get_running_loop()
    try:
        while True:
            current = await loop.run_in_executor(None, builder)
            current_json = json.dumps(current, ensure_ascii=False, default=str)
            if current_json != last_payload:
                await websocket.send_json(current)
                last_payload = current_json
            await asyncio.sleep(interval)
    except WebSocketDisconnect:
        return


@app.websocket("/api/ws/live")
async def ws_live(websocket: WebSocket):
    if _websocket_auth(websocket, "read") is None:
        await websocket.close(code=1008)
        return
    await _send_live_websocket(websocket, get_live, 2.0)


@app.websocket("/api/ws/public")
async def ws_public(websocket: WebSocket):
    await _send_live_websocket(websocket, get_public_state, 4.0)


@app.websocket("/api/ws/live-class")
async def ws_live_class(websocket: WebSocket):
    """WebSocket that pushes live class state to all connected viewers."""
    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue(maxsize=32)
    _LIVE_CLASS_SUBSCRIBERS.add(q)
    try:
        # Send current state immediately on connect
        current = get_live_class_state()
        await websocket.send_text(json.dumps(current, ensure_ascii=False, default=str))
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=30.0)
                await websocket.send_text(payload)
            except asyncio.TimeoutError:
                # Send a keepalive ping
                await websocket.send_text(json.dumps({"ping": True}))
    except WebSocketDisconnect:
        pass
    finally:
        _LIVE_CLASS_SUBSCRIBERS.discard(q)


# ── POST routes ────────────────────────────────────────────────────────────────

class CommandBody(BaseModel):
    command: str


class ChatBody(BaseModel):
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)


class PublicEnquiryBody(BaseModel):
    name: str
    email: str
    subject: str
    message: str
    page: str = ""


class PublicSignupBody(BaseModel):
    name: str
    email: str
    handle: str = ""
    reason: str = ""
    message: str = ""
    page: str = ""


@app.post("/api/command")
async def command(body: CommandBody, ctx: dict[str, Any] = Depends(_require_command_auth)):
    ip = str(ctx["ip"])
    rpm = int(ctx.get("rpm", _RATE_LIMIT_RPM))
    if not _rate_check(ip, limit_rpm=rpm):
        raise HTTPException(status_code=429, detail=f"rate limit exceeded — {rpm} rpm")
    cmd = body.command.strip()
    if not cmd:
        raise HTTPException(status_code=400, detail="command is required")
    return run_command(cmd)


@app.post("/api/jarvis-chat")
async def jarvis_chat(body: ChatBody, request: Request):
    cfg = _public_chat_config()
    ip  = _client_ip(request)
    if not cfg["enabled"]:
        ip = _require_auth(request)
    if not _rate_check(ip, limit_rpm=cfg["rpm"]):
        raise HTTPException(status_code=429, detail=f"rate limit exceeded — {cfg['rpm']} rpm")
    msg = body.message.strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")
    result = await asyncio.to_thread(run_public_chat, msg, client_ip=ip, history=body.history)
    return JSONResponse(content=result, status_code=200 if result.get("ok") else 503)


def _public_form_guard(request: Request) -> str:
    ip = _client_ip(request)
    if not _rate_check(ip, limit_rpm=_PUBLIC_INTAKE_RPM):
        raise HTTPException(status_code=429, detail=f"rate limit exceeded — {_PUBLIC_INTAKE_RPM} rpm")
    return ip


@app.post("/api/public-enquiry")
async def public_enquiry(body: PublicEnquiryBody, request: Request):
    ip = _public_form_guard(request)
    if not body.name.strip() or not body.email.strip() or not body.subject.strip() or not body.message.strip():
        raise HTTPException(status_code=400, detail="name, email, subject, and message are required")
    record = submit_public_enquiry(
        name=body.name,
        email=body.email,
        subject=body.subject,
        message=body.message,
        client_ip=ip,
        page=body.page,
        source="web-api",
    )
    return {
        "ok": True,
        "kind": "enquiry",
        "request_id": record["request_id"],
        "ts": record["ts"],
    }


@app.post("/api/public-signup")
async def public_signup(body: PublicSignupBody, request: Request):
    ip = _public_form_guard(request)
    if not body.name.strip() or not body.email.strip():
        raise HTTPException(status_code=400, detail="name and email are required")
    record = submit_public_signup(
        name=body.name,
        email=body.email,
        handle=body.handle,
        reason=body.reason,
        message=body.message,
        client_ip=ip,
        page=body.page,
        source="web-api",
    )
    return {
        "ok": True,
        "kind": "signup",
        "request_id": record["request_id"],
        "ts": record["ts"],
    }


@app.get("/api/intake-stats")
async def intake_stats():
    """Public no-PII aggregate engagement stats for website widgets."""
    summary = get_public_intake_summary(limit=2000)
    chat_count = 0
    try:
        chat_count = len(PUBLIC_CHAT_LOG.read_text(encoding="utf-8").splitlines())
    except Exception:
        pass
    return {
        "enquiry_count": summary.get("enquiry_count", 0),
        "signup_count": summary.get("signup_count", 0),
        "total_submissions": summary.get("count", 0),
        "chat_messages": chat_count,
    }


@app.get("/api/public-intake")
async def public_intake(ctx: dict[str, Any] = Depends(_require_read_auth), limit: int = 100):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    return get_public_intake_summary(limit=limit)


@app.post("/api/local-admin-sync")
async def local_admin_sync(body: LocalAdminSyncBody, request: Request):
    ip = _client_ip(request)
    if not _rate_check(ip, limit_rpm=_LOCAL_ADMIN_SYNC_RPM):
        raise HTTPException(status_code=429, detail=f"rate limit exceeded — {_LOCAL_ADMIN_SYNC_RPM} rpm")
    origin = (request.headers.get("origin") or "").strip()
    referer = (request.headers.get("referer") or "").strip()
    if not _origin_allowed(origin, referer):
        raise HTTPException(status_code=403, detail="origin not allowed")
    username = body.username.strip().lower()
    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if not body.password_hash.strip():
        raise HTTPException(status_code=400, detail="passwordHash is required")
    record = record_local_admin_user(
        username=username,
        password_hash=body.password_hash,
        password_salt=body.password_salt,
        hash_version=body.hash_version,
        action=body.action,
        source=body.source,
        page=body.page,
        client_ip=ip,
        device_id=body.device_id,
        user_agent=body.user_agent,
    )
    return {
        "ok": True,
        "kind": record["kind"],
        "username": record["username"],
        "ts": record["ts"],
    }


@app.get("/api/local-admin-users")
async def local_admin_users(ctx: dict[str, Any] = Depends(_require_read_auth), limit: int = 500):
    if limit < 1 or limit > 1000:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 1000")
    return get_local_admin_users(limit=limit)


# ── entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    uvicorn.run(app, host=API_HOST, port=API_PORT, log_level="info")


if __name__ == "__main__":
    main()
