#!/usr/bin/env python3
"""Phase 5 — Multi-Device Intelligence: sync protocol.

Jarvis devices discover each other via registered peer URLs and exchange:
  - Memories (filtered to public or explicitly shared)
  - State summaries (workflow focus, current status)
  - Session awareness (which device is currently active)

Sync is always pull-then-push. Last-write-wins by created_at timestamp.
No private memories leave the device unless explicitly marked for sharing.

Peer registry: logs/sync_peers.json
  [{"label": "laptop", "url": "http://192.168.1.10:5050", "trusted": true, ...}]

Environment:
  JARVIS_SYNC_SHARE_LEVEL = public | shared | none   (default: public)
  JARVIS_SYNC_TIMEOUT     = 10   (seconds per HTTP request)
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin

ROOT_DIR = Path(__file__).resolve().parent.parent
PEERS_PATH = ROOT_DIR / "logs" / "sync_peers.json"
SYNC_LOG = ROOT_DIR / "logs" / "sync.log"
SYNC_STATE_PATH = ROOT_DIR / "logs" / "sync_state.json"

sys.path.insert(0, str(ROOT_DIR / "shared"))
sys.path.insert(0, str(ROOT_DIR / "Kingofyadav"))

_SHARE_LEVEL = os.getenv("JARVIS_SYNC_SHARE_LEVEL", "public").strip().lower()
_SYNC_TIMEOUT = max(1, int(os.getenv("JARVIS_SYNC_TIMEOUT", "10")))
_API_KEY = os.getenv("JARVIS_API_KEY", "").strip()
_SYNC_SECRET = os.getenv("JARVIS_SYNC_SECRET", "").strip()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(message: str) -> None:
    SYNC_LOG.parent.mkdir(parents=True, exist_ok=True)
    record = {"ts": _utc_now(), "msg": message}
    with SYNC_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Peer registry ─────────────────────────────────────────────────────────────

def load_peers() -> list[dict[str, Any]]:
    try:
        return json.loads(PEERS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_peers(peers: list[dict[str, Any]]) -> None:
    PEERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PEERS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(peers, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(PEERS_PATH)


def add_peer(url: str, label: str = "", trusted: bool = True, peer_secret: str = "") -> dict[str, Any]:
    """Register or update a sync peer.

    peer_secret — shared HMAC secret for authenticating push-memories calls from this peer.
    When set, Jarvis includes X-Jarvis-Peer-Secret on outbound requests to this peer and
    validates the header on inbound push-memories requests originating from it.
    """
    url = url.strip().rstrip("/")
    if not url:
        raise ValueError("Peer URL is required")
    peers = load_peers()
    for peer in peers:
        if peer.get("url") == url:
            peer["label"] = label or peer.get("label", "")
            peer["trusted"] = trusted
            if peer_secret:
                peer["peer_secret"] = peer_secret
            peer["updated_at"] = _utc_now()
            save_peers(peers)
            return peer
    peer: dict[str, Any] = {
        "id": uuid.uuid4().hex[:12],
        "url": url,
        "label": label or url,
        "trusted": trusted,
        "added_at": _utc_now(),
        "last_sync": None,
        "last_sync_status": None,
    }
    if peer_secret:
        peer["peer_secret"] = peer_secret
    peers.append(peer)
    save_peers(peers)
    _log(f"Peer added: {label or url} → {url}")
    return peer


def remove_peer(url_or_id: str) -> bool:
    peers = load_peers()
    before = len(peers)
    peers = [p for p in peers if p.get("url") != url_or_id and p.get("id") != url_or_id]
    if len(peers) < before:
        save_peers(peers)
        _log(f"Peer removed: {url_or_id}")
        return True
    return False


def list_peers() -> list[dict[str, Any]]:
    return load_peers()


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _peer_headers(peer: dict[str, Any] | None = None) -> dict[str, str]:
    """Build auth headers for outbound requests to a peer."""
    headers: dict[str, str] = {"Accept": "application/json"}
    if _API_KEY:
        headers["X-API-Key"] = _API_KEY
    if peer:
        secret = peer.get("peer_secret", "").strip()
        if secret:
            headers["X-Jarvis-Peer-Secret"] = secret
    return headers


def _http_get(url: str, timeout: int = _SYNC_TIMEOUT, peer: dict[str, Any] | None = None) -> dict[str, Any]:
    req = Request(url, headers=_peer_headers(peer))
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}: {exc.reason}")
    except URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}")


def _http_post(url: str, data: dict[str, Any], timeout: int = _SYNC_TIMEOUT, peer: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    headers = {**_peer_headers(peer), "Content-Type": "application/json"}
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}: {exc.reason}")
    except URLError as exc:
        raise RuntimeError(f"Cannot reach {url}: {exc.reason}")


# ── Sync manifest ─────────────────────────────────────────────────────────────

def _local_manifest() -> dict[str, Any]:
    """Describe this device's sync state for a peer."""
    from device_registry import load_registered_device
    reg = load_registered_device()
    inventory = reg.get("inventory", {})
    identity = inventory.get("identity", {})

    sync_state = _load_sync_state()

    return {
        "device_id": reg.get("inventory", {}).get("fingerprint", socket.gethostname()),
        "label": reg.get("label", socket.gethostname()),
        "hostname": identity.get("hostname", socket.gethostname()),
        "api_version": "5.0",
        "share_level": _SHARE_LEVEL,
        "last_sync": sync_state.get("last_sync"),
        "memory_count": sync_state.get("memory_count", 0),
        "ts": _utc_now(),
    }


