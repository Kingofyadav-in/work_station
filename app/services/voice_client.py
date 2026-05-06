from __future__ import annotations

import contextlib
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
JARVIS_DIR = ROOT_DIR / "Jarvis"

if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))


@contextlib.contextmanager
def _quiet():
    """Redirect fd 2 to /dev/null to suppress ALSA/JACK noise from PyAudio."""
    devnull = os.open("/dev/null", os.O_WRONLY)
    old = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old, 2)
        os.close(old)


def _voice_input():
    import voice_input  # noqa: PLC0415 — deferred: PyAudio init aborts if imported at module level
    return voice_input


def voice_available() -> bool:
    """Cheap check — only verifies speech_recognition is installed, no PyAudio call."""
    try:
        return _voice_input().speech_support_available()
    except Exception:
        return False


def get_voice_status() -> dict[str, str]:
    try:
        with _quiet():
            return _voice_input().get_voice_status()
    except Exception as exc:
        return {"status": "unavailable", "message": str(exc)}


def capture_voice_command(
    *,
    device_index: int | None = None,
    timeout: int = 10,
    phrase_time_limit: int = 10,
    retries: int = 2,
) -> str:
    with _quiet():
        response = _voice_input().transcribe_voice_command(
            device_index=device_index,
            timeout=timeout,
            phrase_time_limit=phrase_time_limit,
            retries=retries,
        )
    return response["transcript"]
