#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_message import ValidationError, validate_message_dict

ROOT_DIR = Path(__file__).resolve().parent.parent
BUS_DIR = ROOT_DIR / "shared" / "bus"

REQUESTS_DIR = BUS_DIR / "requests"
RESPONSES_DIR = BUS_DIR / "responses"
PROCESSED_DIR = BUS_DIR / "processed"
DEADLETTER_DIR = BUS_DIR / "deadletter"

LOG_DIR = ROOT_DIR / "logs"
BUS_LOG = LOG_DIR / "bus.log"
ACTIVITY_LOG = LOG_DIR / "activity.log"

def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default

_REQUEST_TTL_SECONDS      = _env_int("JARVIS_BUS_REQUEST_TTL",      300)
_STALE_PROCESSING_SECONDS = _env_int("JARVIS_BUS_STALE_PROCESSING",  30)
_RESPONSE_TTL_SECONDS     = _env_int("JARVIS_BUS_RESPONSE_TTL",     300)
_DL_ALERT_INTERVAL        = _env_int("JARVIS_BUS_DL_ALERT_INTERVAL", 300)
_PROCESSED_KEEP = 500
_RESPONSE_POLL_INTERVAL = 0.1

_last_dl_alert: float = 0.0


def ensure_dirs() -> None:
    for p in [REQUESTS_DIR, RESPONSES_DIR, PROCESSED_DIR, DEADLETTER_DIR, LOG_DIR]:
        p.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_log(message: str) -> None:
    ensure_dirs()
    record = {"ts": utc_now_iso(), "msg": message}
    with BUS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def new_request_id(prefix: str = "msg") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass
class MessageBus:
    actor: str

    def _write_json_atomic(self, path: Path, data: dict[str, Any]) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(path)

    def _reap_stale_processing(self) -> None:
        cutoff = time.time() - _STALE_PROCESSING_SECONDS
        for stale in REQUESTS_DIR.glob("*.processing"):
            try:
                if stale.stat().st_mtime < cutoff:
                    reclaimed = stale.with_suffix(".json")
                    stale.replace(reclaimed)
                    write_log(f"REAP_STALE file={stale.name}")
            except Exception:
                pass

    def reap_stale_responses(self) -> int:
        """Archive abandoned response files so responses/ only contains live replies."""
        ensure_dirs()
        cutoff = time.time() - _RESPONSE_TTL_SECONDS
        archived = 0
        for stale in RESPONSES_DIR.glob("*.json"):
            try:
                if stale.stat().st_mtime >= cutoff:
                    continue
                claimed = self._claim_path(stale)
                if claimed is None:
                    continue
                self.mark_processed(claimed)
                archived += 1
            except Exception as exc:
                write_log(f"RESPONSE_REAP_ERROR file={stale.name} error={exc}")
        if archived:
            write_log(f"REAP_STALE_RESPONSES archived={archived}")
        return archived

    def _claim_path(self, path: Path) -> Path | None:
        claimed = path.with_suffix(".processing")
        try:
            path.replace(claimed)
            return claimed
        except FileNotFoundError:
            return None

    def _is_request_expired(self, msg: dict[str, Any]) -> bool:
        ts_str = msg.get("timestamp", "")
        if not ts_str:
            return True
        try:
            sent_at = datetime.fromisoformat(ts_str)
            age = (datetime.now(timezone.utc) - sent_at).total_seconds()
            return age > _REQUEST_TTL_SECONDS
        except Exception:
            return True

    def rotate_processed(self) -> None:
        try:
            files = sorted(
                PROCESSED_DIR.iterdir(),
                key=lambda p: p.stat().st_mtime,
            )
            excess = files[:-_PROCESSED_KEEP] if len(files) > _PROCESSED_KEEP else []
            for f in excess:
                f.unlink(missing_ok=True)
            if excess:
                write_log(f"ROTATE_PROCESSED removed={len(excess)}")
        except Exception:
            pass

    def alert_deadletter(self) -> int:
        global _last_dl_alert
        try:
            items = [p for p in DEADLETTER_DIR.iterdir() if not p.name.startswith(".")]
            if not items:
                return 0
            now = time.time()
            if now - _last_dl_alert < _DL_ALERT_INTERVAL:
                return len(items)
            _last_dl_alert = now
            names = [f.name for f in items[:5]]
            write_log(f"DEADLETTER_ALERT count={len(items)} files={names}")
            record = {
                "ts": utc_now_iso(),
                "source": "message_bus",
                "event": "deadletter_alert",
                "count": len(items),
                "files": names,
            }
            try:
                ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
                with ACTIVITY_LOG.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            except Exception:
                pass
            print(
                f"[MessageBus] WARNING: {len(items)} message(s) in dead-letter queue — {DEADLETTER_DIR}",
                flush=True,
            )
            return len(items)
        except Exception:
            return 0

    def build_message(
        self,
        intent: str,
        target: str,
        payload: dict[str, Any],
        priority: str = "normal",
        request_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        msg = {
            "version": "1.0",
            "intent": intent,
            "source": self.actor,
            "target": target,
            "payload": payload,
            "timestamp": utc_now_iso(),
            "request_id": request_id or new_request_id(self.actor.lower()),
            "priority": priority,
            "meta": meta or {},
        }
        return validate_message_dict(msg)

    def send_request(
        self,
        intent: str,
        target: str,
        payload: dict[str, Any],
        priority: str = "normal",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ensure_dirs()
        msg = self.build_message(intent, target, payload, priority=priority, meta=meta)
        name = f"{msg['timestamp'].replace(':', '-')}__{msg['request_id']}.json"
        path = REQUESTS_DIR / name
        self._write_json_atomic(path, msg)
        write_log(f"REQUEST source={msg['source']} target={msg['target']} intent={msg['intent']} request_id={msg['request_id']}")
        return msg

    def send_response(
        self,
        request_message: dict[str, Any],
        payload: dict[str, Any],
        status: str = "ok",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ensure_dirs()
        msg = {
            "version": "1.0",
            "intent": f"{request_message['intent']}_response",
            "source": self.actor,
            "target": request_message["source"],
            "payload": payload,
            "timestamp": utc_now_iso(),
            "request_id": request_message["request_id"],
            "priority": request_message.get("priority", "normal"),
            "meta": {
                "status": status,
                "reply_to_intent": request_message["intent"],
                **(meta or {})
            },
        }
        msg = validate_message_dict(msg)
        path = RESPONSES_DIR / f"{msg['request_id']}.json"
        self._write_json_atomic(path, msg)
        write_log(f"RESPONSE source={msg['source']} target={msg['target']} intent={msg['intent']} request_id={msg['request_id']}")
        return msg

    def read_message(self, path: Path) -> dict[str, Any]:
        msg = json.loads(path.read_text(encoding="utf-8"))
        return validate_message_dict(msg)

    def list_requests_for_me(self) -> list[Path]:
        ensure_dirs()
        self._reap_stale_processing()
        self.reap_stale_responses()
        out = []
        for path in sorted(REQUESTS_DIR.glob("*.json")):
            try:
                msg = self.read_message(path)
                if msg.get("target") != self.actor:
                    continue
                if self._is_request_expired(msg):
                    write_log(f"TTL_EXPIRED file={path.name} intent={msg.get('intent')}")
                    self.move_to_deadletter(path, "TTL expired")
                    continue
                claimed = self._claim_path(path)
                if claimed is not None:
                    out.append(claimed)
            except Exception as exc:
                if isinstance(exc, FileNotFoundError):
                    continue
                write_log(f"REQUEST_ERROR file={path.name} error={exc}")
                self.move_to_deadletter(path, str(exc))
        return out

    def list_responses_for_me(self) -> list[Path]:
        ensure_dirs()
        out = []
        for path in sorted(RESPONSES_DIR.glob("*.json")):
            try:
                msg = self.read_message(path)
                if msg.get("target") == self.actor:
                    out.append(path)
            except Exception as exc:
                write_log(f"RESPONSE_ERROR file={path.name} error={exc}")
                self.move_to_deadletter(path, str(exc))
        return out

    def mark_processed(self, path: Path) -> Path:
        ensure_dirs()
        target = PROCESSED_DIR / path.name
        shutil.move(str(path), str(target))
        write_log(f"PROCESSED file={path.name}")
        self.rotate_processed()
        return target

    def move_to_deadletter(self, path: Path, reason: str) -> Path:
        ensure_dirs()
        target = DEADLETTER_DIR / path.name
        if path.exists():
            shutil.move(str(path), str(target))
        write_log(f"DEADLETTER file={path.name} reason={reason}")
        return target

    def wait_for_response(
        self,
        request_id: str,
        timeout: int = 15,
        poll_interval: float = _RESPONSE_POLL_INTERVAL,
    ) -> dict[str, Any] | None:
        deadline = time.time() + timeout
        response_path = RESPONSES_DIR / f"{request_id}.json"
        while time.time() < deadline:
            claimed = self._claim_path(response_path)
            if claimed is not None:
                try:
                    msg = self.read_message(claimed)
                    if msg.get("target") != self.actor:
                        self.move_to_deadletter(claimed, f"Unexpected response target: {msg.get('target')}")
                        return None
                    self.mark_processed(claimed)
                    return msg
                except Exception as exc:
                    self.move_to_deadletter(claimed, str(exc))
                    return None
            time.sleep(poll_interval)
        write_log(f"TIMEOUT actor={self.actor} request_id={request_id} timeout={timeout}")
        return None
