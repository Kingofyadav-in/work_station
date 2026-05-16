#!/usr/bin/env python3
"""Phase 5 — Multi-Device Sync Agent (background daemon).

Runs on an interval and syncs memories + state with all registered peers.

Usage:
  python3 scripts/sync_agent.py              # run once and exit
  python3 scripts/sync_agent.py --loop       # run every JARVIS_SYNC_INTERVAL seconds
  python3 scripts/sync_agent.py --loop --interval 300

Environment:
  JARVIS_SYNC_INTERVAL = 300  (seconds between sync cycles)
  JARVIS_SYNC_SHARE_LEVEL = public | shared | none
  JARVIS_API_KEY          = shared API key for peer auth
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "shared"))
sys.path.insert(0, str(_ROOT / "Kingofyadav"))
sys.path.insert(0, str(_ROOT / "Jarvis"))

_PID_FILE = _ROOT / "logs" / "sync_agent.pid"
_LOG_FILE = _ROOT / "logs" / "sync_agent.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(_LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
_log = logging.getLogger("sync_agent")

_DEFAULT_INTERVAL = max(60, int(os.getenv("JARVIS_SYNC_INTERVAL", "300")))
_RUNNING = True


def _write_pid() -> None:
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    try:
        _PID_FILE.unlink()
    except FileNotFoundError:
        pass


def _shutdown(signum: int, frame: object) -> None:
    global _RUNNING
    _log.info(f"Received signal {signum}, shutting down sync agent")
    _RUNNING = False


def run_sync_cycle() -> dict:
    """Run one sync cycle across all peers. Returns result dict."""
    try:
        from device_sync import sync_all_peers, list_peers
        peers = list_peers()
        if not peers:
            _log.info("No sync peers registered — skipping cycle")
            return {"ok": True, "peers_synced": 0, "message": "no peers"}

        _log.info(f"Starting sync cycle with {len(peers)} peer(s)")
        result = sync_all_peers()
        _log.info(
            f"Sync complete: {result['peers_synced']}/{len(peers)} ok, "
            f"pulled={result['total_pulled']}, pushed={result['total_pushed']}"
        )
        if result.get("peers_failed", 0) > 0:
            for r in result["results"]:
                if not r.get("ok"):
                    _log.warning(f"Peer {r['peer_label']} failed: {r.get('error')}")
        return result
    except Exception as exc:
        _log.error(f"Sync cycle error: {exc}", exc_info=True)
        return {"ok": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis Phase 5 sync agent")
    parser.add_argument("--loop", action="store_true", help="Run continuously on an interval")
    parser.add_argument("--interval", type=int, default=_DEFAULT_INTERVAL, help="Sync interval in seconds")
    parser.add_argument("--json", action="store_true", help="Print results as JSON")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    if args.loop:
        _write_pid()
        _log.info(f"Sync agent started (pid={os.getpid()}, interval={args.interval}s)")
        try:
            while _RUNNING:
                result = run_sync_cycle()
                if args.json:
                    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)
                next_at = time.monotonic() + args.interval
                while _RUNNING and time.monotonic() < next_at:
                    time.sleep(1)
        finally:
            _remove_pid()
            _log.info("Sync agent stopped")
        return 0
    else:
        result = run_sync_cycle()
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            ok = result.get("ok", False)
            synced = result.get("peers_synced", 0)
            pulled = result.get("total_pulled", 0)
            pushed = result.get("total_pushed", 0)
            print(f"Sync {'OK' if ok else 'FAILED'}: {synced} peer(s) — pulled={pulled}, pushed={pushed}")
            if result.get("error"):
                print(f"Error: {result['error']}")
        return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
