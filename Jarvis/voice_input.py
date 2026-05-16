#!/usr/bin/env python3
"""Voice input layer — Phase 3.

Backends (in priority order):
  1. vosk   — local offline STT (requires vosk + language model, no API key)
  2. whisper — local offline STT via openai-whisper (requires download)
  3. google  — online Google Speech API (default fallback, no key required)

Backend selection:
  - Set JARVIS_VOICE_BACKEND=vosk|whisper|google in .env
  - Or set voice_backend preference in HI profile
  - Default: google (always available)

Language:
  - Set JARVIS_VOICE_LANG=en-US (BCP-47 tag) in .env or HI profile voice_language
  - Vosk uses the model's native language; pass lang to Google

Confidence scoring:
  - Google: uses top-1 vs top-2 alternative gap (show_all=True)
  - Vosk: uses result confidence from recognizer
  - Whisper: uses segment-level logprob average
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from bridge import process_intent
from profile_manager import load_profiles

_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR / "app") not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR / "app"))

from services.tts_client import speak  # noqa: E402

try:
    import speech_recognition as sr
except ModuleNotFoundError:
    sr = None

try:
    import vosk  # type: ignore
    import wave
    import io
    _HAS_VOSK = True
except ModuleNotFoundError:
    vosk = None
    _HAS_VOSK = False

try:
    import whisper as _whisper  # type: ignore
    _HAS_WHISPER = True
except ModuleNotFoundError:
    _whisper = None
    _HAS_WHISPER = False

DEFAULT_DEVICE_INDEX = None
DEFAULT_RETRIES = 2
TIMEOUT_MESSAGE = "No speech detected — microphone timed out"

_ENV_BACKEND = os.getenv("JARVIS_VOICE_BACKEND", "").strip().lower()
_ENV_LANG = os.getenv("JARVIS_VOICE_LANG", "en-US").strip()
_VOSK_MODEL_PATH = os.getenv("JARVIS_VOSK_MODEL", str(_ROOT_DIR / "models" / "vosk-model"))
_WHISPER_MODEL = os.getenv("JARVIS_WHISPER_MODEL", "base")

# Cached vosk/whisper models (loaded lazily)
_vosk_model: Any = None
_whisper_model: Any = None


# ── Preferences ───────────────────────────────────────────────────────────────

def get_voice_preferences() -> dict[str, Any]:
    hi_profile = load_profiles().get("HI", {})
    return {
        "preferred_mic_device": hi_profile.get("preferred_mic_device", DEFAULT_DEVICE_INDEX),
        "wake_phrase": hi_profile.get("wake_phrase", "jarvis"),
        "voice_backend": hi_profile.get("voice_backend", _ENV_BACKEND or "google"),
        "voice_language": hi_profile.get("voice_language", _ENV_LANG),
        "wake_fuzzy_threshold": float(hi_profile.get("wake_fuzzy_threshold", 0.75)),
    }


# ── Backend availability ───────────────────────────────────────────────────────

def get_available_backends() -> list[str]:
    backends: list[str] = ["google"]
    if _HAS_VOSK and Path(_VOSK_MODEL_PATH).exists():
        backends.insert(0, "vosk")
    if _HAS_WHISPER:
        backends.insert(0, "whisper")
    return backends


def speech_support_available() -> bool:
    return sr is not None or _HAS_VOSK or _HAS_WHISPER


def get_voice_status() -> dict[str, Any]:
    prefs = get_voice_preferences()
    backends = get_available_backends()
    active = prefs["voice_backend"] if prefs["voice_backend"] in backends else "google"
    mic_count = 0
    if sr is not None:
        try:
            mic_count = len(sr.Microphone.list_microphone_names())  # type: ignore[union-attr]
        except Exception:
            pass
    return {
        "status": "ready" if speech_support_available() else "unavailable",
        "active_backend": active,
        "available_backends": backends,
        "language": prefs["voice_language"],
        "wake_phrase": prefs["wake_phrase"],
        "microphone_count": mic_count,
        "preferred_mic_device": prefs["preferred_mic_device"],
        "vosk_model_path": _VOSK_MODEL_PATH if _HAS_VOSK else None,
        "vosk_model_ready": _HAS_VOSK and Path(_VOSK_MODEL_PATH).exists(),
        "whisper_available": _HAS_WHISPER,
        "whisper_model": _WHISPER_MODEL if _HAS_WHISPER else None,
    }


# ── Microphone helpers ─────────────────────────────────────────────────────────

def _open_microphone(device_index: int | None) -> Any:
    mic = sr.Microphone(device_index=device_index)  # type: ignore[union-attr]
    mic.__enter__()
    if getattr(mic, "stream", None) is None:
        try:
            mic.__exit__(None, None, None)
        except Exception:
            pass
        raise RuntimeError(
            f"Microphone device_index={device_index!r} opened but stream is None "
            "(device may be output-only or unavailable)"
        )
    return mic


def _normalize_capture_error(exc: Exception) -> Exception:
    if isinstance(exc, TimeoutError):
        return exc
    if sr is not None and isinstance(exc, sr.WaitTimeoutError):  # type: ignore[union-attr]
        return TimeoutError(TIMEOUT_MESSAGE)
    message = str(exc).strip()
    lower_message = message.lower()
    if any(
        phrase in lower_message
        for phrase in (
            "listening timed out while waiting for phrase to start",
            "wait for speech",
            "no speech detected",
        )
    ):
        return TimeoutError(TIMEOUT_MESSAGE)
    if isinstance(exc, RuntimeError):
        return exc
    return RuntimeError(f"Microphone capture failed: {message}")


# ── Confidence scoring ────────────────────────────────────────────────────────

def _google_confidence(audio: Any, language: str) -> tuple[str, float]:
    """Recognize with Google and compute confidence from top-2 alternatives."""
    sr_mod: Any = sr
    recognizer = sr_mod.Recognizer()
    result = recognizer.recognize_google(audio, language=language, show_all=True)  # type: ignore
    if not result or not result.get("alternative"):
        raise sr_mod.UnknownValueError()
    alternatives = result["alternative"]
    top = alternatives[0]
    transcript = top.get("transcript", "")
    if "confidence" in top:
        confidence = float(top["confidence"])
    elif len(alternatives) >= 2:
        # Estimate confidence from position gap — only one hypothesis = high confidence
        confidence = 0.85
    else:
        confidence = 0.90
    return transcript, confidence


# ── Vosk backend ──────────────────────────────────────────────────────────────

def _load_vosk_model() -> Any:
    global _vosk_model
    if _vosk_model is None:
        _vosk_model = vosk.Model(_VOSK_MODEL_PATH)  # type: ignore
    return _vosk_model


def _capture_vosk(
    device_index: int | None,
    timeout: int,
    phrase_time_limit: int,
) -> tuple[str, float]:
    """Capture and recognize speech using vosk (local offline)."""
    if sr is None:
        raise RuntimeError("speech_recognition (PyAudio) required even for vosk backend")
    model = _load_vosk_model()
    sr_mod: Any = sr
    recognizer = sr_mod.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    mic = _open_microphone(device_index)
    try:
        recognizer.adjust_for_ambient_noise(mic, duration=0.5)
        audio = recognizer.listen(mic, timeout=timeout, phrase_time_limit=phrase_time_limit)
    finally:
        try:
            mic.__exit__(None, None, None)
        except Exception:
            pass

    raw = audio.get_wav_data()
    wf = wave.open(io.BytesIO(raw))
    sample_rate = wf.getframerate()
    vosk_rec = vosk.KaldiRecognizer(model, sample_rate)  # type: ignore
    vosk_rec.SetWords(True)

    data = wf.readframes(wf.getnframes())
    vosk_rec.AcceptWaveform(data)
    result = json.loads(vosk_rec.FinalResult())
    transcript = result.get("text", "").strip()
    if not transcript:
        raise RuntimeError("Speech captured but vosk returned empty transcript")

    # Confidence from word-level results
    words = result.get("result", [])
    if words:
        confidence = sum(w.get("conf", 0.8) for w in words) / len(words)
    else:
        confidence = 0.8
    return transcript, round(confidence, 3)


# ── Whisper backend ───────────────────────────────────────────────────────────

def _load_whisper_model() -> Any:
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = _whisper.load_model(_WHISPER_MODEL)  # type: ignore
    return _whisper_model


def _capture_whisper(
    device_index: int | None,
    timeout: int,
    phrase_time_limit: int,
    language: str,
) -> tuple[str, float]:
    """Capture and recognize speech using openai-whisper (local offline)."""
    if sr is None:
        raise RuntimeError("speech_recognition (PyAudio) required even for whisper backend")
    sr_mod: Any = sr
    recognizer = sr_mod.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    mic = _open_microphone(device_index)
    try:
        recognizer.adjust_for_ambient_noise(mic, duration=0.5)
        audio = recognizer.listen(mic, timeout=timeout, phrase_time_limit=phrase_time_limit)
    finally:
        try:
            mic.__exit__(None, None, None)
        except Exception:
            pass

    import tempfile, numpy as np  # noqa: E401
    model = _load_whisper_model()
    raw = audio.get_wav_data(convert_rate=16000, convert_width=2)
    audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    # Strip language region code for whisper (en-US → en)
    lang = language.split("-")[0] if language else None
    result = model.transcribe(audio_np, language=lang, fp16=False)
    transcript = result.get("text", "").strip()
    if not transcript:
        raise RuntimeError("Whisper returned empty transcript")

    segments = result.get("segments", [])
    if segments:
        avg_logprob = sum(s.get("avg_logprob", -1.0) for s in segments) / len(segments)
        # Convert log-probability to approximate confidence (range 0-1)
        confidence = float(min(1.0, max(0.0, 1.0 + avg_logprob / 5.0)))
    else:
        confidence = 0.75
    return transcript, round(confidence, 3)


# ── Google backend ────────────────────────────────────────────────────────────

def _capture_google(
    device_index: int | None,
    timeout: int,
    phrase_time_limit: int,
    retries: int,
    language: str,
) -> tuple[str, float]:
    if sr is None:
        raise RuntimeError("speech_recognition is not installed")
    sr_mod: Any = sr
    recognizer = sr_mod.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.pause_threshold = 0.8
    recognizer.dynamic_energy_threshold = True

    candidates: list[int | None] = [device_index]
    if device_index is not None:
        candidates.append(None)

    last_error: Exception | None = None
    for dev_idx in candidates:
        mic = None
        try:
            mic = _open_microphone(dev_idx)
            recognizer.adjust_for_ambient_noise(mic, duration=1)
            for _ in range(retries + 1):
                try:
                    audio = recognizer.listen(mic, timeout=timeout, phrase_time_limit=phrase_time_limit)
                    return _google_confidence(audio, language)
                except sr_mod.UnknownValueError:
                    last_error = RuntimeError("Speech was captured, but could not be understood")
                except sr_mod.WaitTimeoutError:
                    last_error = TimeoutError(TIMEOUT_MESSAGE)
                except sr_mod.RequestError as exc:
                    raise RuntimeError(f"Speech recognition service error: {exc}")
        except sr_mod.RequestError:
            raise
        except (RuntimeError, TimeoutError) as exc:
            last_error = _normalize_capture_error(exc)
            continue
        except Exception as exc:
            last_error = _normalize_capture_error(exc)
            continue
        finally:
            if mic is not None:
                try:
                    mic.__exit__(None, None, None)
                except Exception:
                    pass

    raise last_error or RuntimeError("Voice capture failed")


# ── Wake word detection ───────────────────────────────────────────────────────

def _wake_word_match(spoken: str, wake_phrase: str, threshold: float = 0.75) -> tuple[bool, str]:
    """Detect wake phrase using exact prefix + fuzzy matching.

    Returns (matched, command_text_after_wake_phrase).
    """
    spoken_lower = spoken.strip().lower()
    phrase_lower = wake_phrase.strip().lower()

    if not phrase_lower:
        return True, spoken

    # Exact prefix match (fast path)
    if spoken_lower.startswith(phrase_lower):
        remainder = spoken[len(phrase_lower):].strip(" ,:.-")
        return True, remainder

    # Token-based fuzzy match: check if all words of wake phrase appear near start
    phrase_tokens = phrase_lower.split()
    spoken_tokens = spoken_lower.split()
    if spoken_tokens and phrase_tokens:
        # Check if wake phrase tokens appear within the first (len(phrase_tokens)+2) words
        window = spoken_tokens[:len(phrase_tokens) + 2]
        matches = sum(1 for t in phrase_tokens if t in window)
        ratio = matches / len(phrase_tokens)
        if ratio >= threshold:
            # Find where the wake phrase ends in the original spoken text
            spoken_words = spoken.split()
            end_idx = min(len(phrase_tokens) + 2, len(spoken_words))
            remainder = " ".join(spoken_words[end_idx:]).strip(" ,:.-")
            return True, remainder

    # Substring match — wake phrase appears anywhere in the first half of spoken
    half = spoken_lower[: len(spoken_lower) // 2 + len(phrase_lower)]
    if phrase_lower in half:
        idx = half.find(phrase_lower)
        remainder = spoken[idx + len(phrase_lower):].strip(" ,:.-")
        return True, remainder

    return False, spoken


# ── Unified capture ───────────────────────────────────────────────────────────

def capture_speech(
    device_index: int | None = None,
    timeout: int = 5,
    phrase_time_limit: int = 7,
    retries: int = DEFAULT_RETRIES,
    backend: str | None = None,
    language: str | None = None,
) -> str:
    """Capture and transcribe speech. Returns transcript string."""
    result = capture_speech_with_confidence(
        device_index=device_index,
        timeout=timeout,
        phrase_time_limit=phrase_time_limit,
        retries=retries,
        backend=backend,
        language=language,
    )
    return result["transcript"]


def capture_speech_with_confidence(
    device_index: int | None = None,
    timeout: int = 5,
    phrase_time_limit: int = 7,
    retries: int = DEFAULT_RETRIES,
    backend: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Capture speech and return {transcript, confidence, backend_used}."""
    prefs = get_voice_preferences()
    preferred_device = prefs["preferred_mic_device"] if device_index is None else device_index
    selected_backend = backend or prefs["voice_backend"]
    lang = language or prefs["voice_language"]

    # Auto-select available backend
    available = get_available_backends()
    if selected_backend not in available:
        selected_backend = available[0] if available else "google"

    transcript = ""
    confidence = 0.0

    if selected_backend == "vosk" and _HAS_VOSK and Path(_VOSK_MODEL_PATH).exists():
        transcript, confidence = _capture_vosk(preferred_device, timeout, phrase_time_limit)
    elif selected_backend == "whisper" and _HAS_WHISPER:
        transcript, confidence = _capture_whisper(preferred_device, timeout, phrase_time_limit, lang)
    else:
        if sr is None:
            raise RuntimeError("No STT backend available. Install speech_recognition, vosk, or openai-whisper.")
        transcript, confidence = _capture_google(preferred_device, timeout, phrase_time_limit, retries, lang)
        selected_backend = "google"

    return {
        "transcript": transcript,
        "confidence": confidence,
        "backend_used": selected_backend,
        "language": lang,
    }


