from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import tempfile
import threading
from typing import Any

# ── Active TTS process tracking (for stop_speaking) ───────────────────────────
_tts_lock = threading.Lock()
_tts_proc: subprocess.Popen | None = None


def _set_tts_proc(proc: subprocess.Popen | None) -> None:
    global _tts_proc
    with _tts_lock:
        _tts_proc = proc


def stop_speaking() -> None:
    """Immediately terminate any active TTS playback."""
    global _tts_proc
    with _tts_lock:
        proc, _tts_proc = _tts_proc, None
    if proc is not None:
        try:
            proc.terminate()
        except Exception:
            pass

# ── Backends ──────────────────────────────────────────────────────────────────
_ESPEAK = shutil.which("espeak-ng")
_FFPLAY  = shutil.which("ffplay")


def _audio_env() -> dict:
    """Return os.environ with PulseAudio socket injected when Streamlit strips it."""
    env = os.environ.copy()
    if "PULSE_RUNTIME_PATH" not in env and "PULSE_SERVER" not in env:
        candidate = f"/run/user/{os.getuid()}/pulse"
        if os.path.exists(candidate):
            env["PULSE_RUNTIME_PATH"] = candidate
    return env

try:
    import edge_tts as _edge_tts
    _EDGE_AVAILABLE = True
except ImportError:
    _edge_tts = None  # type: ignore[assignment]
    _EDGE_AVAILABLE = False

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_ONLINE_VOICE  = "en-GB-RyanNeural"   # classic Jarvis feel
DEFAULT_OFFLINE_VOICE = "en-gb-x-rp"         # clearer espeak pronunciation
DEFAULT_SPEED         = 1.0                  # 1.0 = normal (0.5 slow → 2.0 fast)
DEFAULT_PITCH         = 44                   # espeak pitch (0-99)

# ── Action → spoken phrase map ────────────────────────────────────────────────
_PHRASES: dict[str, str] = {
    "profile":               "Profile loaded.",
    "preferences":           "Preferences loaded.",
    "memory":                "Memory loaded.",
    "status":                "Status ready.",
    "workflow":              "Workflow loaded.",
    "relationship":          "Relationship loaded.",
    "context":               "Context loaded.",
    "ai_status":             "AI status ready.",
    "system_info":           "System info ready.",
    "memory_added":          "Memory note saved.",
    "profile_updated":       "Profile updated.",
    "preference_updated":    "Preference updated.",
    "workflow_updated":      "Workflow updated.",
    "language_set":          "Language updated.",
    "focus_set":             "Focus updated.",
    "ai_response":           "AI response ready.",
    "ai_plan":               "Plan ready.",
    "confirmation_required": "Confirmation required.",
    "confirmed":             "Confirmed.",
    "cancelled":             "Cancelled.",
    "shell_exec":            "Shell command done.",
    "shell_blocked":         "Shell command blocked.",
}


def tts_available() -> bool:
    return _EDGE_AVAILABLE or _ESPEAK is not None


def _load_tts_profile() -> dict[str, Any]:
    """Read TTS settings from AI profile without hard-coupling to profile_manager."""
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        if str(root / "Jarvis") not in sys.path:
            sys.path.insert(0, str(root / "Jarvis"))
        from profile_manager import get_ai_profile
        ai = get_ai_profile()
        return {
            "connectivity": ai.get("connectivity", "online"),
            "voice":        ai.get("tts_voice", DEFAULT_ONLINE_VOICE),
            "offline_voice": ai.get("tts_offline_voice", DEFAULT_OFFLINE_VOICE),
            "speed":        float(ai.get("tts_speed", DEFAULT_SPEED)),
        }
    except Exception:
        return {
            "connectivity": "online",
            "voice": DEFAULT_ONLINE_VOICE,
            "offline_voice": DEFAULT_OFFLINE_VOICE,
            "speed": DEFAULT_SPEED,
        }


def _clean(text: str, max_chars: int) -> str:
    """Strip markdown and truncate."""
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'^\s*[-*]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n+', '. ', text).strip()
    return text[:max_chars]


def _humanize_action(action: str) -> str:
    if not action:
        return "Command"
    return action.replace("_", " ").strip().capitalize()


# ── edge-tts (online, neural) ─────────────────────────────────────────────────

def _speed_to_edge_rate(speed: float) -> str:
    """Convert 0.5-2.0 speed to edge-tts rate string like '+20%' or '-30%'."""
    pct = int((speed - 1.0) * 100)
    return f"{pct:+d}%"


