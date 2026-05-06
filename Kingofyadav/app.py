#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "shared"))
from bus_db import SQLiteMessageBus, get_bus  # noqa: E402
from message_bus import MessageBus             # noqa: E402
from handler import handle_request

ROOT_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT_DIR / "logs"
PID_FILE = LOG_DIR / "kingofyadav.pid"

_running = True


def _write_pid() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _remove_pid() -> None:
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _on_signal(signum, frame) -> None:
    global _running
    _running = False


signal.signal(signal.SIGTERM, _on_signal)
signal.signal(signal.SIGINT, _on_signal)


# ── inotify-based dispatch (watchdog) ─────────────────────────────────────────

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    _HAS_WATCHDOG = True
except ImportError:
    _HAS_WATCHDOG = False


def _process_files(bus: MessageBus, paths: list[Path] | None = None) -> int:
    claimed_paths = paths if paths is not None else bus.list_requests_for_me()
    processed = 0
    for path in claimed_paths:
        if not _running:
            break
        try:
            msg = bus.read_message(path)
            try:
                print(json.dumps(msg, indent=2), flush=True)
            except BrokenPipeError:
                pass
            result = handle_request(msg)
            is_error = result.pop("_error", False)
            bus.send_response(
                request_message=msg,
                payload=result,
                status="error" if is_error else "ok",
                meta={"handler": "Kingofyadav.app"},
            )
            bus.mark_processed(path)
            processed += 1
        except Exception as exc:
            bus.move_to_deadletter(path, str(exc))
            processed += 1
    return processed


_DL_CHECK_INTERVAL = 300  # check dead-letter every 5 minutes


def _run_with_watchdog(bus: MessageBus) -> None:
    from watchdog.events import FileSystemEventHandler  # type: ignore[import]
    from watchdog.observers import Observer              # type: ignore[import]

    wake = threading.Event()
    last_dl_check = 0.0

    class _BusWatcher(FileSystemEventHandler):
        def on_created(self, event) -> None:
            if not event.is_directory and str(event.src_path).endswith(".json"):
                wake.set()

        def on_moved(self, event) -> None:
            # Atomic renames (.tmp → .json) appear as "moved" events
            if not event.is_directory and str(event.dest_path).endswith(".json"):
                wake.set()

    requests_dir = ROOT_DIR / "shared" / "bus" / "requests"
    requests_dir.mkdir(parents=True, exist_ok=True)

    observer = Observer()
    observer.schedule(_BusWatcher(), str(requests_dir), recursive=False)
    observer.start()
    print("[Kingofyadav] inotify watcher active (watchdog)", flush=True)

    # Process any files that arrived before the watcher started
    _process_files(bus)

    try:
        while _running:
            wake.wait(timeout=5.0)
            wake.clear()
            _process_files(bus)
            now = time.time()
            if now - last_dl_check > _DL_CHECK_INTERVAL:
                bus.alert_deadletter()
                last_dl_check = now
    finally:
        observer.stop()
        observer.join()


def _run_with_polling(bus: MessageBus | SQLiteMessageBus) -> None:
    _POLL_MIN  = 0.05
    _POLL_MAX  = 1.0
    _POLL_STEP = 0.1
    poll_interval = _POLL_MIN
    last_dl_check = 0.0
    backend = "sqlite" if isinstance(bus, SQLiteMessageBus) else "filesystem"
    print(f"[Kingofyadav] adaptive polling active (backend={backend})", flush=True)

    while _running:
        processed = _process_files(bus)
        if processed == 0:
            poll_interval = min(poll_interval + _POLL_STEP, _POLL_MAX)
            time.sleep(poll_interval)
        else:
            poll_interval = _POLL_MIN
        now = time.time()
        if now - last_dl_check > _DL_CHECK_INTERVAL:
            bus.alert_deadletter()
            last_dl_check = now


# ── entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    _write_pid()
    bus = get_bus("Kingofyadav")
    bus.alert_deadletter()
    print("[Kingofyadav] listener started", flush=True)

    # Watchdog inotify only makes sense for the filesystem bus
    use_watchdog = _HAS_WATCHDOG and not isinstance(bus, SQLiteMessageBus)
    if use_watchdog:
        _run_with_watchdog(bus)
    else:
        _run_with_polling(bus)

    _remove_pid()
    print("[Kingofyadav] listener stopped", flush=True)


if __name__ == "__main__":
    main()
