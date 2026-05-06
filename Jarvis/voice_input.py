#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
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


DEFAULT_DEVICE_INDEX = None  # use system default; specific index can be set in HI profile
DEFAULT_RETRIES = 2
TIMEOUT_MESSAGE = "No speech detected — microphone timed out"


def get_voice_preferences() -> dict[str, Any]:
    hi_profile = load_profiles().get("HI", {})
    return {
        "preferred_mic_device": hi_profile.get("preferred_mic_device", DEFAULT_DEVICE_INDEX),
        "wake_phrase": hi_profile.get("wake_phrase", "jarvis"),
    }


def speech_support_available() -> bool:
    return sr is not None


def get_voice_status() -> dict[str, str]:
    if sr is None:
        return {
            "status": "unavailable",
            "message": "speech_recognition is not installed",
        }

    microphone_names = sr.Microphone.list_microphone_names()  # type: ignore[union-attr]
    prefs = get_voice_preferences()
    return {
        "status": "ready",
        "message": (
            f"Voice input ready with {len(microphone_names)} microphone device(s); "
            f"default device index is {prefs['preferred_mic_device']}; "
            f"wake phrase is {prefs['wake_phrase']}"
        ),
    }


def _open_microphone(device_index: int | None) -> Any:
    """Open a Microphone and verify the PyAudio stream was created.

    PyAudio silently leaves stream=None for certain device indices that exist
    in the device list but can't actually be opened (e.g. HDMI/loopback hw
    entries). Calling .close() on None then raises AttributeError. We detect
    this early and raise a clear RuntimeError so callers can fall back.
    """
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
    """Convert backend/library exceptions into stable UI-facing errors."""
    if isinstance(exc, TimeoutError):
        return exc

    if sr is not None and isinstance(exc, sr.WaitTimeoutError):
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


def capture_speech(
    device_index: int | None = None,
    timeout: int = 5,
    phrase_time_limit: int = 7,
    retries: int = DEFAULT_RETRIES,
) -> str:
    if sr is None:
        raise RuntimeError("speech_recognition is not installed")

    prefs = get_voice_preferences()
    preferred = prefs["preferred_mic_device"] if device_index is None else device_index
    sr_mod: Any = sr
    recognizer = sr_mod.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.pause_threshold = 0.8
    recognizer.dynamic_energy_threshold = True

    # Try the requested device first; if it fails to open, fall back to the
    # system default (device_index=None) which maps to the PulseAudio/ALSA
    # default and is always safe.
    candidates: list[int | None] = [preferred]
    if preferred is not None:
        candidates.append(None)

    last_error: Exception | None = None
    for dev_idx in candidates:
        mic = None
        try:
            mic = _open_microphone(dev_idx)
            recognizer.adjust_for_ambient_noise(mic, duration=1)
            for _ in range(retries + 1):
                try:
                    audio = recognizer.listen(
                        mic,
                        timeout=timeout,
                        phrase_time_limit=phrase_time_limit,
                    )
                    return recognizer.recognize_google(audio)
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
            continue  # try next candidate device
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


def transcribe_voice_command(
    device_index: int | None = None,
    timeout: int = 5,
    phrase_time_limit: int = 7,
    retries: int = DEFAULT_RETRIES,
) -> dict[str, str]:
    transcript = capture_speech(
        device_index=device_index,
        timeout=timeout,
        phrase_time_limit=phrase_time_limit,
        retries=retries,
    )
    return {"status": "captured", "transcript": transcript}


def process_voice_command(
    transcript: str | None = None,
    *,
    device_index: int | None = None,
    timeout: int = 5,
    phrase_time_limit: int = 7,
    retries: int = DEFAULT_RETRIES,
    require_wake_phrase: bool = False,
) -> dict[str, Any]:
    if transcript is None:
        transcript = transcribe_voice_command(
            device_index=device_index,
            timeout=timeout,
            phrase_time_limit=phrase_time_limit,
            retries=retries,
        )["transcript"]

    prefs = get_voice_preferences()
    wake_phrase = prefs["wake_phrase"].strip().lower()
    spoken = transcript.strip()
    spoken_lower = spoken.lower()

    if wake_phrase and spoken_lower.startswith(wake_phrase):
        spoken = spoken[len(wake_phrase):].strip(" ,:.-")
        spoken_lower = spoken.lower()
        if not spoken:
            return {
                "status": "ignored",
                "transcript": transcript,
                "bridge": {
                    "ok": False,
                    "intent": "",
                    "action": "wake_phrase",
                    "payload": "",
                    "result": None,
                    "error": "Wake phrase detected, but no command followed.",
                },
            }
    elif require_wake_phrase and wake_phrase:
        if not spoken_lower.startswith(wake_phrase):
            return {
                "status": "ignored",
                "transcript": spoken,
                "bridge": {
                    "ok": False,
                    "intent": spoken_lower,
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
        "bridge": bridge_result,
    }


def print_response(response: dict[str, Any], json_mode: bool = False) -> int:
    if json_mode:
        print(json.dumps(response, indent=2, ensure_ascii=False))
        return 0 if response["bridge"]["ok"] else 1

    bridge = response["bridge"]
    behavior = bridge.get("behavior", {})
    print("Jarvis Voice Input")
    print("------------------")
    print(f"Transcript: {response['transcript']}")
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
) -> int:
    prefs = get_voice_preferences()
    resolved_device = prefs["preferred_mic_device"] if device_index is None else device_index
    print(
        f"Jarvis loop mode started on mic {resolved_device}. "
        f"Say '{prefs['wake_phrase']} ...' and use 'exit', 'quit', or 'stop' to end."
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
            )

            transcript = response["transcript"].strip().lower()
            if transcript in {"exit", "quit", "stop"}:
                if json_mode:
                    print(json.dumps({
                        "status": "ok",
                        "transcript": response["transcript"],
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
        description="Jarvis voice input layer for microphone capture, recognition, and bridge routing."
    )
    parser.add_argument("--text", help="Use typed text instead of microphone capture.")
    parser.add_argument("--device-index", type=int, default=None, help="Microphone device index.")
    parser.add_argument("--timeout", type=int, default=5, help="Maximum seconds to wait for speech to start.")
    parser.add_argument(
        "--phrase-time-limit",
        type=int,
        default=7,
        help="Maximum seconds to record a single phrase.",
    )
    parser.add_argument("--retries", type=int, default=DEFAULT_RETRIES, help="Recognition retries after unclear speech.")
    parser.add_argument("--json", action="store_true", help="Print the full structured response as JSON.")
    parser.add_argument("--loop", action="store_true", help="Continuously listen until exit, quit, or stop.")
    parser.add_argument("--no-wake-phrase", action="store_true", help="Disable wake phrase filtering in loop mode.")
    args = parser.parse_args()

    if args.loop:
        return run_loop(
            device_index=args.device_index,
            timeout=args.timeout,
            phrase_time_limit=args.phrase_time_limit,
            json_mode=args.json,
            retries=args.retries,
            require_wake_phrase=not args.no_wake_phrase,
        )

    try:
        response = process_voice_command(
            transcript=args.text,
            device_index=args.device_index,
            timeout=args.timeout,
            phrase_time_limit=args.phrase_time_limit,
            retries=args.retries,
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