def _load_sync_state() -> dict[str, Any]:
    try:
        return json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_sync_state(state: dict[str, Any]) -> None:
    SYNC_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SYNC_STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(SYNC_STATE_PATH)


# ── Memory export for sync ────────────────────────────────────────────────────

def _get_shareable_memories(since: str | None = None) -> list[dict[str, Any]]:
    """Return memories eligible for sync based on share level."""
    try:
        from memory_store import list_memories
        if _SHARE_LEVEL == "none":
            return []
        visibility = "public" if _SHARE_LEVEL == "public" else None
        memories = list_memories(limit=500, visibility=visibility)
        if since:
            try:
                since_dt = datetime.fromisoformat(since.rstrip("Z").replace("Z", "+00:00"))
                memories = [
                    m for m in memories
                    if datetime.fromisoformat(
                        str(m.get("created_at", "")).rstrip("Z").replace("Z", "+00:00")
                    ) > since_dt
                ]
            except Exception:
                pass
        return memories
    except Exception as exc:
        _log(f"Memory export error: {exc}")
        return []


def _merge_incoming_memories(
    incoming: list[dict[str, Any]],
    source_label: str,
) -> dict[str, int]:
    """Merge memories received from a peer into local store (dedup by content)."""
    try:
        from memory_store import upsert_memory
    except Exception as exc:
        _log(f"Memory merge import error: {exc}")
        return {"imported": 0, "skipped": 0}

    imported = 0
    skipped = 0
    for mem in incoming:
        if not isinstance(mem, dict):
            skipped += 1
            continue
        # Tag the source so we know where it came from
        mem.setdefault("source", f"sync:{source_label}")
        mem.setdefault("visibility", "private")  # imported memories default private
        # Remove local-only fields that don't transfer
        mem.pop("score", None)
        mem.pop("relation", None)
        try:
            result_id = upsert_memory(mem, check_duplicate=True)
            orig_id = str(mem.get("id", ""))
            if orig_id and result_id != orig_id:
                skipped += 1
            else:
                imported += 1
        except Exception as exc:
            _log(f"Memory merge error for entry: {exc}")
            skipped += 1

    return {"imported": imported, "skipped": skipped}


# ── State summary for sync ────────────────────────────────────────────────────

def _get_state_summary() -> dict[str, Any]:
    """Return a public-safe state summary for cross-device awareness."""
    try:
        state_path = ROOT_DIR / "Kingofyadav" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        workflow = state.get("workflow", {})
        return {
            "current_focus": workflow.get("current_focus", ""),
            "active_tasks": [
                {"id": t.get("id"), "title": t.get("title"), "status": t.get("status")}
                for t in workflow.get("tasks", [])
                if t.get("status") in {"todo", "doing"}
            ],
            "device": socket.gethostname(),
            "ts": _utc_now(),
        }
    except Exception:
        return {"device": socket.gethostname(), "ts": _utc_now()}


# ── Per-peer sync ─────────────────────────────────────────────────────────────

