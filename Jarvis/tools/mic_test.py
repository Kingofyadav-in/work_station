#!/usr/bin/env python3
"""
Jarvis microphone test utility.

Features:
- Safe import behavior for pytest/module reuse
- Lists available microphones
- Lets you choose device index from CLI
- Ambient noise calibration
- Speech capture with timeout controls
- Clear error handling
- Optional JSON-style structured output can be added later

Usage:
    python3 mic_test.py
    python3 mic_test.py --device 11
    python3 mic_test.py --timeout 5 --phrase-time-limit 6
"""

from __future__ import annotations

import argparse
from typing import Any, List

sr: Any | None = None


def _load_sr() -> Any:
    global sr
    if sr is not None:
        return sr
    try:
        import speech_recognition as speech_recognition
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency: speech_recognition. Install with: pip install SpeechRecognition"
        ) from exc
    sr = speech_recognition
    return sr


def list_microphones() -> List[str]:
    """Return all visible microphone/device names."""
    speech_recognition = _load_sr()
    return speech_recognition.Microphone.list_microphone_names()


def print_microphones(mic_names: List[str]) -> None:
    """Print available microphone list."""
    print("Microphones found:")
    if not mic_names:
        print("  No microphones detected")
        return

    for index, name in enumerate(mic_names):
        print(f"  {index}: {name}")


def resolve_device_index(requested_index: int | None, mic_names: List[str]) -> int | None:
    """
    Resolve the microphone device index.
    If None, use system default by returning None.
    """
    if requested_index is None:
        return None

    if requested_index < 0 or requested_index >= len(mic_names):
        raise ValueError(
            f"Invalid device index {requested_index}. "
            f"Valid range: 0 to {len(mic_names) - 1}"
        )

    return requested_index


def capture_audio(
    device_index: int | None,
    adjust_duration: float,
    timeout: float,
    phrase_time_limit: float,
) -> object:
    """Capture audio from the selected microphone."""
    speech_recognition = _load_sr()
    recognizer = speech_recognition.Recognizer()

    with speech_recognition.Microphone(device_index=device_index) as source:
        print("\nMic opened successfully")
        print(f"Calibrating for ambient noise ({adjust_duration:.1f}s)...")
        recognizer.adjust_for_ambient_noise(source, duration=adjust_duration)
        print("Now speak...")
        audio = recognizer.listen(
            source,
            timeout=timeout,
            phrase_time_limit=phrase_time_limit,
        )

    print("Audio captured successfully")
    return audio


def transcribe_audio(audio: object) -> str:
    """Convert captured audio to text using Google recognition."""
    speech_recognition = _load_sr()
    recognizer = speech_recognition.Recognizer()
    return recognizer.recognize_google(audio)


def run_test(
    device_index: int | None,
    adjust_duration: float,
    timeout: float,
    phrase_time_limit: float,
    show_devices: bool,
) -> int:
    """Run the microphone and speech recognition test."""
    speech_recognition = None
    try:
        speech_recognition = _load_sr()
        mic_names = list_microphones()

        if show_devices:
            print_microphones(mic_names)

        if not mic_names:
            print("No microphones detected")
            return 1

        selected_index = resolve_device_index(device_index, mic_names)

        if selected_index is None:
            print("\nUsing system default microphone")
        else:
            print(f"\nUsing microphone index: {selected_index}")
            print(f"Device name: {mic_names[selected_index]}")

        audio = capture_audio(
            device_index=selected_index,
            adjust_duration=adjust_duration,
            timeout=timeout,
            phrase_time_limit=phrase_time_limit,
        )

        try:
            text = transcribe_audio(audio)
            print(f'You said: "{text}"')
            return 0
        except speech_recognition.UnknownValueError:
            print("Speech was captured, but could not be understood")
            return 2
        except speech_recognition.RequestError as exc:
            print(f"Google recognition service error: {exc}")
            return 3

    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 4
    except RuntimeError as exc:
        print(exc)
        return 1
    except OSError as exc:
        print(f"Audio device error: {exc}")
        return 6
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 130
    except Exception as exc:
        if speech_recognition is not None and isinstance(exc, speech_recognition.WaitTimeoutError):
            print("Timeout: no speech detected in time")
            return 5
        print(f"Mic error: {exc}")
        return 10


def build_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Professional microphone test for Jarvis voice input."
    )
    parser.add_argument(
        "--device",
        type=int,
        default=11,
        help="Microphone device index. Use --device 11 for your pulse device, or omit for default.",
    )
    parser.add_argument(
        "--default-device",
        action="store_true",
        help="Use the system default microphone instead of a fixed device index.",
    )
    parser.add_argument(
        "--adjust-duration",
        type=float,
        default=1.0,
        help="Seconds to calibrate ambient noise.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Maximum seconds to wait before speech starts.",
    )
    parser.add_argument(
        "--phrase-time-limit",
        type=float,
        default=5.0,
        help="Maximum seconds for captured speech.",
    )
    parser.add_argument(
        "--hide-devices",
        action="store_true",
        help="Do not print microphone device list.",
    )
    return parser


def main() -> int:
    """Program entry point."""
    parser = build_parser()
    args = parser.parse_args()

    device_index = None if args.default_device else args.device

    return run_test(
        device_index=device_index,
        adjust_duration=args.adjust_duration,
        timeout=args.timeout,
        phrase_time_limit=args.phrase_time_limit,
        show_devices=not args.hide_devices,
    )


if __name__ == "__main__":
    raise SystemExit(main())
