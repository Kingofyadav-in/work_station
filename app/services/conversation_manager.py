from __future__ import annotations

import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[2]
JARVIS_DIR = ROOT_DIR / "Jarvis"
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

# Module-level state persists across Streamlit script reruns within the same process.
_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop_event = threading.Event()
_state: dict[str, Any] = {
    "status": "idle",
    "error": "",
    "conversation": [],
}

_WAKE_PHRASE = "jarvis"


def get_state() -> dict[str, Any]:
    with _lock:
        return {
            "status": _state["status"],
            "error": _state["error"],
            "conversation": list(_state["conversation"]),
        }


def is_running() -> bool:
    with _lock:
        return (
            _thread is not None
            and _thread.is_alive()
            # Bug 5 fix: exclude "error" so auto-refresh pauses on error state
            and _state["status"] not in ("stopped", "idle", "error")
        )


def start_conversation(
    *,
    timeout: int = 8,
    phrase_time_limit: int = 10,
    require_wake_phrase: bool = False,  # Bug 6 fix
) -> None:
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        _state["status"] = "starting"
        _state["error"] = ""
    _stop_event.clear()
    t = threading.Thread(
        target=_conversation_loop,
        kwargs={
            "timeout": timeout,
            "phrase_time_limit": phrase_time_limit,
            "require_wake_phrase": require_wake_phrase,
        },
        daemon=True,
        name="jarvis-conversation",
    )
    with _lock:
        _thread = t
    t.start()


def stop_conversation() -> None:
    _stop_event.set()
    with _lock:
        _state["status"] = "stopped"


def clear_conversation() -> None:
    # Bug 9 fix: always force "idle" — thread's final _set_status("stopped")
    # checks this and skips overwriting when already "idle".
    with _lock:
        _state["conversation"] = []
        _state["error"] = ""
        _state["status"] = "idle"


def _set_status(status: str, error: str = "") -> None:
    with _lock:
        # Don't overwrite "idle" — clear_conversation() may have already reset us.
        if _state["status"] == "idle" and status == "stopped":
            return
        _state["status"] = status
        _state["error"] = error


def _add_message(role: str, text: str) -> None:
    with _lock:
        _state["conversation"].append({
            "role": role,
            "text": text,
            "ts": datetime.now().strftime("%H:%M:%S"),
        })


_MAX_CONSECUTIVE_HW_ERRORS = 3


def _conversation_loop(
    timeout: int,
    phrase_time_limit: int,
    require_wake_phrase: bool,
) -> None:
    import os  # noqa: PLC0415
    import contextlib  # noqa: PLC0415
    import voice_input  # noqa: PLC0415
    from services.jarvis_client import run_command  # noqa: PLC0415
    from services.tts_client import speak_text, stop_speaking  # noqa: PLC0415

    @contextlib.contextmanager
    def _quiet():
        devnull = os.open("/dev/null", os.O_WRONLY)
        old = os.dup(2)
        os.dup2(devnull, 2)
        os.close(devnull)
        try:
            yield
        finally:
            os.dup2(old, 2)
            os.close(old)

    if not voice_input.speech_support_available():
        _set_status("error", "speech_recognition is not installed — install it with: pip install SpeechRecognition pyaudio")
        return

    _set_status("listening")
    consecutive_hw_errors = 0
    speech_service_error = (
        "Speech recognition service unavailable. "
        "If the backend is returning 502, check network access or try again later."
    )

    while not _stop_event.is_set():
        try:
            _set_status("listening")
            with _quiet():
                transcript = voice_input.capture_speech(
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )
            consecutive_hw_errors = 0

            if _stop_event.is_set():
                break

            clean = transcript.strip().lower()

            # Bug 6 fix: wake phrase gate
            if require_wake_phrase:
                if not clean.startswith(_WAKE_PHRASE):
                    continue
                transcript = transcript[len(_WAKE_PHRASE):].strip(" ,:.-")
                clean = transcript.lower()

            if clean in {"exit", "quit", "stop", "goodbye", "bye"}:
                _add_message("system", "Conversation ended by voice command.")
                _stop_event.set()
                break

            _add_message("user", transcript)

            _set_status("processing")
            result = run_command(f"ask {transcript}")
            reply = (result.get("data", {}).get("result") or "").strip() or "Sorry, I had no response."
            _add_message("jarvis", reply)

            if _stop_event.is_set():
                break

            # Bug 4 fix: run TTS in a thread so stop_event can interrupt it
            _set_status("speaking")
            _tts_done = threading.Event()

            def _tts_worker(text: str = reply) -> None:
                speak_text(text, wait=True)
                _tts_done.set()

            tts_thread = threading.Thread(target=_tts_worker, daemon=True)
            tts_thread.start()

            while not _tts_done.wait(timeout=0.1):
                if _stop_event.is_set():
                    stop_speaking()
                    break

            time.sleep(0.3)

        except TimeoutError:
            _set_status("listening")
            time.sleep(0.1)
            continue
        except Exception as exc:
            msg = str(exc)
            lower_msg = msg.lower()

            if any(k in lower_msg for k in ("speech was captured", "not be understood", "unknown value")):
                consecutive_hw_errors = 0
                _set_status("listening")
                continue
            if any(k in lower_msg for k in ("timeout", "wait for speech", "listening timed out")):
                consecutive_hw_errors = 0
                _set_status("listening")
                time.sleep(0.1)
                continue
            if any(k in lower_msg for k in ("speech recognition service error", "bad gateway", "http error 502", "502")):
                _set_status("error", f"{speech_service_error} Details: {msg}")
                break

            consecutive_hw_errors += 1
            if consecutive_hw_errors >= _MAX_CONSECUTIVE_HW_ERRORS:
                _set_status(
                    "error",
                    f"Audio hardware unavailable after {_MAX_CONSECUTIVE_HW_ERRORS} attempts: {msg}. "
                    "Check that a microphone is connected and accessible.",
                )
                break

            _set_status("error", msg)
            time.sleep(2)
            if not _stop_event.is_set():
                _set_status("listening")

    _set_status("stopped")