def sync_with_peer(peer: dict[str, Any]) -> dict[str, Any]:
    """Run a full sync cycle with a single peer. Returns sync result."""
    url = peer.get("url", "").rstrip("/")
    label = peer.get("label", url)
    result: dict[str, Any] = {
        "peer_url": url,
        "peer_label": label,
        "ts": _utc_now(),
        "ok": False,
        "pulled": 0,
        "pushed": 0,
        "error": None,
    }

    try:
        # 1. Fetch peer manifest to confirm it's a Jarvis device
        manifest = _http_get(f"{url}/api/sync/manifest", peer=peer)
        peer_share_level = manifest.get("share_level", "public")
        last_peer_sync = manifest.get("last_sync")

        # 2. Pull shareable memories from peer
        pull_params = f"?since={last_peer_sync}" if last_peer_sync else ""
        pull_data = _http_get(f"{url}/api/sync/pull-memories{pull_params}", peer=peer)
        incoming = pull_data.get("memories", [])
        if incoming:
            merge_result = _merge_incoming_memories(incoming, label)
            result["pulled"] = merge_result["imported"]
            _log(f"Pulled {merge_result['imported']} memories from {label} ({merge_result['skipped']} skipped)")

        # 3. Push our shareable memories to peer
        sync_state = _load_sync_state()
        last_push = sync_state.get(f"last_push_{peer.get('id', url)}")
        shareable = _get_shareable_memories(since=last_push)
        if shareable:
            push_result = _http_post(f"{url}/api/sync/push-memories", {
                "memories": shareable,
                "source_label": socket.gethostname(),
            }, peer=peer)
            result["pushed"] = push_result.get("imported", 0)
            _log(f"Pushed {len(shareable)} memories to {label}, {result['pushed']} imported")

        # 4. Update sync state
        sync_state["last_sync"] = _utc_now()
        sync_state[f"last_push_{peer.get('id', url)}"] = _utc_now()
        sync_state["memory_count"] = len(_get_shareable_memories())
        _save_sync_state(sync_state)

        result["ok"] = True
        result["peer_manifest"] = {
            "device_id": manifest.get("device_id"),
            "label": manifest.get("label"),
            "share_level": peer_share_level,
        }

    except Exception as exc:
        result["error"] = str(exc)
        _log(f"Sync with {label} failed: {exc}")

    return result


# ── Full sync across all peers ────────────────────────────────────────────────

def sync_all_peers() -> dict[str, Any]:
    """Sync with all trusted registered peers. Returns aggregate report."""
    peers = [p for p in load_peers() if p.get("trusted", True)]
    if not peers:
        return {"ok": True, "peers_synced": 0, "results": [], "message": "No peers registered"}

    results = []
    for peer in peers:
        result = sync_with_peer(peer)
        results.append(result)
        # Update peer last_sync in registry
        all_peers = load_peers()
        for p in all_peers:
            if p.get("id") == peer.get("id"):
                p["last_sync"] = result["ts"]
                p["last_sync_status"] = "ok" if result["ok"] else "error"
        save_peers(all_peers)

    ok_count = sum(1 for r in results if r["ok"])
    total_pulled = sum(r.get("pulled", 0) for r in results)
    total_pushed = sum(r.get("pushed", 0) for r in results)

    return {
        "ok": ok_count == len(results),
        "peers_synced": ok_count,
        "peers_failed": len(results) - ok_count,
        "total_pulled": total_pulled,
        "total_pushed": total_pushed,
        "results": results,
    }


# ── Peer reachability check ───────────────────────────────────────────────────

def check_peer_health(url: str) -> dict[str, Any]:
    """Check if a peer's Jarvis API is reachable."""
    url = url.strip().rstrip("/")
    try:
        start = time.monotonic()
        data = _http_get(f"{url}/api/health", timeout=5)
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "ok": data.get("ok", False),
            "reachable": True,
            "latency_ms": latency_ms,
            "url": url,
        }
    except Exception as exc:
        return {"ok": False, "reachable": False, "error": str(exc), "url": url}


# ── Public interface helpers ──────────────────────────────────────────────────

def get_sync_status() -> dict[str, Any]:
    """Return current sync status for display."""
    peers = load_peers()
    sync_state = _load_sync_state()
    return {
        "peer_count": len(peers),
        "trusted_peers": [p for p in peers if p.get("trusted")],
        "last_sync": sync_state.get("last_sync"),
        "memory_count": sync_state.get("memory_count", 0),
        "share_level": _SHARE_LEVEL,
    }