def _try_unlink(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


async def _edge_speak_async(text: str, voice: str, speed: float, wait: bool) -> None:
    rate = _speed_to_edge_rate(speed)
    communicate = _edge_tts.Communicate(text, voice, rate=rate)
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_path = tmp.name
    tmp.close()
    proc = None
    try:
        await communicate.save(tmp_path)
        if not _FFPLAY:
            # Bug 6 fix: raise so _speak_edge falls back to espeak
            raise RuntimeError("ffplay not available — install ffmpeg for edge-tts playback")
        cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", tmp_path]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_audio_env())
        _set_tts_proc(proc)
        if wait:
            proc.wait()
            _set_tts_proc(None)
    finally:
        if proc is None or wait:
            # Bug 4 fix: always clean up when no background process is running
            _try_unlink(tmp_path)
        else:
            # proc is playing asynchronously — clean up after it finishes
            _p, _path = proc, tmp_path
            threading.Thread(
                target=lambda: (_p.wait(), _try_unlink(_path)),
                daemon=True,
            ).start()


def _speak_edge(text: str, voice: str, speed: float, wait: bool = False) -> None:
    # Bug 5 fix: use a fresh event loop instead of asyncio.run() to avoid
    # "This event loop is already running" RuntimeError in async contexts (FastAPI).
    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_edge_speak_async(text, voice, speed, wait))
        finally:
            loop.close()
    except Exception:
        _speak_espeak(text, speed=speed, wait=wait)


# ── espeak-ng (offline, fallback) ─────────────────────────────────────────────

def _speed_to_espeak_rate(speed: float) -> int:
    """Map 0.5-2.0 speed to espeak words-per-minute (100-200 range)."""
    return max(80, min(220, int(150 * speed)))


def _speak_espeak(text: str, *, voice: str = DEFAULT_OFFLINE_VOICE, speed: float = DEFAULT_SPEED, wait: bool = False) -> None:
    if not _ESPEAK:
        return
    rate = _speed_to_espeak_rate(speed)
    cmd = [_ESPEAK, "-v", voice, "-s", str(rate), "-p", str(DEFAULT_PITCH), text]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_audio_env())
    _set_tts_proc(proc)
    if wait:
        proc.wait()
        _set_tts_proc(None)


# ── Public API ────────────────────────────────────────────────────────────────

def speak(text: str, *, wait: bool = False) -> None:
    """Speak text using the best available engine based on AI profile settings."""
    text = text.strip()[:120]
    if not text:
        return
    cfg = _load_tts_profile()
    if cfg["connectivity"] == "online" and _EDGE_AVAILABLE:
        _speak_edge(text, voice=cfg["voice"], speed=cfg["speed"], wait=wait)
    else:
        _speak_espeak(text, voice=cfg["offline_voice"], speed=cfg["speed"], wait=wait)


def speak_text(text: str, *, max_chars: int = 250, wait: bool = False) -> None:
    """Speak raw text — strips markdown, truncates, picks best engine."""
    if not tts_available():
        return
    text = _clean(text, max_chars)
    if not text:
        return
    cfg = _load_tts_profile()
    if cfg["connectivity"] == "online" and _EDGE_AVAILABLE:
        _speak_edge(text, voice=cfg["voice"], speed=cfg["speed"], wait=wait)
    else:
        _speak_espeak(text, voice=cfg["offline_voice"], speed=cfg["speed"], wait=wait)


def speak_result(result: dict[str, Any]) -> None:
    """Derive a short spoken confirmation from a jarvis_client result dict."""
    data = result.get("data", {})
    ok   = result.get("ok", data.get("ok", False))
    if not ok:
        raw_error = str(data.get("error", "")).strip()
        short = raw_error.split(".")[0][:80] if raw_error else "Command failed."
        speak(f"Error. {short}.")
        return
    phrase = _PHRASES.get(data.get("action", ""), f"{_humanize_action(str(data.get('action', '')))} complete.")
    speak(phrase)


def speak_full_result(result: dict[str, Any], *, max_chars: int = 700) -> None:
    """Speak the full command result when the caller wants detailed audible output."""
    data = result.get("data", {})
    ok   = result.get("ok", data.get("ok", False))
    action = str(data.get("action", "")).strip()

    if ok:
        payload = str(data.get("payload", "")).strip()
        result_text = str(data.get("result", "")).strip()
        parts = []
        if action:
            parts.append(f"{_humanize_action(action)}.")
        if payload and payload != "(none)":
            parts.append(f"Details {payload}.")
        if result_text:
            parts.append(f"{result_text}.")
        else:
            parts.append("Result complete.")
        speak_text(" ".join(parts), max_chars=max_chars, wait=True)
        return

    raw_error = str(data.get("error", "")).strip() or "Command failed."
    parts = []
    if action:
        parts.append(f"{_humanize_action(action)}.")
    parts.append(f"Error {raw_error}.")
    speak_text(" ".join(parts), max_chars=max_chars, wait=True)