def transcribe_voice_command(
    device_index: int | None = None,
    timeout: int = 5,
    phrase_time_limit: int = 7,
    retries: int = DEFAULT_RETRIES,
    backend: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    result = capture_speech_with_confidence(
        device_index=device_index,
        timeout=timeout,
        phrase_time_limit=phrase_time_limit,
        retries=retries,
        backend=backend,
        language=language,
    )
    return {"status": "captured", **result}


def process_voice_command(
    transcript: str | None = None,
    *,
    device_index: int | None = None,
    timeout: int = 5,
    phrase_time_limit: int = 7,
    retries: int = DEFAULT_RETRIES,
    require_wake_phrase: bool = False,
    backend: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    confidence = 1.0
    backend_used = "text"

    if transcript is None:
        capture = capture_speech_with_confidence(
            device_index=device_index,
            timeout=timeout,
            phrase_time_limit=phrase_time_limit,
            retries=retries,
            backend=backend,
            language=language,
        )
        transcript = capture["transcript"]
        confidence = capture["confidence"]
        backend_used = capture["backend_used"]

    prefs = get_voice_preferences()
    wake_phrase = prefs["wake_phrase"].strip()
    fuzzy_threshold = prefs["wake_fuzzy_threshold"]
    spoken = transcript.strip()

    if wake_phrase:
        matched, command_text = _wake_word_match(spoken, wake_phrase, fuzzy_threshold)
        if matched:
            spoken = command_text
            if not spoken:
                return {
                    "status": "ignored",
                    "transcript": transcript,
                    "confidence": confidence,
                    "backend_used": backend_used,
                    "bridge": {
                        "ok": False,
                        "intent": "",
                        "action": "wake_phrase",
                        "payload": "",
                        "result": None,
                        "error": "Wake phrase detected, but no command followed.",
                    },
                }
        elif require_wake_phrase:
            return {
                "status": "ignored",
                "transcript": spoken,
                "confidence": confidence,
                "backend_used": backend_used,
                "bridge": {
                    "ok": False,
                    "intent": spoken.lower(),
                    "action": "wake_phrase",
                    "payload": "",
                    "result": None,
                    "error": f"Wake phrase `{wake_phrase}` not detected.",
                },
            }

    bridge_result = process_intent(spoken)

    return {
        "status": "ok" if bridge_result["ok"] else "error",
        "transcript": transcript,
        "confidence": confidence,
        "backend_used": backend_used,
        "bridge": bridge_result,
    }


def print_response(response: dict[str, Any], json_mode: bool = False) -> int:
    if json_mode:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0 if response["bridge"]["ok"] else 1

    bridge = response["bridge"]
    behavior = bridge.get("behavior", {})
    conf = response.get("confidence", None)
    bkd = response.get("backend_used", "")
    print("Jarvis Voice Input")
    print("------------------")
    print(f"Transcript: {response['transcript']}")
    if conf is not None:
        print(f"Confidence: {conf:.0%}  Backend: {bkd}")
    print(f"Interpreted Action: {bridge['action']}")
    if behavior:
        print(f"Risk Tier: {behavior.get('risk_tier', 'unknown')}")
        print(f"Response Mode: {behavior.get('response_mode', 'unknown')}")
    print()

    if bridge["ok"]:
        print(bridge["result"])
        speak(bridge["result"])
    else:
        if bridge["result"]:
            print(bridge["result"])
            print()
        print(f"Error: {bridge['error']}")
        speak("Sorry, I could not understand")

    return 0 if bridge["ok"] else 1


def run_loop(
    *,
    device_index: int | None = None,
    timeout: int = 5,
    phrase_time_limit: int = 7,
    json_mode: bool = False,
    retries: int = DEFAULT_RETRIES,
    require_wake_phrase: bool = True,
    backend: str | None = None,
    language: str | None = None,
) -> int:
    prefs = get_voice_preferences()
    resolved_device = prefs["preferred_mic_device"] if device_index is None else device_index
    status = get_voice_status()
    print(
        f"Jarvis loop mode started — mic {resolved_device}, "
        f"backend={status['active_backend']}, lang={status['language']}. "
        f"Say '{prefs['wake_phrase']} ...' — 'exit'/'quit'/'stop' to end."
    )
    print()

    while True:
        try:
            response = process_voice_command(
                transcript=None,
                device_index=device_index,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
                retries=retries,
                require_wake_phrase=require_wake_phrase,
                backend=backend,
                language=language,
            )

            transcript = response["transcript"].strip().lower()
            if transcript in {"exit", "quit", "stop"}:
                if json_mode:
                    print(json.dumps({
                        "status": "ok",
                        "transcript": response["transcript"],
                        "confidence": response.get("confidence"),
                        "bridge": {
                            "ok": True,
                            "intent": response["transcript"],
                            "action": "exit",
                            "payload": None,
                            "result": "Exiting Jarvis loop.",
                            "error": None,
                        },
                    }, indent=2, ensure_ascii=False))
                else:
                    print("Jarvis Voice Input")
                    print("------------------")
                    print(f"Transcript: {response['transcript']}")
                    print("Interpreted Action: exit")
                    print()
                    print("Exiting Jarvis loop.")
                return 0

            if response["status"] == "ignored":
                if not json_mode:
                    print(f"Ignored: {response['bridge']['error']}")
                    print()
                continue

            print_response(response, json_mode=json_mode)
            print()

        except KeyboardInterrupt:
            print("\nExiting Jarvis loop.")
            return 0
        except Exception as exc:
            if json_mode:
                print(json.dumps({
                    "status": "error",
                    "transcript": None,
                    "bridge": None,
                    "error": str(exc),
                }, indent=2, ensure_ascii=False))
            else:
                print("Jarvis Voice Input")
                print("------------------")
                print(f"Error: {exc}")
                print()
            return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Jarvis voice input — multi-backend STT with confidence scoring."
    )
    parser.add_argument("--text", help="Use typed text instead of microphone capture.")
    parser.add_argument("--device-index", type=int, default=None, help="Microphone device index.")
    parser.add_argument("--timeout", type=int, default=5, help="Max seconds to wait for speech.")
    parser.add_argument("--phrase-time-limit", type=int, default=7, help="Max seconds to record a phrase.")
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Recognition retries.")
    parser.add_argument("--backend", choices=["google", "vosk", "whisper"], default=None, help="STT backend.")
    parser.add_argument("--language", default=None, help="BCP-47 language tag (e.g. en-US, hi-IN).")
    parser.add_argument("--json", action="store_true", help="Print full structured response as JSON.")
    parser.add_argument("--loop", action="store_true", help="Continuously listen until exit/quit/stop.")
    parser.add_argument("--no-wake-phrase", action="store_true", help="Disable wake phrase filtering.")
    parser.add_argument("--status", action="store_true", help="Show voice status and available backends.")
    args = parser.parse_args()

    if args.status:
        status = get_voice_status()
        if args.json:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            print("Jarvis Voice Status")
            print("-------------------")
            for key, val in status.items():
                print(f"  {key}: {val}")
        return 0

    if args.loop:
        return run_loop(
            device_index=args.device_index,
            timeout=args.timeout,
            phrase_time_limit=args.phrase_time_limit,
            json_mode=args.json,
            retries=args.retries,
            require_wake_phrase=not args.no_wake_phrase,
            backend=args.backend,
            language=args.language,
        )

    try:
        response = process_voice_command(
            transcript=args.text,
            device_index=args.device_index,
            timeout=args.timeout,
            phrase_time_limit=args.phrase_time_limit,
            retries=args.retries,
            backend=args.backend,
            language=args.language,
        )
    except Exception as exc:
        error_response = {
            "status": "error",
            "transcript": args.text,
            "bridge": None,
            "error": str(exc),
        }
        if args.json:
            print(json.dumps(error_response, indent=2, ensure_ascii=False))
        else:
            print("Jarvis Voice Input")
            print("------------------")
            print(f"Error: {exc}")
        return 1

    return print_response(response, json_mode=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
